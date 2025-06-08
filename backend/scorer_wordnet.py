from nltk.corpus import wordnet
import nltk
from config_constants import (
    COMMON_WORDS, CONCRETE_INDICATORS, ABSTRACT_KEYWORDS, CONCRETE_ROOTS,
    WORDNET_SIMILARITY_WEIGHT, WORDNET_HYPONYM_WEIGHT,
    WORDNET_HYPERNYM_WEIGHT, WORDNET_SISTER_WEIGHT,
    WORDNET_FREQUENCY_WEIGHT, WORDNET_CONCRETE_WEIGHT
)

def is_concrete_by_hypernyms(synset):
    try:
        hypernym_paths = synset.hypernym_paths()
        return any(any(h.name() in CONCRETE_ROOTS for h in path) for path in hypernym_paths)
    except:
        return False

def is_concrete_noun(word):
    synsets = wordnet.synsets(word, pos=wordnet.NOUN)
    word = word.lower()
    
    if not synsets:
        return False
    
    for synset in synsets:
        definition = synset.definition().lower()
        if any(keyword in definition for keyword in ABSTRACT_KEYWORDS):
            continue
        if any(indicator in definition for indicator in CONCRETE_INDICATORS):
            return True
        if is_concrete_by_hypernyms(synset):
            return True
    return False

class WordNetScorer:
    def __init__(self):
        self.similarity_weight = WORDNET_SIMILARITY_WEIGHT
        self.hyponym_weight = WORDNET_HYPONYM_WEIGHT
        self.hypernym_weight = WORDNET_HYPERNYM_WEIGHT
        self.sister_weight = WORDNET_SISTER_WEIGHT
        self.frequency_weight = WORDNET_FREQUENCY_WEIGHT
        self.concrete_weight = WORDNET_CONCRETE_WEIGHT
    
    def get_similarity(self, word1, word2):
        synsets1 = wordnet.synsets(word1, pos=[wordnet.NOUN, wordnet.ADJ])
        synsets2 = wordnet.synsets(word2, pos=[wordnet.NOUN, wordnet.ADJ])
        
        return max(
            (s1.path_similarity(s2) or 0)
            for s1 in synsets1
            for s2 in synsets2
        ) if synsets1 and synsets2 else 0
    
    def score_word(self, word, original_word, relation_type, similarity):
        score = 0
        score += similarity * self.similarity_weight
        
        if relation_type == 'hyponym':
            score += self.hyponym_weight
        elif relation_type == 'hypernym':
            score += self.hypernym_weight
        elif relation_type == 'sister':
            score += self.sister_weight
        
        if word.lower() in COMMON_WORDS:
            score += self.frequency_weight
        
        if is_concrete_noun(word):
            score += self.concrete_weight
        
        return score