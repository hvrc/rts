"""What can be known about a message without asking a model.

Everything here is free, instant and certain - the shape of the text, not what it means.
It feeds the prompt as observations rather than conclusions, and that distinction is the
whole point of the module.

An earlier version of this idea *overrode* the model: any one-word message was forced to
be a move. It was right often enough to look reasonable and wrong in exactly the cases
that mattered, because "bro" opening a game and "what" answering a question are the same
shape and only context separates them. Deciding from shape alone can't work. Pointing out
the shape and leaving the decision alone can.

So: no rules here, no vetoes. Just things worth noticing.
"""

import re

# Words that are almost never a move. Not a blocklist - the model still decides, and
# "no" genuinely is a word someone could play. But when one of these arrives with a
# question already open, it is answering the question roughly always, and saying so out
# loud costs nothing.
CHATTER = {
    "what", "wat", "huh", "eh", "why", "how", "when", "where", "who",
    "no", "nope", "nah", "yes", "yeah", "yep", "yup", "ok", "okay", "k",
    "lol", "lmao", "haha", "hmm", "hm", "oh", "ah", "ohh", "wow", "damn",
    "wait", "hold", "stop", "bye", "hi", "hey", "yo", "sup", "thanks", "ty",
    "sure", "fine", "really", "seriously", "idk", "wdym", "wym",
}

_BARE_WORD = re.compile(r"[A-Za-z]+")
_QUESTIONISH = re.compile(
    r"^(what|why|how|who|when|where|which|is|are|do|does|did|can|could|would|will|"
    r"should|explain|tell)\b", re.I
)


def observe(text, pending=None):
    """Notes on a message, or "" when there's nothing worth saying.

    Deliberately quiet. A plain word on a plain turn produces nothing at all - the model
    doesn't need to be told that a word looks like a word, and a prompt that comments on
    every turn trains it to stop reading the comments.
    """
    text = (text or "").strip()
    if not text:
        return ""

    notes = []
    bare = _BARE_WORD.fullmatch(text)
    low = text.lower().rstrip("?!.")

    if bare and low in CHATTER:
        notes.append(
            f'"{text}" is one of those words people say rather than play. It can be a '
            "move, but usually it is them talking to you"
            + (" - and with a question of yours open, it is almost certainly their answer"
               if pending else "")
        )
    elif not bare and pending and _QUESTIONISH.match(text):
        notes.append("that reads as a question back at you, not as an answer to yours")

    if text.endswith("?"):
        notes.append("they ended on a question mark")

    if len(text.split()) > 12:
        notes.append("that's a long message - likely an argument or an aside, not a word")

    return "; ".join(notes)


def is_bare_word(text):
    return bool(_BARE_WORD.fullmatch((text or "").strip()))
