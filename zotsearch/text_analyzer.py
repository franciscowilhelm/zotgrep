"""
Text analysis module for ZotSearch.

This module handles text processing, search term matching, context extraction,
and text highlighting functionality.
"""

import re
import nltk
from typing import List, Dict, Tuple, Any


class TextAnalyzer:
    """Handles text analysis, search, and context extraction."""
    
    def __init__(self, context_sentence_window: int = 2):
        """
        Initialize text analyzer.
        
        Args:
            context_sentence_window: Number of sentences before and after match
        """
        self.context_sentence_window = context_sentence_window
        self._setup_nltk()
    
    def _setup_nltk(self) -> None:
        """Setup NLTK dependencies."""
        try:
            nltk.data.find('tokenizers/punkt')
        except nltk.downloader.DownloadError:
            print("NLTK 'punkt' tokenizer not found. Downloading...")
            nltk.download('punkt')
        except LookupError:
            print("NLTK 'punkt' tokenizer seems to be missing or corrupted. Downloading...")
            nltk.download('punkt')
    
    def find_context_sentences(self, text: str, term: str, sentence_window: int = None) -> List[str]:
        """
        Find a term and return surrounding sentences.
        
        Args:
            text: Text to search in
            term: Search term
            sentence_window: Number of sentences before/after (uses default if None)
            
        Returns:
            List of context strings with highlighted terms
        """
        if sentence_window is None:
            sentence_window = self.context_sentence_window
            
        contexts = []
        sentences = nltk.sent_tokenize(text)
        
        for i, sentence in enumerate(sentences):
            if re.search(re.escape(term), sentence, re.IGNORECASE):
                start_idx = max(0, i - sentence_window)
                end_idx = min(len(sentences), i + sentence_window + 1)
                
                context_sentences = sentences[start_idx:end_idx]
                context_text = ' '.join(context_sentences)
                
                # Highlight the term
                highlighted_context = self._highlight_term(context_text, term)
                contexts.append(highlighted_context)
        
        return contexts
    
    def find_context_sentences_detailed(self, sentences_list: List[str], term: str, 
                                     sentence_window: int = None) -> List[Dict[str, Any]]:
        """
        Find a term in a list of pre-tokenized sentences and return detailed data.
        
        Args:
            sentences_list: List of sentences to search
            term: Search term
            sentence_window: Number of sentences before/after (uses default if None)
            
        Returns:
            List of dictionaries with term and sentence indices information
        """
        if sentence_window is None:
            sentence_window = self.context_sentence_window
            
        contexts_data = []
        # Use whole-word matching for the search term
        term_pattern_search = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)

        for i, sentence in enumerate(sentences_list):
            if term_pattern_search.search(sentence):
                start_idx = max(0, i - sentence_window)
                # end_idx is the index *after* the last sentence in the window
                end_idx_exclusive = min(len(sentences_list), i + sentence_window + 1)
                
                contexts_data.append({
                    'term': term,
                    # Store sentence indices as (inclusive_start, inclusive_end)
                    'sentence_indices': (start_idx, end_idx_exclusive - 1),
                })
        
        return contexts_data
    
    def find_context(self, text: str, term: str, window_chars: int = 300) -> List[str]:
        """
        Find a term in text and return a character-based snippet around it.
        
        Args:
            text: Text to search in
            term: Search term
            window_chars: Number of characters before/after the term
            
        Returns:
            List of context snippets with highlighted terms
        """
        contexts = []
        
        for match in re.finditer(re.escape(term), text, re.IGNORECASE):
            start, end = match.span()
            context_start = max(0, start - window_chars)
            context_end = min(len(text), end + window_chars)
            
            # Look for paragraph boundaries with more generous limits
            para_start_search = text.rfind('\n', 0, start)
            if para_start_search != -1 and start - para_start_search < window_chars * 2:
                context_start = max(context_start, para_start_search + 1)

            para_end_search = text.find('\n', end)
            if para_end_search != -1 and para_end_search - end < window_chars * 2:
                context_end = min(context_end, para_end_search)
                
            snippet = text[context_start:context_end]
            highlighted_snippet = self._highlight_term(snippet, match.group(0))
            contexts.append(f"...{highlighted_snippet}...")
        
        return contexts
    
    def _highlight_term(self, text: str, term: str) -> str:
        """
        Highlight a term in text with *** markers.
        
        Args:
            text: Text to highlight in
            term: Term to highlight
            
        Returns:
            Text with highlighted term
        """
        term_pattern = re.compile(re.escape(term), re.IGNORECASE)
        return term_pattern.sub(f"***{term}***", text)
    
    def highlight_multiple_terms(self, text: str, terms: List[str]) -> str:
        """
        Highlight multiple terms in text with *** markers.
        
        Args:
            text: Text to highlight in
            terms: List of terms to highlight
            
        Returns:
            Text with all terms highlighted
        """
        highlighted_text = text
        
        # Sort terms by length (descending) to handle overlapping terms correctly
        for term in sorted(terms, key=len, reverse=True):
            # Use word boundaries for highlighting to avoid partial highlights within words
            term_pattern = re.compile(r'\b(' + re.escape(term) + r')\b', re.IGNORECASE)
            highlighted_text = term_pattern.sub(lambda m: f"***{m.group(1)}***", highlighted_text)
        
        return highlighted_text
    
    def merge_overlapping_contexts(self, page_hits: List[Dict[str, Any]], 
                                 all_page_sentences: List[str]) -> List[Dict[str, Any]]:
        """
        Merge overlapping or adjacent sentence windows.
        
        Args:
            page_hits: List of hit dictionaries with sentence indices
            all_page_sentences: List of all sentences on the page
            
        Returns:
            List of merged interval dictionaries
        """
        if not page_hits:
            return []
        
        # Sort hits by start sentence index, then by end sentence index
        page_hits.sort(key=lambda x: (x['sentence_indices'][0], x['sentence_indices'][1]))
        
        merged_intervals = []
        
        # Initialize with the first hit
        current_interval_info = {
            'start_sentence_idx': page_hits[0]['sentence_indices'][0],
            'end_sentence_idx': page_hits[0]['sentence_indices'][1],
            'terms': {page_hits[0]['term']}
        }

        for i in range(1, len(page_hits)):
            hit = page_hits[i]
            hit_start_idx, hit_end_idx = hit['sentence_indices']

            # Check for overlap: if hit_start_idx is within or adjacent to current interval
            # Merge if hit_start_idx <= current_interval_info['end_sentence_idx'] + 1 (adjacency included)
            if hit_start_idx <= current_interval_info['end_sentence_idx'] + 1:
                current_interval_info['end_sentence_idx'] = max(current_interval_info['end_sentence_idx'], hit_end_idx)
                current_interval_info['terms'].add(hit['term'])
            else:
                # No overlap, current interval is complete. Add it to merged_intervals.
                start_idx = current_interval_info['start_sentence_idx']
                end_idx_inclusive = current_interval_info['end_sentence_idx']
                context_text_list = all_page_sentences[start_idx : end_idx_inclusive + 1]
                
                merged_intervals.append({
                    'sentence_indices': (start_idx, end_idx_inclusive),
                    'terms_found': sorted(list(current_interval_info['terms'])),
                    'context_text_unhighlighted': ' '.join(context_text_list)
                })
                
                # Start a new interval
                current_interval_info = {
                    'start_sentence_idx': hit_start_idx,
                    'end_sentence_idx': hit_end_idx,
                    'terms': {hit['term']}
                }
        
        # Add the last processed interval
        if current_interval_info:
            start_idx = current_interval_info['start_sentence_idx']
            end_idx_inclusive = current_interval_info['end_sentence_idx']
            context_text_list = all_page_sentences[start_idx : end_idx_inclusive + 1]
            merged_intervals.append({
                'sentence_indices': (start_idx, end_idx_inclusive),
                'terms_found': sorted(list(current_interval_info['terms'])),
                'context_text_unhighlighted': ' '.join(context_text_list)
            })

        return merged_intervals
    
    def tokenize_sentences(self, text: str) -> List[str]:
        """
        Tokenize text into sentences using NLTK.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of sentences
        """
        if not text.strip():
            return []
        
        return nltk.sent_tokenize(text)


# Convenience functions for backward compatibility
def find_context_sentences(text: str, term: str, sentence_window: int = 3) -> List[str]:
    """Find context sentences (backward compatibility function)."""
    analyzer = TextAnalyzer(sentence_window)
    return analyzer.find_context_sentences(text, term, sentence_window)


def find_context_sentences_detailed(sentences_list: List[str], term: str, 
                                  sentence_window: int = 2) -> List[Dict[str, Any]]:
    """Find detailed context sentences (backward compatibility function)."""
    analyzer = TextAnalyzer(sentence_window)
    return analyzer.find_context_sentences_detailed(sentences_list, term, sentence_window)


def find_context(text: str, term: str, window_chars: int = 300) -> List[str]:
    """Find character-based context (backward compatibility function)."""
    analyzer = TextAnalyzer()
    return analyzer.find_context(text, term, window_chars)