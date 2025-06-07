PLAYER_THRESHOLD = 0.20       # similarity threshold for player's words
AI_THRESHOLD = 0.90           # similarity for AI's words
SIMILARITY_THRESHOLD = 0.2    # base similarity threshold
SISTER_TERM_THRESHOLD = 0.5   # minimum similarity for sister terms
MAX_RELATED_WORDS = 25        # max words to consider
MAX_HYPONYMS = 20             # max hyponyms
MAX_HYPERNYMS = 10            # max hypernyms
MAX_SISTERS = 3               # max sister terms per parent
MAX_SYNONYMS = 5              # max synonyms

class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.last_word = None
        self.last_reason = None
        self.last_similarity = None
        self.word_history = set()
    
    def add_word(self, word):
        word = word.lower()
        if word in self.word_history:
            return False
        self.word_history.add(word)
        return True