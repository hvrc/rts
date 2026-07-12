"""Prompt loading.

No prompt text lives in Python. Everything the model reads is in prompts/*.md — edit
those files to change how the AI plays, and nothing else needs to be touched.

  prompts/system.md              the whole brain, with a {{LETTER_RULE}} placeholder
  prompts/letter_rule.normal.md  r/t/s are banned
  prompts/letter_rule.reverse.md r/t/s are the only legal openers

Files are read on every call, so editing a prompt during local dev takes effect on the
next turn without a restart. They're small; the cost is nothing.
"""

from pathlib import Path

_DIR = Path(__file__).parent / "prompts"


def _read(name):
    return (_DIR / name).read_text(encoding="utf-8").strip()


def system_prompt(rule):
    """The full system prompt, with the active letter rule spliced in."""
    block = _read("letter_rule.reverse.md" if rule.reverse else "letter_rule.normal.md")
    return _read("system.md").replace("{{LETTER_RULE}}", block)


def turn_message(game, player_input, correction=None):
    """The per-turn user message: the state of the board plus what the human said."""
    lines = [
        "Chain so far: "
        + (" -> ".join(game.chain) if game.chain else "(empty — this is the first move)"),
        "Words already used: "
        + (", ".join(sorted(game.used)) if game.used else "(none)"),
        "The human must connect to: "
        + (game.last_word or "(nothing yet — any legal real word is fine)"),
        f'The human just said: "{player_input}"',
    ]
    if correction:
        lines.append(
            f"NOTE: your previous attempt was rejected ({correction}). Pick a different "
            "legal word, or CONCEDE if you're truly cornered."
        )
    lines.append("Reply with the structured output only.")
    return "\n".join(lines)
