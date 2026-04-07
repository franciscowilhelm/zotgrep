"""
Search engine module for ZotGrep.

This module contains the core search logic that orchestrates Zotero metadata search,
PDF full-text search, and result processing.
"""

from typing import List, Dict, Any, Optional, Tuple
from pyzotero import zotero

from .config import ZotGrepConfig
from .pdf_processor import PDFProcessor
from .text_analyzer import TextAnalyzer
from .result_handler import ResultHandler


class ZoteroSearchEngine:
    """Main search engine that orchestrates the search process."""
    
    def __init__(self, config: ZotGrepConfig):
        """
        Initialize the search engine.
        
        Args:
            config: ZotGrep configuration object
        """
        self.config = config
        self.pdf_processor = PDFProcessor()
        self.text_analyzer = TextAnalyzer(config.context_sentence_window)
        self.result_handler = ResultHandler()
        self.zot_conn = None
        self.warnings: List[str] = []
        
    def connect_to_zotero(self) -> bool:
        """
        Connect to Zotero API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.zot_conn = zotero.Zotero(
                self.config.zotero_user_id,
                self.config.library_type,
                self.config.zotero_api_key,
                local=True,
            )
            
            # Test connection
            self.zot_conn.top(limit=1)
            print("Successfully connected to Zotero API.")
            return True
            
        except Exception as e:
            print(f"Failed to connect to Zotero API: {e}")
            return False
    
    def search_zotero_and_full_text(self, metadata_search_terms: str,
                                   full_text_search_terms: List[str],
                                   verbose: bool = False,
                                   include_abstract: bool = True,
                                   metadata_only: bool = False) -> List[Dict[str, Any]]:
        """
        Search Zotero metadata and full-text PDFs.
        
        Args:
            metadata_search_terms: Terms to search in Zotero metadata
            full_text_search_terms: Terms to search in PDF full text
            include_abstract: Whether to include item abstracts in results
            metadata_only: Whether to stop after metadata search
            verbose: If True, print detailed output. If False, print summary only.
            
        Returns:
            List of finding dictionaries
        """
        if not self.zot_conn:
            if not self.connect_to_zotero():
                return []
        
        # Stage 1: Search Zotero metadata
        items = self._search_metadata(metadata_search_terms)
        if not items:
            return []
        
        print(f"Found {len(items)} references matching metadata search.")

        if metadata_only or not full_text_search_terms:
            if metadata_only:
                print("Metadata-only mode enabled. Skipping PDF/full-text processing.")
            else:
                print("No full-text terms supplied. Returning metadata-only results.")
            return self._build_metadata_results(items, include_abstract=include_abstract)
        
        # Stage 2: Search full text in PDFs
        all_findings = []
        
        for item_index, item in enumerate(items):
            item_data = item.get('data', {})
            item_title = item_data.get('title', 'N/A')
            item_key = item_data.get('key', 'N/A')
            
            print(f"\n[{item_index + 1}/{len(items)}] Processing: '{item_title}'")
            
            # Process PDFs for this item
            findings, summary_lines = self._process_item_pdfs(
                item_data,
                full_text_search_terms,
                include_abstract=include_abstract,
                verbose=verbose
            )
            all_findings.extend(findings)
            if not verbose and summary_lines:
                for line in summary_lines:
                    print(line)
        
        return all_findings

    def _build_metadata_results(
        self,
        items: List[Dict[str, Any]],
        include_abstract: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Build metadata-only result rows from Zotero items.
        """
        return [
            self.result_handler.create_reference_result(
                item.get('data', {}),
                include_abstract=include_abstract
            )
            for item in items
        ]
    
    def _search_metadata(self, search_terms: str) -> List[Dict[str, Any]]:
        """
        Search Zotero metadata.
        
        Args:
            search_terms: Search terms for metadata
            
        Returns:
            List of Zotero items
        """
        print(f"--- Stage 1: Searching Zotero metadata for: '{search_terms}' ---")
        
        try:
            items = self.zot_conn.items(
                q=search_terms,
                itemType='-attachment',
                limit=self.config.max_results_stage1
            )

            items = self._filter_items_by_publication_title(items)
            
            if not items:
                print("No references found matching metadata search terms.")
                
            return items
            
        except Exception as e:
            print(f"Error during Zotero metadata search: {e}")
            return []

    def _filter_items_by_publication_title(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter items by publication title (client-side).
        """
        filters = self.config.publication_title_filter or []
        if not filters:
            return items

        if self.config.debug_publication_filter:
            print("Publication titles from matched metadata items:")
            for item in items:
                title = item.get('data', {}).get('title', 'N/A')
                pub_title = item.get('data', {}).get('publicationTitle', '') or ''
                print(f"  - {pub_title if pub_title else 'N/A'} | {title}")

        normalized_filters = [f.lower() for f in filters]
        filtered_items = []
        for item in items:
            pub_title = item.get('data', {}).get('publicationTitle', '') or ''
            pub_title_lower = pub_title.lower()
            if any(f in pub_title_lower for f in normalized_filters):
                filtered_items.append(item)

        print(f"Filtered {len(items)} items to {len(filtered_items)} by publication title.")
        return filtered_items
    
    def _process_item_pdfs(self, item_data: Dict[str, Any],
                          full_text_terms: List[str],
                          include_abstract: bool = False,
                          verbose: bool = False) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process PDFs for a single Zotero item.
        
        Args:
            item_data: Zotero item data
            full_text_terms: Terms to search in PDF text
            include_abstract: Whether to include item abstracts in results
            verbose: If True, print detailed output. If False, print summary only.
            
        Returns:
            Tuple: (List of findings for this item, List of summary lines)
        """
        item_key = item_data.get('key', 'N/A')
        item_title = item_data.get('title', 'N/A')
        
        try:
            attachments = self.zot_conn.children(item_key)
        except Exception as e:
            print(f"  Error fetching attachments for {item_key}: {e}")
            return [], []
        
        # Filter PDF attachments
        pdf_attachments = [
            att for att in attachments
            if self.pdf_processor.is_pdf_attachment(att.get('data', {}))
        ]
        
        if not pdf_attachments:
            print("  No processable PDF attachments found for this item.")
            return [], []
        
        findings = []
        found_text_in_item = False
        summary_counter = {}  # {filename: {term: count}}
        pdf_filenames = []
        
        for pdf_att in pdf_attachments:
            pdf_att_data = pdf_att.get('data', {})
            pdf_info = self.pdf_processor.get_pdf_info(pdf_att_data)
            pdf_filename = pdf_info.get('filename', 'N/A')
            pdf_filenames.append(pdf_filename)
            
            # Extract text from PDF
            text_by_page = self._extract_pdf_text(pdf_info, item_title)
            if not text_by_page:
                continue
            
            if not found_text_in_item:
                print(f"  --- Stage 2: Searching PDF(s) for '{item_title}' for: '{', '.join(full_text_terms)}' ---")
                found_text_in_item = True
            
            # Search each page
            page_findings, page_counter = self._search_pdf_pages(
                text_by_page, full_text_terms, item_data, pdf_info,
                include_abstract=include_abstract, verbose=verbose
            )
            findings.extend(page_findings)
            if not verbose:
                # Merge page_counter into summary_counter
                if pdf_filename not in summary_counter:
                    summary_counter[pdf_filename] = {}
                for term, count in page_counter.items():
                    summary_counter[pdf_filename][term] = summary_counter[pdf_filename].get(term, 0) + count
        
        summary_lines = []
        if not verbose and summary_counter:
            for pdf_filename, term_counts in summary_counter.items():
                for term, count in term_counts.items():
                    summary_lines.append(f"    Found '{term}' {count} times in '{pdf_filename}'.")
        
        return findings, summary_lines
    
    def _extract_pdf_text(self, pdf_info: Dict[str, str], item_title: str) -> Optional[Dict[int, str]]:
        """
        Extract text from PDF based on its type (linked or imported).
        
        Args:
            pdf_info: PDF information dictionary
            item_title: Title of the parent item
            
        Returns:
            Dictionary mapping page numbers to text, or None if extraction fails
        """
        link_mode = pdf_info['link_mode']
        
        if link_mode == 'linked_file':
            if not pdf_info['path']:
                return None
            if not self.config.base_attachment_path:
                warning = (
                    f"Skipping linked PDF {pdf_info['key']}: "
                    "BASE_ATTACHMENT_PATH is not configured."
                )
                self.warnings.append(warning)
                print(f"    {warning}")
                return None
            
            return self.pdf_processor.process_linked_pdf(
                self.config.base_attachment_path,
                pdf_info['path']
            )
            
        elif link_mode in {'imported_file', 'imported_url'}:
            try:
                pdf_bytes_content = self.zot_conn.file(pdf_info['key'])
                if not pdf_bytes_content:
                    return None
                
                return self.pdf_processor.process_imported_pdf(pdf_bytes_content)
                
            except Exception as e:
                print(f"    Error downloading or processing stored PDF {pdf_info['key']}: {e}")
                return None
        
        return None
    
    def _search_pdf_pages(self, text_by_page: Dict[int, str], full_text_terms: List[str],
                         item_data: Dict[str, Any], pdf_info: Dict[str, str],
                         include_abstract: bool = False,
                         verbose: bool = False) -> Tuple[List[Dict[str, Any]], dict]:
        """
        Search for terms in PDF pages.
        
        Args:
            text_by_page: Dictionary mapping page numbers to text
            full_text_terms: Terms to search for
            item_data: Zotero item data
            pdf_info: PDF information dictionary
            include_abstract: Whether to include item abstracts in results
            verbose: If True, print detailed output. If False, only count for summary.
            
        Returns:
            Tuple: (List of findings, dict of {term: count})
        """
        findings = []
        term_counter = {}  # {term: count}
        
        for page_num, page_text in text_by_page.items():
            if not page_text.strip():
                continue

            page_contexts = self.text_analyzer.build_page_contexts(
                page_text,
                full_text_terms,
                language=item_data.get("language"),
            )
            if not page_contexts:
                continue

            # Create findings for each merged interval
            for interval_data in page_contexts:
                unhighlighted_ctx = interval_data['context_text_unhighlighted']
                terms_in_context = interval_data['terms_found']

                # Create highlighted context
                highlighted_ctx = self.text_analyzer.highlight_multiple_terms(
                    unhighlighted_ctx, terms_in_context
                )

                # Create finding
                finding = self.result_handler.create_finding(
                    item_data, pdf_info, page_num, terms_in_context,
                    unhighlighted_ctx, highlighted_ctx, include_abstract=include_abstract
                )

                findings.append(finding)

                # Print progress if verbose
                if verbose:
                    print(f"      Found '{', '.join(terms_in_context)}' on page {page_num} in '{pdf_info['filename']}'")
                # Count for summary if not verbose
                for term in terms_in_context:
                    term_counter[term] = term_counter.get(term, 0) + 1
        
        return findings, term_counter
    
    def get_search_summary(self, results: List[Dict[str, Any]]) -> str:
        """
        Get a summary of search results.
        
        Args:
            results: List of search results
            
        Returns:
            Summary string
        """
        return self.result_handler.format_result_summary(results)


# Convenience function for backward compatibility
def search_zotero_and_full_text(zot_conn, base_attachment_dir: str,
                               metadata_search_terms: str, full_text_search_terms: List[str],
                               max_results_stage1: int = 100, include_abstract: bool = True,
                               verbose: bool = False, metadata_only: bool = False) -> List[Dict[str, Any]]:
    """
    Search Zotero and full text (backward compatibility function).
    
    Args:
        zot_conn: Zotero connection object
        base_attachment_dir: Base directory for attachments
        metadata_search_terms: Metadata search terms
        full_text_search_terms: Full text search terms
        max_results_stage1: Maximum results for stage 1
        include_abstract: Whether to include item abstracts in results
        verbose: If True, print detailed output. If False, print summary only.
        metadata_only: Whether to stop after metadata search

    Returns:
        List of findings
    """
    from .config import ZotGrepConfig
    
    # Create config from parameters
    config = ZotGrepConfig(
        base_attachment_path=base_attachment_dir,
        max_results_stage1=max_results_stage1
    )
    
    # Create search engine and set connection
    engine = ZoteroSearchEngine(config)
    engine.zot_conn = zot_conn
    
    return engine.search_zotero_and_full_text(
        metadata_search_terms,
        full_text_search_terms,
        verbose=verbose,
        include_abstract=include_abstract,
        metadata_only=metadata_only
    )
