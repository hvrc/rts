"""One turn of RTS.

The shape of a turn, and the only place the pieces meet:

  1. deterministic pre-checks   — free, reliable, never wrong (rules.py)
  2. ask the brain              — one structured call (providers/)
  3. deterministic post-checks  — the AI must obey the rules too; one retry, else concede
  4. advance the game           — (state.py) and shape the reply (contract.py)

Steps 1 and 3 exist because the letter rule and duplicate detection must be 100%
reliable and a model is not. Everything else is the model's job.
"""

from . import contract, prompts, rules
from .providers import TurnContext, get_provider
from .state import GAMES, SOLO_ID


def play(player_input, game_id=SOLO_ID, reverse=False):
    """Handle one /echo turn. Returns the frozen contract dict."""
    game = GAMES.get(game_id)

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
            return contract.contract("RTS", rule.violation_message)
        if rules.is_variation(word, game.used):
            return contract.contract("DUPLICATE", f"{word}? already been there")

    # The human's word isn't committed to game.used until step 4, so hold the set the
    # AI must actually avoid: everything used, plus the word the human just played.
    # Without this the AI can echo the human's word straight back and the duplicate
    # check won't see it.
    spent = game.used | {text.lower()}

    # --- 2. ask the brain ---
    try:
        data = _ask(game, text, spent=spent)
    except Exception as e:
        return contract.error(e)                    # frontend already renders "?" on ERROR

    code = data.get("response_code", "INVALID")
    reply = (data.get("response") or "").strip()

    # --- 3. deterministic post-checks on the AI's own word ---
    if code == "OK":
        chosen = _clean(data.get("chosen_word"))

        if not _legal(chosen, rule, spent):
            try:
                data = _ask(game, text, correction="you played an illegal or repeated word",
                            spent=spent)
            except Exception as e:
                return contract.error(e)
            code = data.get("response_code", "CONCEDE")
            reply = (data.get("response") or "ok, you got me").strip()
            chosen = _clean(data.get("chosen_word"))

            if code == "OK" and not _legal(chosen, rule, spent):
                # Still illegal after a retry — concede rather than break a rule.
                return contract.contract("CONCEDE", "ok, you got me")

        # --- 4. legal both ways: advance the chain ---
        if code == "OK":
            game.add(text.lower())
            game.add(chosen)
            tot = contract.clean_train_of_thought(
                data.get("train_of_thought", []), chosen, rule
            )
            return contract.contract("OK", reply or chosen, tot)

    # Non-advancing codes: UNRELATED / DUPLICATE / INVALID / CHAT / CONCEDE.
    return contract.contract(code, reply or "?", [])


def reset(game_id=SOLO_ID, reverse=False):
    """Handle /reset. Clears the game, keeping whichever rule the client is on."""
    GAMES.reset(game_id, reverse)
    return {"response": "new game", "train_of_thought": []}


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------
def _ask(game, player_input, correction=None, spent=None):
    # `spent` = used words plus the human's pending word, so a provider can avoid
    # echoing it back rather than being caught by the post-check.
    ctx = TurnContext(game.rule, spent or game.used, game.chain, game.last_word)
    return get_provider().move(
        prompts.system_prompt(game.rule),
        prompts.turn_message(game, player_input, correction),
        ctx,
    )


def _clean(word):
    return (word or "").strip().lower()


def _legal(word, rule, used):
    return bool(word) and rule.allows(word) and not rules.is_variation(word, used)
