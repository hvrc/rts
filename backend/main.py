from nltk.corpus import wordnet
import nltk
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

# Download required NLTK data
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

# Game thresholds
PLAYER_THRESHOLD = 0.20  # Similarity threshold for player's words
AI_THRESHOLD = 0.90      # Similarity for AI's words
SIMILARITY_THRESHOLD = 0.2  # Base similarity threshold
SISTER_TERM_THRESHOLD = 0.5  # Minimum similarity for sister terms
MAX_RELATED_WORDS = 25   # Max words to consider
MAX_HYPONYMS = 20        # Max hyponyms
MAX_HYPERNYMS = 10       # Max hypernyms
MAX_SISTERS = 3          # Max sister terms per parent
MAX_SYNONYMS = 5        # Max synonyms

# Word scoring weights
SIMILARITY_WEIGHT = 0.4
HYPONYM_WEIGHT = 0.2
HYPERNYM_WEIGHT = 0.2
SISTER_WEIGHT = 0.15
FREQUENCY_WEIGHT = 0.15
CONCRETE_WEIGHT = 0.1

# WordNet concrete roots
CONCRETE_ROOTS = {
    'physical_entity.n.01', 'matter.n.03', 'artifact.n.01', 'natural_object.n.01',
    'organism.n.01', 'plant.n.02', 'animal.n.01', 'substance.n.01', 'food.n.01',
    'object.n.01', 'structure.n.01', 'body_part.n.01'
}

# Keywords for definition scoring
ABSTRACT_KEYWORDS = {
    'abstract', 'quality', 'state', 'condition', 'feeling', 'emotion', 'concept',
    'idea', 'activity', 'action', 'process', 'phenomenon', 'manner', 'way', 'belief',
    'thought', 'system', 'method', 'principle', 'theory', 'relationship', 'attitude',
    'perception', 'intention', 'event', 'time', 'situation', 'experience', 'notion',
    'perspective', 'value', 'judgment', 'opinion', 'motivation', 'consciousness',
    'awareness', 'memory', 'imagination', 'creativity', 'ethics', 'morality', 'justice',
    'freedom', 'culture', 'language', 'knowledge', 'wisdom', 'faith', 'hope', 'love',
    'fear', 'curiosity', 'decision', 'expectation', 'possibility', 'potential',
    'responsibility', 'intellect', 'attention', 'strategy', 'goal', 'habit', 'intuition',
    'insight', 'identity', 'motif', 'theme', 'ideal', 'rule', 'norm', 'law',
    'influence', 'conceptualization', 'inspiration', 'state of mind', 'impression',
    'symbolism'
}

CONCRETE_INDICATORS = {
    'object', 'thing', 'item', 'entity', 'physical', 'material', 'substance',
    'structure', 'device', 'tool', 'container', 'animal', 'plant', 'machine',
    'building', 'vehicle', 'furniture', 'instrument', 'appliance', 'equipment',
    'artifact', 'product', 'element', 'component', 'part', 'organism', 'creature',
    'materiality', 'surface', 'texture', 'solid', 'liquid', 'gas', 'metal', 'wood',
    'fabric', 'clothing', 'fruit', 'vegetable', 'mineral', 'rock', 'body', 'hand',
    'face', 'foot', 'flower', 'leaf', 'seed', 'fruit', 'toolkit', 'utensil', 'weapon',
    'box', 'bag', 'fossil', 'statue', 'coin', 'jewel', 'gem', 'crystal', 'fiber'
}

COMMON_WORDS = {
    'dog', 'cat', 'house', 'book', 'food', 'water', 'bed', 'chair', 'phone', 'car',
    'door', 'box', 'cup', 'desk', 'bird', 'fish', 'hand', 'key', 'milk', 'paper',
    'coin', 'glass', 'mouth', 'nose', 'ball', 'eye', 'beach'
}

