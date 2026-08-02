"""Rooms: the same game, with more than two people in it.

A room is a `Game` (the board, from state.py) plus the three things solo play never
needed - who is here, whose turn it is, and a clock that belongs to the room rather
than to whoever happens to be looking at it.

The bot is a seat in the rotation, not a special case. It sits in `order` under the id
"bot" and takes its turn when its turn comes round, which is what makes a room with the
bot switched off the same code path as one with it switched on: the seat is simply not
there. Everything that asks "whose turn is it" gets an id back and doesn't care whether
a person or a model is going to fill it.

Turn order is a list of ids and a *pointer by id*, never an index. An index into a list
that people join and leave means every departure silently shifts whose turn it is, and
that bug reads as the game skipping someone at random an hour later.

The clock is the server's, not the client's. Round-robin means the current player can
close their laptop, and a countdown owned by their browser would then never fire and the
room would wait forever on someone who isn't coming back.

State is in memory. The backend runs `--max-instances 1`, so one process sees every
room, and rooms are ephemeral social spaces - a room nobody is in is a room that should
be gone. Messages are durable regardless: they go to Firestore through transcript.py
under the room's id, so a run can still be read back after the room itself is dropped.
"""

import re
import threading
import time
import unicodedata

from .state import Game

BOT_ID = "bot"
BOT_NAME = "rts"

#: Room ids are the first path segment on the site, so a room called "rooms" would
#: shadow the lobby. Reserved rather than moved under a prefix: the link to a room is
#: the point of rooms, and the shortest link is the best one.
RESERVED = {"rooms", "settings", "api", "static", "assets", "index", "favicon"}

#: Seconds a player has to take their turn. The client draws the same number.
TURN_S = 20

#: An empty room is dropped once it has been empty this long.
IDLE_S = 15 * 60

#: Messages kept in memory for someone who has just walked in.
LOG_LIMIT = 200

#: Ceiling on rooms held at once, oldest-idle dropped first. A toy needs a bound
#: somewhere, and an unbounded dict of rooms is the one thing here that a passerby
#: could grow without limit.
MAX_ROOMS = 200


def slug(text, fallback="room"):
    """A room name as something safe to put in a URL and a database key."""
    plain = unicodedata.normalize("NFKD", (text or "")).encode("ascii", "ignore").decode()
    out = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    return out[:32] or fallback


class Member:
    __slots__ = ("user_id", "name", "joined_at", "present")

    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        self.joined_at = time.time()
        self.present = True

    def public(self):
        return {"user_id": self.user_id, "name": self.name, "present": self.present}


