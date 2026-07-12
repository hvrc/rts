"""One turn of RTS.

The shape of a turn, and the only place the pieces meet:

  1. deterministic pre-checks   — free, reliable, never wrong (rules.py)
  2. ask the brain              — one structured call (providers/)
  3. deterministic post-checks  — the AI must obey the rules too; one retry, else concede
  4. advance the game           — (state.py) and shape the reply (contract.py)

Steps 1 and 3 exist because the letter rule and duplicate detection must be 100%
reliable and a model is not. Everything else is the model's job.

Losing ends the game. Breaking the letter rule and replaying a word are both losses, and
so is the AI conceding. A loss wipes the chain and starts a fresh game immediately — the
words are all free again. The chat history in the UI survives; only the game behind it is
new.
"""

from . import contract, prompts, rules
from .preferences import Preferences
from .providers import TurnContext, get_provider
from .state import GAMES, SOLO_ID


def play(player_input, game_id=SOLO_ID, reverse=False, preferences=None):
    """Handle one /echo turn. Returns the frozen contract dict."""
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

    if rules.is_single_word(text):
        word = text.lower()
        if rule.rejects(word):                      # the signature rule, either direction
            return _lose(game_id, rule, "RTS",
                         f"{rule.violation_message}. you lose. new game — go")
        if rules.is_variation(word, game.used):
            return _lose(game_id, rule, "DUPLICATE",
                         f"{word}? already played. you lose. new game — go")

    # The human's word isn't committed to game.used until step 4, so hold the set the AI
    # must actually avoid: everything used, plus the word the human just played. Without
    # this the AI can echo the human's word straight back and the duplicate check won't
    # see it.
    spent = game.used | {text.lower()}

    # --- 2. ask the brain ---
    try:
        data = _ask(game, text, taste=taste, spent=spent)
    except Exception as e:
        return contract.error(e)                    # frontend already renders "?" on ERROR

    code = data.get("response_code", "INVALID")
    reply = (data.get("response") or "").strip()

    # --- the human asked to start over, or asked the AI to open ---
    if code == "RESTART":
        return _restart(game_id, rule, data, reply)

    # --- the AI is cornered: it loses, and the game restarts ---
    if code == "CONCEDE":
        return _lose(game_id, rule, "CONCEDE", reply or "ok, you got me. new game — go")

    # --- the model caught a subtler repeat than the deterministic check could ---
    if code == "DUPLICATE":
        return _lose(game_id, rule, "DUPLICATE", reply or "already played. you lose. new game — go")

    # --- 3. deterministic post-checks on the AI's own word ---
    if code == "OK":
        chosen = _clean(data.get("chosen_word"))

        if not _legal(chosen, rule, spent):
            try:
                data = _ask(game, text, correction="you played an illegal or repeated word",
                            taste=taste, spent=spent)
            except Exception as e:
                return contract.error(e)
            code = data.get("response_code", "CONCEDE")
            reply = (data.get("response") or "ok, you got me").strip()
            chosen = _clean(data.get("chosen_word"))

            if code != "OK" or not _legal(chosen, rule, spent):
                # Cornered even after a retry. The AI loses; new game.
                return _lose(game_id, rule, "CONCEDE", "ok, you got me. new game — go")

        # --- 4. legal both ways: advance the chain ---
        played = text.lower()
        game.add(played)
        game.add(chosen)
        tot = contract.clean_train_of_thought(data.get("train_of_thought", []), chosen, rule)
        # The link is what the human rates: "from this word, the AI leapt to that one".
        return contract.contract("OK", reply or chosen, tot,
                                 link={"from": played, "to": chosen})

    # Non-advancing, non-losing: UNRELATED / INVALID / CHAT. The board is unchanged.
    return contract.contract(code, reply or "?", [])


def reset(game_id=SOLO_ID, reverse=False):
    """Handle /reset. Clears the game, keeping whichever rule the client is on."""
    GAMES.reset(game_id, reverse)
    return {"response": "new game", "train_of_thought": []}


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _lose(game_id, rule, code, message):
    """Somebody broke a rule or got cornered. Wipe the board and start again — the
    letter rule carries over, since that's a client toggle, not part of the game."""
    GAMES.reset(game_id, rule.reverse)
    return contract.contract(code, message, new_game=True)


def _restart(game_id, rule, data, reply):
    """The human asked for a new game, or asked the AI to open with a word."""
    game = GAMES.reset(game_id, rule.reverse)

    chosen = _clean(data.get("chosen_word"))
    if not chosen or rule.rejects(chosen):
        # It didn't hand us a usable opener — start the game anyway and let them lead.
        return contract.contract("RESTART", reply or "new game. you go first", new_game=True)

    game.add(chosen)
    tot = contract.clean_train_of_thought(data.get("train_of_thought", []), chosen, rule)
    return contract.contract("RESTART", reply or chosen, tot, new_game=True)


def _ask(game, player_input, correction=None, taste=None, spent=None):
    # `spent` = used words plus the human's pending word, so a provider can avoid
    # echoing it back rather than being caught by the post-check.
    ctx = TurnContext(game.rule, spent or game.used, game.chain, game.last_word)
    return get_provider().move(
        prompts.system_prompt(game.rule),
        prompts.turn_message(game, player_input, correction, taste),
        ctx,
    )


def _clean(word):
    return (word or "").strip().lower()


def _legal(word, rule, used):
    return bool(word) and rule.allows(word) and not rules.is_variation(word, used)
