from config_db import word_pairs, training_sentences, model_weights
import numpy as np
from datetime import datetime

DEFAULT_WEIGHTS = {
    'wordnet_base': 0.4,
    'bert_base': 0.4,
    'user_feedback': 0.2,
    'sentence_context': 0.2,
    'active': True,
    'created_at': datetime.now()
}

class TrainableScorer:
    def __init__(self):
        self.weights = self._load_or_create_weights()
        
    def _load_or_create_weights(self):
        try:
            weights = model_weights.find_one({'active': True})
            if not weights:
                model_weights.insert_one(DEFAULT_WEIGHTS)
                return DEFAULT_WEIGHTS
            return weights
        except Exception as e:
            print(f"Error loading weights: {str(e)}")
            print("Using default weights")
            return DEFAULT_WEIGHTS
    
    def save_word_pair(self, word1, word2, rating=None, sentence=None):
        """Store a word pair with optional rating and context sentence"""
        word_pair = {
            'word1': word1.lower(),
            'word2': word2.lower(),
            'ratings': [],
            'sentences': [],
            'created_at': datetime.now()
        }
        
        if rating is not None:
            word_pair['ratings'].append({
                'rating': rating,
                'timestamp': datetime.now()
            })
            
        if sentence:
            word_pair['sentences'].append({
                'text': sentence,
                'timestamp': datetime.now()
            })
            
        word_pairs.update_one(
            {'word1': word1, 'word2': word2},
            {'$set': word_pair},
            upsert=True
        )
    
    def get_learned_score(self, word1, word2):
        """Get learned similarity score for a word pair"""
        pair = word_pairs.find_one({
            '$or': [
                {'word1': word1, 'word2': word2},
                {'word1': word2, 'word2': word1}
            ]
        })
        
        if not pair:
            return 0.0
            
        rating_score = np.mean([r['rating'] for r in pair.get('ratings', [])] or [0])
        has_sentences = len(pair.get('sentences', [])) > 0
        
        return (rating_score * self.weights['user_feedback'] + 
                (1.0 if has_sentences else 0.0) * self.weights['sentence_context'])