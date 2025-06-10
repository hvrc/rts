from flask import Flask, request, jsonify
from flask_cors import CORS
from scripts.game_state import GameState
from scripts.game_response import format_response
from scripts.config_constants import initialize_constants, get_constant, update_constant
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
        response = format_response(message, game_state)
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
        message_id = data.get('message_id')
        current_word = data.get('word')
        
        # Get the previous bot word from game state
        previous_word = game_state.previous_word  # Use previous_word instead of last_word
        
        if previous_word and current_word:
            # Update the rating to 1.0 since user accepted the relation
            update_rating(previous_word, current_word, 1.0)
            print(f"Updated pair rating to 1.0: {previous_word} -> {current_word}")
        else:
            print(f"Could not update rating - Missing words: previous={previous_word}, current={current_word}")
        
        return jsonify({
            'success': True,
            'message': 'Question mark removed and rating updated'
        }), 200
    
    except Exception as e:
        print(f"Error in remove_question: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/update_rating', methods=['POST'])
def update_rating_route():
    try:
        data = request.json
        message_id = data.get('message_id')
        current_word = data.get('word')
        rating = data.get('rating', 0.0)
        
        if game_state.current_pair:
            # Use the stored pair instead of trying to figure it out
            word1, word2 = game_state.current_pair
            update_rating(word1, word2, rating)
            print(f"Updated pair rating to {rating}: {word1} -> {word2}")
        else:
            print(f"Could not update rating - No current word pair available")
        
        return jsonify({
            'success': True,
            'message': 'Rating updated'
        }), 200
    
    except Exception as e:
        print(f"Error in update_rating: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)