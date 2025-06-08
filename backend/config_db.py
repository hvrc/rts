from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, AutoReconnect
import os
import time

# Update MongoDB URI configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:4999/')
IS_PRODUCTION = os.getenv('GAE_ENV', '').startswith('standard')

if IS_PRODUCTION:
    # Use MongoDB Atlas URI in production
    MONGO_URI = os.getenv('MONGODB_ATLAS_URI', '')
    DB_NAME = 'rts_memory_prod'
else:
    # Use local MongoDB in development
    MONGO_URI = 'mongodb://localhost:4999/'
    DB_NAME = 'rts_memory_dev'

class MockCollection:
    def __init__(self):
        self.data = {}
    
    def find_one(self, query):
        return None
    
    def update_one(self, query, update, upsert=False):
        pass
    
    def insert_one(self, document):
        pass
    
    def create_index(self, keys, **kwargs):
        pass

MAX_RETRIES = 3
RETRY_DELAY = 2

def get_database():
    for attempt in range(MAX_RETRIES):
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            client.server_info()
            db = client[DB_NAME]
            return db, client
        except (AutoReconnect, ServerSelectionTimeoutError) as e:
            if attempt == MAX_RETRIES - 1:
                print(f"Could not connect to MongoDB after {MAX_RETRIES} attempts")
                print("Please ensure MongoDB is running locally")
                print(f"Error: {str(e)}")
                print("Using mock collections as fallback")
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

    try:
        word_pairs.create_index([("word1", 1), ("word2", 1)], unique=True)
        training_sentences.create_index([("word1", 1), ("word2", 1)])
        constants.create_index([("name", 1)], unique=True)
    except Exception as e:
        print(f"Error creating indexes: {str(e)}")