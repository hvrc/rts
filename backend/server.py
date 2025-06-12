from flask import Flask, request, jsonify
from flask_cors import CORS
from scripts.game_state import GameState
from scripts.game_response import format_response
from scripts.config_constants import initialize_constants, get_constant, update_constant, RESPONSE_CONFIG
from scripts.model_trainer import update_rating
import os

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": [
            "https://rts0-462101.ue.r.appspot.com", 
            "http://localhost:5001"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

initialize_constants()
update_constant('ACTIVE_MODEL', 'trained_wordnet')
game_state = GameState()

@app.route('/')
def home():
    game_state.reset()
    return "welcome to the rts brain!"

@app.route('/echo', methods=['POST'])
def echo():
    try:
        data = request.json
        message = data.get('message', '')
          # process response first to validate the word
        response = format_response(message, game_state)
        
        # only add user's word to history if it's valid (not an error response)
        user_word_valid = response.get('response_code') not in [
            'INVALID_WORD', 'DUPLICATE', 'ERROR', 'EMPTY', 'RTS', 'SAME_WORD', 'TOO_SIMILAR'
        ]
        
        if user_word_valid:
            game_state.add_word(message, 'user')
        
        # only add bot's response to history if it should be trained (has_train=true)
        response_config = RESPONSE_CONFIG.get(response.get('response_code', ''), {})
        should_add_bot_response = response_config.get('has_train', False)
        
        if should_add_bot_response and response.get('response'):
            # for unrelated responses, the actual word is in the response
            bot_word = response['response']
            game_state.add_word(bot_word, 'bot')
        
        return jsonify({
            'response': response['response'],
            'train_of_thought': response.get('train_of_thought', []),
            'response_code': response.get('response_code', '')
        }), 200
    except Exception as e:
        return jsonify({
            'response': 'Error processing request',
            'train_of_thought': [],
            'response_code': 'ERROR',
            'error': str(e)
        }), 500

@app.route('/reset', methods=['POST'])
def reset():
    game_state.reset()
    response = format_response('reset', game_state)
    return jsonify({
        'response': response['response'],
        'train_of_thought': response.get('train_of_thought', []),
        'response_code': response.get('response_code', '')
    })

@app.route('/remove_question', methods=['POST'])
def remove_question():
    try:
        data = request.json
        current_word = data.get('word')
          # find the word entry and get its pair
        context = game_state.find_word_context(current_word)
        if context and context['previous_word']:
            # add 0.2 to rating when question mark is removed
            rating_change = 0.2
            result = update_rating(context['previous_word'], current_word, rating_change)
            if result:
                change_text = "increased" if result['change'] > 0 else "decreased"
                print(f"{context['previous_word']} -> {current_word}: score {change_text} from {result['previous_score']:.3f} to {result['new_score']:.3f}")
        
        return jsonify({
            'success': True,
            'message': 'Question mark removed and rating updated'
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/update_rating', methods=['POST'])
def update_rating_route():
    try:
        data = request.json
        current_word = data.get('word')
        is_like = data.get('rating', 0.0) == 1.0
          # find the word entry and get its pair
        context = game_state.find_word_context(current_word)
        if context and context['previous_word']:
            # add 0.1 for like, subtract 0.1 for dislike
            rating_change = 0.1 if is_like else -0.1
            result = update_rating(context['previous_word'], current_word, rating_change)
            if result:
                change_text = "increased" if result['change'] > 0 else "decreased"
                print(f"{context['previous_word']} -> {current_word}: score {change_text} from {result['previous_score']:.3f} to {result['new_score']:.3f}")
        
        return jsonify({
            'success': True,
            'message': 'Rating updated'
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug/history', methods=['GET'])
def debug_history():
    # debug endpoint to view conversation history
    try:
        history = game_state.get_conversation_history()
        return jsonify({
            'conversation_history': history,
            'total_words': len(game_state.word_history),
            'user_words': list(game_state.user_words),
            'current_pair': game_state.get_current_pair()
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)