"""One turn of RTS.

The shape of a turn, and the only place the pieces meet:

  1. deterministic pre-checks   - free, reliable, never wrong (rules.py)
  2. ask the brain              - one structured call (providers/)
  3. deterministic post-checks  - the AI must obey the rules too; one retry, else concede
  4. advance the game           - (state.py) and shape the reply (contract.py)

Steps 1 and 3 exist because the letter rule and duplicate detection must be 100%
reliable and a model is not. Everything else is the model's job - including, now, the
wording of a rule break, which the model phrases and the post-check enforces.

Breaking the letter rule or replaying a word doesn't end anything. It's called, recorded
in the history, and play carries on: ending a game over a slip is miserable, and typo
repair means an honest mistype would otherwise kill a good chain. Only giving up ends a
game, and only conceding wipes the board.

Rounds are lost by dropping an argument, never by having one. Asking "how?" and arguing
back both cost nothing. What costs is walking away - saying so, asking for a fresh word
instead of answering, or quietly playing something else while a question is still open.
That last one is why `pending` exists.
"""

import queue
import threading
import time

from . import contract, history, prompts, rules, transcript
from .preferences import Preferences
from .providers import TurnContext, get_provider
from .schema import move_schema as schema_for
from .state import GAMES, SOLO_ID


def play_stream(player_input, game_id=SOLO_ID, reverse=False, preferences=None,
                thoughts=True):
    """One turn, yielded as it is written.

    Yields ("delta", text) as the reply arrives and finally ("done", payload) with the
    same contract dict `play` returns - so the client's handling of a finished turn is
    unchanged and only the arrival time differs.

    The turn runs on a worker thread feeding a queue rather than being restructured as
    a generator. `_play` is a decision tree with three possible model calls and several
    early returns; turning it inside out to yield from every branch would put streaming
    plumbing into every rule in the game. A queue keeps the rules readable and confines
    the concurrency to these fifteen lines.
    """
    events = queue.Queue()
    sink = Sink(lambda text: events.put(("delta", text)), thoughts=thoughts)

    def run():
        try:
            events.put(("done", play(player_input, game_id, reverse, preferences, sink)))
        except Exception as e:                      # noqa: BLE001 - the client gets "?"
            events.put(("done", contract.error(e)))
        finally:
            events.put(None)

    threading.Thread(target=run, daemon=True).start()

    while True:
        item = events.get()
        if item is None:
            return
        yield item


def play(player_input, game_id=SOLO_ID, reverse=False, preferences=None, sink=None):
    """Handle one /echo turn. Returns the frozen contract dict.

    Both sides of the exchange are recorded afterwards, not before: the prompt already
    carries the human's current message in its own block, so remembering it up front
    would send it twice. A loss or restart mid-turn swaps the Game object, hence the
    re-fetch - the transcript survives that swap, the board doesn't.
    """
    started = time.monotonic()
    payload = _play(player_input, game_id, reverse, preferences, sink)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    game = GAMES.get(game_id)
    game.remember("user", (player_input or "").strip())
    game.remember("assistant", payload.get("response", ""))

    # Written here rather than inside _play because this is the one point where a turn
    # is definitely over and its shape is final - _play has several early returns and
    # can call the model three times, and recording from in there would either miss
    # branches or log turns that were then replaced by a retry.
    transcript.record_turn(game_id, player_input, payload,
                           reverse=game.rule.reverse, latency_ms=elapsed_ms,
                           thoughts=sink.thoughts if sink else None)

    # Along for the ride, deliberately unmentioned. The bot never brings the score up and
    # nothing is obliged to render it - but it's tracked from the first turn, so whatever
    # decides to show it later has a history to show rather than starting from zero.
    payload["score"] = history.score(game.history, "human")
    return payload


