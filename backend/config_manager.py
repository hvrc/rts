from config_db import constants
from datetime import datetime

DEFAULT_CONSTANTS = {
    'PLAYER_THRESHOLD': 0.5,
    'AI_THRESHOLD': 0.9,
    'SISTER_TERM_THRESHOLD': 0.5,
    'BASE_SIMILARITY_THRESHOLD': 0.2,
    'WORDNET_WEIGHT': 0.5,
    'BERT_WEIGHT': 0.5,
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
    ]
}

def initialize_constants():
    for name, value in DEFAULT_CONSTANTS.items():
        try:
            constants.update_one(
                {'name': name},
                {
                    '$setOnInsert': {
                        'value': value,
                        'created_at': datetime.now(),
                        'updated_at': datetime.now()
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error initializing constant {name}: {str(e)}")

def get_constant(name):
    try:
        constant = constants.find_one({'name': name})
        return constant['value'] if constant else DEFAULT_CONSTANTS.get(name)
    except Exception as e:
        print(f"Error getting constant {name}: {str(e)}")
        return DEFAULT_CONSTANTS.get(name)

def update_constant(name, value):
    try:
        constants.update_one(
            {'name': name},
            {
                '$set': {
                    'value': value,
                    'updated_at': datetime.now()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Error updating constant {name}: {str(e)}")
        return False