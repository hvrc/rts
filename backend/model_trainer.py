from config_storage import StorageManager
import argparse
from datetime import datetime

storage = StorageManager()

# train model using an explanatory sentence
def train_from_sentence(word1, word2, sentence):
    try:
        storage.add_word_pair(word1, word2, sentence=sentence)
        weights = storage.load_model_weights()
        print(f"\nAdded training sentence for {word1}-{word2}")
        print(f"Training iterations: {weights['training_iterations']}")
        print(f"Accuracy: {(weights['correct_predictions']/weights['total_predictions']*100):.2f}%" 
              if weights['total_predictions'] > 0 else "No predictions yet")
        return True
    except Exception as e:
        print(f"Error adding sentence: {str(e)}")
        return False

# train model using a rating (0 or 1)
def train_from_rating(word1, word2, rating):
    try:
        storage.add_word_pair(word1, word2, rating=float(rating))
        print(f"Added rating {rating} for {word1}-{word2}")
        return True
    except Exception as e:
        print(f"Error adding rating: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the RTS model")
    parser.add_argument('--mode', choices=['sentence', 'rating'], required=True)
    parser.add_argument('--word1', required=True)
    parser.add_argument('--word2', required=True)
    parser.add_argument('--value', required=True, help="Rating (0/1) or sentence")
    
    args = parser.parse_args()
    
    if args.mode == 'sentence':
        train_from_sentence(args.word1, args.word2, args.value)
    else:
        train_from_rating(args.word1, args.word2, float(args.value))