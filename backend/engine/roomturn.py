"""One turn in a room.

The same four steps a solo turn has - pre-check, ask, post-check, advance - with two
differences that account for most of this file.

**The pre-checks are all there is, most of the time.** In a room the bot is one seat in
the rotation, so between its turns other people are playing off each other and it isn't
being asked anything. Somebody has to notice a banned letter in the meantime, and it
can't be the model, because the model isn't in the loop. So a rule break, a repeat and
a word played out of turn are all called here, deterministically, by name, and instantly
- no round-trip, no tokens. That's not a cost saving; it's the only way the correction
can arrive before the next person has already answered the illegal word.

**Nothing here loses a round.** Solo play wipes the board when somebody is cornered,
because there are two people and the game is between them. With four people, one of them
walking off to make tea is not a reason to throw away a chain the other three built. So
the consequences are all "your turn passes": the miss is recorded against the player and
shows up in the score, the board carries on.

The bot's turn runs on a worker thread. Everything that touches room state takes
`room.lock`, and the model call deliberately happens outside it - holding the lock across
a two-second request would stop everyone else in the room from typing while the bot
thinks, which is the one moment they're most likely to want to.
"""

import threading
import time
import uuid

from . import bus, history, prompts, rules, transcript
from .providers import TurnContext, get_provider
from .rooms import BOT_ID, BOT_NAME, ROOMS


# ---------------------------------------------------------------------------
# rooms
# ---------------------------------------------------------------------------
def create(name, bot=True, timer=True, reverse=False):
    """A new room, with its clock wired to the skip below."""
    room = ROOMS.create(name, bot=bot, timer=timer, reverse=reverse)
    room.on_expire = expire
    return room


def join(room, user_id, name):
    with room.lock:
        first = not room.members
        member = room.join(user_id, name)

        # "ana joined" to an empty room is a note addressed to nobody. The first person
        # in gets the bot's opening line instead, which says the same thing and also
        # says what to do about it.
        if first and room.bot:
            _bot_says(room, _opening(room))
        else:
            _post(room, _msg(room, None, member.name, f"{member.name} joined",
                             kind="system"))

        _state(room)
        due = room.bot_turn
    if due:
        _wake(room)
    return member


def _opening(room):
    """Who starts, and what counts. Said once, when a room comes to life.

    Deterministic rather than asked for: this is the first thing anybody sees, it is
    the same every time, and making the room wait two seconds on a model to be told
    whose go it is would be a strange way to open.
    """
    who = room.named(room.turn) if room.turn else "somebody"
    rule = ("any word starting with r, t or s" if room.game.rule.reverse
            else "any word that doesn't start with r, t or s")
    return f"{who} starts - {rule}, and we go round from there"


def leave(room, user_id):
    with room.lock:
        member = room.members.get(user_id)
        if not member:
            return
        name = member.name
        room.leave(user_id)
        _post(room, _msg(room, None, name, f"{name} left", kind="system"))
        _state(room)
        due = room.bot_turn
    if due:
        _wake(room)


def configure(room, *, bot=None, timer=None, reverse=None):
    """Change a room setting and tell everyone what changed.

    Settings are shared, not per-person: they describe the room, and a timer that only
    some of the people in a room can see is not a timer anybody can play against.
    """
    said = []
    with room.lock:
        if bot is not None and bool(bot) != room.bot:
            room.set_bot(bot)
            said.append("bot's in, playing along" if room.bot
                        else "bot's out - no rules, just talk")
        if timer is not None and bool(timer) != room.timer:
            room.set_timer(timer)
            said.append("clock's on" if room.timer else "clock's off")
        if reverse is not None and bool(reverse) != room.game.rule.reverse:
            room.game.set_reverse(reverse)
            said.append("new rules... every word has to start with r t or s now"
                        if reverse else
                        "back to normal - no word can start with r, t or s")
        for line in said:
            _post(room, _msg(room, None, None, line, kind="system"))
        _state(room)
        due = room.bot_turn
    if due:
        _wake(room)


