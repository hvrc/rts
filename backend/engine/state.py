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

# How many past messages ride along in the prompt. The bot needs enough to see what it
# just said and what it was asked; it does not need the whole session. Capped because
# this is resent on every turn.
TRANSCRIPT_WINDOW = 40


class Game:
    """One game's worth of state.

    The chain and the transcript are different things and get reset at different times.
    The chain is the game; it's wiped whenever a game ends. The transcript is the
    conversation, and conversations don't restart just because a game did — the human
    can still see the last twenty messages on screen, so the bot has to remember them too.
    """

    def __init__(self, reverse=False, transcript=None):
        self.chain = []                     # ordered words played, both sides
        self.used = set()                   # lowercased words already spent
        self.last_word = None               # the word the next move must relate to
        self.rule = LetterRule(reverse)     # normal or reversed letter rule
        self.transcript = list(transcript or [])   # [(role, text)] — survives a restart

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
        """Wipe the game, keep the conversation.

        A loss or a restart clears the board, but the two of them are still talking and
        the history is still on screen. Carrying the transcript over is what stops the bot
        answering "why did you say owl?" with "what owl?" one turn after a new game began.
        """
        previous = self._games.get(game_id)
        self._games[game_id] = Game(
            reverse, transcript=previous.transcript if previous else None
        )
        return self._games[game_id]


GAMES = GameStore()