class Room:
    def __init__(self, room_id, name, bot=True, timer=True, reverse=False):
        self.id = room_id
        self.name = name or room_id
        self.created_at = time.time()
        self.last_active = self.created_at

        self.bot = bool(bot)
        self.timer = bool(timer)

        self.members = {}                     # user_id -> Member
        self.order = [BOT_ID] if self.bot else []
        self.turn = None                      # user_id whose turn it is, or None
        self.deadline = None                  # wall-clock seconds, or None

        self.game = Game(reverse)

        # What has been said, for a client that has just walked in. Bounded: a room is
        # a place you join, not an archive, and the durable copy is in Firestore.
        self.log = []

        # True while the bot's turn is out at the model. Guards against a second turn
        # being started for the same seat by two messages landing together.
        self.thinking = False

        # Set once, by whoever is running turns for this room. Kept as a hook rather
        # than an import so rooms.py stays free of the turn logic that uses it.
        self.on_expire = None

        self._clock = None
        self.lock = threading.RLock()

        # Turns skipped in a row without a human saying anything, and whether the room
        # has given up waiting. A round-robin room with nobody in it will otherwise
        # walk the rotation forever, announcing each absence to an empty screen.
        self.skips = 0
        self.idle = False

    # --- membership ------------------------------------------------------------
    def unique_name(self, wanted):
        """`wanted`, or `wanted2` if somebody in here already has it."""
        wanted = (wanted or "").strip()[:24] or "anon"
        taken = {m.name.lower() for m in self.members.values()} | {BOT_NAME}
        if wanted.lower() not in taken:
            return wanted
        for n in range(2, 100):
            if f"{wanted}{n}".lower() not in taken:
                return f"{wanted}{n}"
        return wanted

    def join(self, user_id, name):
        """Seat someone directly after whoever is playing, so they are up next.

        Rejoining is not joining: a reload arrives as the same user id, and treating it
        as a new player would move them in the running order every time their wifi
        blinked.
        """
        existing = self.members.get(user_id)
        if existing:
            existing.present = True
            if user_id not in self.order:
                self._seat(user_id)
            self.touch()
            return existing

        member = Member(user_id, self.unique_name(name))
        self.members[user_id] = member
        self._seat(user_id)

        # First body through the door starts the round; until then there was nobody
        # for the clock to be running against.
        if self.turn is None and self.playing:
            self.turn = user_id
        self.arm()
        self.touch()
        return member

    def _seat(self, user_id):
        if self.turn in self.order:
            self.order.insert(self.order.index(self.turn) + 1, user_id)
        else:
            self.order.append(user_id)

    def leave(self, user_id):
        member = self.members.get(user_id)
        if not member:
            return
        member.present = False
        if self.turn == user_id:
            self.advance()
        if user_id in self.order:
            self.order.remove(user_id)
        del self.members[user_id]
        if not self.members:
            self.turn = None
            self.disarm()
        self.touch()

    def named(self, user_id):
        if user_id == BOT_ID:
            return BOT_NAME
        member = self.members.get(user_id)
        return member.name if member else "someone"

    def seated(self):
        """[(name, is_bot)] in seat order - the running order as people, for the prompt."""
        return [(BOT_NAME, True) if uid == BOT_ID else (self.members[uid].name, False)
                for uid in self.order if uid == BOT_ID or uid in self.members]

    @property
    def bot_turn(self):
        return self.bot and self.turn == BOT_ID

    @property
    def humans(self):
        return [uid for uid in self.order if uid != BOT_ID and uid in self.members]

    @property
    def deserted(self):
        """Has everyone in here now had a silent go?

        The floor of two is for a room with one person in it: a single missed turn is
        someone reading the board, and calling that an empty room after twenty seconds
        would be wrong far more often than it was right.
        """
        return self.skips >= max(2, len(self.humans))

    # --- turn order ------------------------------------------------------------
    @property
    def playing(self):
        """Is anyone's turn being tracked at all?

        With the bot switched off nobody is refereeing, so there is no running order
        to be next in - the room is a group chat and the clock is just a clock.
        """
        return self.bot and bool(self.members)

    def advance(self):
        """Pass the turn to the next seat and restart the clock."""
        if not self.playing:
            self.turn = None
            self.disarm()
            return None
        if not self.order:
            self.turn = None
            return None
        if self.turn in self.order:
            nxt = self.order[(self.order.index(self.turn) + 1) % len(self.order)]
        else:
            nxt = self.order[0]
        self.turn = nxt
        self.arm()
        return nxt

    def set_bot(self, on):
        """Add or remove the bot's seat.

        Switching it off does not just silence it - it takes the referee out of the
        room, and with nobody enforcing anything there is no running order left to
        enforce. The clock stays, as a shared pace-maker with nothing riding on it.
        """
        on = bool(on)
        if on == self.bot:
            return
        self.bot = on
        if on:
            self.order.append(BOT_ID)
            if self.turn is None and self.members:
                self.turn = next(iter(self.members))
            self.arm()
        else:
            if BOT_ID in self.order:
                self.order.remove(BOT_ID)
            self.turn = None
            self.arm()          # the ambient clock keeps running; nothing rides on it
        self.touch()

    # --- the clock -------------------------------------------------------------
    @property
    def running(self):
        """Is there anything for a clock to be counting?

        Not while the board is empty. Whoever is up is opening, and an opening move is
        not a response - there is no word to connect to, so there is nothing to be slow
        about. It's the same rule solo play has, and without it a room starts counting
        down the moment its first player walks in and finds themselves alone.

        With the bot off there is no board to be empty, so the ambient clock instead
        waits for somebody to say something - a room nobody has spoken in yet has
        nothing to keep pace with either.
        """
        if not self.timer or self.idle:
            return False
        return self.game.last_word is not None if self.playing else bool(self.log)

    def arm(self):
        """(Re)start the countdown, if this room is running one at all."""
        self.disarm()
        if not self.running:
            self.deadline = None
            return
        self.deadline = time.time() + TURN_S

        # Nothing rides on the clock when the bot is off - it resets on any message and
        # nothing happens when it empties - so there is no expiry to schedule.
        if not self.playing:
            return

        expiring = self.turn
        timer = threading.Timer(TURN_S, self._expired, args=(expiring,))
        timer.daemon = True
        self._clock = timer
        timer.start()

    def disarm(self):
        if self._clock is not None:
            self._clock.cancel()
            self._clock = None

    def _expired(self, whose):
        # The turn may have moved on between this timer firing and it getting the
        # lock - somebody answering in the last few milliseconds. Whoever it was is
        # no longer late, so there is nothing to skip.
        if self.turn != whose or self.on_expire is None:
            return
        try:
            self.on_expire(self, whose)
        except Exception:                                   # noqa: BLE001
            pass

    def set_timer(self, on):
        self.timer = bool(on)
        if self.timer:
            self.arm()
        else:
            self.disarm()
            self.deadline = None
        self.touch()

    # --- misc ------------------------------------------------------------------
    def touch(self):
        self.last_active = time.time()

    def append(self, message):
        self.log.append(message)
        del self.log[:-LOG_LIMIT]

    @property
    def empty(self):
        return not self.members

    def public(self):
        """What the lobby shows about a room without being in it."""
        return {
            "id": self.id,
            "name": self.name,
            "members": [m.public() for m in self.members.values()],
            "count": len(self.members),
            "bot": self.bot,
            "timer": self.timer,
            "reverse": self.game.rule.reverse,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    def state(self):
        """Everything a client in the room needs to draw it.

        `turn` is reported as nobody's whenever the room isn't running a rotation, so a
        client never has to also know the rule about when turns apply. Switching the bot
        off mid-game leaves a stale pointer behind otherwise, and the room draws itself
        as waiting on a player who isn't on the clock.
        """
        whose = self.turn if self.playing else None
        return {
            **self.public(),
            "turn": whose,
            "turn_name": self.named(whose) if whose else None,
            "deadline_ms": int(self.deadline * 1000) if self.deadline else None,
            "chain": list(self.game.chain),
            "word": self.game.last_word,
        }


class RoomStore:
    def __init__(self):
        self._rooms = {}
        self._lock = threading.Lock()

    def create(self, name, bot=True, timer=True, reverse=False):
        with self._lock:
            self._sweep()
            base = slug(name)
            room_id = base
            n = 2
            while room_id in self._rooms or room_id in RESERVED:
                room_id = f"{base}-{n}"
                n += 1
            room = Room(room_id, (name or "").strip()[:32] or base,
                        bot=bot, timer=timer, reverse=reverse)
            self._rooms[room_id] = room
            return room

    def get(self, room_id):
        return self._rooms.get(room_id)

    def list(self):
        """Rooms worth walking into: the ones with somebody in them.

        An empty room is not a place, it is a leftover - and it lingers for as long as
        the sweep takes, so a lobby that showed them would mostly be showing where
        people used to be. It stays reachable by its link until it's swept, which is
        what matters: you can make a room, send the link and go and put the kettle on
        without the room evaporating because you were the only one in it.
        """
        with self._lock:
            self._sweep()
            rooms = [r for r in self._rooms.values() if r.members]
        rooms.sort(key=lambda r: (-len(r.members), -r.last_active))
        return [r.public() for r in rooms]

    def drop(self, room_id):
        with self._lock:
            room = self._rooms.pop(room_id, None)
        if room:
            room.disarm()

    def _sweep(self):
        """Drop rooms nobody has been in for a while. Caller holds the lock."""
        cutoff = time.time() - IDLE_S
        for room_id, room in list(self._rooms.items()):
            if room.empty and room.last_active < cutoff:
                room.disarm()
                del self._rooms[room_id]

        if len(self._rooms) > MAX_ROOMS:
            for room_id, room in sorted(self._rooms.items(),
                                        key=lambda kv: kv[1].last_active)[:-MAX_ROOMS]:
                room.disarm()
                del self._rooms[room_id]


ROOMS = RoomStore()