RESPONSE_CONFIG = {
    'EMPTY': {
        'code': 'EMPTY',
        'message': '?',
        'has_train': False
    },
    'RTS': {
        'code': 'RTS',
        'message': 'rts',
        'has_train': False
    },
    'INVALID_WORD': {
        'code': 'INVALID_WORD',
        'message': "doesn't count",
        'has_train': False
    },
    'DUPLICATE': {
        'code': 'DUPLICATE',
        'message': "we used {word} already",
        'has_train': False
    },
    'SAME_WORD': {
        'code': 'SAME_WORD',
        'message': "we just used {word}",
        'has_train': False
    },
    'TOO_SIMILAR': {
        'code': 'TOO_SIMILAR',
        'message': "isn't {word} too similar to {last_word}?",
        'has_train': False
    },
    'UNRELATED': {
        'code': 'UNRELATED',
        'message': "{suggestion}",
        'has_train': True
    },
    'NO_RELATION': {
        'code': 'NO_RELATION',
        'message': "new word pls?",
        'has_train': False
    },
    # 'HOW_WHAT': {
    #     'code': 'HOW_WHAT',
    #     'message': "how what?",
    #     'has_train': False
    # },
    # 'DEFINE_WHAT': {
    #     'code': 'DEFINE_WHAT',
    #     'message': "define what?",
    #     'has_train': False
    # },
    'RESET': {
        'code': 'RESET',
        'message': "alright, give me a word",
        'has_train': False
    },
    'ERROR': {
        'code': 'ERROR',
        'message': "?",
        'has_train': False
    }
}

def format_response_with_code(code, **kwargs):
    """Format response using response code and optional parameters"""
    response_type = RESPONSE_CONFIG[code]
    return {
        'response': response_type['message'].format(**kwargs) if kwargs else response_type['message'],
        'train_of_thought': kwargs.get('train_of_thought', []),
        'response_code': code
    }

class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.last_word = None
        self.last_reason = None
        self.last_similarity = None
        self.word_history = set()
    
    def add_word(self, word):
        word = word.lower()
        if word in self.word_history:
            return False
        self.word_history.add(word)
        return True

game_state = GameState()

def is_concrete_by_hypernyms(synset):
    try:
        hypernym_paths = synset.hypernym_paths()
        return any(any(h.name() in CONCRETE_ROOTS for h in path) for path in hypernym_paths)
    except:
        return False

def is_concrete_noun(word):
    synsets = wordnet.synsets(word, pos=wordnet.NOUN)
    word = word.lower()
    
    if not synsets:
        return False
    
    for synset in synsets:
        definition = synset.definition().lower()
        if any(keyword in definition for keyword in ABSTRACT_KEYWORDS):
            continue
        if any(indicator in definition for indicator in CONCRETE_INDICATORS):
            return True
        if is_concrete_by_hypernyms(synset):
            return True
    return False

def is_noun_or_adjective(word):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    return len(synsets) > 0

def is_valid_word(word):
    if not word:
        return False, " "
    if word.lower()[0] in ['r', 't', 's']:
        return False, "rts"
    if not word.isalpha():
        return False, f"{word} doesn't count"
    if not is_noun_or_adjective(word):
        return False, f"{word} doesn't count"
    return True, "Valid word"

def is_word_contained(word1, word2):
    """Check if words are variations/forms of each other."""
    word1, word2 = word1.lower(), word2.lower()
    
    # Only check exact matches or full word + suffix
    if word1 == word2:
        return True
    
    # General suffix handling
    suffixes = [
        ('s', ''),      # plural
        ('es', ''),     # plural
        ('ies', 'y'),   # plural
        ('ing', ''),    # gerund
        ('ed', ''),     # past tense
        ('er', ''),     # comparative
        ('est', '')     # superlative
    ]
    
    # Check if one word is a suffix variation of the other
    for suffix, replacement in suffixes:
        if word1.endswith(suffix):
            stem1 = word1[:-len(suffix)] + replacement
            if stem1 == word2:  # Only exact matches
                return True
        if word2.endswith(suffix):
            stem2 = word2[:-len(suffix)] + replacement
            if stem2 == word1:  # Only exact matches
                return True
                
    return False

