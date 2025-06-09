from config_storage import StorageManager

def get_trained_similarity(word1, word2):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    key = f"{word1.lower()}-{word2.lower()}"
    alt_key = f"{word2.lower()}-{word1.lower()}"
    
    if key in pairs:
        pair_data = pairs[key]
        ratings = pair_data.get('ratings', [])
        if ratings:
            avg_rating = sum(r['rating'] for r in ratings) / len(ratings)
            return True, avg_rating
        return True, 1.0
    elif alt_key in pairs:
        pair_data = pairs[alt_key]
        ratings = pair_data.get('ratings', [])
        if ratings:
            avg_rating = sum(r['rating'] for r in ratings) / len(ratings)
            return True, avg_rating
        return True, 1.0
    
    return False, 0.0

def get_trained_relations(word, train_of_thought=[]):
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    related_words = []
    
    for key, data in pairs.items():
        if word.lower() in [data['word1'].lower(), data['word2'].lower()]:
            related_word = data['word2'] if word.lower() == data['word1'].lower() else data['word1']

            ratings = data.get('ratings', [])
            rating_score = sum(r['rating'] for r in ratings) / len(ratings) if ratings else 0
            has_sentences = bool(data.get('sentences', []))
            if rating_score > 0 or has_sentences:
                related_words.append({
                    'word': related_word,
                    'reason': f"trained association with {word}",
                    'relation_type': 'trained',
                    'score': rating_score if rating_score > 0 else 0.5,
                    'similarity': rating_score if rating_score > 0 else 0.5,
                    'source': 'trained'
                })
    
    if related_words and train_of_thought is not None:
        train_of_thought.append([w['word'] for w in related_words])
    
    return related_words