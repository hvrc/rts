from transformers import BertTokenizer, BertModel
import torch
import numpy as np

class BertEmbedder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BertEmbedder, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        self.model = BertModel.from_pretrained('bert-base-uncased')
        self.model.eval()
        
    def get_embedding(self, word):
        with torch.no_grad():
            inputs = self.tokenizer(word, return_tensors="pt", padding=True)
            outputs = self.model(**inputs)
            return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

    def compute_similarity(self, word1, word2):
        emb1 = self.get_embedding(word1)
        emb2 = self.get_embedding(word2)
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))

bert_embedder = BertEmbedder()