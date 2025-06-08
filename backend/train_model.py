from config_db import word_pairs, training_sentences, model_weights
import argparse
from datetime import datetime

# train model using an explanatory sentence
def train_from_sentence(word1, word2, sentence):
    try:
        training_sentences.insert_one({
            'word1': word1.lower(),
            'word2': word2.lower(),
            'sentence': sentence,
            'timestamp': datetime.now()
        })
        print(f"Added training sentence for {word1}-{word2}")
        return True
    except Exception as e:
        print(f"Error adding sentence: {str(e)}")
        return False

# train model using a rating (0 or 1)
def train_from_rating(word1, word2, rating):
    try:
        word_pairs.update_one(
            {'word1': word1.lower(), 'word2': word2.lower()},
            {
                '$push': {
                    'ratings': {
                        'rating': float(rating),
                        'timestamp': datetime.now()
                    }
                }
            },
            upsert=True
        )
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