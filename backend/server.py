"""RTS backend — thin Flask layer over the engine package.

  POST /echo  {"message": str, "reverse": bool}  -> {response, train_of_thought, response_code}
  POST /reset {"reverse": bool}                  -> {response, train_of_thought}

`reverse` is the letter-rule mode, owned by the client (the "r" button in the header).
It rides along on every request rather than being stored server-side, so the two can
never disagree about which rule is in force. It defaults to false, which is the
original game.
"""

import os

from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()  # pull ANTHROPIC_API_KEY (and anything else) from backend/.env

# In production (App Engine) there is no .env — pull the key from Secret Manager.
# GOOGLE_CLOUD_PROJECT is set automatically on App Engine and absent locally, so
# local dev skips this entirely and keeps using .env.
if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("GOOGLE_CLOUD_PROJECT"):
    from google.cloud import secretmanager

    _project = os.environ["GOOGLE_CLOUD_PROJECT"]
    _sm = secretmanager.SecretManagerServiceClient()
    _name = f"projects/{_project}/secrets/anthropic-api-key/versions/latest"
    os.environ["ANTHROPIC_API_KEY"] = (
        _sm.access_secret_version(name=_name).payload.data.decode("utf-8")
    )

import engine  # noqa: E402  (import after the key is in env so the client sees it)

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
    return jsonify(engine.play(
        data.get("message", ""),
        reverse=bool(data.get("reverse", False)),
    )), 200


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    return jsonify(engine.reset(reverse=bool(data.get("reverse", False)))), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
