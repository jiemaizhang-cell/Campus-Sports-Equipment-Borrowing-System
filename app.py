"""Flask prototype for verifying cards, reserving, borrowing, and returning equipment."""

import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from database import (
    DEFAULT_RESERVATION_MINUTES,
    ActiveLoanExists,
    ActiveReservationExists,
    CardNotRegistered,
    EquipmentNotFound,
    EquipmentUnavailable,
    InvalidReservationDuration,
    NoActiveLoan,
    ReservationNotFound,
    ReservationStateError,
    borrow_equipment,
    cancel_reservation,
    claim_reservation,
    create_reservation,
    find_active_reservation,
    find_card_loan_status,
    list_equipment,
    read_staff_dashboard,
    return_equipment,
)
from validation import validate_card_id

app = Flask(__name__)
app.config["DATABASE"] = Path(app.instance_path) / "campus.db"


@app.get("/")
def index():
    try:
        equipment = list_equipment(app.config["DATABASE"])
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to read equipment availability")
        equipment = None

    return render_template("index.html", equipment=equipment), 200, {"Cache-Control": "no-store"}


@app.get("/staff")
def staff():
    headers = {"Cache-Control": "no-store"}
    try:
        equipment, loans, reservations = read_staff_dashboard(app.config["DATABASE"])
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to read staff records")
        return render_template("staff.html", loans=None, reservations=None), 503, headers

    return (
        render_template(
            "staff.html",
            equipment=equipment,
            loans=loans,
            reservations=reservations,
        ),
        200,
        headers,
    )


@app.get("/counter")
def counter():
    headers = {"Cache-Control": "no-store"}
    try:
        equipment, loans, reservations = read_staff_dashboard(app.config["DATABASE"])
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to read pickup counter records")
        return (
            render_template(
                "counter.html",
                equipment=None,
                active_loans=None,
                active_reservations=None,
            ),
            503,
            headers,
        )

    active_loans = [row for row in loans if row["returned_at"] is None]
    active_reservations = [row for row in reservations if row["status"] == "active"]
    return (
        render_template(
            "counter.html",
            equipment=equipment,
            active_loans=active_loans,
            active_reservations=active_reservations,
        ),
        200,
        headers,
    )


@app.get("/api/equipment")
def equipment_list():
    headers = {"Cache-Control": "no-store"}
    try:
        equipment = list_equipment(app.config["DATABASE"])
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to read equipment availability")
        return jsonify(message="Equipment availability is temporarily unavailable."), 503, headers

    return (
        jsonify(
            equipment=[
                {
                    "item_id": row["item_id"],
                    "name": row["name"],
                    "available_quantity": row["available_quantity"],
                }
                for row in equipment
            ]
        ),
        200,
        headers,
    )


def _read_json_object():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def _read_card_input(payload=None):
    if payload is None:
        payload = _read_json_object()
    if not isinstance(payload, dict):
        return False, None, "Send a JSON object containing card_id."
    return validate_card_id(payload.get("card_id"))


def _read_record_id(field, payload=None):
    if payload is None:
        payload = _read_json_object()
    if not isinstance(payload, dict):
        return None
    value = payload.get(field)
    if isinstance(value, str) and len(value) <= 19 and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is int and 0 < value < 2**63:
        return value
    return None


def _read_pickup_code(payload):
    if not isinstance(payload, dict):
        return None
    value = payload.get("pickup_code")
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if not normalized or len(normalized) > 32:
        return None
    return normalized


def _read_duration_minutes(payload):
    if not isinstance(payload, dict):
        return None
    if "duration_minutes" not in payload or payload["duration_minutes"] is None:
        return DEFAULT_RESERVATION_MINUTES
    value = payload["duration_minutes"]
    if isinstance(value, str) and len(value) <= 4 and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is int:
        return value
    return None


def _active_loan_payload(loan):
    return {
        "loan_id": str(loan["loan_id"]),
        "item_id": str(loan["item_id"]),
        "item_name": loan["item_name"],
        "status": "active",
    }


@app.post("/api/validate-card")
def validate_card():
    valid, normalized, message = _read_card_input()
    if not valid:
        return jsonify({"valid": False, "message": message}), 400

    return jsonify({"valid": True, "card_id": normalized, "message": message}), 200


@app.post("/api/verify-card")
def verify_card():
    valid, normalized, message = _read_card_input()
    if not valid:
        return jsonify(valid=False, message=message), 400

    try:
        card = find_card_loan_status(app.config["DATABASE"], normalized)
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to look up a registered test card")
        return jsonify(valid=False, message="Card verification is temporarily unavailable."), 503

    if card is None:
        return jsonify(valid=False, message="This test card ID is not registered."), 404

    active_loan = None
    if card["item_name"] is not None:
        active_loan = _active_loan_payload(card)

    return jsonify(
        valid=True, card_id=card["card_id"], message="Test card verified.", active_loan=active_loan
    ), 200


