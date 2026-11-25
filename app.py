"""Flask prototype for verifying cards, borrowing, and returning equipment."""

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from database import (
    ActiveLoanExists,
    CardNotRegistered,
    EquipmentNotFound,
    EquipmentUnavailable,
    NoActiveLoan,
    borrow_equipment,
    find_card_loan_status,
    list_equipment,
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


def _read_card_input():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return False, None, "Send a JSON object containing card_id."
    return validate_card_id(payload.get("card_id"))


def _read_record_id(field):
    value = request.get_json().get(field)
    if isinstance(value, str) and len(value) <= 19 and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is int and 0 < value < 2**63:
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
    valid, card_id, message = _read_card_input()
    if not valid:
        return jsonify(message=message), 400

    item_id = _read_record_id("item_id")
    if item_id is None:
        return jsonify(message="Select a valid equipment item."), 400

    try:
        loan = borrow_equipment(app.config["DATABASE"], card_id, item_id)
    except (CardNotRegistered, EquipmentNotFound) as error:
        return jsonify(message=str(error)), 404
    except (ActiveLoanExists, EquipmentUnavailable) as error:
        return jsonify(message=str(error)), 409
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to record an equipment loan")
        return jsonify(message="Equipment borrowing is temporarily unavailable."), 503

    return jsonify(
        loan=loan, active_loan=_active_loan_payload(loan), message=f"Borrowed {loan['item_name']}."
    ), 201


@app.post("/api/return")
def return_loan():
    valid, card_id, message = _read_card_input()
    if not valid:
        return jsonify(message=message), 400

    loan_id = _read_record_id("loan_id")
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
