from flask import Flask, request, jsonify
from flask_cors import CORS
from reply_handler import format_response, game_state

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    # Reset game state on page load
    game_state.reset()
    return "Hello, World!"

@app.route('/echo', methods=['POST'])
def echo():
    data = request.json
    message = data.get('message', '')
    return jsonify(format_response(message))

@app.route('/reset', methods=['POST'])
def reset():
    game_state.reset()
    return jsonify({'response': 'Game reset!'})

if __name__ == '__main__':
    app.run(debug=True)