# ---------------------------------------------------------------------------
# a turn
# ---------------------------------------------------------------------------
def say(room, user_id, text):
    """Somebody typed something. Returns the message that was posted."""
    text = (text or "").strip()
    if not text:
        return None

    with room.lock:
        member = room.members.get(user_id)
        if member is None:
            raise KeyError(user_id)
        room.touch()

        # Somebody is here. Whatever they said, the room is awake again and the count
        # of silent turns starts over - it is a run of consecutive misses that means an
        # empty room, and one answer anywhere in it breaks the run.
        woke, room.idle, room.skips = room.idle, False, 0
        if woke:
            room.arm()

        # No bot means nobody is refereeing, so nothing below applies: every message is
        # just a message. The clock stays, resetting on any of them - a shared
        # pace-maker with nothing riding on it.
        if not room.bot:
            message = _post(room, _msg(room, user_id, member.name, text))
            room.arm()
            _state(room)
            return message

        word = text.lower() if rules.is_single_word(text) else None
        theirs = room.turn == user_id

        flag = None
        if word and not theirs:
            flag = "out_of_turn"
        elif word:
            flag = _illegal(room, user_id, word)

        message = _post(room, _msg(room, user_id, member.name, text, flag=flag))
        room.game.remember("user", f"{member.name}: {text}")

        # A sentence is conversation, not a move - so it costs nothing and changes
        # nothing, including whose turn it is. If it was your turn before you started
        # talking, it still is, and the clock is still yours.
        if word:
            _resolve(room, user_id, member.name, word, flag)

        _state(room)
        due = room.bot_turn

    if due:
        _wake(room)
    return message


def _illegal(room, user_id, word):
    """Deterministic pre-checks, recorded against the player who made the move."""
    if room.game.rule.rejects(word):
        room.game.history.record(history.RULE_BREAK, user_id, word)
        return "rts"
    if rules.is_variation(word, room.game.used):
        room.game.history.record(history.REPEAT, user_id, word)
        return "duplicate"
    return None


def _resolve(room, user_id, name, word, flag):
    """Act on a word: seat it in the chain, or call it and pass the turn on."""
    if flag == "out_of_turn":
        # Nothing said about it. The word arrives greyed out, which is the whole
        # message - and a room where three people answer at once is a room enjoying
        # itself, not something that needs a line of correction each time it happens.
        return

    if flag:
        # Called, and their turn goes by without a word on the board. Nobody has lost
        # anything except the go, which is the point: the rule bites without the round
        # being thrown away over a slip.
        room.advance()
        reason = (f"{name}, {rules.first_letter(word)}. doesn't count"
                  if flag == "rts" else f"{name}, {word}'s already been played")
        _bot_says(room, reason + _whos_up(room))
        return

    previous = room.game.last_word
    room.game.add(word)
    room.game.history.record(history.MOVE, user_id, word)
    room.game.history.link(previous, word, user_id)
    room.advance()


def _whos_up(room):
    """" - cara, moth's still up", or nothing when the bot is about to answer anyway."""
    if room.bot_turn or not room.turn:
        return ""
    who = room.named(room.turn)
    return f" - {who}, {room.game.last_word} is still up" if room.game.last_word \
        else f" - {who}, board's yours"


def expire(room, whose):
    """The clock ran out on somebody. Skip them; the board survives.

    Called from the room's own timer thread, so it can't assume anything about who is
    connected - which is exactly why the server owns this clock rather than the browser
    of the player it is counting down.
    """
    with room.lock:
        if room.turn != whose:
            return
        name = room.named(whose)
        room.game.history.record(history.CONCEDED, whose, room.game.last_word,
                                 history.TIMED_OUT)
        if whose != BOT_ID:
            room.skips += 1

        # Everyone has now had a silent go, so there is nobody here. Stop, rather than
        # walking the rotation announcing each absence in turn - a room left open in a
        # background tab would otherwise do that until the room was swept, and what it
        # produces is a screen of "X ran out of time" for anyone who does come back.
        if room.deserted:
            room.idle = True
            room.disarm()
            room.deadline = None
            _bot_says(room, _resting(room))
            _state(room)
            return

        room.advance()
        _bot_says(room, f"{name} ran out of time" + _whos_up(room))
        _state(room)
        due = room.bot_turn
    if due:
        _wake(room)


def _resting(room):
    """What the room says when it stops waiting. Says how to start it again."""
    word = room.game.last_word
    return (f"nobody's about - i'll leave it there. say anything and we'll pick it back "
            f"up from {word}" if word else
            "nobody's about - i'll leave it there. say anything when you're back")


