"""
Text analysis module for ZotGrep.

This module handles text processing, search term matching, context extraction,
and text highlighting functionality.
"""

import importlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FullTextTerm:
    """A single searchable full-text term or phrase."""

    raw: str
    pattern: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        normalized = self.raw.strip()
        if not normalized:
            raise ValueError("Full-text terms cannot be empty.")
        object.__setattr__(self, "raw", normalized)
        object.__setattr__(self, "pattern", compile_full_text_term_pattern(normalized))

    def matches(self, text: str) -> bool:
        return bool(self.pattern.search(text))


class FullTextNode:
    """Base class for full-text query AST nodes."""

    def evaluate(self, text: str) -> Optional[set[str]]:
        raise NotImplementedError


@dataclass(frozen=True)
class FullTextTermNode(FullTextNode):
    term: FullTextTerm

    def evaluate(self, text: str) -> Optional[set[str]]:
        if self.term.matches(text):
            return {self.term.raw}
        return None


@dataclass(frozen=True)
class FullTextAndNode(FullTextNode):
    left: FullTextNode
    right: FullTextNode

    def evaluate(self, text: str) -> Optional[set[str]]:
        left_match = self.left.evaluate(text)
        if left_match is None:
            return None
        right_match = self.right.evaluate(text)
        if right_match is None:
            return None
        return left_match | right_match


@dataclass(frozen=True)
class FullTextOrNode(FullTextNode):
    left: FullTextNode
    right: FullTextNode

    def evaluate(self, text: str) -> Optional[set[str]]:
        left_match = self.left.evaluate(text)
        right_match = self.right.evaluate(text)
        if left_match is None and right_match is None:
            return None
        return (left_match or set()) | (right_match or set())


@dataclass(frozen=True)
class FullTextQuery:
    """Parsed full-text query with ordered leaf terms."""

    raw: str
    root: FullTextNode
    terms: Tuple[FullTextTerm, ...]

    @property
    def leaf_terms(self) -> List[str]:
        return [term.raw for term in self.terms]

    def matching_terms(self, text: str) -> List[str]:
        matched = self.root.evaluate(text)
        if matched is None:
            return []
        return [term.raw for term in self.terms if term.raw in matched]

    def term_pattern(self, term: str) -> re.Pattern[str]:
        for candidate in self.terms:
            if candidate.raw == term:
                return candidate.pattern
        return compile_full_text_term_pattern(term)


def compile_full_text_term_pattern(term: str) -> re.Pattern[str]:
    """Compile a phrase or wildcard term into a safe regex."""
    stripped = term.strip()
    if not stripped:
        raise ValueError("Full-text terms cannot be empty.")

    pieces: List[str] = []
    for chunk_index, chunk in enumerate(re.split(r"(\s+)", stripped)):
        if not chunk:
            continue
        if chunk.isspace():
            pieces.append(r"\s+")
            continue

        token_parts = [re.escape(part) for part in chunk.split("*")]
        token_pattern = r"\w*".join(token_parts)
        if re.search(r"\w", chunk) and chunk[0].isalnum():
            token_pattern = r"\b" + token_pattern
        if re.search(r"\w", chunk) and chunk[-1].isalnum():
            token_pattern = token_pattern + r"\b"
        pieces.append(token_pattern)

    return re.compile("".join(pieces), re.IGNORECASE)


def metadata_query_uses_unsupported_operators(query: str) -> bool:
    """Detect operator-like syntax that Zotero quick search does not support."""
    return bool(re.search(r"\*|\bAND\b|\bOR\b", query or "", re.IGNORECASE))


