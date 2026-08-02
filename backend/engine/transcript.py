"""Durable record of every turn, for looking at afterwards.

The engine keeps a game in memory and forgets it; this writes down what happened so a
run can be read back later - which words were played, what the bot called them, how long
each turn took, and whether a train of thought was asked for.

Two stores behind one interface, chosen by where the process is running:

  Firestore   in the cloud. Cloud Run's disk is ephemeral and the service is pinned to
              a single instance, so a file on it survives a restart but not a redeploy -
              which is exactly when you most want the history. Firestore is already
              enabled on this project and already holds a native database per app, so
              this follows that shape rather than introducing a new dependency.

  SQLite      locally. No credentials, no network, and `sqlite3 transcripts.db` is a
              usable analysis session on its own.

Both speak the same three functions, so nothing above this file knows which is in use.

Writing is best-effort by design: a failure here must never cost the player their turn,
so every error is swallowed after being logged. A missing row is a gap in the analysis;
a raised exception would be a lost game.

  RTS_TRANSCRIPT_DB   SQLite path. Defaults to backend/transcripts.db.
                      Set it empty to turn recording off entirely.
  RTS_FIRESTORE_DB    Firestore database id. Set (and reachable) means Firestore wins.
                      Defaults to "rts-transcripts" when GOOGLE_CLOUD_PROJECT is set, which is
                      true on Cloud Run and false on a laptop.
"""

import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Column order shared by both stores, so a row means the same thing either way.
FIELDS = ("message_id", "chat_id", "seq", "ts", "role", "type", "text", "word",
          "link_from", "link_to", "reverse", "new_game", "latency_ms", "thoughts")

_SQLITE_PATH = os.environ.get(
    "RTS_TRANSCRIPT_DB",
    str(Path(__file__).resolve().parent.parent / "transcripts.db"),
).strip()

def _hosted():
    """Are we running on Google's infrastructure?

    Checked across both, because they advertise themselves differently and getting this
    wrong fails silently: Cloud Run sets K_SERVICE and does *not* set
    GOOGLE_CLOUD_PROJECT, which is an App Engine variable. Keying only on the latter
    meant the deployed service quietly chose the SQLite fallback and wrote its history
    to a disk that is discarded on the next deploy - persistence that reported success
    and kept nothing.
    """
    return bool(os.environ.get("K_SERVICE") or os.environ.get("GAE_ENV")
                or os.environ.get("GOOGLE_CLOUD_PROJECT"))


_FIRESTORE_DB = os.environ.get(
    "RTS_FIRESTORE_DB",
    "rts-transcripts" if _hosted() else "",
).strip()


