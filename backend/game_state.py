from scorer_wordnet import WordNetScorer
from scorer_bert import BertScorer
from scorer_combined import CombinedScorer
from config_constants import PLAYER_THRESHOLD

class GameState:
    def __init__(self, scorer_type="combined"):
        self.scorer_type = scorer_type
        self.scorer = self._initialize_scorer(scorer_type)
        self.reset()
    
    def _initialize_scorer(self, scorer_type):
        if scorer_type == "wordnet":
            return WordNetScorer()
        elif scorer_type == "bert":
            return BertScorer()
        return CombinedScorer()
    
    def reset(self):
        self.last_word = None
        self.last_reason = None
        self.last_similarity = None
        self.word_history = set()
        self.player_similarity_threshold = PLAYER_THRESHOLD
    
    def add_word(self, word):
        word = word.lower()
        if word in self.word_history:
            return False
        self.word_history.add(word)
        return True