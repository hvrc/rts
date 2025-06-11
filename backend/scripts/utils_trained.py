from .config_storage import StorageManager
from .config_constants import get_constant

def get_trained_similarity(word1, word2):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    key = f"{word1.lower()}-{word2.lower()}"
    alt_key = f"{word2.lower()}-{word1.lower()}"
    pair_data = pairs.get(key) or pairs.get(alt_key)
    
    if pair_data:
        total_score = pair_data.get('total_score', 0.5)
        return True, total_score
    
    return False, 0.0

def get_low_rated_words(word):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    trained_threshold = get_constant('TRAINED_THRESHOLD')
    low_rated_words = set()
    
    for key, data in pairs.items():
        if word.lower() in [data['word1'].lower(), data['word2'].lower()]:
            related_word = data['word2'] if word.lower() == data['word1'].lower() else data['word1']
            total_score = data.get('total_score', 0.5)
            sentences = data.get('sentences', [])
            has_sentences = len(sentences) > 0 and any(
                sentence.get('text', '').strip() for sentence in sentences
            )
            
            if total_score <= trained_threshold and not has_sentences:
                low_rated_words.add(related_word.lower())
    
    return low_rated_words

def get_trained_relations(word, train_of_thought=[]):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    related_words = []
    
    for key, data in pairs.items():
        if word.lower() in [data['word1'].lower(), data['word2'].lower()]:
            
            related_word = data['word2'] if word.lower() == data['word1'].lower() else data['word1']
            default_score = get_constant('DEFAULT_RATING_SCORE')
            trained_threshold = get_constant('TRAINED_THRESHOLD')
            total_score = data.get('total_score', default_score)
            sentences = data.get('sentences', [])
            has_sentences = len(sentences) > 0 and any(
                sentence.get('text', '').strip() for sentence in sentences
            )
            
            if total_score > trained_threshold or has_sentences:
                related_words.append({
                    'word': related_word,
                    'reason': f"trained association with {word}",
                    'relation_type': 'trained',
                    'score': total_score,
                    'similarity': total_score,
                    'source': 'trained'
                })
    
    if related_words and train_of_thought is not None:
        train_of_thought.append([w['word'] for w in related_words])
    
    return related_words