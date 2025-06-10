import os
import json
from datetime import datetime

def load_json_config(filename):
    """Load a JSON configuration file from the config directory"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', filename)
    try:
        with open(config_path, 'r') as f:
            print(f"Loading configuration from {config_path}")
            data = json.load(f)
            print(f"Successfully loaded {len(data)} settings from {filename}")
            return data
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return {}

# Load configurations from JSON files
MODEL_WEIGHTS = load_json_config('model_weights.json')
CONSTANTS = load_json_config('constants.json')
RESPONSE_CONFIG = load_json_config('responses.json')

# Combine all constants
ALL_CONSTANTS = {**CONSTANTS, **MODEL_WEIGHTS}

# In-memory storage for runtime constants
_runtime_constants = {}

def initialize_constants():
    """Initialize constants in runtime storage"""
    global _runtime_constants
    _runtime_constants = ALL_CONSTANTS.copy()
    print(f"Initialized {len(_runtime_constants)} constants")

def get_constant(name):
    """Get constant from runtime storage with fallback to defaults"""
    global _runtime_constants
    if not _runtime_constants:
        initialize_constants()
    return _runtime_constants.get(name, ALL_CONSTANTS.get(name))

def update_constant(name, value):
    """Update constant in runtime storage"""
    global _runtime_constants
    try:
        if not _runtime_constants:
            initialize_constants()
        _runtime_constants[name] = value
        print(f"Updated constant {name} = {value}")
        return True
    except Exception as e:
        print(f"Error updating constant {name}: {str(e)}")
        return False

# Initialize constants on module load
initialize_constants()

# Export commonly used constants for convenience
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

# New relation weights
WORDNET_SYNONYM_SCORE = get_constant('WORDNET_SYNONYM_SCORE')
WORDNET_SYNONYM_SIMILARITY = get_constant('WORDNET_SYNONYM_SIMILARITY')
WORDNET_HYPONYM_SCORE = get_constant('WORDNET_HYPONYM_SCORE')
WORDNET_HYPONYM_SIMILARITY = get_constant('WORDNET_HYPONYM_SIMILARITY')
WORDNET_HYPERNYM_SCORE = get_constant('WORDNET_HYPERNYM_SCORE')
WORDNET_HYPERNYM_SIMILARITY = get_constant('WORDNET_HYPERNYM_SIMILARITY')

INITIAL_WORDNET_BASE = get_constant('INITIAL_WORDNET_BASE')
INITIAL_USER_FEEDBACK = get_constant('INITIAL_USER_FEEDBACK')
INITIAL_SENTENCE_CONTEXT = get_constant('INITIAL_SENTENCE_CONTEXT')
INITIAL_LEARNING_RATE = get_constant('INITIAL_LEARNING_RATE')
INITIAL_MODEL_ACTIVE = get_constant('INITIAL_MODEL_ACTIVE')