@app.post("/api/borrow")
def borrow():
    payload = _read_json_object()
    valid, card_id, message = _read_card_input(payload)
    if not valid:
        return jsonify(message=message), 400

    item_id = _read_record_id("item_id", payload)
    if item_id is None:
        return jsonify(message="Select a valid equipment item."), 400

    try:
        loan = borrow_equipment(app.config["DATABASE"], card_id, item_id)
    except (CardNotRegistered, EquipmentNotFound) as error:
        return jsonify(message=str(error)), 404
    except (ActiveLoanExists, ActiveReservationExists, EquipmentUnavailable) as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to record an equipment loan")
        return jsonify(message="Equipment borrowing is temporarily unavailable."), 503

    return jsonify(
        loan=loan, active_loan=_active_loan_payload(loan), message=f"Borrowed {loan['item_name']}."
    ), 201


@app.post("/api/return")
def return_loan():
    payload = _read_json_object()
    valid, card_id, message = _read_card_input(payload)
    if not valid:
        return jsonify(message=message), 400

    loan_id = _read_record_id("loan_id", payload)
    if loan_id is None:
        return jsonify(message="Select a valid loan to return."), 400

    try:
        loan = return_equipment(app.config["DATABASE"], card_id, loan_id)
    except NoActiveLoan as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to return an equipment loan")
        return jsonify(message="Equipment return is temporarily unavailable."), 503

    return jsonify(loan=loan, message=f"Returned {loan['item_name']}."), 200


@app.post("/api/reservations/status")
def reservation_status():
    payload = _read_json_object()
    valid, card_id, message = _read_card_input(payload)
    if not valid:
        return jsonify(valid=False, message=message), 400

    try:
        card = find_card_loan_status(app.config["DATABASE"], card_id)
        if card is None:
            return jsonify(valid=False, message="This test card ID is not registered."), 404
        active_reservation = find_active_reservation(app.config["DATABASE"], card_id)
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to look up card reservation status")
        return jsonify(valid=False, message="Reservation status is temporarily unavailable."), 503

    return jsonify(
        valid=True,
        card_id=card["card_id"],
        active_reservation=active_reservation,
    ), 200


@app.post("/api/reservations")
def create_equipment_reservation():
    payload = _read_json_object()
    valid, card_id, message = _read_card_input(payload)
    if not valid:
        return jsonify(message=message), 400

    item_id = _read_record_id("item_id", payload)
    if item_id is None:
        return jsonify(message="Select a valid equipment item."), 400

    duration_minutes = _read_duration_minutes(payload)
    if duration_minutes is None:
        return jsonify(message="Reservation duration must be 5, 10, 15, or 20 minutes."), 400

    try:
        reservation = create_reservation(
            app.config["DATABASE"], card_id, item_id, duration_minutes=duration_minutes
        )
    except InvalidReservationDuration as error:
        return jsonify(message=str(error)), 400
    except (CardNotRegistered, EquipmentNotFound) as error:
        return jsonify(message=str(error)), 404
    except (ActiveLoanExists, ActiveReservationExists, EquipmentUnavailable) as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to create an equipment reservation")
        return jsonify(message="Equipment reservation is temporarily unavailable."), 503

    return jsonify(
        reservation=reservation,
        message=f"Reserved {reservation['item_name']}. Pickup code: {reservation['pickup_code']}.",
    ), 201


@app.post("/api/reservations/claim")
def claim_equipment_reservation():
    payload = _read_json_object()
    pickup_code = _read_pickup_code(payload)
    if pickup_code is None:
        return jsonify(message="Enter a valid pickup code."), 400

    try:
        result = claim_reservation(app.config["DATABASE"], pickup_code)
    except ReservationNotFound as error:
        return jsonify(message=str(error)), 404
    except (ReservationStateError, ActiveLoanExists) as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to claim an equipment reservation")
        return jsonify(message="Reservation pickup is temporarily unavailable."), 503

    loan = result["loan"]
    reservation = result["reservation"]
    return jsonify(
        loan=loan,
        active_loan=_active_loan_payload(loan),
        reservation=reservation,
        message=f"Claimed {loan['item_name']} for card {reservation['card_id']}.",
    ), 201


@app.post("/api/reservations/cancel")
def cancel_equipment_reservation():
    payload = _read_json_object()
    if not isinstance(payload, dict):
        return jsonify(message="Send a JSON object to cancel a reservation."), 400

    pickup_code = _read_pickup_code(payload) if payload.get("pickup_code") is not None else None
    card_id = None
    reservation_id = None

    if pickup_code is None:
        if payload.get("pickup_code") is not None:
            return jsonify(message="Enter a valid pickup code."), 400
        valid, card_id, message = _read_card_input(payload)
        if not valid:
            return jsonify(message=message), 400
        reservation_id = _read_record_id("reservation_id", payload)
        if reservation_id is None:
            return jsonify(message="Select a valid reservation to cancel."), 400

    try:
        reservation = cancel_reservation(
            app.config["DATABASE"],
            card_id=card_id,
            reservation_id=reservation_id,
            pickup_code=pickup_code,
        )
    except ReservationNotFound as error:
        return jsonify(message=str(error)), 404
    except ReservationStateError as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to cancel an equipment reservation")
        return jsonify(message="Reservation cancellation is temporarily unavailable."), 503

    return jsonify(
        reservation=reservation,
        message=f"Cancelled reservation for {reservation['item_name']}.",
    ), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1").lower() not in ("0", "false", "no")
    app.run(host="127.0.0.1", port=port, debug=debug)
