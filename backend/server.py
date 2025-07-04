from flask import Flask, request, jsonify
from flask_cors import CORS
from main import format_response, game_state
import os

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": ["https://rts0-462101.ue.r.appspot.com", "http://localhost:5173"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.route('/')
def home():
    game_state.reset()
    return "welcome to the rts brain!"

@app.route('/echo', methods=['POST'])
def echo():
    try:
        data = request.json
        message = data.get('message', '')
        response = format_response(message)
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
    response = format_response('reset')
    return jsonify({
        'response': response['response'],
        'train_of_thought': []
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)