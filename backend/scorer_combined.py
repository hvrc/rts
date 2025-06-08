from scorer_wordnet import WordNetScorer
from scorer_bert import BertScorer
from scorer_trainable import TrainableScorer
from config_constants import WORDNET_WEIGHT, BERT_WEIGHT

class CombinedScorer:
    def __init__(self, wordnet_weight=WORDNET_WEIGHT, bert_weight=BERT_WEIGHT):
        self.wordnet_scorer = WordNetScorer()
        self.bert_scorer = BertScorer()
        self.trainable_scorer = TrainableScorer()
        self.wordnet_weight = wordnet_weight
        self.bert_weight = bert_weight
    
    def get_similarity(self, word1, word2):
        wordnet_similarity = self.wordnet_scorer.get_similarity(word1, word2)
        bert_similarity = self.bert_scorer.get_similarity(word1, word2)
        learned_similarity = self.trainable_scorer.get_learned_score(word1, word2)
        
        return (self.wordnet_weight * wordnet_similarity + 
                self.bert_weight * bert_similarity +
                learned_similarity)
    
    def score_word(self, word, original_word, relation_type, similarity):
        wordnet_score = self.wordnet_scorer.score_word(word, original_word, relation_type, similarity)
        bert_score = self.bert_scorer.score_word(word, original_word)
        return (self.wordnet_weight * wordnet_score) + (self.bert_weight * bert_score)
    
    def are_words_related(self, word1, word2):
        similarity = self.get_similarity(word1, word2)
        return similarity >= 0.2, similarity