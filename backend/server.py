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
        
        print(f"[Server] Processing user message: {message}")
        
        # Process response first to validate the word
        response = format_response(message, game_state)
        
        # Only add user's word to history if it's valid (not an error response)
        user_word_valid = response.get('response_code') not in [
            'INVALID_WORD', 'DUPLICATE', 'ERROR', 'EMPTY', 'RTS', 'SAME_WORD', 'TOO_SIMILAR'
        ]
        
        if user_word_valid:
            if game_state.add_word(message, 'user'):
                print(f"[Server] Added user word to history: {message}")
            else:
                print(f"[Server] Failed to add user word to history: {message}")
        else:
            print(f"[Server] User word rejected ({response.get('response_code')}): {message}")
        
        # Only add bot's response to history if it should be trained (has_train=true)
        response_config = RESPONSE_CONFIG.get(response.get('response_code', ''), {})
        should_add_bot_response = response_config.get('has_train', False)
        
        if should_add_bot_response and response.get('response'):
            # For UNRELATED responses, the actual word is in the response
            bot_word = response['response']
            if game_state.add_word(bot_word, 'bot'):
                print(f"[Server] Added bot word to history: {bot_word}")
            else:
                print(f"[Server] Failed to add bot word to history: {bot_word}")
        else:
            print(f"[Server] Bot response not added to history ({response.get('response_code')}): {response.get('response')}")
        
        return jsonify({
            'response': response['response'],
            'train_of_thought': response.get('train_of_thought', []),
            'response_code': response.get('response_code', '')
        }), 200
    except Exception as e:
        print(f"[Server] Error in echo: {str(e)}")
        return jsonify({
            'response': 'Error processing request',
            'train_of_thought': [],
            'response_code': 'ERROR',
            'error': str(e)
        }), 500

@app.route('/reset', methods=['POST'])
def reset():
    print("[Server] Resetting game state...")
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
        
        print(f"[Server] Removing question mark for word: {current_word}")
        
        # Find the word entry and get its pair
        context = game_state.find_word_context(current_word)
        if context and context['previous_word']:
            # Add 0.1 to rating when question mark is removed
            rating_change = 0.1
            update_rating(context['previous_word'], current_word, rating_change)
            print(f"[Server] Added {rating_change} to score: {context['previous_word']} -> {current_word}")
        else:
            print(f"[Server] Could not find context for word: {current_word}")
        
        return jsonify({
            'success': True,
            'message': 'Question mark removed and rating updated'
        }), 200
    
    except Exception as e:
        print(f"[Server] Error in remove_question: {str(e)}")
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
        
        print(f"[Server] Rating update for word: {current_word}, like: {is_like}")
        
        # Find the word entry and get its pair
        context = game_state.find_word_context(current_word)
        if context and context['previous_word']:
            # Add 0.1 for like, subtract 0.1 for dislike
            rating_change = 0.1 if is_like else -0.1
            update_rating(context['previous_word'], current_word, rating_change)
            print(f"[Server] {'Added' if is_like else 'Subtracted'} 0.1 from score: {context['previous_word']} -> {current_word}")
        else:
            print(f"[Server] Could not find context for word: {current_word}")
        
        return jsonify({
            'success': True,
            'message': 'Rating updated'
        }), 200
    
    except Exception as e:
        print(f"[Server] Error in update_rating: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug/history', methods=['GET'])
def debug_history():
    """Debug endpoint to view conversation history"""
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