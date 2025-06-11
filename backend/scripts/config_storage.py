import os
import pickle
from datetime import datetime

try: from .config_constants import get_constant
except ImportError: from config_constants import get_constant

class StorageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StorageManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self, data_dir="model_rts_1"):     
        script_dir = os.path.dirname(os.path.dirname(__file__))
        self.data_dir = os.path.join(script_dir, data_dir)
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            self._initialize_default_data()
    
    def _initialize_default_data(self):        
        self.save_word_pairs({})
        self.save_model_weights({
            'wordnet_base': get_constant('INITIAL_WORDNET_BASE'),
            'user_feedback': get_constant('INITIAL_USER_FEEDBACK'),
            'sentence_context': get_constant('INITIAL_SENTENCE_CONTEXT'),
            'learning_rate': get_constant('INITIAL_LEARNING_RATE'),
            'active': get_constant('INITIAL_MODEL_ACTIVE'),
            'created_at': datetime.now(),
            'training_iterations': 0,
            'correct_predictions': 0,
            'total_predictions': 0
        })

    def _get_file_path(self, name):
        file_path = os.path.join(self.data_dir, f"{name}.pkl")
        return os.path.normpath(file_path)

    def _load_data(self, name):
        try:
            file_path = self._get_file_path(name)
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            return {}
    
    def _save_data(self, name, data):
        try:
            file_path = self._get_file_path(name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            raise
    
    def load_word_pairs(self):
        return self._load_data('word_pairs')
    
    def save_word_pairs(self, pairs):
        self._save_data('word_pairs', pairs)
    
    def load_model_weights(self):
        return self._load_data('model_weights')
    
    def save_model_weights(self, weights):
        self._save_data('model_weights', weights)
    
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