from flask import Flask, request, jsonify
from flask_cors import CORS
from main import format_response, game_state

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    game_state.reset()
    return "Hello, World!"

@app.route('/echo', methods=['POST'])
def echo():
    data = request.json
    message = data.get('message', '')
    return jsonify(format_response(message))

@app.route('/reset', methods=['POST'])
def reset():
    return jsonify(format_response('reset'))

if __name__ == '__main__':
    app.run(debug=True)