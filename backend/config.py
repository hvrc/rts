# Game thresholds
PLAYER_THRESHOLD = 0.01  # 1% similarity threshold for player's words
AI_THRESHOLD = 0.98      # 98% similarity for AI's words
SIMILARITY_THRESHOLD = 0.2  # Base similarity threshold
SISTER_TERM_THRESHOLD = 0.5  # Minimum similarity for sister terms

# Word scoring weights
LENGTH_SCORE_WEIGHT = 0.3
COMMON_WORD_SCORE = 0.7
DIRECT_RELATION_BOOST = 1.5

# WordNet concrete roots
CONCRETE_ROOTS = {
    'physical_entity.n.01',  # Most concrete objects
    'matter.n.03',          # Physical substances
    'artifact.n.01',        # Man-made objects
    'natural_object.n.01',  # Natural objects
    'organism.n.01',        # Living things
    'plant.n.02',           # Plants
    'animal.n.01',          # Animals
    'substance.n.01',       # Materials
    'food.n.01',            # Food items
    'object.n.01',          # Physical objects
    'structure.n.01',       # Buildings/constructions
    'body_part.n.01'        # Body parts
}

# Keywords for definition scoring
ABSTRACT_KEYWORDS = {
    'abstract', 'quality', 'state', 'condition', 'feeling', 
    'emotion', 'concept', 'idea', 'activity', 'action',
    'process', 'phenomenon', 'manner', 'way', 'belief',
    'thought', 'system', 'method', 'principle', 'theory',
    'relationship', 'attitude', 'perception', 'intention',
    'event', 'time', 'situation', 'experience'
}

CONCRETE_INDICATORS = {
    'object', 'thing', 'item', 'entity', 'physical',
    'material', 'substance', 'structure', 'device', 
    'tool', 'container', 'animal', 'plant', 'machine',
    'building', 'vehicle', 'furniture', 'instrument',
    'appliance', 'equipment', 'artifact', 'product'
}

TECHNICAL_TERMS = {
    'technical', 'specialized', 'scientific', 'formal',
    'specifically', 'particularly', 'in mathematics',
    'in physics', 'in chemistry', 'in biology'
}

COMMON_WORDS = {
    'dog', 'cat', 'house', 'book', 'food', 'water', 'bed', 'chair',
    'car', 'door', 'box', 'cup', 'desk', 'bird', 'fish', 'hand',
    'milk', 'paper', 'coin', 'glass', 'mouth', 'nose', 'ball', 'eye'
}

PROPER_NOUNS = {
    'cheetos', 'pepsi', 'coca-cola', 'nike', 'adidas', 'lego',
    'nintendo', 'playstation', 'xbox', 'oreo', 'doritos'
}