def get_related_words(word, train_of_thought=[]):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    related_words = []
    raw_words = []
    
    for synset in synsets:
        # Synonyms
        synonyms = [lemma.name().replace('_', '') for lemma in synset.lemmas()][:MAX_SYNONYMS]
        raw_words.extend(synonyms)
        for w in synonyms:
            related_words.append({'word': w, 'reason': f"is a synonym of {word}", 'relation_type': 'synonym'})
        
        # Hyponyms
        hyponyms = [hyponym.lemmas()[0].name().replace('_', '') for hyponym in synset.hyponyms()][:MAX_HYPONYMS]
        raw_words.extend(hyponyms)
        for w in hyponyms:
            related_words.append({'word': w, 'reason': f"is a type of {word}", 'relation_type': 'hyponym'})
        
        # Hypernyms
        hypernyms = [hypernym.lemmas()[0].name().replace('_', '') for hypernym in synset.hypernyms()][:MAX_HYPERNYMS]
        raw_words.extend(hypernyms)
        for w in hypernyms:
            related_words.append({'word': w, 'reason': f"is a more general category than {word}", 'relation_type': 'hypernym'})
        
        # Sister terms
        for hypernym in synset.hypernyms():
            sisters = [sister.lemmas()[0].name().replace('_', '') for sister in hypernym.hyponyms() if sister != synset][:MAX_SISTERS]
            raw_words.extend(sisters)
            for w in sisters:
                related_words.append({'word': w, 'reason': f"is related to {word} via common parent", 'relation_type': 'sister'})
    
    # Add unique raw words to train of thought
    raw_words = list(set(raw_words))
    if raw_words:
        train_of_thought.append(raw_words)
    
    return related_words[:MAX_RELATED_WORDS]

def score_word(word, original_word, relation_type, similarity):
    score = 0
    # Similarity score
    score += similarity * SIMILARITY_WEIGHT
    
    # Relation type score
    if relation_type == 'hyponym':
        score += HYPONYM_WEIGHT
    elif relation_type == 'hypernym':
        score += HYPERNYM_WEIGHT
    elif relation_type == 'sister':
        score += SISTER_WEIGHT
    
    # Frequency score
    if word.lower() in COMMON_WORDS:
        score += FREQUENCY_WEIGHT
    
    # Concreteness score
    if is_concrete_noun(word):
        score += CONCRETE_WEIGHT
    
    return score

def get_best_related_word(word, train_of_thought):
    # 1. Get all raw words and related words
    related_objects = get_related_words(word)
    all_words = list(set(w['word'].replace('_', '') for w in related_objects))
    train_of_thought.append(sorted(all_words))
    
    # 2. Filter nouns and adjectives
    related_words = [w for w in all_words if is_noun_or_adjective(w)]
    if related_words and set(related_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(related_words))
    
    # 3. Filter valid words (no RTS, alphanumeric)
    valid_words = [w for w in related_words if is_valid_word(w)[0]]
    if valid_words and set(valid_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(valid_words))
    
    # 4. Filter unused words
    unused_words = [w for w in valid_words if w.lower() not in game_state.word_history]
    if unused_words and set(unused_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(unused_words))
    
    # 5. Filter variations
    non_variations = [w for w in unused_words if not is_word_contained(word, w)]
    if non_variations and set(non_variations) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(non_variations))
    
    # 6. Filter by similarity threshold and score words
    scored_words = []
    for w in non_variations:
        synsets1 = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
        synsets2 = wordnet.synsets(w, pos=[wordnet.NOUN, wordnet.ADJ])
        similarity = max((s1.path_similarity(s2) or 0) 
                        for s1 in synsets1 
                        for s2 in synsets2) if synsets1 and synsets2 else 0
        
        if similarity >= SIMILARITY_THRESHOLD:
            candidate = next((obj for obj in related_objects if obj['word'] == w), None)
            if candidate:
                score = score_word(w, word, candidate['relation_type'], similarity)
                scored_words.append({
                    'word': w,
                    'reason': candidate['reason'],
                    'score': score,
                    'similarity': similarity
                })
    
    if not scored_words:
        return None
        
    # Sort by score and get words
    scored_words.sort(key=lambda x: x['score'], reverse=True)
    similar_words = [w['word'] for w in scored_words]
    if similar_words and set(similar_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(similar_words))
    
    # Final selected word
    selected_word = [scored_words[0]['word']]
    train_of_thought.append(selected_word)
    
    return scored_words[0]

def get_word_definition(word):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    if not synsets:
        return "I don't know what that means"
    
    scored_defs = []
    for synset in synsets:
        score = 0
        definition = synset.definition().lower()
        score += len(synset.lemmas()) * 3
        score += (len(synsets) - synsets.index(synset)) * 2
        if any(indicator in definition for indicator in CONCRETE_INDICATORS):
            score += 2
        if any(keyword in definition for keyword in ABSTRACT_KEYWORDS):
            score -= 5
        if is_concrete_by_hypernyms(synset):
            score += 2
        scored_defs.append((score, definition))
    
    scored_defs.sort(key=lambda x: x[0], reverse=True)
    definitions = [f"{i+1}. {definition.capitalize()}" for i, (_, definition) in enumerate(scored_defs)]
    return "\n".join(definitions)

