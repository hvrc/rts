import os
import pickle
from datetime import datetime

class StorageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StorageManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self, data_dir="model_rts_1"):
        self.data_dir = data_dir
        self.collections = {}
        
        # Initialize storage directory
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            self._initialize_default_data()
    
    def _initialize_default_data(self):
        """Set up default data structures"""
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
        return os.path.join(self.data_dir, f"{name}.pkl")
    
    def _load_data(self, name):
        try:
            with open(self._get_file_path(name), 'rb') as f:
                return pickle.load(f)
        except:
            return {}
    
    def _save_data(self, name, data):
        with open(self._get_file_path(name), 'wb') as f:
            pickle.dump(data, f)
    
    def find_one(self, collection, query):
        data = self._load_data(collection)
        key, value = next(iter(query.items()))
        return next((item for item in data.values() if item.get(key) == value), None)
    
    def update_one(self, collection, query, update, upsert=False):
        data = self._load_data(collection)
        key, value = next(iter(query.items()))
        item = next((item for item in data.values() if item.get(key) == value), None)
        
        if item is None and upsert:
            doc_id = str(len(data) + 1)
            item = query.copy()
            item.update(update.get('$set', {}))
            data[doc_id] = item
        elif item is not None:
            item.update(update.get('$set', {}))
            
        self._save_data(collection, data)
    
    def insert_one(self, collection, document):
        data = self._load_data(collection)
        doc_id = str(len(data) + 1)
        document['_id'] = doc_id
        data[doc_id] = document
        self._save_data(collection, data)
    
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

storage_manager = StorageManager()
word_pairs = storage_manager
training_sentences = storage_manager
model_weights = storage_manager
training_history = storage_manager
constants = storage_manager