# ---------------------------------------------------------------------------
# stores
# ---------------------------------------------------------------------------
class _Sqlite:
    """One connection, guarded by a lock.

    Turns can run on a worker thread (see turn.play_stream), so the connection is opened
    with `check_same_thread=False` and every write goes through the lock. SQLite would
    serialise the writes anyway; the lock is what keeps `seq` from being handed out
    twice for the same chat.
    """

    name = "sqlite"

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS messages (
        message_id  TEXT PRIMARY KEY,
        chat_id     TEXT NOT NULL,
        seq         INTEGER NOT NULL,      -- position within the chat, 1-based
        ts          TEXT NOT NULL,         -- ISO-8601, UTC
        role        TEXT NOT NULL,         -- 'human' | 'bot'
        type        TEXT NOT NULL,         -- SAID for a human turn, else the response code
        text        TEXT NOT NULL,
        word        TEXT,                  -- the word that entered the chain, normalised
        link_from   TEXT,                  -- the leap the bot made, when it played one
        link_to     TEXT,
        reverse     INTEGER NOT NULL,      -- which letter rule was in force
        new_game    INTEGER NOT NULL DEFAULT 0,
        latency_ms  INTEGER,               -- bot rows only: how long the turn took
        thoughts    INTEGER                -- was a train of thought asked for?
    );
    CREATE INDEX IF NOT EXISTS messages_by_chat ON messages(chat_id, seq);
    CREATE INDEX IF NOT EXISTS messages_by_time ON messages(ts);
    CREATE INDEX IF NOT EXISTS messages_by_type ON messages(type);
    """

    def __init__(self, path):
        self._path = path
        self._lock = threading.Lock()
        self._conn = None

    def _connect(self):
        if self._conn is None:
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.executescript(self._SCHEMA)
            self._conn.commit()
        return self._conn

    def append(self, chat_id, rows):
        with self._lock:
            conn = self._connect()
            start = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM messages WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()[0]
            conn.executemany(
                f"INSERT INTO messages ({','.join(FIELDS)})"
                f" VALUES ({','.join('?' * len(FIELDS))})",
                [tuple(dict(r, seq=start + i + 1)[f] for f in FIELDS)
                 for i, r in enumerate(rows)],
            )
            conn.commit()

    def chat(self, chat_id):
        with self._lock:
            conn = self._connect()
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY seq", (chat_id,)
            ).fetchall()
            conn.row_factory = None
        return [dict(r) for r in rows]

    def chats(self, limit):
        with self._lock:
            rows = self._connect().execute(
                "SELECT chat_id, COUNT(*), MIN(ts), MAX(ts) FROM messages"
                " GROUP BY chat_id ORDER BY MAX(ts) DESC LIMIT ?", (limit,),
            ).fetchall()
        return [{"chat_id": c, "messages": n, "started": s, "last_seen": l}
                for c, n, s, l in rows]


class _Firestore:
    """chats/{chat_id}/messages/{message_id}, with a summary on the parent.

    A subcollection rather than one flat collection with a `chat_id` field: reading a
    run back is then a single ordered query under one document, and no composite index
    has to be declared for it. The parent doc carries the counters so listing recent
    chats doesn't have to count messages across the whole collection.

    `seq` comes from a transaction on the parent. Two writers on the same chat is not a
    situation this game produces, but a counter that can hand out the same number twice
    is a silently corrupted transcript, and a transaction is the cheap way to not have
    to think about it again.
    """

    name = "firestore"

    def __init__(self, database):
        from google.cloud import firestore

        self._firestore = firestore
        self._db = firestore.Client(database=database)
        self._chats = self._db.collection("chats")

    def append(self, chat_id, rows):
        parent = self._chats.document(chat_id)
        transaction = self._db.transaction()

        @self._firestore.transactional
        def commit(tx):
            snapshot = parent.get(transaction=tx)
            start = (snapshot.get("messages") or 0) if snapshot.exists else 0
            for i, row in enumerate(rows):
                record = dict(row, seq=start + i + 1)
                tx.set(parent.collection("messages").document(record["message_id"]),
                       record)
            tx.set(parent, {
                "chat_id": chat_id,
                "messages": start + len(rows),
                "started": snapshot.get("started") if snapshot.exists else rows[0]["ts"],
                "last_seen": rows[-1]["ts"],
            }, merge=True)

        commit(transaction)

    def chat(self, chat_id):
        docs = (self._chats.document(chat_id).collection("messages")
                .order_by("seq").stream())
        return [d.to_dict() for d in docs]

    def chats(self, limit):
        docs = (self._chats.order_by(
            "last_seen", direction=self._firestore.Query.DESCENDING)
            .limit(limit).stream())
        out = []
        for d in docs:
            data = d.to_dict() or {}
            out.append({"chat_id": data.get("chat_id", d.id),
                        "messages": data.get("messages", 0),
                        "started": data.get("started"),
                        "last_seen": data.get("last_seen")})
        return out


_store = None
_store_lock = threading.Lock()


def store():
    """The active store, built once.

    Firestore is preferred when configured, but a failure to reach it falls back to
    SQLite rather than taking recording down with it - a local file that outlives the
    process is still better than nothing, and the turn must not fail either way.
    """
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            if _FIRESTORE_DB:
                try:
                    _store = _Firestore(_FIRESTORE_DB)
                    log.info("recording turns to firestore database %r", _FIRESTORE_DB)
                except Exception:                       # noqa: BLE001
                    log.exception("firestore unavailable; falling back to sqlite")
            if _store is None:
                _store = _Sqlite(_SQLITE_PATH)
    return _store


def enabled():
    return bool(_FIRESTORE_DB or _SQLITE_PATH)


# ---------------------------------------------------------------------------
# api
# ---------------------------------------------------------------------------
def record_turn(chat_id, player_input, payload, reverse, latency_ms=None,
                thoughts=None):
    """Write both halves of one exchange.

    Called from the one place that already knows a turn is over, so it can't drift out
    of step with what the player actually saw.
    """
    if not enabled():
        return
    try:
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        link = payload.get("link") or {}
        base = {"chat_id": chat_id, "ts": now, "reverse": int(bool(reverse)),
                "word": None, "link_from": None, "link_to": None, "new_game": 0,
                "latency_ms": None, "thoughts": None, "seq": None}

        rows = [
            # What they said, verbatim - not the model's normalised reading of it. The
            # difference between the two is exactly what typo repair does, and it is
            # only visible if both are kept.
            {**base, "message_id": uuid.uuid4().hex, "role": "human", "type": "SAID",
             "text": (player_input or "").strip()},
            {**base, "message_id": uuid.uuid4().hex, "role": "bot",
             "type": payload.get("response_code", "UNKNOWN"),
             "text": payload.get("response", ""),
             "word": link.get("to"),
             "link_from": link.get("from"), "link_to": link.get("to"),
             "new_game": int(bool(payload.get("new_game"))),
             "latency_ms": latency_ms,
             "thoughts": None if thoughts is None else int(bool(thoughts))},
        ]
        store().append(chat_id, rows)
    except Exception:                                   # noqa: BLE001
        # A recording failure is not worth a lost turn.
        log.exception("could not record turn for chat %s", chat_id)


def chat(chat_id):
    """Every message in one chat, in order."""
    return store().chat(chat_id)


def chats(limit=50):
    """The most recently active chats, newest first."""
    return store().chats(limit)
