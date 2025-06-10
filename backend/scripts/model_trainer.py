from .config_storage import StorageManager
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

def remove_word_pair(word1, word2):
    """Remove a word pair from the training data"""
    try:
        pairs = storage.load_word_pairs()
        key = f"{word1.lower()}-{word2.lower()}"
        alt_key = f"{word2.lower()}-{word1.lower()}"
        
        if key in pairs:
            del pairs[key]
            storage.save_word_pairs(pairs)
            print(f"Removed pair {word1}-{word2}")
            return True
        elif alt_key in pairs:
            del pairs[alt_key]
            storage.save_word_pairs(pairs)
            print(f"Removed pair {word2}-{word1}")
            return True
            
        print(f"Pair {word1}-{word2} not found")
        return False
    except Exception as e:
        print(f"Error removing pair: {str(e)}")
        return False

def update_rating(word1, word2, new_rating):
    """Update or add a new rating for an existing word pair"""
    try:
        pairs = storage.load_word_pairs()
        key = f"{word1.lower()}-{word2.lower()}"
        alt_key = f"{word2.lower()}-{word1.lower()}"
        
        pair_data = pairs.get(key) or pairs.get(alt_key)
        if not pair_data:
            print(f"Pair {word1}-{word2} not found")
            return False
            
        # Add new rating
        storage.add_word_pair(
            pair_data['word1'],
            pair_data['word2'],
            rating=float(new_rating)
        )
        
        print(f"Updated rating for {word1}-{word2} to {new_rating}")
        return True
    except Exception as e:
        print(f"Error updating rating: {str(e)}")
        return False

# Update main to include new commands
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the RTS model")
    parser.add_argument('--mode', choices=['sentence', 'rating', 'remove', 'update'], required=True)
    parser.add_argument('--word1', required=True)
    parser.add_argument('--word2', required=True)
    parser.add_argument('--value', help="Rating (0-1) or sentence", required=False)
    
    args = parser.parse_args()
    
    if args.mode == 'sentence':
        train_from_sentence(args.word1, args.word2, args.value)
    elif args.mode == 'rating':
        train_from_rating(args.word1, args.word2, float(args.value))
    elif args.mode == 'remove':
        remove_word_pair(args.word1, args.word2)
    elif args.mode == 'update':
        if not args.value:
            print("Error: --value required for update mode")
        else:
            update_rating(args.word1, args.word2, float(args.value))