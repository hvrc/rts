"""RTS backend — thin Flask layer over engine.py.

Endpoints match the frozen frontend contract exactly:
  POST /echo  {"message": str}  -> {response, train_of_thought, response_code}
  POST /reset                   -> {response, train_of_thought}
"""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()  # pull ANTHROPIC_API_KEY (and anything else) from backend/.env

import engine  # noqa: E402  (import after load_dotenv so the client sees the key)

app = Flask(__name__)

# Prod origin + any localhost port (Vite may land on 5173/5174/...).
CORS(app, resources={r"/*": {
    "origins": ["https://rts0-462101.ue.r.appspot.com",
                r"http://localhost:\d+",
                r"http://127\.0\.0\.1:\d+"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type"],
}})


@app.route("/")
def home():
    return "welcome to the rts brain!"


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    return jsonify(engine.play(message)), 200


@app.route("/reset", methods=["POST"])
def reset():
    return jsonify(engine.reset()), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
