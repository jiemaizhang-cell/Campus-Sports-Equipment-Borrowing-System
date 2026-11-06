"""Minimal Flask prototype for Assignment 1 / B1 card input."""
from flask import Flask, jsonify, render_template, request
from validation import validate_card_id

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/validate-card")
def validate_card():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"valid": False, "message": "Send a JSON object containing card_id."}), 400

    valid, normalized, message = validate_card_id(payload.get("card_id"))
    if not valid:
        return jsonify({"valid": False, "message": message}), 400

    return jsonify({"valid": True, "card_id": normalized, "message": message}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
