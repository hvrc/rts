"""Game state.

Today the server only ever asks for one game (SOLO_ID) — the app is a single-player
toy. But state is keyed by game id and held in a store, so adding multiplayer means
passing a real id from the route and giving Game a player list. Nothing else in the
engine has to change.

In-memory only: an App Engine instance recycle wipes every game. That's fine for a
toy; a real multiplayer build swaps GameStore for something durable (Redis, Firestore)
without touching the callers.
"""

from .rules import LetterRule

SOLO_ID = "solo"


class Game:
    """One game's worth of state."""

    def __init__(self, reverse=False):
        self.chain = []                     # ordered words played, both sides
        self.used = set()                   # lowercased words already spent
        self.last_word = None               # the word the next move must relate to
        self.rule = LetterRule(reverse)     # normal or reversed letter rule

    def add(self, word):
        w = word.lower()
        self.chain.append(w)
        self.used.add(w)
        self.last_word = w

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
        self._games[game_id] = Game(reverse)
        return self._games[game_id]


GAMES = GameStore()
