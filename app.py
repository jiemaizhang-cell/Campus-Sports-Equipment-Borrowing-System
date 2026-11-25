"""Flask prototype for test card input and registration verification."""

import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from database import is_registered_card
from validation import validate_card_id

app = Flask(__name__)
app.config["DATABASE"] = Path(app.instance_path) / "campus.db"


@app.get("/")
def index():
    return render_template("index.html")


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
        registered = is_registered_card(app.config["DATABASE"], normalized)
    except (OSError, sqlite3.Error):
        app.logger.exception("Unable to look up a registered test card")
        return jsonify(valid=False, message="Card verification is temporarily unavailable."), 503

    if not registered:
        return jsonify(valid=False, message="This test card ID is not registered."), 404

    return jsonify(valid=True, card_id=normalized, message="Test card verified."), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
