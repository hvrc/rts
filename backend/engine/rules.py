"""The rules of RTS, as deterministic code.

These are the checks that must be 100% reliable, so they never go near a model.
Everything the model *is* trusted with (relatedness, banter, strategy) lives in the
prompt instead.

Add a new rule by writing a class with the same shape and wiring it into turn.py.
"""

import difflib
import re

RTS_LETTERS = ("r", "t", "s")


class LetterRule:
    """The rule that names the game.

    normal   - a word may NOT start with r/t/s.
    reversed - a word may ONLY start with r/t/s.

    Same rule object governs the human's word, the AI's word, and every candidate in
    the train of thought, so the two modes can never drift apart.
    """

    def __init__(self, reverse=False):
        self.reverse = bool(reverse)

    def rejects(self, word):
        """True if this word loses the game under the rule currently in force."""
        starts_rts = (word or "")[:1].lower() in RTS_LETTERS
        return not starts_rts if self.reverse else starts_rts

    def allows(self, word):
        return not self.rejects(word)

    @property
    def violation_message(self):
        """What the bot says when the rule is broken."""
        return "rts only" if self.reverse else "rts"

    @property
    def name(self):
        return "reversed" if self.reverse else "normal"

    def allowed_letters(self):
        """The letters a legal word may start with, spelled out.

        Telling the model to "think harder" doesn't work - it fixates on the banned
        letters it already thought of (loud -> sound/siren/scream/shout, all "s") and
        concedes. Handing it the letters it CAN use turns a vague nudge into a concrete
        constraint it can actually search against.
        """
        if self.reverse:
            return list(RTS_LETTERS)
        return [c for c in "abcdefghijklmnopqrstuvwxyz" if c not in RTS_LETTERS]


def is_single_word(text):
    """A move is a single run of letters. Anything else is chat, not a move."""
    return bool(re.fullmatch(r"[A-Za-z]+", text or ""))


def looks_like_duplicate(word, used):
    """Would anyone actually call this word a repeat?

    A repeat is the SAME word, or a trivial variation of it - dog/dogs, run/running.
    Two *different* words that happen to mean similar things are not repeats: "win" and
    "victory" are two words, and both are legal.

    This exists as a veto over the model. Repeating is now a losing move, so a model
    that calls a synonym a duplicate ends the game on a perfectly legal play - which is
    exactly what it did. Duplicate detection is deterministic; the model doesn't get a
    vote it can't be trusted with.

    The similarity check catches irregulars the suffix rules miss (mouse/mice) while
    staying far below anything a synonym would score.
    """
    w = (word or "").lower()
    if is_variation(w, used):
        return True
    return any(difflib.SequenceMatcher(None, w, u).ratio() >= 0.85 for u in used)


def is_variation(word, used):
    """Cheap trivial-variation check (plural / simple tense) against used words.

    Not exhaustive - see looks_like_duplicate for the fuzzier backstop.
    """
    w = (word or "").lower()
    if w in used:
        return True
    for u in used:
        if w == u + "s" or u == w + "s":       # dog / dogs
            return True
        if w == u + "es" or u == w + "es":     # box / boxes
            return True
        if w == u + "ed" or u == w + "ed":     # jump / jumped
            return True
        if w == u + "ing" or u == w + "ing":   # run / running
            return True
    return False
