from game_state import GameState
from wordnet_utils import is_valid_word, is_word_contained, get_best_related_word, are_words_related, get_contextual_definition, get_word_definition

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
            
            is_related, similarity = are_words_related(message, game_state.last_word)
            if similarity < game_state.player_similarity_threshold:
                previous_word = game_state.last_word
                best_related = get_best_related_word(message, train_of_thought, game_state)
                if best_related:
                    game_state.add_word(best_related['word'])
                    game_state.last_word = best_related['word']
                    game_state.last_reason = best_related['reason']
                    game_state.last_similarity = best_related['similarity']
                    return {
                        'response': f"{best_related['word']}", 
                        'train_of_thought': train_of_thought,
                        'response_code': 'UNRELATED'
                    }
                return format_response_with_code('NO_RELATION')
        
        best_related = get_best_related_word(message, train_of_thought, game_state)
        if not best_related:
            game_state.word_history.remove(message)
            return format_response_with_code('NO_RELATION')
        
        game_state.add_word(best_related['word'])
        game_state.last_word = best_related['word']
        game_state.last_reason = best_related['reason']
        game_state.last_similarity = best_related['similarity']
        
        return {
            'response': best_related['word'],
            'train_of_thought': train_of_thought,
            'response_code': 'RELATED'
        }
    except Exception as e:
        print(f"Error in format_response: {str(e)}")
        return format_response_with_code('ERROR')