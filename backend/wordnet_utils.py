from nltk.corpus import wordnet
import nltk
from constants import COMMON_WORDS
from combined_scorer import CombinedScorer
from wordnet_scorer import is_concrete_noun

nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')

scorer = CombinedScorer()

def is_noun_or_adjective(word):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    return len(synsets) > 0

def get_related_words(word, train_of_thought=[]):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    related_words = []
    raw_words = []
    
    for synset in synsets:
        synonyms = [lemma.name().replace('_', '') for lemma in synset.lemmas()][:5]
        raw_words.extend(synonyms)
        for w in synonyms:
            related_words.append({'word': w, 'reason': f"is a synonym of {word}", 'relation_type': 'synonym'})
        
        hyponyms = [hyponym.lemmas()[0].name().replace('_', '') for hyponym in synset.hyponyms()][:20]
        raw_words.extend(hyponyms)
        for w in hyponyms:
            related_words.append({'word': w, 'reason': f"is a type of {word}", 'relation_type': 'hyponym'})
        
        hypernyms = [hypernym.lemmas()[0].name().replace('_', '') for hypernym in synset.hypernyms()][:10]
        raw_words.extend(hypernyms)
        for w in hypernyms:
            related_words.append({'word': w, 'reason': f"is a more general category than {word}", 'relation_type': 'hypernym'})
        
        for hypernym in synset.hypernyms():
            sisters = [sister.lemmas()[0].name().replace('_', '') for sister in hypernym.hyponyms() if sister != synset][:3]
            raw_words.extend(sisters)
            for w in sisters:
                related_words.append({'word': w, 'reason': f"is related to {word} via common parent", 'relation_type': 'sister'})
    
    raw_words = list(set(raw_words))
    if raw_words:
        train_of_thought.append(raw_words)
    
    return related_words[:25]

def are_words_related(word1, word2):
    return scorer.are_words_related(word1, word2)

def score_word(word, original_word, relation_type, similarity):
    return scorer.score_word(word, original_word, relation_type, similarity)

def get_best_related_word(word, train_of_thought, game_state):
    # 1 get all raw words and related words
    related_objects = get_related_words(word)
    all_words = list(set(w['word'].replace('_', '') for w in related_objects))
    train_of_thought.append(sorted(all_words))
    
    # 2 filter nouns and adjectives
    related_words = [w for w in all_words if is_noun_or_adjective(w)]
    if related_words and set(related_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(related_words))
    
    # 3 filter valid words (no RTS, alphanumeric)
    valid_words = [w for w in related_words if is_valid_word(w)[0]]
    if valid_words and set(valid_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(valid_words))
    
    # 4 filter unused words
    unused_words = [w for w in valid_words if w.lower() not in game_state.word_history]
    if unused_words and set(unused_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(unused_words))
    
    # 5 filter variations
    non_variations = [w for w in unused_words if not is_word_contained(word, w)]
    if non_variations and set(non_variations) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(non_variations))
    
    # 6 filter by similarity threshold and score words
    scored_words = []
    for w in non_variations:
        synsets1 = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
        synsets2 = wordnet.synsets(w, pos=[wordnet.NOUN, wordnet.ADJ])
        similarity = max((s1.path_similarity(s2) or 0) 
                        for s1 in synsets1 
                        for s2 in synsets2) if synsets1 and synsets2 else 0
        
        if similarity >= 0.2:
            candidate = next((obj for obj in related_objects if obj['word'] == w), None)
            if candidate:
                score = score_word(w, word, candidate['relation_type'], similarity)
                scored_words.append({
                    'word': w,
                    'reason': candidate['reason'],
                    'score': score,
                    'similarity': similarity
                })
    
    if not scored_words:
        return None
        
    # sort by score and get words
    scored_words.sort(key=lambda x: x['score'], reverse=True)
    similar_words = [w['word'] for w in scored_words]
    if similar_words and set(similar_words) != set(train_of_thought[-1]):
        train_of_thought.append(sorted(similar_words))
    
    # final selected word
    selected_word = [scored_words[0]['word']]
    train_of_thought.append(selected_word)
    
    return scored_words[0]

def get_word_definition(word):
    synsets = wordnet.synsets(word, pos=[wordnet.NOUN, wordnet.ADJ])
    if not synsets:
        return "i don't know what that means"
    
    scored_defs = []
    for synset in synsets:
        score = 0
        definition = synset.definition().lower()
        score += len(synset.lemmas()) * 3
        score += (len(synsets) - synsets.index(synset)) * 2
        if any(indicator in definition for indicator in CONCRETE_INDICATORS):
            score += 2
        if any(keyword in definition for keyword in ABSTRACT_KEYWORDS):
            score -= 5
        if is_concrete_by_hypernyms(synset):
            score += 2
        scored_defs.append((score, definition))
    
    scored_defs.sort(key=lambda x: x[0], reverse=True)
    definitions = [f"{i+1}. {definition.capitalize()}" for i, (_, definition) in enumerate(scored_defs)]
    return "\n".join(definitions)

def get_contextual_definition(word1, word2, reason):
    synsets1 = wordnet.synsets(word1, pos=[wordnet.NOUN, wordnet.ADJ])
    synsets2 = wordnet.synsets(word2, pos=[wordnet.NOUN, wordnet.ADJ])
    
    if not synsets1 or not synsets2:
        return get_word_definition(word2)
    
    best_pair = None
    max_similarity = 0
    for s1 in synsets1:
        for s2 in synsets2:
            similarity = s1.path_similarity(s2) or 0
            if similarity > max_similarity:
                max_similarity = similarity
                best_pair = (s1, s2)
    
    if best_pair:
        definition = best_pair[1].definition()
        return f"In relation to '{word1}', '{word2}' {reason} - {definition}"
    
    return get_word_definition(word2)

def is_valid_word(word):
    if not word:
        return False, " "
    # if word.lower()[0] in ['r', 't', 's']:
    #     return False, "rts"
    if not word.isalpha():
        return False, f"{word} doesn't count ,(doesn't count"
    if not is_noun_or_adjective(word):
        return False, f"{word} doesn't count"
    return True, "Valid word"

def is_word_contained(word1, word2):
    word1, word2 = word1.lower(), word2.lower()
    
    if word1 == word2:
        return True
    
    suffixes = [
        ('s', ''),
        ('es', ''),
        ('ies', 'y'),
        ('ing', ''),
        ('ed', ''),
        ('er', ''),
        ('est', '')
    ]
    
    for suffix, replacement in suffixes:
        if word1.endswith(suffix):
            stem1 = word1[:-len(suffix)] + replacement
            if stem1 == word2:
                return True
        if word2.endswith(suffix):
            stem2 = word2[:-len(suffix)] + replacement
            if stem2 == word1:
                return True
                
    return False