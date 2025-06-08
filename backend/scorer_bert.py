from utils_bert import bert_embedder

class BertScorer:
    def get_similarity(self, word1, word2):
        return bert_embedder.compute_similarity(word1, word2)
    
    def score_word(self, word, original_word):
        return self.get_similarity(word, original_word)