import os
import pickle
from datetime import datetime
import time

class LocalCollection:
    def __init__(self, name):
        self.name = name
        self.data_dir = "model_rts_1"
        self.file_path = os.path.join(self.data_dir, f"{name}.pkl")
        self._initialize_storage()
        
    def _initialize_storage(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if not os.path.exists(self.file_path):
            self._save_data({})
    
    def _load_data(self):
        try:
            with open(self.file_path, 'rb') as f:
                return pickle.load(f)
        except:
            return {}
            
    def _save_data(self, data):
        with open(self.file_path, 'wb') as f:
            pickle.dump(data, f)
    
    def find_one(self, query):
        data = self._load_data()
        key, value = next(iter(query.items()))
        return next((item for item in data.values() if item.get(key) == value), None)
    
    def update_one(self, query, update, upsert=False):
        data = self._load_data()
        key, value = next(iter(query.items()))
        item = next((item for item in data.values() if item.get(key) == value), None)
        
        if item is None and upsert:
            doc_id = str(len(data) + 1)
            item = query.copy()
            item.update(update.get('$set', {}))
            data[doc_id] = item
        elif item is not None:
            item.update(update.get('$set', {}))
            
        self._save_data(data)
    
    def insert_one(self, document):
        data = self._load_data()
        doc_id = str(len(data) + 1)
        document['_id'] = doc_id
        data[doc_id] = document
        self._save_data(data)
    
    def create_index(self, keys, **kwargs):
        pass

word_pairs = LocalCollection('word_pairs')
training_sentences = LocalCollection('training_sentences')
model_weights = LocalCollection('model_weights') 
training_history = LocalCollection('training_history')
constants = LocalCollection('constants')