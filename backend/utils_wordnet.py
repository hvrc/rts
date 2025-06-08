from nltk.corpus import wordnet
from config_constants import (
    COMMON_WORDS, CONCRETE_INDICATORS, ABSTRACT_KEYWORDS, 
    CONCRETE_ROOTS, BASE_SIMILARITY_THRESHOLD
)
from config_storage import StorageManager
from scorer_wordnet import is_concrete_noun
import nltk
import re

nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

def is_valid_word(word):
    """Check if a word is valid for the game."""
    if not word or not isinstance(word, str):
        return False, "invalid input"
    
    cleaned = re.sub(r'[^a-zA-Z]', '', word)
    if not cleaned:
        return False, "no letters"
    
    if not wordnet.synsets(cleaned):
        return False, "not a word"
    
    return True, None

def is_word_contained(word1, word2):
    """Check if one word is contained within another."""
    w1 = word1.lower()
    w2 = word2.lower()
    return w1 in w2 or w2 in w1

def are_words_related(word1, word2):
    """Check if two words are related using both WordNet and trained data."""
    from config_constants import DEFAULT_CONSTANTS
    
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

    synsets1 = wordnet.synsets(word1)
    synsets2 = wordnet.synsets(word2)
    
    if synsets1 and synsets2:
        similarities = []
        for s1 in synsets1:
            for s2 in synsets2:
                sim = s1.path_similarity(s2)
                if sim is not None:
                    similarities.append(sim)
        
        if similarities:
            max_sim = max(similarities)
            return max_sim >= BASE_SIMILARITY_THRESHOLD, max_sim
    
    return False, 0.0

def get_contextual_definition(word):
    """Get a contextual definition of a word."""
    synsets = wordnet.synsets(word)
    if not synsets:
        return None
    
    noun_synsets = [s for s in synsets if s.pos() == wordnet.NOUN]
    if noun_synsets:
        synset = noun_synsets[0]
    else:
        synset = synsets[0]
    
    return synset.definition()

def get_word_definition(word):
    """Get a simple definition of a word."""
    definition = get_contextual_definition(word)
    if definition:
        return definition.split(';')[0].strip()
    return None

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
                    'similarity': rating_score if rating_score > 0 else 0.5
                })
    
    if related_words and train_of_thought is not None:
        train_of_thought.append([w['word'] for w in related_words])
    
    return related_words

def get_wordnet_relations(word, train_of_thought=[]):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    related_words = []
    raw_words = []
    
    for synset in synsets:
        synonyms = [lemma.name().replace('_', '') for lemma in synset.lemmas()][:5]
        raw_words.extend(synonyms)
        for w in synonyms:
            if w != word:
                related_words.append({
                    'word': w,
                    'reason': f"is a synonym of {word}",
                    'relation_type': 'synonym',
                    'score': 0.8,
                    'similarity': 0.8
                })
        
        hyponyms = [h.lemmas()[0].name().replace('_', '') for h in synset.hyponyms()][:20]
        raw_words.extend(hyponyms)
        for w in hyponyms:
            related_words.append({
                'word': w,
                'reason': f"is a type of {word}",
                'relation_type': 'hyponym',
                'score': 0.7,
                'similarity': 0.7
            })
        
        hypernyms = [h.lemmas()[0].name().replace('_', '') for h in synset.hypernyms()][:10]
        raw_words.extend(hypernyms)
        for w in hypernyms:
            related_words.append({
                'word': w,
                'reason': f"is a more general category than {word}",
                'relation_type': 'hypernym',
                'score': 0.6,
                'similarity': 0.6
            })
    
    if raw_words and train_of_thought is not None:
        train_of_thought.append(list(set(raw_words)))
    
    return related_words

def get_bert_relations(word, train_of_thought=[]):
    return []

def get_best_related_word(word, train_of_thought, game_state):
    from config_constants import DEFAULT_CONSTANTS
    active_model = DEFAULT_CONSTANTS.get('ACTIVE_MODEL', 'trained')
    
    if active_model == 'trained':
        related_words = get_trained_relations(word, train_of_thought)
    elif active_model == 'wordnet':
        related_words = get_wordnet_relations(word, train_of_thought)
    elif active_model == 'bert'::
        related_words = get_bert_relations(word, train_of_thought)
    
    scored_words = [
        w for w in related_words 
        if w['word'] not in game_state.word_history 
        and is_valid_word(w['word'])[0]
        and not is_word_contained(word, w['word'])
    ]
    
    if scored_words:
        scored_words.sort(key=lambda x: x['score'], reverse=True)
        best_word = scored_words[0]
        
        if train_of_thought is not None:
            train_of_thought.append([best_word['word']])
        
        return best_word
        
    return None