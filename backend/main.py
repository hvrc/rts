from nltk.corpus import wordnet
import nltk
import random
from flask import Flask, request, jsonify
from flask_cors import CORS

# Download required NLTK data
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

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

TECHNICAL_TERMS = {
    'technical', 'specialized', 'scientific', 'formal', 'specifically', 'particularly',
    'in mathematics', 'in physics', 'in chemistry', 'in biology'
}

COMMON_WORDS = {
    'dog', 'cat', 'house', 'book', 'food', 'water', 'bed', 'chair', 'phone', 'car',
    'door', 'box', 'cup', 'desk', 'bird', 'fish', 'hand', 'key', 'milk', 'paper',
    'coin', 'glass', 'mouth', 'nose', 'ball', 'eye'
}

PROPER_NOUNS = {
    'cheetos', 'pepsi', 'coca-cola', 'nike', 'adidas', 'lego', 'nintendo',
    'playstation', 'xbox', 'oreo', 'doritos'
}

class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.last_word = None
        self.last_reason = None
        self.last_similarity = None
        self.word_history = set()  # Track all used words
    
    def add_word(self, word):
        """Add word to history and return True if it's new, False if repeated."""
        word = word.lower()
        if word in self.word_history:
            return False
        self.word_history.add(word)
        return True

# Create global game state
game_state = GameState()

def is_concrete_by_hypernyms(synset):
    """Check if a synset is concrete based on its hypernym hierarchy."""
    try:
        hypernym_paths = synset.hypernym_paths()
        return any(any(h.name() in CONCRETE_ROOTS for h in path) for path in hypernym_paths)
    except:
        return False

def is_concrete_noun(word):
    """Check if word is a concrete noun."""
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

def is_valid_word(word):
    """Check if word follows game rules."""
    if not word:
        return False, "Please enter a word"
    
    if word.lower()[0] in ['r', 't', 's']:
        return False, "Word cannot start with R, T, or S"
    
    if not is_concrete_noun(word.lower()):
        return False, "Word must be a concrete noun"
    
    return True, "Valid word"

def are_words_related(word1, word2):
    """Check if two words are semantically related."""
    synsets1 = wordnet.synsets(word1, pos=wordnet.NOUN)
    synsets2 = wordnet.synsets(word2, pos=wordnet.NOUN)
    
    if not synsets1 or not synsets2:
        return False, 0
    
    max_similarity = max(
        (s1.path_similarity(s2) or 0)
        for s1 in synsets1
        for s2 in synsets2
    )
    
    return max_similarity >= SIMILARITY_THRESHOLD, max_similarity

def get_related_word(word):
    """Find a related word that follows game rules."""
    synsets = wordnet.synsets(word, pos=wordnet.NOUN)
    related_words = set()
    
    for synset in synsets:
        for hypernym in synset.hypernyms():
            related_words.update([lemma.name() for lemma in hypernym.lemmas()])
        for hyponym in synset.hyponyms():
            related_words.update([lemma.name() for lemma in hyponym.lemmas()])
    
    valid_words = [w for w in related_words 
                   if not w.startswith(('r', 'R', 't', 'T', 's', 'S'))
                   and '_' not in w
                   and is_valid_word(w)[0]]
    
    return random.choice(valid_words) if valid_words else None

def get_word_frequency_score(word):
    """Get a score for word commonness (0-1, higher means more common)."""
    length_score = 0.3 / (len(word) + 1)
    common_word_score = 0.7 if word.lower() in COMMON_WORDS else 0
    return length_score + common_word_score

def get_related_word_with_reason(word):
    """Find a related word and the reason for relation."""
    synsets = wordnet.synsets(word, pos=wordnet.NOUN)
    all_related_words = []
    
    for synset in synsets:
        for hypernym in synset.hypernyms():
            word = hypernym.lemmas()[0].name()
            score = get_word_frequency_score(word) * 1.5
            all_related_words.append({
                'word': word,
                'reason': f"is a more general category than {word}",
                'score': score,
                'relation_type': 'hypernym'
            })
        for hyponym in synset.hyponyms():
            word = hyponym.lemmas()[0].name()
            score = get_word_frequency_score(word) * 1.5
            all_related_words.append({
                'word': word,
                'reason': f"is a type of {word}",
                'score': score,
                'relation_type': 'hyponym'
            })
        for hypernym in synset.hypernyms():
            for sister in hypernym.hyponyms():
                if sister != synset:
                    similarity = synset.path_similarity(sister) or 0
                    if similarity >= SISTER_TERM_THRESHOLD:
                        for lemma in sister.lemmas():
                            word = lemma.name()
                            score = get_word_frequency_score(word) * similarity
                            all_related_words.append({
                                'word': word,
                                'reason': f"is closely related to {word}",
                                'score': score,
                                'relation_type': 'sister'
                            })
    
    valid_words = [w for w in all_related_words 
                   if not w['word'].startswith(('r', 'R', 't', 'T', 's', 'S'))
                   and '_' not in w['word']
                   and is_valid_word(w['word'])[0]]
    
    if not valid_words:
        return None
    
    valid_words.sort(key=lambda x: (
        x['relation_type'] in ['hypernym', 'hyponym'],
        x['score']
    ), reverse=True)
    
    top_words = valid_words[:3] if len(valid_words) > 3 else valid_words
    return random.choice(top_words) if top_words else None

