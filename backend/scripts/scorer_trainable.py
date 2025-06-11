from .config_storage import StorageManager
import numpy as np
from datetime import datetime

class TrainableScorer:
    def __init__(self):
        self.storage = StorageManager()
        self.weights = self._load_or_create_weights()
    
    def _load_or_create_weights(self):
        weights = self.storage.load_model_weights()
        return weights

    def get_learned_score(self, word1, word2):
        pairs = self.storage.load_word_pairs()
        key = f"{word1.lower()}-{word2.lower()}"
        alt_key = f"{word2.lower()}-{word1.lower()}"
        
        pair = pairs.get(key) or pairs.get(alt_key)
        if not pair:
            return 0.0
            
        ratings = pair.get('ratings', [])
        rating_score = np.mean([r['rating'] for r in ratings]) if ratings else 0.0
        has_sentences = bool(pair.get('sentences', []))
        
        return (rating_score * self.weights['user_feedback'] + 
                (1.0 if has_sentences else 0.0) * self.weights['sentence_context'])
    
    def save_word_pair(self, word1, word2, rating=None, sentence=None):
        self.storage.add_word_pair(word1, word2, rating, sentence)
        
    def update_weights(self, correct_prediction):
        self.weights['total_predictions'] += 1
        if correct_prediction:
            self.weights['correct_predictions'] += 1
            self.weights['user_feedback'] *= (1 + self.weights['learning_rate'])
            self.weights['sentence_context'] *= (1 + self.weights['learning_rate'])
        else:
            self.weights['user_feedback'] *= (1 - self.weights['learning_rate'])
            self.weights['sentence_context'] *= (1 - self.weights['learning_rate'])
        
        total = sum(w for k, w in self.weights.items() 
                    if k in ['wordnet_base', 'user_feedback', 'sentence_context'])
        
        for key in ['wordnet_base', 'user_feedback', 'sentence_context']:
            self.weights[key] /= total
        
        self.weights['training_iterations'] += 1
        self.storage.save_model_weights(self.weights)