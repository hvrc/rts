"""The rules of RTS, as deterministic code.

These are the checks that must be 100% reliable, so they never go near a model.
Everything the model *is* trusted with (relatedness, banter, strategy) lives in the
prompt instead.

Add a new rule by writing a class with the same shape and wiring it into turn.py.
"""

import difflib
import re
import unicodedata

RTS_LETTERS = ("r", "t", "s")


def first_letter(word):
    """The letter a word starts with, with any accent taken off it.

    "rêve" and "reve" start with the same letter, and a rule that couldn't see that
    would be trivially escapable by playing in a language that writes its accents
    down. NFD splits a character into its base plus its combining marks, so taking
    the first character of the decomposition is the unaccented letter.

    Words that don't start with a letter at all (quotes, digits) return "", which no
    rule matches - the letter rule has nothing to say about them.
    """
    stripped = unicodedata.normalize("NFD", (word or "").strip().lower())
    return stripped[:1] if stripped[:1].isalpha() else ""


class LetterRule:
    """The rule that names the game.

    normal   - a word may NOT start with r/t/s.
    reversed - a word may ONLY start with r/t/s.

    Same rule object governs the human's word, the AI's word, and every candidate in
    the train of thought, so the two modes can never drift apart.

    It governs every *language* too. "rue" is as illegal as "road": the constraint is
    what the game is named after, and letting it lapse in French would make switching
    language a way of leaving the game rather than a way of playing it.
    """

    def __init__(self, reverse=False):
        self.reverse = bool(reverse)

    def rejects(self, word):
        """True if this word loses the game under the rule currently in force."""
        starts_rts = first_letter(word) in RTS_LETTERS
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


# A move is one word. `[^\W\d_]` is "a letter in any alphabet" - the pattern has to
# survive leaving English, or "café" and "être" stop counting as words the moment
# somebody switches language. Internal apostrophes and hyphens are part of the word
# they sit inside ("l'eau", "sang-froid"), not a gap between two of them.
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")


def is_single_word(text):
    """A move is a single word. Anything else is chat, not a move."""
    return bool(_WORD.fullmatch((text or "").strip()))


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
