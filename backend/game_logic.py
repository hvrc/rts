# Import required modules and config
import nltk
from nltk.corpus import wordnet
import random
from config import (
    PLAYER_THRESHOLD, AI_THRESHOLD, SIMILARITY_THRESHOLD,
    SISTER_TERM_THRESHOLD, CONCRETE_ROOTS, ABSTRACT_KEYWORDS,
    CONCRETE_INDICATORS, PROPER_NOUNS, LENGTH_SCORE_WEIGHT,
    COMMON_WORD_SCORE, DIRECT_RELATION_BOOST, COMMON_WORDS,
    TECHNICAL_TERMS
)

# Download required NLTK data
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

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
        # Skip if definition contains abstract keywords
        definition = synset.definition().lower()
        if any(keyword in definition for keyword in ABSTRACT_KEYWORDS):
            continue
        
        # Check for concrete indicators
        if any(indicator in definition for indicator in CONCRETE_INDICATORS):
            return True
        
        # Check hypernym hierarchy
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

def format_response(message):
    """Handle game logic and format response."""
    if not message or not message.strip():
        return {
            'status': 'error',
            'message': 'Please enter a word'
        }
    
    message = message.strip()
    
    # Handle special commands
    if message.lower() == "how":
        if game_state.last_word:
            return {
                'status': 'success',
                'message': f"'{game_state.last_word}' - {game_state.last_reason}"
            }
        return {
            'status': 'error',
            'message': "No previous word to explain."
        }
    
    if message.lower() == "define":
        if game_state.last_word:
            return {
                'status': 'success',
                'message': f"Definition of '{game_state.last_word}': TODO add definition"
            }
        return {
            'status': 'error',
            'message': "No previous word to define."
        }
    
    if message.lower() == "reset":
        game_state.reset()
        return {
            'status': 'success',
            'message': "Game reset! Start with a new word."
        }
    
    # Check if word is valid
    is_valid, reason = is_valid_word(message)
    if not is_valid:
        return {
            'status': 'error',
            'message': reason
        }
    
    # Check if word is already used
    if not game_state.add_word(message):
        return {
            'status': 'error',
            'message': f"'{message}' has already been used. Try a different word!"
        }
    
    # If there's a previous word, check relationship
    if game_state.last_word:
        is_related, similarity = are_words_related(game_state.last_word, message)
        if not is_related:
            game_state.word_history.remove(message.lower())
            return {
                'status': 'error',
                'message': f"Your word '{message}' is not related to '{game_state.last_word}' (similarity: {int(similarity * 100)}%)"
            }
    
    # Update game state
    game_state.update_last_word(message, "is your word", 1.0)
    
    return {
        'status': 'success',
        'message': f"I accept your word '{message}'. Now it's my turn..."
    }