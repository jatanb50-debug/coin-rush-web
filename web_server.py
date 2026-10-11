from flask import Flask, jsonify, send_from_directory, request
import database
import os
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
def verify_telegram_init_data(init_data):
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token or not init_data:
        return None

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)

        if not received_hash:
            return None

        auth_date = int(pairs.get("auth_date", "0"))
        if abs(int(time.time()) - auth_date) > 86400:
            return None

        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(pairs.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        user = json.loads(pairs.get("user", "{}"))
        if not isinstance(user.get("id"), int):
            return None

        return user

    except (ValueError, TypeError, json.JSONDecodeError):
        return None

@app.route("/")
def home():
    return "COIN RUSH Server is running!"

@app.route("/game")
def game():
    return send_from_directory("webapp", "game.html")

@app.route("/daily-status", methods=["POST"])
def daily_status():
    data = request.get_json(silent=True) or {}
    user = verify_telegram_init_data(data.get("initData", ""))

    if not user:
        return jsonify({"error": "Telegram verification failed"}), 401

    user_id = user["id"]
    database.register_user(user_id, user.get("username"))
    remaining = database.get_daily_reward_remaining(user_id)

    return jsonify({
        "remaining": remaining,
        "balance": database.get_balance(user_id),
    })


@app.route("/daily-claim", methods=["POST"])
def daily_claim():
    data = request.get_json(silent=True) or {}
    user = verify_telegram_init_data(data.get("initData", ""))

    if not user:
        return jsonify({"error": "Telegram verification failed"}), 401

    user_id = user["id"]
    database.register_user(user_id, user.get("username"))

    claimed = database.claim_daily_reward(user_id, 100)
    remaining = database.get_daily_reward_remaining(user_id)

    return jsonify({
        "claimed": claimed,
        "remaining": remaining,
        "balance": database.get_balance(user_id),
    })
@app.route("/mine", methods=["POST"])
def mine():
    data = request.get_json(silent=True) or {}
    user = verify_telegram_init_data(data.get("initData", ""))

    if not user:
        return jsonify({"error": "Telegram verification failed"}), 401

    user_id = user["id"]
    database.register_user(user_id, user.get("username"))

    amount = data.get("amount")
    if type(amount) is not int or amount != 1:
        return jsonify({"error": "Invalid mining amount"}), 400

    database.add_coins(user_id, 1)
    return jsonify({
        "success": True,
        "balance": database.get_balance(user_id)
    })
@app.route("/balance")
def balance():
    return jsonify({
        "error": "Telegram verification is required"
    }), 401

if __name__ == "__main__":
    database.init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
