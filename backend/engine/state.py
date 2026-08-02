"""Game state.

Today the server only ever asks for one game (SOLO_ID) — the app is a single-player
toy. But state is keyed by game id and held in a store, so adding multiplayer means
passing a real id from the route and giving Game a player list. Nothing else in the
engine has to change.

In-memory only: an App Engine instance recycle wipes every game. That's fine for a
toy; a real multiplayer build swaps GameStore for something durable (Redis, Firestore)
without touching the callers.
"""

from .history import History
from .rules import LetterRule

SOLO_ID = "solo"

# How many past messages ride along in the prompt. The bot needs enough to see what it
# just said and what it was asked; it does not need the whole session. Capped because
# this is resent on every turn.
TRANSCRIPT_WINDOW = 40


class Game:
    """One game's worth of state.

    The split that matters is board vs history. The board — chain, spent words, whose
    turn — is the game, and it's wiped whenever one ends. The history is the session: what
    was said, what happened, what was argued over. That doesn't restart just because a
    game did. The human can still see the last twenty messages on screen, so the bot has
    to remember them too, and a score kept across three games is only a score if it
    survives all three.
    """

    def __init__(self, reverse=False, history=None):
        self.chain = []                     # ordered words played, both sides
        self.used = set()                   # lowercased words already spent
        self.last_word = None               # the word the next move must relate to
        self.rule = LetterRule(reverse)     # normal or reversed letter rule
        self.history = history or History() # transcript, events, links — outlives resets
        self.pending = None                 # a question nobody has answered yet

    @property
    def transcript(self):
        return self.history.transcript

    def add(self, word):
        w = word.lower()
        self.chain.append(w)
        self.used.add(w)
        self.last_word = w

    def remember(self, role, text):
        """Append to the conversation. `role` is "user" or "assistant"."""
        text = (text or "").strip()
        if not text:
            return
        self.transcript.append((role, text))
        del self.transcript[:-TRANSCRIPT_WINDOW]

    def set_reverse(self, reverse):
        """Flip the letter rule mid-game.

        The chain survives — already-played words stay played, and the new rule only
        governs words from here on. That's the intended behavior: flipping the rule is
        a twist, not a restart.
        """
        self.rule = LetterRule(reverse)


class GameStore:
    def __init__(self):
        self._games = {}

    def get(self, game_id=SOLO_ID, reverse=False):
        if game_id not in self._games:
            self._games[game_id] = Game(reverse)
        return self._games[game_id]

    def reset(self, game_id=SOLO_ID, reverse=False):
        """Wipe the board, keep the history.

        A loss or a restart clears the chain, but the two of them are still talking and
        the messages are still on screen. Carrying the history over is what stops the bot
        answering "why did you say owl?" with "what owl?" one turn after a new game began
        — and it's what makes a score across several games mean anything.
        """
        previous = self._games.get(game_id)
        self._games[game_id] = Game(
            reverse, history=previous.history if previous else None
        )
        return self._games[game_id]


GAMES = GameStore()
