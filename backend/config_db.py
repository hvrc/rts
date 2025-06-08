from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, AutoReconnect, DuplicateKeyError
import os
import time
from datetime import datetime

class MockCollection:
    def __init__(self):
        self.data = {}
    
    def find_one(self, query):
        return None
    
    def find(self, query=None):
        return []
    
    def update_one(self, query, update, upsert=False):
        pass
    
    def insert_one(self, document):
        pass
    
    def create_index(self, keys, **kwargs):
        pass
    
    def delete_many(self, query):
        pass

MONGO_URI = os.getenv('MONGODB_ATLAS_URI', 'mongodb://localhost:49999/')
DB_NAME = 'rts_memory'

MAX_RETRIES = 3
RETRY_DELAY = 2

def get_database():
    for attempt in range(MAX_RETRIES):
        try:
            print(f"Attempting to connect to MongoDB: {MONGO_URI}")
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.server_info()
            db = client[DB_NAME]
            
            try:
                db['word_pairs'].create_index([("word1", 1), ("word2", 1)], unique=True)
                db['training_sentences'].create_index([("word1", 1), ("word2", 1)])
                db['constants'].create_index([("name", 1)], unique=True)
                print("Successfully created indexes")
            except Exception as e:
                print(f"Index creation warning (may already exist): {str(e)}")
            
            word_pairs = db['word_pairs']
            test_doc = {
                'word1': 'test',
                'word2': 'connection',
                'timestamp': datetime.now(),
                'ratings': []
            }
            try:
                if not word_pairs.find_one({'word1': 'test', 'word2': 'connection'}):
                    word_pairs.insert_one(test_doc)
                    print("Successfully inserted test data")
                else:
                    print("Test data already exists")
            except DuplicateKeyError:
                print("Test data already exists")
            
            return db, client
            
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                print(f"Could not connect to MongoDB after {MAX_RETRIES} attempts")
                return None, None
            time.sleep(RETRY_DELAY)

db, client = get_database()

word_pairs = MockCollection()
training_sentences = MockCollection()
model_weights = MockCollection()
training_history = MockCollection()
constants = MockCollection()

if db is not None:
    word_pairs = db['word_pairs']
    training_sentences = db['training_sentences']
    model_weights = db['model_weights']
    training_history = db['training_history']
    constants = db['constants']

# python train_model.py --mode sentence --word1 morning --word2 coffee --value "People drink coffee in the morning"
# python train_model.py --mode sentence --word1 faze --word2 clan --value "Faze clan is a esports team"