class FullTextQueryParser:
    """Parse the simplified v1 full-text grammar."""

    _LEADING_OPERATOR_RE = re.compile(r"(?i)(AND|OR)\b")
    _NEXT_DELIMITER_RE = re.compile(r'(?i)\s+\b(?:AND|OR)\b(?=\s+|$|[(),"])|[(),"]')

    def __init__(self, query: str):
        self.query = query or ""
        self.tokens = self._tokenize(self.query)
        self.position = 0
        self.terms: List[FullTextTerm] = []

    def parse(self) -> FullTextQuery:
        if not self.query.strip():
            raise ValueError("Full-text query must provide at least one term.")

        root = self._parse_or()
        if self._peek() is not None:
            raise ValueError(f"Unexpected token '{self._peek()}'.")

        if not self.terms:
            raise ValueError("Full-text query must provide at least one term.")

        return FullTextQuery(
            raw=self.query,
            root=root,
            terms=tuple(self.terms),
        )

    def _tokenize(self, query: str) -> List[str]:
        tokens: List[str] = []
        position = 0
        while position < len(query):
            while position < len(query) and query[position].isspace():
                position += 1
            if position >= len(query):
                break

            current = query[position]
            if current in {"(", ")", ","}:
                tokens.append(current)
                position += 1
                continue

            if current == '"':
                closing_quote = query.find('"', position + 1)
                if closing_quote == -1:
                    raise ValueError("Unterminated quoted phrase in full-text query.")
                tokens.append(query[position:closing_quote + 1])
                position = closing_quote + 1
                continue

            operator_match = self._LEADING_OPERATOR_RE.match(query[position:])
            if operator_match:
                tokens.append(operator_match.group(1).upper())
                position += operator_match.end()
                continue

            delimiter_match = self._NEXT_DELIMITER_RE.search(query, position)
            next_position = delimiter_match.start() if delimiter_match else len(query)
            term = query[position:next_position].strip()
            if not term:
                remaining = query[position:].strip()
                raise ValueError(f"Invalid full-text query near '{remaining}'.")
            tokens.append(term)
            position = next_position

        return [token for token in tokens if token]

    def _peek(self) -> Optional[str]:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _consume(self) -> str:
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of full-text query.")
        self.position += 1
        return token

    def _parse_or(self) -> FullTextNode:
        node = self._parse_and()
        while True:
            token = self._peek()
            if token is None or not self._is_or(token):
                return node
            self._consume()
            node = FullTextOrNode(node, self._parse_and())

    def _parse_and(self) -> FullTextNode:
        node = self._parse_term()
        while True:
            token = self._peek()
            if token is None or not self._is_and(token):
                return node
            self._consume()
            node = FullTextAndNode(node, self._parse_term())

    def _parse_term(self) -> FullTextNode:
        token = self._peek()
        if token is None:
            raise ValueError("Full-text query cannot end with an operator.")
        if token in {"(", ")"}:
            raise ValueError("Parentheses are not supported in full-text queries.")
        if self._is_operator(token):
            raise ValueError(f"Expected a search term before '{token}'.")

        raw_term = self._consume()
        if raw_term.startswith('"'):
            raw_term = raw_term[1:-1]
        term = FullTextTerm(raw_term)
        self.terms.append(term)
        return FullTextTermNode(term)

    def _is_operator(self, token: str) -> bool:
        return self._is_and(token) or self._is_or(token)

    def _is_and(self, token: str) -> bool:
        return token.upper() == "AND"

    def _is_or(self, token: str) -> bool:
        return token == "," or token.upper() == "OR"


def parse_full_text_query(query: str | List[str] | FullTextQuery) -> FullTextQuery:
    """Normalize incoming full-text input into a parsed query."""
    if isinstance(query, FullTextQuery):
        return query
    if isinstance(query, list):
        normalized_terms = [term.strip() for term in query if term and term.strip()]
        if not normalized_terms:
            raise ValueError("Full-text query must provide at least one term.")
        return FullTextQueryParser(" OR ".join(normalized_terms)).parse()
    return FullTextQueryParser(query).parse()


