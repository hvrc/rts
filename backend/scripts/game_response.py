from .game_state import GameState
from .utils_wordnet import (
    is_valid_word, is_word_contained, get_wordnet_relations,
    get_contextual_definition, get_word_definition, get_wordnet_similarity
)
from .utils_common import get_best_related_word
from .utils_trained import get_trained_relations, get_trained_similarity
from .config_constants import RESPONSE_CONFIG, get_constant
from .model_trainer import update_rating

def print_rating_change(word1, word2, result):
    """Helper function to print rating changes consistently"""
    if result:
        change_text = f"increased by {result['change']:.3f}" if result['change'] > 0 else f"decreased by {abs(result['change']):.3f}"
        print(f"{word1} -> {word2}: score {change_text} to {result['new_score']:.3f}")

def format_response_with_code(code, **kwargs):
    response_type = RESPONSE_CONFIG[code]
    return {
        'response': response_type['message'].format(**kwargs) if kwargs else response_type['message'],
        'train_of_thought': kwargs.get('train_of_thought', []),
        'response_code': code
    }

def format_response(message, game_state):
    try:
        if not message or not message.strip():
            return format_response_with_code('EMPTY')
        
        message = message.strip().lower()
        
        if message == "reset":
            game_state.reset()
            return format_response_with_code('RESET')
        
        # Word validation only - don't add to history (that's done in server)
        is_valid, reason = is_valid_word(message)
        if not is_valid:
            if reason == "rts":
                return format_response_with_code('RTS')
            return format_response_with_code('INVALID_WORD')
        
        # Initialize train_of_thought list
        train_of_thought = []
        
        # Get last BOT word from conversation history for similarity checking
        last_bot_word = game_state.get_last_word('bot')
        if last_bot_word:
            # Check for word containment with last bot word
            if is_word_contained(message, last_bot_word):
                return format_response_with_code('TOO_SIMILAR', word=message, last_word=last_bot_word)
            
            # Check similarity with last bot word
            active_model = get_constant('ACTIVE_MODEL')
            if active_model == 'trained':
                is_related, similarity = get_trained_similarity(message, last_bot_word)
            else:
                is_related, similarity = get_wordnet_similarity(message, last_bot_word)              # If similarity is too low, find a bridge word
            if similarity < game_state.player_similarity_threshold:
                best_related = get_best_related_word(message, train_of_thought, game_state)
                if best_related:
                    # Train with low rating for unrelated words
                    result = update_rating(last_bot_word, message, -0.1) # 0.5 - 0.1 = 0.4
                    print_rating_change(last_bot_word, message, result)
                    
                    return format_response_with_code('UNRELATED', suggestion=best_related['word'], train_of_thought=train_of_thought)
                
                return format_response_with_code('NO_RELATION')          # Normal case - find related word
        best_related = get_best_related_word(message, train_of_thought, game_state)
        if best_related:
            # Train with medium rating for related words
            if last_bot_word:
                result = update_rating(last_bot_word, message, 0.0)
                print_rating_change(last_bot_word, message, result)
            
            return format_response_with_code('RELATED', suggestion=best_related['word'], train_of_thought=train_of_thought)
        
        return format_response_with_code('NO_RELATION')
    except Exception as e:
        return format_response_with_code('ERROR')