def get_word_definition(word):
    """Get all noun definitions of a word, ranked by commonness and concreteness."""
    synsets = wordnet.synsets(word, pos=wordnet.NOUN)
    if not synsets:
        return "No definitions found."
    
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
        if any(term in definition for term in TECHNICAL_TERMS):
            score -= 10
        if is_concrete_by_hypernyms(synset):
            score += 2
        scored_defs.append((score, definition))
    
    scored_defs.sort(key=lambda x: x[0], reverse=True)
    definitions = [f"{i+1}. {definition.capitalize()}" 
                   for i, (_, definition) in enumerate(scored_defs)]
    return "\n".join(definitions)

def get_contextual_definition(word1, word2, reason):
    """Get definition of word2 in context of its relationship to word1."""
    synsets1 = wordnet.synsets(word1, pos=wordnet.NOUN)
    synsets2 = wordnet.synsets(word2, pos=wordnet.NOUN)
    
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

def is_word_contained(word1, word2):
    """Check if words are the same, variations, or one is part of another."""
    word1, word2 = word1.lower(), word2.lower()
    
    word1_parts = word1.split()
    word2_parts = word2.split()
    
    for part in word1_parts:
        if part in word2 or any(part in w for w in word2_parts):
            return True
    for part in word2_parts:
        if part in word1 or any(part in w for w in word1_parts):
            return True
    
    if word1 in word2 or word2 in word1:
        return True
        
    if word1.endswith('s') and word1[:-1] == word2:
        return True
    if word2.endswith('s') and word2[:-1] == word1:
        return True
    if word1.endswith('es') and word1[:-2] == word2:
        return True
    if word2.endswith('es') and word2[:-2] == word1:
        return True
    if word1.endswith('ies') and word1[:-3] + 'y' == word2:
        return True
    if word2.endswith('ies') and word2[:-3] + 'y' == word1:
        return True
        
    return False

def format_response(message):
    """Handle game logic and format response."""
    if not message or not message.strip():
        return {'response': 'Please enter a word'}
    
    message = message.strip().lower()
    
    if message == "how":
        if game_state.last_word:
            contextual_def = get_contextual_definition(
                message, 
                game_state.last_word, 
                game_state.last_reason
            )
            return {'response': contextual_def}
        return {'response': "No previous word to explain."}
    
    if message == "define":
        if game_state.last_word:
            definitions = get_word_definition(game_state.last_word)
            return {'response': f"'{game_state.last_word}':\n{definitions}"}
        return {'response': "No previous word to define."}
    
    if message == "reset":
        game_state.reset()
        return {'response': "Game reset! Word history cleared. Start with a new word."}
    
    if not game_state.add_word(message):
        return {'response': f"'{message}' has already been used in this game. Try a different word!"}
    
    is_valid, reason = is_valid_word(message)
    if not is_valid:
        game_state.word_history.remove(message)
        return {'response': f"Invalid word: {reason}"}
    
    if game_state.last_word:
        if message == game_state.last_word:
            return {'response': f"'{message}' is the exact same word as '{game_state.last_word}'. Try a different word!"}
        if is_word_contained(message, game_state.last_word):
            return {'response': f"Your word '{message}' contains or is contained within '{game_state.last_word}'. Try a different word!"}
            
        is_related, similarity = are_words_related(game_state.last_word, message)
        if similarity < PLAYER_THRESHOLD:
            game_state.word_history.remove(message)
            return {
                'response': f"Your word '{message}' is not related to '{game_state.last_word}' "
                           f"(similarity: {int(similarity * 100)}%, needed: {int(PLAYER_THRESHOLD * 100)}%)"
            }
    
    related = get_related_word_with_reason(message)
    if not related:
        game_state.reset()
        return {'response': "I can't think of a related word. You win! Game reset."}
    
    best_related = related
    best_similarity = 0
    best_combined_score = 0
    
    for _ in range(25):
        new_related = get_related_word_with_reason(message)
        if new_related and new_related['word'].lower() not in game_state.word_history:
            is_related, similarity = are_words_related(message, new_related['word'])
            frequency_score = get_word_frequency_score(new_related['word'])
            combined_score = (similarity * 0.7) + (frequency_score * 0.3)
            
            if similarity > best_similarity or (
                similarity == best_similarity and 
                frequency_score > get_word_frequency_score(best_related['word'])
            ):
                best_related = new_related
                best_similarity = similarity
                best_combined_score = combined_score
                
            if similarity >= AI_THRESHOLD and frequency_score >= 0.5:
                break
    
    if best_related['word'].lower() in game_state.word_history:
        game_state.reset()
        return {'response': "All related words have been used. Game reset!"}
    
    game_state.add_word(best_related['word'])
    game_state.last_word = best_related['word']
    game_state.last_reason = best_related['reason']
    game_state.last_similarity = best_similarity
    
    return {'response': best_related['word']}