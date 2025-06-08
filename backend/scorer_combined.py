from scorer_wordnet import WordNetScorer
from scorer_bert import BertScorer
from scorer_trainable import TrainableScorer
from config_constants import BASE_SIMILARITY_THRESHOLD, WORDNET_WEIGHT, BERT_WEIGHT

class CombinedScorer:
    def __init__(self):
        self.wordnet_scorer = WordNetScorer()
        self.bert_scorer = BertScorer()
        self.trainable_scorer = TrainableScorer()
    
    def get_similarity(self, word1, word2):
        wordnet_sim = self.wordnet_scorer.get_similarity(word1, word2)
        bert_sim = self.bert_scorer.get_similarity(word1, word2)
        learned_sim = self.trainable_scorer.get_learned_score(word1, word2)

        weights = self.trainable_scorer.weights
        final_score = (
            wordnet_sim * WORDNET_WEIGHT * weights['wordnet_base'] +
            bert_sim * BERT_WEIGHT * weights['bert_base'] +
            learned_sim
        )
        
        return final_score
    
    def score_word(self, word, original_word, relation_type, similarity):
        wordnet_score = self.wordnet_scorer.score_word(word, original_word, relation_type, similarity)
        bert_score = self.bert_scorer.score_word(word, original_word)
        learned_score = self.trainable_scorer.get_learned_score(word, original_word)
        
        weights = self.trainable_scorer.weights
        final_score = (
            wordnet_score * WORDNET_WEIGHT * weights['wordnet_base'] +
            bert_score * BERT_WEIGHT * weights['bert_base'] +
            learned_score * weights['user_feedback'] +
            similarity * weights['sentence_context']
        )
        
        return final_score
    
    def are_words_related(self, word1, word2):
        similarity = self.get_similarity(word1, word2)
        return similarity >= BASE_SIMILARITY_THRESHOLD, similarity