def _play(player_input, game_id, reverse, preferences, sink=None):
    game = GAMES.get(game_id)
    taste = Preferences.from_payload(preferences)

    # The client owns the toggle, so the rule travels with every turn. Cheap, and it
    # makes backend/frontend drift impossible.
    if game.rule.reverse != bool(reverse):
        game.set_reverse(reverse)
    rule = game.rule

    text = (player_input or "").strip()

    # --- 1. deterministic pre-checks ---
    if not text:
        return contract.contract("INVALID", "?")

    # Breaking the letter rule or replaying a word no longer ends the game. It gets
    # called, recorded, and play continues - partly because ending a game over a slip is
    # miserable, and mostly because typo repair means a mistyped "sorange" would otherwise
    # kill a good chain. It still costs: the event lands in the history and shows up in
    # the score, whether or not anyone mentions it at the time.
    #
    # Detection stays here, deterministically, but the *phrasing* goes to the model, so
    # this reads as the bot noticing rather than a canned string. The post-check below is
    # what guarantees the chain doesn't move regardless of what comes back.
    broke_rule = repeated = False
    if rules.is_single_word(text):
        word = text.lower()
        broke_rule = rule.rejects(word)
        repeated = rules.is_variation(word, game.used)
        if broke_rule:
            game.history.record(history.RULE_BREAK, "human", word)
        elif repeated:
            game.history.record(history.REPEAT, "human", word)

    # The human's word isn't committed to game.used until step 4, so hold the set the AI
    # must actually avoid: everything used, plus the word the human just played. Without
    # this the AI can echo the human's word straight back and the duplicate check won't
    # see it.
    spent = game.used | {text.lower()}

    # --- 2. ask the brain ---
    note = None
    if broke_rule:
        note = (f'"{text.lower()}" starts with a banned letter under the rule in force. '
                "Say so briefly and ask for another word. Do not play a word of your own "
                "- the chain doesn't move. Nobody has lost; they just go again.")
    elif repeated:
        note = (f'"{text.lower()}" is already in the chain. Say so briefly and ask for '
                "another. Do not play a word of your own. Nobody has lost.")

    try:
        if sink:
            sink.gate = lambda fields: _will_stand(fields, rule, spent, game)
        data = _ask(game, text, taste=taste, spent=spent, correction=note, sink=sink)
    except Exception as e:
        return contract.error(e)                    # frontend already renders "?" on ERROR

    code = data.get("response_code", "INVALID")
    reply = (data.get("response") or "").strip()

    # An illegal word can't advance the chain no matter how the model answered. The model
    # owns the wording; the board is not up for negotiation.
    if broke_rule or repeated:
        game.pending = None
        return contract.contract(
            "RTS" if broke_rule else "DUPLICATE",
            reply or (f"{rule.violation_message}. go again" if broke_rule
                      else f"{text.lower()}? already played. go again"),
        )

    # The single-word override that used to live here is gone. It forced any one-word
    # message to be a move, because without conversation history the model had no way to
    # tell "bro" opening a game from "what" answering a question - so it guessed, badly,
    # and this rule overruled it whichever way it guessed. The model can see the
    # transcript now, which is the actual fix; forcing the answer on top of that would
    # just reintroduce the bug it was papering over.

    # Veto a bogus duplicate call. Repeating is a losing move now, so a model that
    # mistakes a synonym for a repeat ("win's basically victory") ends the game on a
    # legal play. Duplicates are deterministic - if the word isn't actually one, the
    # model doesn't get to say it is.
    if code == "DUPLICATE" and not rules.looks_like_duplicate(text.lower(), game.used):
        try:
            data = _ask(game, text, taste=taste, spent=spent, sink=_ungated(sink),
                        correction="that word has NOT been played. A different word that "
                                   "happens to mean something similar is NOT a repeat - "
                                   "only the same word, or a plural/tense of it, is. "
                                   "Accept the move and play on.")
        except Exception as e:
            return contract.error(e)
        code = data.get("response_code", "INVALID")
        reply = (data.get("response") or "").strip()

    # A concede used to be second-guessed here, on the grounds that the bot gave up too
    # easily. That was true of a model reasoning with thinking switched off, and the retry
    # made it worse in a subtler way: conceding became so expensive that the bot would
    # rather play a word it couldn't defend. Losing honestly is cheaper than that, and the
    # prompt now says so. If it starts folding early again, raise RTS_EFFORT - that's the
    # dial for "think harder before giving up", not a second round-trip.

    # Settle any open question before acting on this turn. This has to happen before the
    # dispatch below, not inside the OK branch: walking away from a question is walking
    # away whether or not the bot happens to like the word they replaced it with. The
    # first version only noticed abandonment when the new word was accepted, so playing a
    # second unrelated word in a row quietly cost nothing.
    _settle_pending(game, data, text, code)

    # --- the bot can't see the link and wants to know ---
    # Nobody loses and the board doesn't move; the question is simply left open. While
    # it's open the next message is read as an answer to it, which is what lets the
    # conversation wander off and come back without dropping the thread.
    if code == "ASK":
        asked_about = _clean(data.get("their_word")) or text.lower()
        game.pending = history.Pending(asked_about, game.last_word, "bot")
        game.history.record(history.CHALLENGED, "human", asked_about)
        if reply:
            game.history.asks.append(reply)
        return contract.contract("ASK", reply or f"{asked_about}?")

    # --- the human asked to start over, or asked the AI to open ---
    # Asking for a fresh word while you owe an answer is a way of dropping the argument,
    # so it's recorded as giving up the round - same as saying so out loud. Asking for one
    # in open play costs nothing.
    if code == "RESTART":
        if game.pending and game.pending.asked_by == "bot":
            game.history.record(history.CONCEDED, "human",
                                game.pending.word, history.RESTARTED)
        return _restart(game_id, rule, data, reply)

    # --- genuinely cornered: it gives up the round, and the game restarts ---
    if code == "CONCEDE":
        game.history.record(history.CONCEDED, "bot", game.last_word, history.EXPLICIT)
        return _lose(game_id, rule, "CONCEDE", reply or "ok, you got me. new game - go")

    # --- a real repeat the deterministic pre-check couldn't see (an irregular plural,
    #     or a word buried in prose) ---
    if code == "DUPLICATE":
        return _lose(game_id, rule, "DUPLICATE", reply or "already played. you lose. new game - go")

    # --- 3. deterministic post-checks on the AI's own word ---
    if code == "OK":
        chosen = _clean(data.get("chosen_word"))

        if not _legal(chosen, rule, spent):
            try:
                data = _ask(game, text, correction="you played an illegal or repeated word",
                            taste=taste, spent=spent, sink=_ungated(sink))
            except Exception as e:
                return contract.error(e)
            code = data.get("response_code", "CONCEDE")
            reply = (data.get("response") or "ok, you got me").strip()
            chosen = _clean(data.get("chosen_word"))

            if code != "OK" or not _legal(chosen, rule, spent):
                # Cornered even after a retry. The AI loses; new game.
                return _lose(game_id, rule, "CONCEDE", "ok, you got me. new game - go")

        # --- 4. legal both ways: advance the chain ---
        # What they *played*, not what they typed. Falls back to the raw text only when
        # the model didn't name a word, and skips it entirely if that fallback isn't a
        # bare word - better a gap in the chain than "how?" sitting in it as a move.
        played = _clean(data.get("their_word")) or text.lower()

        if rules.is_single_word(played):
            game.add(played)
            game.history.record(history.MOVE, "human", played)
            game.history.link(game.chain[-2] if len(game.chain) > 1 else None,
                              played, "human")
        else:
            played = game.last_word

        game.add(chosen)
        game.history.record(history.MOVE, "bot", chosen)
        game.history.link(played, chosen, "bot")

        tot = contract.clean_train_of_thought(data.get("train_of_thought", []), chosen, rule)
        # The link is what the human rates: "from this word, the AI leapt to that one".
        return contract.contract("OK", reply or chosen, tot,
                                 link={"from": played, "to": chosen})

    # Non-advancing, non-losing: UNRELATED / INVALID / CHAT. The board is unchanged,
    # and any open question stays open - a question or an aside doesn't settle it.
    return contract.contract(code, reply or "?", [])


