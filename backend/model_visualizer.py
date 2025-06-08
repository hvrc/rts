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
        
        if data['ratings']:
            print("\nRatings:")
            for rating in data['ratings']:
                print(f"  • {rating['rating']} ({format_timestamp(rating['timestamp'])})")
        
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