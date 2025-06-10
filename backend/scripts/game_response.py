from .game_state import GameState
from .utils_wordnet import (
    is_valid_word, is_word_contained, get_wordnet_relations,
    get_contextual_definition, get_word_definition, get_wordnet_similarity
)
from .utils_common import get_best_related_word
from .utils_trained import get_trained_relations, get_trained_similarity
from .config_constants import RESPONSE_CONFIG, get_constant
from .model_trainer import train_from_rating

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
        
        # word pre validation
        if not game_state.add_word(message):
            return format_response_with_code('DUPLICATE', word=message)
        
        is_valid, reason = is_valid_word(message)
        if not is_valid:
            game_state.word_history.remove(message)
            if reason == "rts":
                return format_response_with_code('RTS')
            return format_response_with_code('INVALID_WORD')
        
        # initialize train_of_thought list
        train_of_thought = []
        
        if game_state.last_word:
            if message == game_state.last_word:
                return format_response_with_code('SAME_WORD', word=message)
            if is_word_contained(message, game_state.last_word):
                return format_response_with_code('TOO_SIMILAR', word=message, last_word=game_state.last_word)
            
            # Use game_state's scorer instead of CombinedScorer
            active_model = get_constant('ACTIVE_MODEL')
            if active_model == 'trained':
                is_related, similarity = get_trained_similarity(message, game_state.last_word)
            else:
                is_related, similarity = get_wordnet_similarity(message, game_state.last_word)
            
            if similarity < game_state.player_similarity_threshold:
                previous_word = game_state.last_word
                best_related = get_best_related_word(message, train_of_thought, game_state)
                if best_related:
                    game_state.add_word(best_related['word'])
                    game_state.update_words(best_related['word'])  # Replace direct assignment
                    game_state.last_reason = best_related['reason']
                    game_state.last_similarity = best_related['similarity']
                    
                    train_from_rating(previous_word, message, 0.25)
                    train_of_thought.append([f"Added positive association: {previous_word} -> {message}"])

                    return {
                        'response': f"{best_related['word']}", 
                        'train_of_thought': train_of_thought,
                        'response_code': 'UNRELATED'
                    }

                return format_response_with_code('NO_RELATION')
        
        # Update user's word
        game_state.update_words(message, is_bot=False)
        
        if game_state.last_bot_word:
            # Check relation with last bot word
            is_related, similarity = get_wordnet_similarity(message, game_state.last_bot_word)
            
            if similarity < game_state.player_similarity_threshold:
                best_related = get_best_related_word(message, train_of_thought, game_state)
                if best_related:
                    # Update bot's word
                    game_state.update_words(best_related['word'], is_bot=True)
                    game_state.last_reason = best_related['reason']
                    game_state.last_similarity = best_related['similarity']
                    
                    # Train with low rating for unrelated words
                    if game_state.current_pair:
                        train_from_rating(game_state.current_pair[0], game_state.current_pair[1], 0.25)
                        train_of_thought.append([f"Added low rating for unrelated words: {game_state.current_pair[0]} -> {game_state.current_pair[1]}"])
                    
                    return {
                        'response': best_related['word'],
                        'train_of_thought': train_of_thought,
                        'response_code': 'UNRELATED'
                    }
                
                return format_response_with_code('NO_RELATION')
        
        # Handle normal case
        best_related = get_best_related_word(message, train_of_thought, game_state)
        if best_related:
            # Update bot's word
            game_state.update_words(best_related['word'], is_bot=True)
            game_state.last_reason = best_related['reason']
            game_state.last_similarity = best_related['similarity']
            
            # Train with medium rating for related words
            if game_state.current_pair:
                train_from_rating(game_state.current_pair[0], game_state.current_pair[1], 0.5)
                train_of_thought.append([f"Added medium rating for related words: {game_state.current_pair[0]} -> {game_state.current_pair[1]}"])
            
            return {
                'response': best_related['word'],
                'train_of_thought': train_of_thought,
                'response_code': 'RELATED'
            }
        
        game_state.word_history.remove(message)
        return format_response_with_code('NO_RELATION')
        
    except Exception as e:
        print(f"Error in format_response: {str(e)}")
        return format_response_with_code('ERROR')