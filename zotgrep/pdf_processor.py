"""
PDF processing module for ZotGrep.

This module handles PDF text extraction, file handling, and text cleaning.
"""

import io
import os
import re
from typing import Dict, Optional, Union
import pypdfium2 as pdfium


class PDFProcessor:
    """Handles PDF text extraction and processing."""

    _BULLET_RE = re.compile(r'^(?:[-*•◦▪■]|\(?\d+[\).]|\(?[A-Za-z][\).])\s+')
    _HEADING_RE = re.compile(r'^[A-Z0-9][A-Z0-9\s:/&,\-]{2,}$')
    _SOFT_WRAP_HYPHEN_RE = re.compile(r'[A-Za-z]-$')
    _CONTINUATION_START_RE = re.compile(r'^(?:[a-z0-9]|["\'\)\]\},;:])')
    _SENTENCE_END_RE = re.compile(r'[.!?]["\')\]]?$')

    def __init__(self):
        """Initialize PDF processor."""
        pass

    def extract_text_from_pdf_bytes(self, pdf_input: Union[str, io.BytesIO]) -> Optional[Dict[int, str]]:
        """
        Extract text from PDF bytes with better formatting preservation.
        
        Args:
            pdf_input: Either a file path (str) or BytesIO object containing PDF data
            
        Returns:
            Dictionary mapping page numbers (1-indexed) to extracted text,
            or None if extraction fails
        """
        text_by_page = {}
        
        try:
            pdf_doc = pdfium.PdfDocument(pdf_input)
            
            for i, page in enumerate(pdf_doc):
                textpage = page.get_textpage()
                # Get all text with potential formatting improvements
                # Use the current pypdfium2 default behavior explicitly.
                raw_text = textpage.get_text_bounded()
                
                # Clean and format the text
                cleaned_text = self._clean_pdf_text(raw_text)
                
                text_by_page[i + 1] = cleaned_text
                textpage.close()
                page.close()
                
            pdf_doc.close()
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
            return None
            
        return text_by_page
    
    def _clean_pdf_text(self, raw_text: str) -> str:
        """
        Clean and format extracted PDF text.

        Args:
            raw_text: Raw text extracted from PDF

        Returns:
            Cleaned and formatted text
        """
        if not raw_text:
            return ""

        normalized_text = self._normalize_whitespace(raw_text)
        return self._reflow_hard_wrapped_text(normalized_text)

    def _normalize_whitespace(self, raw_text: str) -> str:
        """Normalize whitespace while preserving paragraph breaks."""
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r'[ \t\f\v]+', ' ', text)
        text = re.sub(r' *\n *', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _reflow_hard_wrapped_text(self, text: str) -> str:
        """Repair likely PDF hard wraps without flattening structured text."""
        if not text:
            return ""

        blocks = []
        for raw_block in re.split(r'\n{2,}', text):
            lines = [line.strip() for line in raw_block.split('\n') if line.strip()]
            if not lines:
                continue
            blocks.append('\n'.join(self._reflow_block(lines)))

        return '\n\n'.join(blocks)

    def _reflow_block(self, lines: list[str]) -> list[str]:
        """Reflow a paragraph-like block line by line."""
        reflowed = [lines[0]]

        for line in lines[1:]:
            previous_line = reflowed[-1]
            join_mode = self._classify_line_join(previous_line, line)

            if join_mode == "join_hyphen":
                reflowed[-1] = previous_line[:-1] + line.lstrip()
            elif join_mode == "join_space":
                reflowed[-1] = f"{previous_line.rstrip()} {line.lstrip()}"
            else:
                reflowed.append(line)

        return reflowed

    def _classify_line_join(self, previous_line: str, next_line: str) -> str:
        """Decide whether to join two adjacent PDF lines."""
        if self._should_preserve_line_break(previous_line, next_line):
            return "preserve"

        if self._SOFT_WRAP_HYPHEN_RE.search(previous_line) and re.match(r'^[a-z]', next_line):
            return "join_hyphen"

        if self._CONTINUATION_START_RE.match(next_line):
            return "join_space"

        if not self._SENTENCE_END_RE.search(previous_line):
            return "join_space"

        return "preserve"

    def _should_preserve_line_break(self, previous_line: str, next_line: str) -> bool:
        """Keep boundaries for lines that look like structure rather than wrapped prose."""
        if self._looks_structural_line(previous_line) or self._looks_structural_line(next_line):
            return True

        if (
            self._looks_short_fragment(previous_line)
            and self._looks_short_fragment(next_line)
            and not self._CONTINUATION_START_RE.match(next_line)
        ):
            return True

        if self._SENTENCE_END_RE.search(previous_line) and self._looks_fresh_sentence_start(next_line):
            return True

        return False

    def _looks_structural_line(self, line: str) -> bool:
        if self._BULLET_RE.match(line):
            return True
        if self._HEADING_RE.match(line) and len(line.split()) <= 12:
            return True
        if line.endswith(':') and len(line.split()) <= 8:
            return True
        return False

    def _looks_short_fragment(self, line: str) -> bool:
        words = line.split()
        if not words:
            return False
        if len(words) <= 3 and len(line) <= 28:
            return True
        if len(line) <= 40 and not self._SENTENCE_END_RE.search(line):
            short_token_count = sum(len(word.strip('.,;:()[]')) <= 4 for word in words)
            return short_token_count >= max(2, len(words) - 1)
        return False

    def _looks_fresh_sentence_start(self, line: str) -> bool:
        stripped = line.lstrip()
        if not stripped:
            return False
        if self._BULLET_RE.match(stripped):
            return True
        return bool(re.match(r'^(?:["\'\(\[]?[A-Z0-9])', stripped))

    def process_linked_pdf(self, base_attachment_dir: str, relative_path: str) -> Optional[Dict[int, str]]:
        """
        Process a linked PDF file.
        
        Args:
            base_attachment_dir: Base directory for attachments
            relative_path: Relative path to the PDF file
            
        Returns:
            Dictionary mapping page numbers to text, or None if processing fails
        """
        # Handle Zotero path prefix
        path_prefix_to_strip = "attachments:"
        actual_relative_path = relative_path
        
        if relative_path.startswith(path_prefix_to_strip):
            actual_relative_path = relative_path[len(path_prefix_to_strip):]
        
        full_local_path = os.path.normpath(os.path.join(base_attachment_dir, actual_relative_path))
        
        if not os.path.exists(full_local_path):
            print(f"    ERROR: PDF file not found at {full_local_path}")
            return None
        
        try:
            return self.extract_text_from_pdf_bytes(full_local_path)
        except Exception as e:
            print(f"    Error reading or processing local PDF {full_local_path}: {e}")
            return None
    
    def process_imported_pdf(self, pdf_bytes_content: bytes) -> Optional[Dict[int, str]]:
        """
        Process an imported PDF from bytes content.
        
        Args:
            pdf_bytes_content: PDF content as bytes
            
        Returns:
            Dictionary mapping page numbers to text, or None if processing fails
        """
        if not pdf_bytes_content:
            return None
        
        try:
            pdf_bytes_io = io.BytesIO(pdf_bytes_content)
            return self.extract_text_from_pdf_bytes(pdf_bytes_io)
        except Exception as e:
            print(f"    Error processing imported PDF: {e}")
            return None
    
    def get_pdf_info(self, pdf_attachment_data: Dict) -> Dict[str, str]:
        """
        Extract PDF information from attachment data.
        
        Args:
            pdf_attachment_data: Zotero attachment data dictionary
            
        Returns:
            Dictionary with PDF information (key, filename, link_mode, path)
        """
        pdf_key = pdf_attachment_data.get('key', '')
        link_mode = pdf_attachment_data.get('linkMode', '')
        pdf_filename = pdf_attachment_data.get('filename', f"{pdf_key}.pdf")
        relative_path = pdf_attachment_data.get('path', '')
        
        return {
            'key': pdf_key,
            'filename': pdf_filename,
            'link_mode': link_mode,
            'path': relative_path
        }
    
    def is_pdf_attachment(self, attachment_data: Dict) -> bool:
        """
        Check if attachment is a PDF.
        
        Args:
            attachment_data: Zotero attachment data dictionary
            
        Returns:
            True if attachment is a PDF, False otherwise
        """
        return (
            attachment_data.get('itemType') == 'attachment' and
            attachment_data.get('contentType') == 'application/pdf'
        )


# Convenience function for backward compatibility
def extract_text_from_pdf_bytes(pdf_input: Union[str, io.BytesIO]) -> Optional[Dict[int, str]]:
    """
    Extract text from PDF bytes (backward compatibility function).
    
    Args:
        pdf_input: Either a file path (str) or BytesIO object containing PDF data
        
    Returns:
        Dictionary mapping page numbers to extracted text, or None if extraction fails
    """
    processor = PDFProcessor()
    return processor.extract_text_from_pdf_bytes(pdf_input)