def reset(game_id=SOLO_ID, reverse=False):
    """Handle /reset. Clears the game, keeping whichever rule the client is on."""
    GAMES.reset(game_id, reverse)
    return {"response": "new game", "train_of_thought": []}


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _lose(game_id, rule, code, message):
    """Somebody broke a rule or got cornered. Wipe the board and start again - the
    letter rule carries over, since that's a client toggle, not part of the game."""
    GAMES.reset(game_id, rule.reverse)
    return contract.contract(code, message, new_game=True)


def _restart(game_id, rule, data, reply):
    """The human asked for a new game, or asked the AI to open with a word."""
    game = GAMES.reset(game_id, rule.reverse)

    chosen = _clean(data.get("chosen_word"))
    if not chosen or rule.rejects(chosen):
        # It didn't hand us a usable opener - start the game anyway and let them lead.
        return contract.contract("RESTART", reply or "new game. you go first", new_game=True)

    game.add(chosen)
    tot = contract.clean_train_of_thought(data.get("train_of_thought", []), chosen, rule)
    return contract.contract("RESTART", reply or chosen, tot, new_game=True)


def _settle_pending(game, data, text, code):
    """Close out an open question, if this turn closed it.

    Three ways it ends. They argued for the word and the argument landed, so the reason
    gets stored on the link - that's what "how?" reads later instead of inventing a fresh
    explanation. They argued and it didn't land. Or they said nothing about it and played
    a different word instead, which is the quiet way of giving up a round: nobody
    announces it, and it counts the same as saying so.

    A question or an aside settles nothing and leaves it open, which is the point of
    having this at all - the conversation can wander and come back.
    """
    pending = game.pending
    if not pending or pending.asked_by != "bot":
        return
    if code in ("CHAT", "INVALID"):
        return

    # What they put forward this turn, if anything. Prefer the model's reading, since it
    # sees through typos, but fall back to the raw message: a bare word on its own is an
    # unambiguous "I'm playing this instead", and the model leaves their_word empty when
    # it's rejecting, which would otherwise hide exactly the case we're looking for.
    typed = text.lower()
    played = _clean(data.get("their_word")) or (
        typed if rules.is_single_word(typed) else "")
    moved_on = bool(played) and played != pending.word

    if moved_on:
        game.history.record(history.CONCEDED, "human", pending.word, history.ABANDONED)
    elif code == "UNRELATED":
        game.history.record(history.REJECTED, "human", pending.word)
        return                              # still unsettled - they can try again
    elif code == "OK":
        game.history.record(history.JUSTIFIED, "human", pending.word)
        link = game.history.find_link(pending.word)
        if link:
            link.status, link.why = "accepted", text
    else:
        return                              # nothing conclusive happened

    game.pending = None


