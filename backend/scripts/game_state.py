from datetime import datetime
from .scorer_wordnet import WordNetScorer
from .scorer_trainable import TrainableScorer
from .config_constants import PLAYER_THRESHOLD, get_constant

class WordEntry:
    def __init__(self, word, sender, index):
        self.word = word.lower()
        self.sender = sender
        self.index = index
        self.timestamp = datetime.now()
        self.previous_entry = None
        self.next_entry = None
    
    def get_previous_word(self):
        return self.previous_entry.word if self.previous_entry else None
    
    def get_next_word(self):
        return self.next_entry.word if self.next_entry else None
    
    def get_previous_entry(self):
        return self.previous_entry
    
    def get_next_entry(self):
        return self.next_entry
    
    def to_dict(self):
        return {
            'word': self.word,
            'sender': self.sender,
            'index': self.index,
            'timestamp': self.timestamp.isoformat(),
            'previous_word': self.get_previous_word(),
            'next_word': self.get_next_word()
        }

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
        self.word_history = []        # ordered list of WordEntry objects
        self.word_index = {}          # map word -> list of WordEntry objects
        self.user_words = set()       # set of words used by user, no duplicates
        self.last_entry = None        # reference to last added WordEntry
        self.conversation_count = 0   # index counter for conversation
        self.debug_enabled = True
        self.player_similarity_threshold = PLAYER_THRESHOLD
    
    def add_word(self, word, sender='user'):
        word = word.lower()
        
        # check for user word duplicates only
        if sender == 'user':
            if word in self.user_words:
                return False

            self.user_words.add(word)
        
        # create new word entry
        entry = WordEntry(word, sender, self.conversation_count)
        
        # link to previous entry
        if self.last_entry:
            self.last_entry.next_entry = entry
            entry.previous_entry = self.last_entry
        
        # add to history and index
        self.word_history.append(entry)

        if word not in self.word_index:
            self.word_index[word] = []

        self.word_index[word].append(entry)
        
        # update references
        self.last_entry = entry
        self.conversation_count += 1
        
        return True
    
    def get_word_entries(self, word):
        return self.word_index.get(word.lower(), [])
    
    def get_entry_by_index(self, index):
        if 0 <= index < len(self.word_history):
            return self.word_history[index]
        return None
    
    def get_last_entry(self, sender=None):
        if not self.word_history:
            return None
        
        if sender is None:
            return self.last_entry
        
        # search backwards for last entry from specific sender
        for entry in reversed(self.word_history):
            if entry.sender == sender:
                return entry
        return None
    
    def get_last_word(self, sender=None):
        entry = self.get_last_entry(sender)
        return entry.word if entry else None
    
    def get_word_pair_from_entry(self, entry):
        if entry and entry.previous_entry:
            return (entry.previous_entry.word, entry.word)
        return None
    
    def get_conversation_history(self, limit=None):
        history = [entry.to_dict() for entry in self.word_history]
        if limit: return history[-limit:]
        return history
    
    def find_word_context(self, word, occurrence=1):
        entries = self.get_word_entries(word)
        if len(entries) >= occurrence:
            entry = entries[occurrence - 1]
            return {
                'entry': entry,
                'previous_word': entry.get_previous_word(),
                'next_word': entry.get_next_word(),
                'previous_entry': entry.get_previous_entry(),
                'next_entry': entry.get_next_entry()
            }
        return None
    
    def get_current_pair(self):
        if len(self.word_history) >= 2:
            last_entry = self.word_history[-1]
            prev_entry = self.word_history[-2]
            return (prev_entry.word, last_entry.word)
        return None
    
    # def _debug(self, message):
    #     if self.debug_enabled:
    #         print(f"[GameState] {message}")

    # def _debug_conversation_state(self):
    #     if self.debug_enabled and self.word_history:
    #         last_3 = self.word_history[-3:] if len(self.word_history) >= 3 else self.word_history
    #         conversation = " -> ".join([f"{e.word}({e.sender})" for e in last_3])
    #         print(f"[GameState] last conversation: {conversation}")