class TextAnalyzer:
    """Handles text analysis, search, and context extraction."""

    _FALLBACK_SENTENCE_BOUNDARY_RE = re.compile(r'[.!?]+(?:["\')\]]+)?')
    _FALLBACK_ABBREVIATIONS = {
        "al",
        "approx",
        "art",
        "ca",
        "cf",
        "ch",
        "dr",
        "e.g",
        "eq",
        "etc",
        "fig",
        "i.e",
        "jr",
        "mr",
        "mrs",
        "ms",
        "no",
        "nos",
        "p",
        "pp",
        "prof",
        "sr",
        "st",
        "vs",
    }
    _PLAUSIBLE_SENTENCE_START_RE = re.compile(r'^(?:["\'\(\[]?[A-Z0-9])')
    _WORD_RE = re.compile(r'\w+')

    def __init__(self, context_sentence_window: int = 2):
        """
        Initialize text analyzer.

        Args:
            context_sentence_window: Number of sentences before and after match
        """
        self.context_sentence_window = context_sentence_window
        self._pysbd_module = None
        self._pysbd_import_attempted = False
        self._segmenters: Dict[str, Any] = {}

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
        sentences = self.tokenize_sentences(text)

        for i, sentence in enumerate(sentences):
            if compile_full_text_term_pattern(term).search(sentence):
                start_idx = max(0, i - sentence_window)
                end_idx = min(len(sentences), i + sentence_window + 1)

                context_sentences = sentences[start_idx:end_idx]
                context_text = ' '.join(context_sentences)
                contexts.append(self._highlight_term(context_text, term))

        return contexts

    def find_context_sentences_detailed(
        self,
        sentences_list: List[str],
        term: str,
        sentence_window: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Find a term in a list of pre-tokenized sentences and return detailed data.
        """
        if sentence_window is None:
            sentence_window = self.context_sentence_window
        return self._find_context_blocks_detailed(sentences_list, term, sentence_window)

    def build_page_contexts(
        self,
        text: str,
        terms: List[str] | FullTextQuery,
        language: Optional[str] = None,
        sentence_window: Optional[int] = None,
        char_window: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Build the best available contexts for a page.

        Sentence windows are preferred when the page text looks prose-like.
        Noisy pages fall back to paragraph contexts, then character snippets.
        """
        if not text.strip() or not terms:
            return []

        if sentence_window is None:
            sentence_window = self.context_sentence_window

        query = parse_full_text_query(terms)
        matched_terms = query.matching_terms(text)
        if not matched_terms:
            return []

        sentences = self.tokenize_sentences(text, language=language)
        if sentences and not self._page_looks_noisy(text, sentences):
            sentence_contexts = self._build_block_contexts(sentences, matched_terms, sentence_window, query)
            if sentence_contexts:
                return sentence_contexts

        paragraphs = self._split_paragraphs(text)
        paragraph_contexts = self._build_block_contexts(paragraphs, matched_terms, 0, query)
        if paragraph_contexts:
            return paragraph_contexts

        return self._build_character_contexts(text, matched_terms, char_window, query)

    def find_context(self, text: str, term: str, window_chars: int = 300) -> List[str]:
        """
        Find a term in text and return a character-based snippet around it.
        """
        contexts = []
        term_pattern = compile_full_text_term_pattern(term)

        for match in term_pattern.finditer(text):
            start, end = match.span()
            context_start, context_end = self._context_span_from_match(text, start, end, window_chars)

            snippet = text[context_start:context_end].strip()
            if context_start > 0:
                snippet = f"...{snippet}"
            if context_end < len(text):
                snippet = f"{snippet}..."

            highlighted_snippet = self._highlight_term(snippet, term)
            contexts.append(highlighted_snippet)

        return contexts

    def _highlight_term(self, text: str, term: str) -> str:
        """Highlight a term in text with *** markers."""
        term_pattern = compile_full_text_term_pattern(term)
        return term_pattern.sub(lambda match: f"***{match.group(0)}***", text)

    def highlight_multiple_terms(
        self,
        text: str,
        terms: List[str],
        query: Optional[FullTextQuery] = None,
    ) -> str:
        """Highlight multiple terms in text with *** markers."""
        highlighted_text = text

        for term in sorted(terms, key=len, reverse=True):
            term_pattern = query.term_pattern(term) if query else compile_full_text_term_pattern(term)
            highlighted_text = term_pattern.sub(
                lambda m: f"***{m.group(0)}***",
                highlighted_text,
            )

        return highlighted_text

    def merge_overlapping_contexts(
        self,
        page_hits: List[Dict[str, Any]],
        all_page_blocks: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Merge overlapping or adjacent block windows.
        """
        if not page_hits:
            return []

        page_hits.sort(key=lambda x: (x['sentence_indices'][0], x['sentence_indices'][1]))
        merged_intervals = []
        current_interval_info = {
            'start_sentence_idx': page_hits[0]['sentence_indices'][0],
            'end_sentence_idx': page_hits[0]['sentence_indices'][1],
            'terms': {page_hits[0]['term']},
        }

        for hit in page_hits[1:]:
            hit_start_idx, hit_end_idx = hit['sentence_indices']

            if hit_start_idx <= current_interval_info['end_sentence_idx'] + 1:
                current_interval_info['end_sentence_idx'] = max(
                    current_interval_info['end_sentence_idx'],
                    hit_end_idx,
                )
                current_interval_info['terms'].add(hit['term'])
                continue

            merged_intervals.append(
                self._finalize_block_interval(current_interval_info, all_page_blocks)
            )
            current_interval_info = {
                'start_sentence_idx': hit_start_idx,
                'end_sentence_idx': hit_end_idx,
                'terms': {hit['term']},
            }

        merged_intervals.append(self._finalize_block_interval(current_interval_info, all_page_blocks))
        return merged_intervals

    def tokenize_sentences(self, text: str, language: Optional[str] = None) -> List[str]:
        """
        Tokenize text into sentences using pySBD or a regex fallback.
        """
        if not text.strip():
            return []

        normalized_language = self._normalize_language(language)
        sentences = self._tokenize_with_pysbd(text, normalized_language)
        if sentences is not None:
            return sentences

        return self._tokenize_with_regex_fallback(text)

    def _load_pysbd(self):
        """Load pysbd lazily so regex fallback still works without the package."""
        if self._pysbd_import_attempted:
            return self._pysbd_module

        self._pysbd_import_attempted = True
        try:
            self._pysbd_module = importlib.import_module("pysbd")
        except ModuleNotFoundError:
            self._pysbd_module = None
        return self._pysbd_module

    def _tokenize_with_pysbd(
        self,
        text: str,
        normalized_language: Optional[str],
    ) -> Optional[List[str]]:
        pysbd_module = self._load_pysbd()
        if pysbd_module is None:
            return None

        languages_to_try = []
        if normalized_language:
            languages_to_try.append(normalized_language)
        if "en" not in languages_to_try:
            languages_to_try.append("en")

        for candidate_language in languages_to_try:
            segmenter = self._get_pysbd_segmenter(pysbd_module, candidate_language)
            if segmenter is None:
                continue

            try:
                sentences = segmenter.segment(text)
            except Exception:
                continue

            return self._clean_tokenized_sentences(sentences)

        return None

    def _get_pysbd_segmenter(self, pysbd_module: Any, language: str) -> Optional[Any]:
        if language in self._segmenters:
            return self._segmenters[language]

        try:
            segmenter = pysbd_module.Segmenter(language=language, clean=False)
        except Exception:
            return None

        self._segmenters[language] = segmenter
        return segmenter

    def _normalize_language(self, language: Optional[str]) -> Optional[str]:
        if not language:
            return None

        normalized = language.strip().replace("_", "-").lower()
        if not normalized:
            return None

        primary_subtag = normalized.split("-", 1)[0]
        return primary_subtag or None

    def _tokenize_with_regex_fallback(self, text: str) -> List[str]:
        sentences = []
        sentence_start = 0

        for match in self._FALLBACK_SENTENCE_BOUNDARY_RE.finditer(text):
            boundary_end = match.end()
            next_index = boundary_end
            while next_index < len(text) and text[next_index].isspace():
                next_index += 1

            if not self._is_sentence_boundary(text, match.start(), next_index):
                continue

            sentence = text[sentence_start:boundary_end].strip()
            if sentence:
                sentences.append(sentence)
            sentence_start = next_index

        trailing_text = text[sentence_start:].strip()
        if trailing_text:
            sentences.append(trailing_text)

        return sentences

    def _is_sentence_boundary(self, text: str, punctuation_index: int, next_index: int) -> bool:
        if punctuation_index > 0 and punctuation_index + 1 < len(text):
            if text[punctuation_index - 1].isdigit() and text[punctuation_index + 1].isdigit():
                return False

        token_match = re.search(r'([A-Za-z][A-Za-z.]*)$', text[:punctuation_index])
        if token_match:
            token = token_match.group(1).rstrip(".").lower()
            token_parts = [part for part in token.split(".") if part]
            if token in self._FALLBACK_ABBREVIATIONS:
                return False
            if token_parts and all(len(part) == 1 for part in token_parts):
                return False

        if next_index >= len(text):
            return True

        next_char = text[next_index]
        return next_char.isupper() or next_char.isdigit() or next_char in {'"', "'", "(", "["}

    def _build_block_contexts(
        self,
        blocks: List[str],
        terms: List[str],
        block_window: int,
        query: FullTextQuery,
    ) -> List[Dict[str, Any]]:
        if not blocks:
            return []

        page_hits = []
        for term in terms:
            page_hits.extend(self._find_context_blocks_detailed(blocks, term, block_window, query))

        if not page_hits:
            return []

        return self.merge_overlapping_contexts(page_hits, blocks)

    def _find_context_blocks_detailed(
        self,
        blocks: List[str],
        term: str,
        block_window: int,
        query: Optional[FullTextQuery] = None,
    ) -> List[Dict[str, Any]]:
        contexts_data = []
        term_pattern_search = query.term_pattern(term) if query else compile_full_text_term_pattern(term)

        for i, block in enumerate(blocks):
            if term_pattern_search.search(block):
                start_idx = max(0, i - block_window)
                end_idx_exclusive = min(len(blocks), i + block_window + 1)
                contexts_data.append(
                    {
                        'term': term,
                        'sentence_indices': (start_idx, end_idx_exclusive - 1),
                    }
                )

        return contexts_data

    def _finalize_block_interval(
        self,
        current_interval_info: Dict[str, Any],
        all_page_blocks: List[str],
    ) -> Dict[str, Any]:
        start_idx = current_interval_info['start_sentence_idx']
        end_idx_inclusive = current_interval_info['end_sentence_idx']
        context_text_list = all_page_blocks[start_idx:end_idx_inclusive + 1]
        return {
            'sentence_indices': (start_idx, end_idx_inclusive),
            'terms_found': sorted(list(current_interval_info['terms'])),
            'context_text_unhighlighted': ' '.join(context_text_list),
        }

    def _split_paragraphs(self, text: str) -> List[str]:
        paragraphs = []

        for block in re.split(r'\n{2,}', text):
            for line in block.split('\n'):
                normalized = re.sub(r'\s+', ' ', line).strip()
                if normalized:
                    paragraphs.append(normalized)

        return paragraphs

    def _page_looks_noisy(self, text: str, sentences: List[str]) -> bool:
        if not sentences:
            return True

        residual_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(residual_lines) <= 1:
            return False

        short_sentence_ratio = (
            sum(len(self._WORD_RE.findall(sentence)) <= 4 for sentence in sentences) / len(sentences)
        )
        plausible_start_ratio = (
            sum(self._is_plausible_sentence_start(sentence) for sentence in sentences) / len(sentences)
        )
        fragmented_line_ratio = (
            sum(len(self._WORD_RE.findall(line)) <= 6 for line in residual_lines) / len(residual_lines)
        )
        newline_density = len(residual_lines) / max(len(sentences), 1)

        if newline_density >= 1.4 and fragmented_line_ratio >= 0.45:
            return True
        if short_sentence_ratio >= 0.45 and plausible_start_ratio < 0.7:
            return True
        if len(residual_lines) >= 6 and plausible_start_ratio < 0.55:
            return True

        return False

    def _is_plausible_sentence_start(self, sentence: str) -> bool:
        stripped = sentence.strip()
        if not stripped:
            return False
        return bool(self._PLAUSIBLE_SENTENCE_START_RE.match(stripped))

    def _build_character_contexts(
        self,
        text: str,
        terms: List[str],
        window_chars: int,
        query: FullTextQuery,
    ) -> List[Dict[str, Any]]:
        page_hits = []

        for term in terms:
            term_pattern_search = query.term_pattern(term)
            for match in term_pattern_search.finditer(text):
                context_start, context_end = self._context_span_from_match(
                    text,
                    match.start(),
                    match.end(),
                    window_chars,
                )
                page_hits.append(
                    {
                        'term': term,
                        'char_indices': (context_start, context_end),
                    }
                )

        if not page_hits:
            return []

        page_hits.sort(key=lambda x: (x['char_indices'][0], x['char_indices'][1]))
        merged_intervals = []
        current_interval_info = {
            'start_char_idx': page_hits[0]['char_indices'][0],
            'end_char_idx': page_hits[0]['char_indices'][1],
            'terms': {page_hits[0]['term']},
        }

        for hit in page_hits[1:]:
            hit_start_idx, hit_end_idx = hit['char_indices']
            if hit_start_idx <= current_interval_info['end_char_idx'] + 1:
                current_interval_info['end_char_idx'] = max(
                    current_interval_info['end_char_idx'],
                    hit_end_idx,
                )
                current_interval_info['terms'].add(hit['term'])
                continue

            merged_intervals.append(self._finalize_character_interval(current_interval_info, text))
            current_interval_info = {
                'start_char_idx': hit_start_idx,
                'end_char_idx': hit_end_idx,
                'terms': {hit['term']},
            }

        merged_intervals.append(self._finalize_character_interval(current_interval_info, text))
        return merged_intervals

    def _finalize_character_interval(
        self,
        current_interval_info: Dict[str, Any],
        text: str,
    ) -> Dict[str, Any]:
        start_idx = current_interval_info['start_char_idx']
        end_idx = current_interval_info['end_char_idx']
        context_text = text[start_idx:end_idx].strip()

        if start_idx > 0:
            context_text = f"...{context_text}"
        if end_idx < len(text):
            context_text = f"{context_text}..."

        return {
            'terms_found': sorted(list(current_interval_info['terms'])),
            'context_text_unhighlighted': context_text,
        }

    def _context_span_from_match(
        self,
        text: str,
        start: int,
        end: int,
        window_chars: int,
    ) -> Tuple[int, int]:
        context_start = max(0, start - window_chars)
        context_end = min(len(text), end + window_chars)

        para_start_search = text.rfind('\n', 0, start)
        if para_start_search != -1 and start - para_start_search < window_chars * 2:
            context_start = max(context_start, para_start_search + 1)

        para_end_search = text.find('\n', end)
        if para_end_search != -1 and para_end_search - end < window_chars * 2:
            context_end = min(context_end, para_end_search)

        return context_start, context_end

    def _clean_tokenized_sentences(self, sentences: List[str]) -> List[str]:
        return [sentence.strip() for sentence in sentences if sentence and sentence.strip()]


# Convenience functions for backward compatibility
def find_context_sentences(text: str, term: str, sentence_window: int = 3) -> List[str]:
    """Find context sentences (backward compatibility function)."""
    analyzer = TextAnalyzer(sentence_window)
    return analyzer.find_context_sentences(text, term, sentence_window)


def find_context_sentences_detailed(
    sentences_list: List[str],
    term: str,
    sentence_window: int = 2,
) -> List[Dict[str, Any]]:
    """Find detailed context sentences (backward compatibility function)."""
    analyzer = TextAnalyzer(sentence_window)
    return analyzer.find_context_sentences_detailed(sentences_list, term, sentence_window)


def find_context(text: str, term: str, window_chars: int = 300) -> List[str]:
    """Find character-based context (backward compatibility function)."""
    analyzer = TextAnalyzer()
    return analyzer.find_context(text, term, window_chars)
