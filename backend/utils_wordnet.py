from nltk.corpus import wordnet
from config_constants import (
    COMMON_WORDS, CONCRETE_INDICATORS, ABSTRACT_KEYWORDS, 
    CONCRETE_ROOTS, BASE_SIMILARITY_THRESHOLD, ENFORCE_RTS_RULE
)
from scorer_wordnet import is_concrete_noun
import nltk
import re

nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

def is_valid_word(word):
    if not word or not isinstance(word, str):
        return False, "invalid input"
    
    cleaned = re.sub(r'[^a-zA-Z]', '', word)
    if not cleaned:
        return False, "no letters"
    
    if ENFORCE_RTS_RULE and cleaned[0].lower() in {'r', 't', 's'}:
        return False, "rts"
    
    if not wordnet.synsets(cleaned):
        return False, "not a word"
    
    return True, None

def is_word_contained(word1, word2):
    w1 = word1.lower()
    w2 = word2.lower()
    return w1 in w2 or w2 in w1

def get_wordnet_similarity(word1, word2):
    synsets1 = wordnet.synsets(word1)
    synsets2 = wordnet.synsets(word2)
    
    if synsets1 and synsets2:
        similarities = []
        for s1 in synsets1:
            for s2 in synsets2:
                sim = s1.path_similarity(s2)
                if sim is not None:
                    similarities.append(sim)
        
        if similarities:
            max_sim = max(similarities)
            return max_sim >= BASE_SIMILARITY_THRESHOLD, max_sim
    
    return False, 0.0

def get_contextual_definition(word):
    synsets = wordnet.synsets(word)
    if not synsets:
        return None
    
    noun_synsets = [s for s in synsets if s.pos() == wordnet.NOUN]
    if noun_synsets:
        synset = noun_synsets[0]
    else:
        synset = synsets[0]
    
    return synset.definition()

def get_word_definition(word):
    definition = get_contextual_definition(word)
    if definition:
        return definition.split(';')[0].strip()
    return None

def get_wordnet_relations(word, train_of_thought=[]):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    related_words = []
    raw_words = []
    
    for synset in synsets:
        synonyms = [lemma.name().replace('_', '') for lemma in synset.lemmas()][:5]
        raw_words.extend(synonyms)
        for w in synonyms:
            if w != word:
                related_words.append({
                    'word': w,
                    'reason': f"is a synonym of {word}",
                    'relation_type': 'synonym',
                    'score': 0.8,
                    'similarity': 0.8,
                    'source': 'wordnet'
                })
        
        hyponyms = [h.lemmas()[0].name().replace('_', '') for h in synset.hyponyms()][:20]
        raw_words.extend(hyponyms)
        for w in hyponyms:
            related_words.append({
                'word': w,
                'reason': f"is a type of {word}",
                'relation_type': 'hyponym',
                'score': 0.7,
                'similarity': 0.7,
                'source': 'wordnet'
            })
        
        hypernyms = [h.lemmas()[0].name().replace('_', '') for h in synset.hypernyms()][:10]
        raw_words.extend(hypernyms)
        for w in hypernyms:
            related_words.append({
                'word': w,
                'reason': f"is a more general category than {word}",
                'relation_type': 'hypernym',
                'score': 0.6,
                'similarity': 0.6,
                'source': 'wordnet'
            })
    
    if raw_words and train_of_thought is not None:
        train_of_thought.append(list(set(raw_words)))
    
    return related_words

def get_best_related_word(word, train_of_thought, game_state):
    related_words = get_wordnet_relations(word, train_of_thought)
    
    scored_words = [
        w for w in related_words 
        if w['word'] not in game_state.word_history 
        and is_valid_word(w['word'])[0]
        and not is_word_contained(word, w['word'])
    ]
    
    if scored_words:
        scored_words.sort(key=lambda x: x['score'], reverse=True)
        best_word = scored_words[0]
        
        if train_of_thought is not None:
            train_of_thought.append([best_word['word']])
        
        return best_word
        
    return None