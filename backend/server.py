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
from queue import Empty

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
from engine import bus, transcript  # noqa: E402

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


# ---------------------------------------------------------------------------
# rooms
# ---------------------------------------------------------------------------
#
# A room is the same game with more people in it. The shape here is deliberately
# boring - REST for anything a client does, one server-sent event stream for
# everything that happens *to* it. A room is the first place in this app where the
# interesting events aren't replies to a request: somebody else types, the clock runs
# out, the bot takes its turn.

def _who(data):
    """The player behind a request. No account, no password - a display name and an id
    the browser generated and keeps, which is enough to be the same person on reload
    and enough for the bot to address you by name."""
    return (str(data.get("user_id") or "").strip()[:64],
            str(data.get("name") or "").strip()[:24])


def _room_or_404(room_id):
    room = engine.ROOMS.get(room_id)
    if room is None:
        return None, (jsonify({"error": "no such room"}), 404)
    return room, None


@app.route("/rooms", methods=["GET"])
def rooms_list():
    return jsonify({"rooms": engine.ROOMS.list()}), 200


@app.route("/rooms", methods=["POST"])
def rooms_create():
    data = request.get_json(silent=True) or {}
    user_id, name = _who(data)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    room = engine.roomturn.create(
        data.get("room_name") or data.get("name") or "room",
        bot=data.get("bot", True),
        timer=data.get("timer", True),
        reverse=bool(data.get("reverse", False)),
    )
    member = engine.roomturn.join(room, user_id, name)
    return jsonify({"room": room.state(), "you": member.public(),
                    "messages": room.log}), 200


@app.route("/rooms/<room_id>", methods=["GET"])
def rooms_get(room_id):
    room, missing = _room_or_404(room_id)
    if missing:
        return missing
    return jsonify({"room": room.state(), "messages": room.log}), 200


@app.route("/rooms/<room_id>/join", methods=["POST"])
def rooms_join(room_id):
    room, missing = _room_or_404(room_id)
    if missing:
        return missing
    data = request.get_json(silent=True) or {}
    user_id, name = _who(data)
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    member = engine.roomturn.join(room, user_id, name)
    return jsonify({"room": room.state(), "you": member.public(),
                    "messages": room.log}), 200


@app.route("/rooms/<room_id>/leave", methods=["POST"])
def rooms_leave(room_id):
    room, missing = _room_or_404(room_id)
    if missing:
        return missing
    user_id, _ = _who(request.get_json(silent=True) or {})
    engine.roomturn.leave(room, user_id)
    return jsonify({"ok": True}), 200


@app.route("/rooms/<room_id>/say", methods=["POST"])
def rooms_say(room_id):
    """Post a message. The reply, if there is one, arrives over the event stream.

    Nothing is returned but an ack on purpose: in a room the answer isn't owed to the
    person who spoke, it's owed to everyone in there, and it may well arrive after
    somebody else has already said something. One delivery path for every message,
    whoever it was meant for.
    """
    room, missing = _room_or_404(room_id)
    if missing:
        return missing
    data = request.get_json(silent=True) or {}
    user_id, _ = _who(data)
    try:
        message = engine.roomturn.say(room, user_id, data.get("message", ""))
    except KeyError:
        return jsonify({"error": "you are not in this room"}), 409
    return jsonify({"ok": True, "message": message}), 200


@app.route("/rooms/<room_id>/settings", methods=["POST"])
def rooms_settings(room_id):
    room, missing = _room_or_404(room_id)
    if missing:
        return missing
    data = request.get_json(silent=True) or {}
    engine.roomturn.configure(
        room,
        bot=data.get("bot"),
        timer=data.get("timer"),
        reverse=data.get("reverse"),
    )
    return jsonify({"room": room.state()}), 200


@app.route("/rooms/<room_id>/events", methods=["GET"])
def rooms_events(room_id):
    """Everything that happens in this room, as it happens.

    Server-sent events for the same reasons /stream uses them: one-way traffic, one
    `ReadableStream` on the client, and it survives the proxies an ordinary GET does.

    The stream opens with the room's current state so a client that has just connected
    is never drawing a room from before it arrived, and heartbeats every 20 seconds so
    an idle room's connection isn't dropped by something in the middle.
    """
    room, missing = _room_or_404(room_id)
    if missing:
        return missing

    def events():
        queue = bus.BUS.subscribe(room_id)
        try:
            yield f"event: state\ndata: {json.dumps(room.state())}\n\n"
            while True:
                try:
                    kind, payload = queue.get(timeout=20)
                except Empty:
                    yield ": ping\n\n"
                    continue
                yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"
        finally:
            bus.BUS.unsubscribe(room_id, queue)

    return Response(events(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


# ---------------------------------------------------------------------------
# the archive
# ---------------------------------------------------------------------------
#
# Every conversation this backend has ever recorded, and a way to pull it out. Not
# linked from anywhere in the app: you reach /database by typing it.
#
# Which database that is follows from where the process is running - SQLite on a
# laptop, Firestore on Cloud Run - so the same page shows local runs locally and real
# ones in production without knowing which it is looking at.
#
# RTS_TRANSCRIPT_TOKEN gates all of it when set. Left unset it is open, which is the
# right default for a laptop and the wrong one for the internet: these are real
# conversations people had. Set it in production and pass ?token= to read.

_TOKEN = os.environ.get("RTS_TRANSCRIPT_TOKEN", "").strip()


def _may_read():
    return not _TOKEN or request.args.get("token", "") == _TOKEN


@app.route("/transcripts", methods=["GET"])
def transcripts():
    """Recently active chats, newest first. `?chat_id=` returns one chat's messages."""
    if not _may_read():
        return jsonify({"error": "not allowed"}), 403
    chat_id = request.args.get("chat_id")
    if chat_id:
        return jsonify({"chat_id": chat_id, "messages": transcript.chat(chat_id)}), 200
    try:
        limit = min(int(request.args.get("limit", 500)), 5000)
    except ValueError:
        limit = 500
    return jsonify({"chats": transcript.chats(limit), "store": transcript.store().name}), 200


@app.route("/database", methods=["GET"])
def database():
    """Everything, as one JSON document.

    No interface, no pagination, no download button - the browser's own JSON viewer is
    a better reader than anything worth building here, and `curl .../database | jq` is
    a better one than that. One document rather than a stream of lines because this is
    meant to be *looked at*, and a viewer needs the whole thing anyway.

    `?chat_id=` narrows it to one chat when that is all you wanted.
    """
    if not _may_read():
        return jsonify({"error": "not allowed"}), 403

    one = request.args.get("chat_id")
    listing = ([c for c in transcript.chats(limit=10_000) if c["chat_id"] == one]
               if one else transcript.chats(limit=10_000))

    return jsonify({
        "store": transcript.store().name,
        "chats": [
            {
                "chat_id": c["chat_id"],
                # `messages` is the list; the count it used to hold moves aside rather
                # than sitting under the same name as the thing it counts.
                "count": c.get("messages"),
                "started": c.get("started"),
                "last_seen": c.get("last_seen"),
                "messages": transcript.chat(c["chat_id"]),
            }
            for c in listing
        ],
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
