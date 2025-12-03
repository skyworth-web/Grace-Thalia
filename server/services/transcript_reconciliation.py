# server/services/transcript_reconciliation.py

import time
import re
from collections import deque
from typing import Tuple, List

# Transcript buffer for reconciliation (session-based)
_transcript_buffer = deque(maxlen=50)  # Keep last 50 transcripts
_reconciled_text = ""  # Current reconciled transcript
_buffer_window = 3.0  # 3 seconds window for reconciliation


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    normalized = re.sub(r'[^\w\s]', '', text.lower())
    normalized = ' '.join(normalized.split())
    return normalized


def _normalize_word(word: str) -> str:
    """Normalize a single word for comparison."""
    return word.lower().strip(".,!?;:\"'()[]{}")


def _find_best_overlap(existing_words: list, new_words: list) -> int:
    """Find the best overlap point between existing and new words."""
    if not existing_words or not new_words:
        return 0
    
    max_overlap = min(len(existing_words), len(new_words), 12)
    
    for overlap_len in range(max_overlap, 0, -1):
        existing_suffix = existing_words[-overlap_len:]
        new_prefix = new_words[:overlap_len]
        
        existing_normalized = [_normalize_word(w) for w in existing_suffix]
        new_normalized = [_normalize_word(w) for w in new_prefix]
        
        matches = sum(1 for e, n in zip(existing_normalized, new_normalized) if e == n)
        match_ratio = matches / overlap_len if overlap_len > 0 else 0
        
        if match_ratio >= 0.8:
            return overlap_len
    
    return 0


def _reconcile_transcripts() -> Tuple[str, str]:
    """
    Reconcile overlapping transcripts and return clean text.
    Returns: (display_text, full_transcript)
    """
    global _reconciled_text
    
    if not _transcript_buffer:
        _reconciled_text = ""
        return "", ""
    
    current_time = time.time()
    cutoff_time = current_time - _buffer_window
    
    # Clean old transcripts
    valid_transcripts = [(ts, txt) for ts, txt in _transcript_buffer if ts >= cutoff_time]
    
    if not valid_transcripts:
        _reconciled_text = ""
        return "", ""
    
    # Sort by timestamp
    sorted_transcripts = sorted(valid_transcripts, key=lambda x: x[0])
    
    # Reconcile: merge overlapping transcripts
    reconciled_words = []
    
    for ts, text in sorted_transcripts:
        words = text.split()
        
        if not reconciled_words:
            reconciled_words = words
            continue
        
        # Find overlap
        best_overlap = _find_best_overlap(reconciled_words, words)
        
        if best_overlap > 0:
            # Found overlap - merge
            overlap_start = len(reconciled_words) - best_overlap
            # Replace overlapping words with newer version
            for i, new_word in enumerate(words[:best_overlap]):
                if overlap_start + i < len(reconciled_words):
                    reconciled_words[overlap_start + i] = new_word
            
            # Add new words after overlap
            if best_overlap < len(words):
                reconciled_words.extend(words[best_overlap:])
        else:
            # No overlap - check if it's a correction
            if len(words) > 0 and len(reconciled_words) > 0:
                first_new_word = _normalize_text(words[0])
                last_words = [_normalize_text(w) for w in reconciled_words[-8:]]
                
                if first_new_word in last_words:
                    # Likely a correction - replace from that point
                    idx = last_words.index(first_new_word)
                    replace_start = len(reconciled_words) - (len(last_words) - idx)
                    reconciled_words = reconciled_words[:replace_start] + words
                else:
                    # New text - append
                    reconciled_words.extend(words)
            else:
                reconciled_words.extend(words)
    
    # Remove duplicates: filter out repeated phrases
    if len(reconciled_words) > 0:
        # Check for repeated sequences
        final_words = []
        seen_phrases = set()
        
        for i in range(len(reconciled_words)):
            # Check if this word starts a repeated phrase
            phrase_len = min(5, len(reconciled_words) - i)
            if phrase_len > 0:
                phrase = " ".join(reconciled_words[i:i+phrase_len]).lower()
                if phrase not in seen_phrases:
                    final_words.append(reconciled_words[i])
                    seen_phrases.add(phrase)
                else:
                    # Skip this word if it's part of a repeated phrase
                    continue
            else:
                final_words.append(reconciled_words[i])
        
        reconciled_words = final_words
    
    _reconciled_text = " ".join(reconciled_words)
    
    # Return last 60 words for display
    display_words = reconciled_words[-60:] if len(reconciled_words) > 60 else reconciled_words
    display_text = " ".join(display_words)
    
    return display_text, _reconciled_text


def is_duplicate_transcript(text: str) -> bool:
    """Check if this transcript is a duplicate of recent ones."""
    if not text or not text.strip():
        return True
    
    current_time = time.time()
    cutoff_time = current_time - 2.0  # Check last 2 seconds
    
    new_normalized = _normalize_text(text)
    
    for ts, existing_text in _transcript_buffer:
        if ts >= cutoff_time:
            existing_normalized = _normalize_text(existing_text)
            # Check if texts are very similar
            if new_normalized == existing_normalized or \
               (len(new_normalized) > 10 and new_normalized in existing_normalized) or \
               (len(existing_normalized) > 10 and existing_normalized in new_normalized):
                return True
    
    return False


def add_transcript(text: str) -> Tuple[str, str]:
    """
    Add a transcript to the buffer and return reconciled text.
    Returns: (display_text, full_transcript)
    """
    if not text or not text.strip():
        return _reconcile_transcripts()
    
    # Check for duplicates
    if is_duplicate_transcript(text):
        return _reconcile_transcripts()
    
    # Add to buffer with timestamp
    current_time = time.time()
    _transcript_buffer.append((current_time, text.strip()))
    
    # Reconcile and return
    return _reconcile_transcripts()


def clear_buffer():
    """Clear the transcript buffer."""
    global _transcript_buffer, _reconciled_text
    _transcript_buffer.clear()
    _reconciled_text = ""

