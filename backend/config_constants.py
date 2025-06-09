from datetime import datetime
from config_storage import storage_manager

DEFAULT_CONSTANTS = {
    'PLAYER_THRESHOLD': 0.5,
    'AI_THRESHOLD': 0.9,
    'SISTER_TERM_THRESHOLD': 0.5,
    'BASE_SIMILARITY_THRESHOLD': 0.2,
    
    'MAX_RELATED_WORDS': 25,
    'MAX_HYPONYMS': 20,
    'MAX_HYPERNYMS': 10,
    'MAX_SISTERS': 3,
    'MAX_SYNONYMS': 5,
    
    'COMMON_WORDS': [
        'dog', 'cat', 'house', 'book', 'food', 'water', 'bed', 'chair', 'phone', 'car',
        'door', 'box', 'cup', 'desk', 'bird', 'fish', 'hand', 'key', 'milk', 'paper',
        'coin', 'glass', 'mouth', 'nose', 'ball', 'eye', 'beach'
    ],
    'CONCRETE_ROOTS': [
        'physical_entity.n.01', 'matter.n.03', 'artifact.n.01', 'natural_object.n.01',
        'organism.n.01', 'plant.n.02', 'animal.n.01', 'substance.n.01', 'food.n.01',
        'object.n.01', 'structure.n.01', 'body_part.n.01'
    ],
    'ABSTRACT_KEYWORDS': [
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
    ],
    'CONCRETE_INDICATORS': [
        'object', 'thing', 'item', 'entity', 'physical', 'material', 'substance',
        'structure', 'device', 'tool', 'container', 'animal', 'plant', 'machine',
        'building', 'vehicle', 'furniture', 'instrument', 'appliance', 'equipment',
        'artifact', 'product', 'element', 'component', 'part', 'organism', 'creature',
        'materiality', 'surface', 'texture', 'solid', 'liquid', 'gas', 'metal', 'wood',
        'fabric', 'clothing', 'fruit', 'vegetable', 'mineral', 'rock', 'body', 'hand',
        'face', 'foot', 'flower', 'leaf', 'seed', 'fruit', 'toolkit', 'utensil', 'weapon',
        'box', 'bag', 'fossil', 'statue', 'coin', 'jewel', 'gem', 'crystal', 'fiber'
    ],

    # wordnet, trained
    'ACTIVE_MODEL': '',
    
    'WORDNET_SIMILARITY_WEIGHT': 0.4,
    'WORDNET_HYPONYM_WEIGHT': 0.2,
    'WORDNET_HYPERNYM_WEIGHT': 0.2,
    'WORDNET_SISTER_WEIGHT': 0.15,
    'WORDNET_FREQUENCY_WEIGHT': 0.15,
    'WORDNET_CONCRETE_WEIGHT': 0.1,
    'ENFORCE_RTS_RULE': True,
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

def initialize_constants():
    """Initialize constants in local storage"""
    for name, value in DEFAULT_CONSTANTS.items():
        try:
            stored = storage_manager.find_one('constants', {'name': name})
            if stored is None:
                storage_manager.insert_one('constants', {
                    'name': name,
                    'value': value,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })
        except Exception as e:
            print(f"Error initializing constant {name}: {str(e)}")

def get_constant(name):
    """Get constant from local storage with fallback to defaults"""
    try:
        constant = storage_manager.find_one('constants', {'name': name})
        return constant['value'] if constant else DEFAULT_CONSTANTS.get(name)
    except Exception as e:
        print(f"Error getting constant {name}, using default: {str(e)}")
        return DEFAULT_CONSTANTS.get(name)

def update_constant(name, value):
    """Update constant in local storage"""
    try:
        now = datetime.now()
        storage_manager.update_one(
            'constants',
            {'name': name},
            {
                '$set': {
                    'value': value,
                    'updated_at': now
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating constant {name}: {str(e)}")
        return False

initialize_constants()

PLAYER_THRESHOLD = get_constant('PLAYER_THRESHOLD')
AI_THRESHOLD = get_constant('AI_THRESHOLD')
SISTER_TERM_THRESHOLD = get_constant('SISTER_TERM_THRESHOLD')
BASE_SIMILARITY_THRESHOLD = get_constant('BASE_SIMILARITY_THRESHOLD')

MAX_RELATED_WORDS = get_constant('MAX_RELATED_WORDS')
MAX_HYPONYMS = get_constant('MAX_HYPONYMS')
MAX_HYPERNYMS = get_constant('MAX_HYPERNYMS')
MAX_SISTERS = get_constant('MAX_SISTERS')
MAX_SYNONYMS = get_constant('MAX_SYNONYMS')

COMMON_WORDS = set(get_constant('COMMON_WORDS'))
CONCRETE_ROOTS = set(get_constant('CONCRETE_ROOTS'))
ABSTRACT_KEYWORDS = set(get_constant('ABSTRACT_KEYWORDS'))
CONCRETE_INDICATORS = set(get_constant('CONCRETE_INDICATORS'))

WORDNET_SIMILARITY_WEIGHT = get_constant('WORDNET_SIMILARITY_WEIGHT')
WORDNET_HYPONYM_WEIGHT = get_constant('WORDNET_HYPONYM_WEIGHT')
WORDNET_HYPERNYM_WEIGHT = get_constant('WORDNET_HYPERNYM_WEIGHT')
WORDNET_SISTER_WEIGHT = get_constant('WORDNET_SISTER_WEIGHT')
WORDNET_FREQUENCY_WEIGHT = get_constant('WORDNET_FREQUENCY_WEIGHT')
WORDNET_CONCRETE_WEIGHT = get_constant('WORDNET_CONCRETE_WEIGHT')
ENFORCE_RTS_RULE = get_constant('ENFORCE_RTS_RULE')