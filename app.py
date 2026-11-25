"""Flask prototype for test cards, equipment, and active loans."""

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from database import find_card_loan_status, list_equipment
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
        active_loan = {"item_name": card["item_name"], "status": "active"}

    return jsonify(
        valid=True, card_id=card["card_id"], message="Test card verified.", active_loan=active_loan
    ), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
