"""RTS backend - thin Flask layer over the engine package.

  POST /echo  {"message": str, "reverse": bool}  -> {response, train_of_thought, response_code}
  POST /reset {"reverse": bool}                  -> {response, train_of_thought}

`reverse` is the letter-rule mode, owned by the client (the "r" button in the header).
It rides along on every request rather than being stored server-side, so the two can
never disagree about which rule is in force. It defaults to false, which is the
original game.
"""

import json
import os

from dotenv import load_dotenv
from flask import Flask, Response, request, jsonify
from flask_cors import CORS

load_dotenv()  # pull ANTHROPIC_API_KEY (and anything else) from backend/.env

# In production (App Engine) there is no .env - pull the key from Secret Manager.
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
from engine import transcript  # noqa: E402

app = Flask(__name__)

# Allowed origins come from the CORS_ORIGINS env var (comma-separated): the prod
# custom domain + the Cloud Run URL are injected at deploy time, so moving hosts or
# domains needs no code change. The legacy App Engine origin stays as a fallback,
# and any localhost port is always allowed for dev.
_extra_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
CORS(app, resources={r"/*": {
    "origins": _extra_origins + ["https://rts0-462101.ue.r.appspot.com",
                r"http://localhost:\d+",
                r"http://127\.0\.0\.1:\d+"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type"],
}})


@app.route("/")
def home():
    return "welcome to the rts brain!"


def _game_id(data):
    """One game per browser. Without this every player on the site shares a single
    chain and stomps each other's words."""
    gid = data.get("game_id")
    return gid if isinstance(gid, str) and gid.strip() else engine.SOLO_ID


@app.route("/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify(engine.play(
        data.get("message", ""),
        game_id=_game_id(data),
        reverse=bool(data.get("reverse", False)),
        preferences=data.get("preferences"),
    )), 200


@app.route("/stream", methods=["POST"])
def stream():
    """The same turn as /echo, sent as it is written.

    Server-sent events rather than a websocket: the traffic is one-way and short-lived,
    it survives the same proxies ordinary POSTs do, and the browser side is one
    `ReadableStream` instead of a connection to keep alive.

    Two event types. `delta` carries more of the reply; `done` carries the identical
    payload /echo returns, so a client that ignores every delta and reads only `done`
    behaves exactly as it did before - which is also the fallback when a provider has
    no streaming path.
    """
    data = request.get_json(silent=True) or {}
    turn = engine.play_stream(
        data.get("message", ""),
        game_id=_game_id(data),
        reverse=bool(data.get("reverse", False)),
        preferences=data.get("preferences"),
        # The train of thought is only drawn when the "s" toggle is on. When it's off,
        # asking for it anyway spends the largest field on the schema generating an
        # animation nobody will see.
        thoughts=bool(data.get("thoughts", False)),
    )

    def events():
        for kind, payload in turn:
            yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"

    return Response(events(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",     # tell any nginx in front of us not to buffer
        "Connection": "keep-alive",
    })


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json(silent=True) or {}
    return jsonify(engine.reset(
        game_id=_game_id(data),
        reverse=bool(data.get("reverse", False)),
    )), 200


@app.route("/timeout", methods=["POST"])
def timeout():
    """The clock ran out on the human's turn.

    Its own route rather than a magic message through /echo: running out of time is
    something the client observed, not something the player typed, and faking it as a
    message would write a sentence they never said into both the transcript and the
    model's view of the conversation.
    """
    data = request.get_json(silent=True) or {}
    who = data.get("who")
    return jsonify(engine.timeout(
        game_id=_game_id(data),
        reverse=bool(data.get("reverse", False)),
        who="bot" if who == "bot" else "human",
    )), 200


@app.route("/transcripts", methods=["GET"])
def transcripts():
    """Recently active chats, newest first. `?chat_id=` returns one chat's messages."""
    chat_id = request.args.get("chat_id")
    if chat_id:
        return jsonify({"chat_id": chat_id, "messages": transcript.chat(chat_id)}), 200
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
    except ValueError:
        limit = 50
    return jsonify({"chats": transcript.chats(limit)}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
