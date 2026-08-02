"""Prompt assembly.

No prompt text lives in Python. Everything the model reads is in prompts/*.md - edit
those to change how the bot plays, and nothing here needs to be touched.

  prompts/identity.md      who the bot is. persona and epistemics. no rules.
  prompts/game.md          what RTS is, plus the {{LETTER_RULE}} slot and the name lore
  prompts/judging.md       how to think about relatedness
  prompts/language.md      playing across languages, and why a translation isn't a move
  prompts/conversation.md  reading the human, turn-taking, requests
  prompts/room.md          appended only in a room: names, seats, staying out of the way
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

from . import history, reading

_DIR = Path(__file__).parent / "prompts"

# Order matters: who you are, then what the game is, then how to judge, then how to talk.
_LAYERS = ("identity.md", "game.md", "judging.md", "language.md", "conversation.md")


def _read(name):
    return (_DIR / name).read_text(encoding="utf-8").strip()


def system_prompt(rule, room=False):
    """The full system prompt, with the active letter rule spliced in.

    Stable for the whole session - nothing per-turn belongs in here. The room layer is
    appended rather than interleaved so that solo play's prefix is byte-identical to
    what it was, and a room's prefix is stable for as long as the room lasts. Either
    way the cache sees one fixed string.
    """
    rule_block = _read("letter_rule.reverse.md" if rule.reverse else "letter_rule.normal.md")
    layers = _LAYERS + (("room.md",) if room else ())
    return "\n\n".join(_read(name) for name in layers).replace(
        "{{LETTER_RULE}}", rule_block
    )


def messages(game, player_input, correction=None, preferences=None, room=None):
    """The conversation, as the model should see it.

    Real message history, rather than a synthesised description of it. Without this the
    bot reads every message cold, and "what" arriving after one of its own questions looks
    identical to "what" opening a game - which is exactly how a bare "what" ends up played
    as a move.

    The board rides in the final user message rather than the system prompt: it changes
    every turn, so in the prefix it would invalidate the cache on every request, and it
    belongs next to the message it describes anyway.
    """
    out = [{"role": role, "content": text} for role, text in game.transcript]
    out.append({
        "role": "user",
        "content": _turn_block(game, player_input, correction, preferences, room),
    })
    return out


def _turn_block(game, player_input, correction=None, preferences=None, room=None):
    lines = []

    # Who is here, and whose go it is. First, because in a room it's the thing that
    # decides whether this message is even addressed to you.
    if room is not None:
        here = ", ".join(f"{name}{' (you)' if is_bot else ''}"
                         for name, is_bot in room.seated())
        lines += [
            "<room>",
            f"room: {room.name}",
            f"here: {here or '(just you)'}",
            f"whose turn: {room.named(room.turn)}"
            + (" - that's you" if room.bot_turn else ""),
            "</room>",
            "",
        ]

    lines += [
        "<board>",
        "chain: " + (" -> ".join(game.chain) if game.chain
                     else "(empty - nothing played yet this game)"),
        "already played, cannot be replayed: "
        + (", ".join(sorted(game.used)) if game.used else "(nothing)"),
        # Worded neutrally on purpose. This block is resent every single turn, so any
        # phrasing in it becomes the phrasing the bot reaches for - "they must connect to"
        # was priming a stock question ("X? how's that connect to Y") that no amount of
        # telling it to vary could shift.
        "word in play: "
        + (game.last_word or "(nothing yet - any legal word opens)"),
        "</board>",
    ]

    # An open question changes how the next message reads. Without this the bot asks
    # "how?", gets an answer, and has no idea the answer is an answer.
    if game.pending:
        p = game.pending
        lines += [
            "",
            "<open_question>",
            f"you asked how {p.word!r} connects to {p.frm!r} and they haven't settled it "
            "yet. Read what they just said as their answer to that.",
            "If they've argued for it, judge the argument. If they've dropped it and "
            "played something else instead, that's them giving up the round - take the "
            "new word and move on without making a thing of it.",
            "</open_question>",
        ]

    # Shown rather than described, because being told to vary the phrasing doesn't work -
    # the same sentence comes back with one word swapped. Seeing the actual repetition does.
    asked = game.history.asks[-4:]
    if asked:
        lines += [
            "",
            "<questions_you_have_already_asked>",
            *(f"  {a}" for a in asked),
            "Read those back. If they're the same sentence with the words changed, you're "
            "handing them a form to fill in rather than asking anything. Ask the next one "
            "some other way entirely.",
            "</questions_you_have_already_asked>",
        ]

    record = history.describe_track_record(game.history, "human")
    if record:
        lines += ["", "<how_their_arguments_have_gone>", record,
                  "</how_their_arguments_have_gone>"]

    taste = preferences.as_prompt_block() if preferences else ""
    if taste:
        lines += ["", "<their_taste>", taste, "</their_taste>"]

    if player_input:
        lines += ["", f'they just said: "{player_input}"']

        # Observations, not instructions. The last thing that read the shape of a
        # message decided from it, and forced any single word to be a move - right
        # often enough to look fine, wrong exactly where it mattered. Noticing is
        # safe; concluding wasn't.
        noticed = reading.observe(player_input, game.pending)
        if noticed:
            lines += ["", f"(worth noticing: {noticed}. Your call either way.)"]
    else:
        # A room's turn, where several people may have spoken since the bot's last go.
        # There is no single "they" to quote, and picking the most recent speaker would
        # aim the answer at whoever happened to type last rather than at the board.
        lines += ["", "it's your turn. Play a word off the one in play."]

    if correction:
        lines += ["", f"NOTE: {correction}"]

    return "\n".join(lines)
