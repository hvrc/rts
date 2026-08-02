"""What outlives a game.

A game is a board: a chain, a set of spent words, whose turn it is. It gets wiped
constantly - every loss, every restart. The conversation around it doesn't. The two
players are still talking, the messages are still on screen, and what happened three
games ago still counts.

So this holds the durable half: what was said, what happened, and which links were
argued over. `Game` keeps the board and hands this object to its successor.

Everything derived - score, how much the bot should trust a justification - is a
projection over `events` rather than a counter kept alongside it. That's deliberate.
Counters have to be updated correctly at every call site and they rot the moment the rule
changes; a projection is a pure function you can rewrite in one place. Scoring rules here
are expected to change, so nothing downstream should depend on how they're computed today.
"""

# --- what can happen -------------------------------------------------------------

MOVE = "move"                      # a word was played and accepted
RULE_BREAK = "rule_break"          # started with a banned letter
REPEAT = "repeat"                  # word already in the chain
CHALLENGED = "challenged"          # somebody asked "how?" - costs nothing, see below
DEFENDED = "defended"              # they answered the challenge
JUSTIFIED = "justified"            # ...and the answer landed
REJECTED = "rejected"              # ...and it didn't
ON_FAITH = "on_faith"              # accepted without seeing it. counted, quietly
CONCEDED = "conceded"              # gave up the round

# Why a round was given up. Asking is free and arguing is free; dropping the argument is
# what costs you. ABANDONED covers the silent version - a live challenge against your word
# and you play something new instead of answering it.
EXPLICIT = "explicit"              # "ok you got me"
ABANDONED = "abandoned_challenge"  # walked away from an open question
RESTARTED = "requested_restart"    # asked for a new word instead of finishing this one


class Event:
    __slots__ = ("kind", "player", "word", "reason")

    def __init__(self, kind, player, word=None, reason=None):
        self.kind = kind
        self.player = player          # "human" or "bot" - the one it happened TO
        self.word = word
        self.reason = reason

    def __repr__(self):
        bits = [self.kind, self.player]
        if self.word:
            bits.append(repr(self.word))
        if self.reason:
            bits.append(self.reason)
        return f"<{' '.join(bits)}>"


class Link:
    """One step in a chain, and the argument about it.

    The justification matters as much as the words. Without it, "how?" asked three turns
    later gets answered by inventing a fresh reason, which is how the bot ended up giving
    two different explanations for the same move.
    """

    __slots__ = ("frm", "to", "by", "why", "status")

    def __init__(self, frm, to, by, why=None, status="asserted"):
        self.frm = frm
        self.to = to
        self.by = by                  # who played `to`
        self.why = why                # the reason given at the time, if one ever was
        self.status = status          # asserted | questioned | accepted | on_faith | rejected

    def __repr__(self):
        return f"<{self.frm}->{self.to} by {self.by} [{self.status}]>"


class Pending:
    """An open question. Somebody asked, nobody has answered yet.

    This is what makes the conversation able to wander without losing the thread: while
    it's set, the next message is read as an answer to *this*, not as a fresh move.
    """

    __slots__ = ("word", "frm", "asked_by")

    def __init__(self, word, frm, asked_by):
        self.word = word              # the word being questioned
        self.frm = frm                # the word it was supposed to connect to
        self.asked_by = asked_by

    def __repr__(self):
        return f"<{self.asked_by} asked: {self.frm}->{self.word}>"


class History:
    """The durable half of a session. Survives every reset the board doesn't."""

    def __init__(self):
        self.transcript = []          # [(role, text)] - what was said
        self.events = []              # [Event]        - what happened
        self.links = []               # [Link]         - what was argued over

        # Every question the bot has asked, verbatim. Kept because telling a model to
        # "vary your phrasing" does almost nothing - it has a strong prior for one shape
        # and reaches for it every time, swapping a synonym in when the shape is banned.
        # Showing it what it actually said works where the instruction didn't.
        self.asks = []

    def record(self, kind, player, word=None, reason=None):
        self.events.append(Event(kind, player, word, reason))

    def link(self, frm, to, by, why=None, status="asserted"):
        self.links.append(Link(frm, to, by, why, status))
        return self.links[-1]

    def find_link(self, to):
        """The most recent link that landed on this word. Used to answer "how?" from what
        was actually said, rather than inventing a reason after the fact."""
        for link in reversed(self.links):
            if link.to == to:
                return link
        return None


# --- projections -----------------------------------------------------------------

def score(history, player):
    """Rounds lost, and why. Nobody is shown this unless they ask for it.

    A round is lost by giving it up - saying so, or walking away from an open question,
    or asking for a fresh word rather than finishing the one you're on. Asking and
    arguing are free, and deliberately so: questioning is how the game is played, and
    charging for it would teach people not to.
    """
    lost = [e for e in history.events if e.kind == CONCEDED and e.player == player]
    return {
        "lost": len(lost),
        "gave_up": sum(1 for e in lost if e.reason == EXPLICIT),
        "walked_away": sum(1 for e in lost if e.reason == ABANDONED),
        "restarted": sum(1 for e in lost if e.reason == RESTARTED),
        "rule_breaks": _count(history, RULE_BREAK, player),
        "repeats": _count(history, REPEAT, player),
    }


def track_record(history, player="human"):
    """How this player's arguments have been going.

    Feeds the bot's read on a thin justification. Note what it counts and what it doesn't:
    challenges *raised* are not held against anyone, because playing a word the bot hasn't
    met is normal and the whole point. What counts is arguments that were made and didn't
    hold - and, quietly, links accepted without ever really being seen.
    """
    return {
        "moves": _count(history, MOVE, player),
        "challenged": _count(history, CHALLENGED, player),
        "held_up": _count(history, JUSTIFIED, player),
        "fell_over": _count(history, REJECTED, player),
        "on_faith": _count(history, ON_FAITH, player),
    }


def describe_track_record(history, player="human"):
    """The track record as a line for the prompt, or "" when there's nothing to say.

    Prose rather than a number on purpose. A number invites the model to treat it as a
    threshold and start refusing things at 0.7; a description is read as what it is - a
    prior about how the arguing has gone, not a rule about what to accept.
    """
    r = track_record(history, player)
    if r["fell_over"] == 0 and r["on_faith"] == 0:
        return ""

    bits = []
    if r["fell_over"]:
        bits.append(
            f"{r['fell_over']} of their explanations this session didn't hold up"
        )
    if r["on_faith"]:
        bits.append(f"you took {r['on_faith']} of their links on faith without seeing it")
    if r["held_up"]:
        bits.append(f"{r['held_up']} did hold up")

    return (
        ", ".join(bits)
        + ". Worth a closer read of the next explanation - but this is about their "
          "arguments, not their words. An unfamiliar word is still just an unfamiliar "
          "word."
    )


def _count(history, kind, player):
    return sum(1 for e in history.events if e.kind == kind and e.player == player)
