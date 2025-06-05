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
    'HOW_WHAT': {
        'code': 'HOW_WHAT',
        'message': "how what?",
        'has_train': False
    },
    'DEFINE_WHAT': {
        'code': 'DEFINE_WHAT',
        'message': "define what?",
        'has_train': False
    },
    'RESET': {
        'code': 'RESET',
        'message': "alright, give me a word",
        'has_train': False
    },
    'ERROR': {
        'code': 'ERROR',
        'message': "Sorry, I had trouble processing that word. Try another?",
        'has_train': False
    }
}