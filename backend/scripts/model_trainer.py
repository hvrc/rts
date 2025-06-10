from .config_storage import StorageManager
import argparse
from datetime import datetime

storage = StorageManager()

def update_rating(word1, word2, rating_change):
    """Update rating for a word pair by adding/subtracting from current score"""
    try:
        pairs = storage.load_word_pairs()
        key = f"{word1.lower()}-{word2.lower()}"
        alt_key = f"{word2.lower()}-{word1.lower()}"
        
        # Get pair data using either key
        pair_data = pairs.get(key) or pairs.get(alt_key)
        if not pair_data:
            # Create new pair if it doesn't exist
            pairs[key] = {
                'word1': word1.lower(),
                'word2': word2.lower(),
                'total_score': 0.5,  # Start at neutral score
                'ratings': [],
                'sentences': [],
                'created_at': datetime.now()
            }
            pair_data = pairs[key]
        
        # Get current score (default to 0.5 if not found)
        current_score = pair_data.get('total_score', 0.5)
        
        # Calculate new score by adding/subtracting the rating change
        new_total = max(0, min(1, current_score + rating_change))
        actual_change = new_total - current_score
        
        # Add the rating event with change details
        pair_data['ratings'].append({
            'rating_change': rating_change,
            'actual_change': actual_change,
            'previous_score': current_score,
            'new_score': new_total,
            'timestamp': datetime.now()
        })
        
        # Update the total score
        pair_data['total_score'] = new_total
          # Save updated pairs
        storage.save_word_pairs(pairs)
        return {'new_score': new_total, 'change': actual_change, 'previous_score': current_score}
        
    except Exception as e:
        print(f"Error updating rating: {str(e)}")
        return None

# Keep existing functions for backward compatibility
def train_from_sentence(word1, word2, sentence):
    try:
        storage.add_word_pair(word1, word2, sentence=sentence)
        print(f"Added training sentence for {word1}-{word2}")
        return True
    except Exception as e:
        print(f"Error adding sentence: {str(e)}")
        return False

def train_from_rating(word1, word2, rating):
    """Train from an absolute rating value (0-1 scale)"""
    try:
        # Convert absolute rating to incremental change
        # If rating is 0.5 (neutral), no change needed
        # If rating < 0.5, it's a negative change from neutral
        # If rating > 0.5, it's a positive change from neutral
        rating_change = rating - 0.5
        return update_rating(word1, word2, rating_change)
    except Exception as e:
        print(f"Error adding rating: {str(e)}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the RTS model")
    parser.add_argument('--mode', choices=['sentence', 'rating', 'remove', 'update'], required=True)
    parser.add_argument('--word1', required=True)
    parser.add_argument('--word2', required=True)
    parser.add_argument('--value', help="Rating change or sentence", required=False)
    
    args = parser.parse_args()
    
    if args.mode == 'sentence':
        train_from_sentence(args.word1, args.word2, args.value)
    elif args.mode == 'rating':
        train_from_rating(args.word1, args.word2, float(args.value))
    elif args.mode == 'update':
        if not args.value:
            print("Error: --value required for update mode")
        else:
            update_rating(args.word1, args.word2, float(args.value))