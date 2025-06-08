import pickle
import os
from datetime import datetime

class StorageManager:
    def __init__(self, data_dir="model_rts_1"):
        self.data_dir = data_dir
        self.word_pairs_file = "word_pairs.pkl"
        self.model_weights_file = "model_weights.pkl"
        self.constants_file = "constants.pkl"
        self.training_file = "training.pkl"
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Create storage directory and initialize default data files"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            self._initialize_default_data()
    
    def _initialize_default_data(self):
        """Set up default data structures"""
        self.save_word_pairs({})
        self.save_model_weights({
            'wordnet_base': 0.4,
            'bert_base': 0.4,
            'user_feedback': 0.2,
            'sentence_context': 0.2,
            'learning_rate': 0.01,
            'active': True,
            'created_at': datetime.now(),
            'training_iterations': 0,
            'correct_predictions': 0,
            'total_predictions': 0
        })
        
    def _get_file_path(self, filename):
        return os.path.join(self.data_dir, filename)
    
    def load_word_pairs(self):
        try:
            with open(self._get_file_path(self.word_pairs_file), 'rb') as f:
                return pickle.load(f)
        except:
            return {}
    
    def save_word_pairs(self, pairs):
        with open(self._get_file_path(self.word_pairs_file), 'wb') as f:
            pickle.dump(pairs, f)
    
    def load_model_weights(self):
        try:
            with open(self._get_file_path(self.model_weights_file), 'rb') as f:
                return pickle.load(f)
        except:
            return None
            
    def save_model_weights(self, weights):
        with open(self._get_file_path(self.model_weights_file), 'wb') as f:
            pickle.dump(weights, f)
    
    def add_word_pair(self, word1, word2, rating=None, sentence=None):
        pairs = self.load_word_pairs()
        key = f"{word1.lower()}-{word2.lower()}"
        
        if key not in pairs:
            pairs[key] = {
                'word1': word1.lower(),
                'word2': word2.lower(),
                'ratings': [],
                'sentences': [],
                'created_at': datetime.now()
            }
        
        if rating is not None:
            pairs[key]['ratings'].append({
                'rating': rating,
                'timestamp': datetime.now()
            })
            
        if sentence:
            pairs[key]['sentences'].append({
                'text': sentence,
                'timestamp': datetime.now()
            })
            
        self.save_word_pairs(pairs)