def get_contextual_definition(word1, word2, reason):
    synsets1 = wordnet.synsets(word1, pos=[wordnet.NOUN, wordnet.ADJ])
    synsets2 = wordnet.synsets(word2, pos=[wordnet.NOUN, wordnet.ADJ])
    
    if not synsets1 or not synsets2:
        return get_word_definition(word2)
    
    best_pair = None
    max_similarity = 0
    for s1 in synsets1:
        for s2 in synsets2:
            similarity = s1.path_similarity(s2) or 0
            if similarity > max_similarity:
                max_similarity = similarity
                best_pair = (s1, s2)
    
    if best_pair:
        definition = best_pair[1].definition()
        return f"In relation to '{word1}', '{word2}' {reason} - {definition}"
    
    return get_word_definition(word2)

def format_response(message):
    try:
        if not message or not message.strip():
            return format_response_with_code('EMPTY')
        
        message = message.strip().lower()
        
        # Special commands
        # if message == "how":
        #     if game_state.last_word:
        #         contextual_def = get_contextual_definition(message, game_state.last_word, game_state.last_reason)
        #         return format_response_with_code('CONTEXTUAL_DEF', definition=contextual_def)
        #     return format_response_with_code('HOW_WHAT')
        
        # if message == "define":
        #     if game_state.last_word:
        #         definitions = get_word_definition(game_state.last_word)
        #         return format_response_with_code('DEFINITION', definition=definitions)
        #     return format_response_with_code('DEFINE_WHAT')
        
        if message == "reset":
            game_state.reset()
            return format_response_with_code('RESET')
        
        # Word Pre-validation
        if not game_state.add_word(message):
            return format_response_with_code('DUPLICATE', word=message)
        
        is_valid, reason = is_valid_word(message)
        if not is_valid:
            game_state.word_history.remove(message)
            if reason == "rts":
                return format_response_with_code('RTS')
            return format_response_with_code('INVALID_WORD')
        
        train_of_thought = []  # Initialize train_of_thought list
        
        if game_state.last_word:
            if message == game_state.last_word:
                return format_response_with_code('SAME_WORD', word=message)
            if is_word_contained(message, game_state.last_word):
                return format_response_with_code('TOO_SIMILAR', word=message, last_word=game_state.last_word)
            
            is_related, similarity = are_words_related(message, game_state.last_word)
            if similarity < PLAYER_THRESHOLD:
                previous_word = game_state.last_word
                best_related = get_best_related_word(message, train_of_thought)
                if best_related:
                    game_state.add_word(best_related['word'])
                    game_state.last_word = best_related['word']
                    game_state.last_reason = best_related['reason']
                    game_state.last_similarity = best_related['similarity']
                    return {
                        'response': f"{best_related['word']}", 
                        'train_of_thought': train_of_thought,
                        'response_code': 'UNRELATED'  # Add this explicitly
                    }
                return {
                    'response': f"i don't know what relates to {message}. new word pls?",
                    'train_of_thought': []
                }
        
        best_related = get_best_related_word(message, train_of_thought)
        if not best_related:
            game_state.word_history.remove(message)
            return {
                'response': f"i don't know what relates to {message}. can you give me another word?",
                'train_of_thought': []
            }
        
        game_state.add_word(best_related['word'])
        game_state.last_word = best_related['word']
        game_state.last_reason = best_related['reason']
        game_state.last_similarity = best_related['similarity']
        
        return {
            'response': best_related['word'],
            'train_of_thought': train_of_thought
        }
    except Exception as e:
        print(f"Error in format_response: {str(e)}")  # Log the error
        return {
            'response': "?",
            'train_of_thought': []
        }

def are_words_related(word1, word2):
    """Check if two words are related and return similarity score."""
    synsets1 = wordnet.synsets(word1, pos=[wordnet.NOUN, wordnet.ADJ])
    synsets2 = wordnet.synsets(word2, pos=[wordnet.NOUN, wordnet.ADJ])
    
    if not synsets1 or not synsets2:
        return False, 0
    
    # Calculate maximum similarity between any pair of synsets
    max_similarity = max(
        (s1.path_similarity(s2) or 0)
        for s1 in synsets1
        for s2 in synsets2
    )
    
    return max_similarity >= SIMILARITY_THRESHOLD, max_similarity