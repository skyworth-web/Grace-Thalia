# app/ui/utils/text_utils.py

import re


def normalize_text(text: str) -> str:
    """Normalize text for comparison (remove punctuation, lowercase, normalize spaces)."""
    normalized = re.sub(r'[^\w\s]', '', text.lower())
    normalized = ' '.join(normalized.split())
    return normalized


def normalize_word(word: str) -> str:
    """Normalize a single word for comparison."""
    return word.lower().strip(".,!?;:\"'()[]{}")


def find_best_overlap(existing_words: list, new_words: list) -> int:
    """
    Find the best overlap point between existing and new words.
    Returns the number of overlapping words (0 if no good overlap found).
    """
    if not existing_words or not new_words:
        return 0
    
    max_overlap = min(len(existing_words), len(new_words), 12)  # Check up to 12 words
    
    # Try to find the longest matching suffix-prefix
    for overlap_len in range(max_overlap, 0, -1):
        existing_suffix = existing_words[-overlap_len:]
        new_prefix = new_words[:overlap_len]
        
        # Normalize words for comparison
        existing_normalized = [normalize_word(w) for w in existing_suffix]
        new_normalized = [normalize_word(w) for w in new_prefix]
        
        # Check if they match (allowing for minor differences)
        matches = sum(1 for e, n in zip(existing_normalized, new_normalized) if e == n)
        match_ratio = matches / overlap_len if overlap_len > 0 else 0
        
        # Require at least 80% match for a valid overlap
        if match_ratio >= 0.8:
            return overlap_len
    
    return 0


def texts_similar(text1: str, text2: str) -> bool:
    """
    Check if two text strings are similar (for overlap detection).
    """
    if not text1 or not text2:
        return False
    
    # Check if one contains the other (for partial matches)
    if len(text1) > len(text2):
        return text2 in text1 or text1.startswith(text2[:min(len(text2), len(text1)//2)])
    else:
        return text1 in text2 or text2.startswith(text1[:min(len(text1), len(text2)//2)])

