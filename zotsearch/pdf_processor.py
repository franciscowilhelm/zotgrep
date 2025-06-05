"""
PDF processing module for ZotSearch.

This module handles PDF text extraction, file handling, and text cleaning.
"""

import io
import os
import re
from typing import Dict, Optional, Union
import pypdfium2 as pdfium


class PDFProcessor:
    """Handles PDF text extraction and processing."""
    
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
                raw_text = textpage.get_text_range()
                
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
        
        # Remove excessive whitespace but preserve paragraph breaks
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', raw_text)  # Normalize paragraph breaks
        cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)   # Normalize spaces
        
        return cleaned_text
    
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