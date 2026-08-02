"""Prompt assembly.

No prompt text lives in Python. Everything the model reads is in prompts/*.md — edit
those to change how the bot plays, and nothing here needs to be touched.

  prompts/identity.md      who the bot is. persona and epistemics. no rules.
  prompts/game.md          what RTS is, plus the {{LETTER_RULE}} slot and the name lore
  prompts/judging.md       how to think about relatedness
  prompts/conversation.md  reading the human, turn-taking, requests
  prompts/letter_rule.*.md the active letter rule, spliced into game.md

The split is by *concern*, so the voice can change without touching the rules and the
rules can change without touching the voice. It also happens to order the prompt by rate
of change, which is what makes it cacheable: identity and rules are fixed for the whole
session and sit in `system`, while everything that moves per turn rides at the end of the
last user message, where it can't invalidate the cached prefix.

Files are read on every call so edits during local dev take effect on the next turn
without a restart. They're small; the cost is nothing.
"""

from pathlib import Path

_DIR = Path(__file__).parent / "prompts"

# Order matters: who you are, then what the game is, then how to judge, then how to talk.
_LAYERS = ("identity.md", "game.md", "judging.md", "conversation.md")


def _read(name):
    return (_DIR / name).read_text(encoding="utf-8").strip()


def system_prompt(rule):
    """The full system prompt, with the active letter rule spliced in.

    Stable for the whole session — nothing per-turn belongs in here.
    """
    rule_block = _read("letter_rule.reverse.md" if rule.reverse else "letter_rule.normal.md")
    return "\n\n".join(_read(name) for name in _LAYERS).replace(
        "{{LETTER_RULE}}", rule_block
    )


def messages(game, player_input, correction=None, preferences=None):
    """The conversation, as the model should see it.

    Real message history, rather than a synthesised description of it. Without this the
    bot reads every message cold, and "what" arriving after one of its own questions looks
    identical to "what" opening a game — which is exactly how a bare "what" ends up played
    as a move.

    The board rides in the final user message rather than the system prompt: it changes
    every turn, so in the prefix it would invalidate the cache on every request, and it
    belongs next to the message it describes anyway.
    """
    out = [{"role": role, "content": text} for role, text in game.transcript]
    out.append({
        "role": "user",
        "content": _turn_block(game, player_input, correction, preferences),
    })
    return out


def _turn_block(game, player_input, correction=None, preferences=None):
    lines = [
        "<board>",
        "chain: " + (" -> ".join(game.chain) if game.chain
                     else "(empty — nothing played yet this game)"),
        "already played, cannot be replayed: "
        + (", ".join(sorted(game.used)) if game.used else "(nothing)"),
        "they must connect to: "
        + (game.last_word or "(nothing yet — any legal word opens)"),
        "</board>",
    ]

    taste = preferences.as_prompt_block() if preferences else ""
    if taste:
        lines += ["", "<their_taste>", taste, "</their_taste>"]

    lines += ["", f'they just said: "{player_input}"']

    if correction:
        lines += ["", f"NOTE: {correction}"]

    return "\n".join(lines)
