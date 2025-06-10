from .utils_wordnet import get_wordnet_relations, is_valid_word, is_word_contained
from .utils_trained import get_trained_relations
from .config_constants import get_constant

def get_best_related_word(word, train_of_thought, game_state):
    active_model = get_constant('ACTIVE_MODEL')
    
    related_words = []
    
    if active_model == 'trained_wordnet':
        # First try trained model
        trained_words = get_trained_relations(word, train_of_thought)
        if trained_words:
            related_words = trained_words
            if train_of_thought is not None:
                train_of_thought.append(["Using trained model first"])
        
        # If no trained words found, fallback to WordNet
        if not related_words:
            wordnet_words = get_wordnet_relations(word, train_of_thought)
            if wordnet_words:
                related_words = wordnet_words
                if train_of_thought is not None:
                    train_of_thought.append(["Falling back to WordNet model"])
    
    elif active_model == 'wordnet':
        wordnet_words = get_wordnet_relations(word, train_of_thought)
        if wordnet_words:
            related_words = wordnet_words
    elif active_model == 'trained':
        trained_words = get_trained_relations(word, train_of_thought)
        if trained_words:
            related_words = trained_words
        
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
            train_of_thought.append([f"Using {best_word.get('source', 'unknown')} model"])
        
        return best_word
    
    return None