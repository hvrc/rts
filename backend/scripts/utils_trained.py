from .config_storage import StorageManager

def get_trained_similarity(word1, word2):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    key = f"{word1.lower()}-{word2.lower()}"
    alt_key = f"{word2.lower()}-{word1.lower()}"
    
    # Check for pair data using either key
    pair_data = pairs.get(key) or pairs.get(alt_key)
    
    if pair_data:
        # Use the total_score from incremental rating system
        total_score = pair_data.get('total_score', 0.5)
        return True, total_score
    
    return False, 0.0

def get_trained_relations(word, train_of_thought=[]):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    related_words = []
    
    for key, data in pairs.items():
        if word.lower() in [data['word1'].lower(), data['word2'].lower()]:
            related_word = data['word2'] if word.lower() == data['word1'].lower() else data['word1']

            # Use total_score from incremental rating system
            total_score = data.get('total_score', 0.5)
            has_sentences = bool(data.get('sentences', []))
            
            # Only include words with positive scores or sentences
            if total_score > 0.5 or has_sentences:
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