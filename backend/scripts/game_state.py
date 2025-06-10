from .scorer_wordnet import WordNetScorer
from .scorer_trainable import TrainableScorer
from .config_constants import PLAYER_THRESHOLD, get_constant

class GameState:
    def __init__(self):
        self.reset()
        active_model = get_constant('ACTIVE_MODEL')
        self.scorer_type = active_model
        self.scorer = self._initialize_scorer(active_model)
    
    def _initialize_scorer(self, scorer_type):
        if scorer_type == "trained":
            return TrainableScorer()
        return WordNetScorer()
    
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