# ---------------------------------------------------------------------------
# the bot's own turn
# ---------------------------------------------------------------------------
def _wake(room):
    """Start the bot's turn, unless one is already out at the model."""
    with room.lock:
        if room.thinking or not room.bot_turn or room.idle:
            return
        room.thinking = True
    threading.Thread(target=_bot_turn, args=(room,), daemon=True).start()


def _bot_turn(room):
    started = time.monotonic()
    bus.BUS.publish(room.id, "thinking", {"room": room.id})
    try:
        data = _ask(room)
        chosen = _clean(data.get("chosen_word"))

        # One retry on an illegal word, same as solo. The board is not up for
        # negotiation whatever came back, but a second look is usually all it takes,
        # and the alternative is the bot's whole go passing in silence.
        if data.get("response_code") == "OK" and not _legal(room, chosen):
            data = _ask(room, "you played a word that breaks the letter rule or has "
                              "already been played. Play a legal one.")
            chosen = _clean(data.get("chosen_word"))

        reply = (data.get("response") or "").strip()
        elapsed = int((time.monotonic() - started) * 1000)

        with room.lock:
            # The room can move on while the model is thinking - the bot switched off,
            # everyone left, the settings changed. Its answer is about a board that no
            # longer exists, so it is dropped rather than played into a new one.
            if not room.bot_turn:
                return

            link = None
            if data.get("response_code") == "OK" and _legal(room, chosen):
                previous = room.game.last_word
                room.game.add(chosen)
                room.game.history.record(history.MOVE, BOT_ID, chosen)
                room.game.history.link(previous, chosen, BOT_ID)
                link = {"from": previous, "to": chosen}
                reply = reply or chosen

            # Its go is over either way. A question it asked, a word it couldn't find,
            # a joke - it had its turn and used it, and the rotation carries on.
            room.advance()
            _bot_says(room, reply or "...", code=data.get("response_code"), link=link,
                      latency_ms=elapsed)
            _state(room)
    except Exception:                                   # noqa: BLE001
        with room.lock:
            if room.bot_turn:
                room.advance()
                _bot_says(room, "?", code="ERROR")
                _state(room)
    finally:
        room.thinking = False


def _ask(room, correction=None):
    game = room.game
    ctx = TurnContext(game.rule, game.used, game.chain, game.last_word)
    system = prompts.system_prompt(game.rule, room=True)
    # No player_input: several people may have spoken since the bot's last go, and they
    # are all in the transcript already. Handing one of them over as "they just said"
    # would single out whoever happened to be last.
    conversation = prompts.messages(game, "", correction, None, room=room)
    return get_provider().move(system, conversation, ctx)


def _legal(room, word):
    return bool(word) and room.game.rule.allows(word) \
        and not rules.is_variation(word, room.game.used)


def _clean(word):
    return (word or "").strip().lower()


# ---------------------------------------------------------------------------
# messages
# ---------------------------------------------------------------------------
def _msg(room, user_id, name, text, kind="say", code=None, link=None, flag=None):
    return {
        "id": uuid.uuid4().hex,
        "room": room.id,
        "user_id": user_id,
        "name": name,
        "text": text,
        "ts": time.time(),
        "kind": kind,               # say | bot | system
        "code": code,
        "link": link,
        "flag": flag,               # out_of_turn | rts | duplicate
    }


def _bot_says(room, text, code=None, link=None, latency_ms=None):
    room.game.remember("assistant", text)
    return _post(room, _msg(room, BOT_ID, BOT_NAME, text, kind="bot", code=code,
                            link=link), latency_ms=latency_ms)


def _post(room, message, latency_ms=None):
    """Everything a message has to reach: the room, everyone watching, the record."""
    room.append(message)
    bus.BUS.publish(room.id, "message", message)
    transcript.record_message(
        room.id,
        role="bot" if message["kind"] == "bot" else "human",
        type=message.get("code") or message.get("flag") or (
            "SYSTEM" if message["kind"] == "system" else "SAID"),
        text=message["text"],
        reverse=room.game.rule.reverse,
        user_id=message.get("user_id"),
        user_name=message.get("name"),
        link=message.get("link"),
        latency_ms=latency_ms,
    )
    return message


def _state(room):
    bus.BUS.publish(room.id, "state", room.state())
