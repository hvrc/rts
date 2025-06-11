from config_storage import StorageManager
from datetime import datetime
import json

def format_timestamp(timestamp):
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def visualize_word_pairs():
    storage = StorageManager()
    pairs = storage.load_word_pairs()
    
    if not pairs:
        print("No word pairs found in storage.")
        return
    
    print("\n=== Word Pairs Training Data ===\n")
    
    for key, data in pairs.items():
        print(f"Word Pair: {data['word1']} - {data['word2']}")
        print(f"Created: {format_timestamp(data['created_at'])}")
        
        # Show current total score
        total_score = data.get('total_score', 0.5)
        print(f"Current Score: {total_score}")
        
        if data['ratings']:
            print("\nRating History:")
            for rating in data['ratings']:
                # Handle both old and new rating formats
                if 'rating' in rating:
                    # Old format
                    print(f"  • {rating['rating']} ({format_timestamp(rating['timestamp'])})")
                elif 'rating_change' in rating:
                    # New incremental format
                    change = rating['rating_change']
                    prev_score = rating.get('previous_score', 'N/A')
                    new_score = rating.get('new_score', 'N/A')
                    change_text = f"+{change}" if change >= 0 else str(change)
                    print(f"  • {change_text} (from {prev_score} to {new_score}) ({format_timestamp(rating['timestamp'])})")
                else:
                    # Unknown format
                    print(f"  • Unknown rating format: {rating}")
        
        if data['sentences']:
            print("\nTraining Sentences:")
            for sentence in data['sentences']:
                print(f"  • {sentence['text']}")
                print(f"    Added: {format_timestamp(sentence['timestamp'])}")
        
        print("\n" + "="*50 + "\n")

def visualize_model_weights():
    storage = StorageManager()
    weights = storage.load_model_weights()
    
    if not weights:
        print("No model weights found in storage.")
        return
    
    print("\n=== Current Model Weights ===\n")
    for key, value in weights.items():
        if key != 'created_at':
            print(f"{key}: {value}")
    print(f"\nLast Updated: {format_timestamp(weights['created_at'])}")

if __name__ == "__main__":
    print("\nRTS Model Data Visualization")
    print("==========================")
    
    visualize_model_weights()
    visualize_word_pairs()