def _ask(game, player_input, correction=None, taste=None, spent=None, sink=None):
    # `spent` = used words plus the human's pending word, so a provider can avoid
    # echoing it back rather than being caught by the post-check.
    ctx = TurnContext(game.rule, spent or game.used, game.chain, game.last_word)
    provider = get_provider()
    system = prompts.system_prompt(game.rule)
    conversation = prompts.messages(game, player_input, correction, taste)

    if sink is None:
        return provider.move(system, conversation, ctx)

    schema = schema_for(with_train_of_thought=sink.thoughts)
    return sink.consume(provider.stream_move(system, conversation, ctx, schema))


class Sink:
    """Carries a streamed reply out to the client, once it is safe to show.

    The engine may reject a turn and ask again - an illegal word, an invented
    duplicate. Text already on screen cannot be taken back, so nothing is forwarded
    until `gate` has approved this particular answer.

    That check is possible mid-stream only because the schema puts `response_code`,
    `their_word` and `chosen_word` ahead of `response`: by the time the first character
    of the reply exists, the engine already knows the word it is about to play. A
    rejected answer is swallowed whole and the retry streams in its place.
    """

    def __init__(self, emit, thoughts=True):
        self.emit = emit
        self.thoughts = thoughts
        self.gate = None
        self._open = None

    def consume(self, events):
        """Drain a provider stream and return the finished move."""
        self._open = None
        fields, data = {}, None

        for kind, payload in events:
            if kind == "field":
                name, value = payload
                fields[name] = value
            elif kind == "delta":
                if self._open is None:
                    self._open = self.gate is None or bool(self.gate(fields))
                if self._open:
                    self.emit(payload)
            elif kind == "done":
                data = payload

        return data if data is not None else fields


def _ungated(sink):
    """The same sink with its gate cleared.

    A retry's answer is the one that gets used - there is no further round to replace
    it - so it streams unconditionally. Without this it would inherit the gate that
    rejected the answer it was sent to replace.
    """
    if sink:
        sink.gate = None
    return sink


def _will_stand(fields, rule, spent, game):
    """Will this answer be used as-is, or is the engine about to ask again?

    Mirrors the two post-checks below that trigger a retry. It reads the three fields
    the schema guarantees have already arrived, so the decision is available before the
    reply itself starts - which is the whole reason a turn can stream at all.

    Deliberately conservative: anything this can't confidently approve is withheld and
    simply arrives a moment later when the turn finishes. A wrong "yes" puts text on
    screen that the engine then contradicts; a wrong "no" costs nothing but the stream.
    """
    code = fields.get("response_code", "")

    if code == "DUPLICATE":
        return rules.looks_like_duplicate(_clean(fields.get("their_word")) or "", game.used)

    if code == "OK":
        return _legal(_clean(fields.get("chosen_word")), rule, spent)

    return True


def _clean(word):
    return (word or "").strip().lower()


def _legal(word, rule, used):
    return bool(word) and rule.allows(word) and not rules.is_variation(word, used)
