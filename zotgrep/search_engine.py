"""
Search engine module for ZotGrep.

This module contains the core search logic that orchestrates Zotero metadata search,
PDF full-text search, and result processing.
"""

from dataclasses import dataclass
import re
from typing import List, Dict, Any, Optional, Tuple
from pyzotero import zotero

from .config import ZotGrepConfig
from .pdf_processor import PDFProcessor
from .text_analyzer import FullTextQuery, TextAnalyzer, parse_full_text_query
from .result_handler import ResultHandler


@dataclass
class MetadataFilters:
    item_types: List[str]
    collection: Optional[str]
    tags: List[str]
    tag_match_mode: str
    publication_titles: List[str]


@dataclass
class ResolvedCollection:
    input_value: str
    key: str
    name: str


class ZoteroSearchEngine:
    """Main search engine that orchestrates the search process."""
    COLLECTION_KEY_PATTERN = re.compile(r"^[A-Z0-9]{8}$", re.IGNORECASE)
    
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
        self.metadata_filters_for_output = self._build_metadata_filters_for_output(
            self._normalize_metadata_filters(),
            None,
        )
        
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
                                   full_text_search_terms: List[str] | str,
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
        
        full_text_query = self._normalize_full_text_query(full_text_search_terms)

        # Stage 1: Search Zotero metadata
        items = self._search_metadata(metadata_search_terms)
        if not items:
            return []
        
        print(f"Found {len(items)} references matching metadata search.")

        if metadata_only or full_text_query is None:
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
                full_text_query,
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

    def _normalize_csv_filter(self, values: Optional[List[str]] | str) -> List[str]:
        if not values:
            return []

        raw_values = values.split(",") if isinstance(values, str) else values
        normalized: List[str] = []
        seen: set[str] = set()
        for value in raw_values:
            normalized_value = str(value).strip()
            if not normalized_value or normalized_value in seen:
                continue
            normalized.append(normalized_value)
            seen.add(normalized_value)
        return normalized

    def _normalize_metadata_filters(self) -> MetadataFilters:
        return MetadataFilters(
            item_types=self._normalize_csv_filter(self.config.item_type_filter or []),
            collection=(self.config.collection_filter or "").strip() or None,
            tags=self._normalize_csv_filter(self.config.tag_filter or []),
            tag_match_mode=(self.config.tag_match_mode or "all").strip().lower() or "all",
            publication_titles=self._normalize_csv_filter(
                self.config.publication_title_filter or []
            ),
        )

    def _build_metadata_filters_for_output(
        self,
        filters: MetadataFilters,
        resolved_collection: Optional[ResolvedCollection],
    ) -> Dict[str, Any]:
        collection_value: Optional[Dict[str, str]] = None
        if resolved_collection:
            collection_value = {
                "input": resolved_collection.input_value,
                "key": resolved_collection.key,
                "name": resolved_collection.name,
            }
        elif filters.collection:
            collection_value = {
                "input": filters.collection,
                "key": "",
                "name": "",
            }

        return {
            "item_types": list(filters.item_types),
            "collection": collection_value,
            "tags": list(filters.tags),
            "tag_match_mode": filters.tag_match_mode,
            "publication_titles": list(filters.publication_titles),
        }

    def _normalize_full_text_query(
        self,
        full_text_search_terms: List[str] | str,
    ) -> Optional[FullTextQuery]:
        if isinstance(full_text_search_terms, str) and not full_text_search_terms.strip():
            return None
        if isinstance(full_text_search_terms, list) and not any(
            term and term.strip() for term in full_text_search_terms
        ):
            return None
        return parse_full_text_query(full_text_search_terms)
    
    def _search_metadata(self, search_terms: str) -> List[Dict[str, Any]]:
        """
        Search Zotero metadata.
        
        Args:
            search_terms: Search terms for metadata
            
        Returns:
            List of Zotero items
        """
        print(f"--- Stage 1: Searching Zotero metadata for: '{search_terms}' ---")
        filters = self._normalize_metadata_filters()

        try:
            resolved_collection = self._resolve_collection_filter(filters.collection)
            self.metadata_filters_for_output = self._build_metadata_filters_for_output(
                filters,
                resolved_collection,
            )
            self._print_active_metadata_filters(self.metadata_filters_for_output)

            items = self._fetch_metadata_items(
                search_terms,
                filters,
                resolved_collection,
            )

            items = self._filter_items_by_item_type(items, filters.item_types)
            items = self._filter_items_by_tags(items, filters.tags, filters.tag_match_mode)
            items = self._filter_items_by_publication_title(items)
            
            if not items:
                print("No references found matching metadata search terms.")
                
            return items
            
        except ValueError:
            raise
        except Exception as e:
            print(f"Error during Zotero metadata search: {e}")
            return []

    def _fetch_metadata_items(
        self,
        search_terms: str,
        filters: MetadataFilters,
        resolved_collection: Optional[ResolvedCollection],
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {
            "q": search_terms,
            "limit": self.config.max_results_stage1,
        }

        single_item_type = filters.item_types[0] if len(filters.item_types) == 1 else None

        if resolved_collection:
            if single_item_type:
                kwargs["itemType"] = single_item_type
            return self.zot_conn.collection_items_top(resolved_collection.key, **kwargs)

        if filters.item_types:
            if single_item_type:
                kwargs["itemType"] = single_item_type
            return self.zot_conn.top(**kwargs)

        kwargs["itemType"] = "-attachment"
        return self.zot_conn.items(**kwargs)

    def _resolve_collection_filter(
        self,
        collection_filter: Optional[str],
    ) -> Optional[ResolvedCollection]:
        if not collection_filter:
            return None

        candidate = collection_filter.strip()
        if self.COLLECTION_KEY_PATTERN.fullmatch(candidate):
            try:
                collection = self.zot_conn.collection(candidate)
            except Exception as exc:
                raise ValueError(f"Collection key '{candidate}' was not found.") from exc
            data = collection.get("data", {})
            return ResolvedCollection(
                input_value=collection_filter,
                key=data.get("key", candidate.upper()),
                name=data.get("name", ""),
            )

        collections = self.zot_conn.all_collections()
        normalized_candidate = candidate.lower()
        matches = [
            collection
            for collection in collections
            if (collection.get("data", {}).get("name", "").strip().lower() == normalized_candidate)
        ]
        if not matches:
            raise ValueError(
                f"Collection '{collection_filter}' was not found. Use an exact name or collection key."
            )
        if len(matches) > 1:
            keys = ", ".join(sorted(match.get("data", {}).get("key", "") for match in matches))
            raise ValueError(
                f"Collection name '{collection_filter}' is ambiguous. Use a collection key instead: {keys}."
            )

        match_data = matches[0].get("data", {})
        return ResolvedCollection(
            input_value=collection_filter,
            key=match_data.get("key", ""),
            name=match_data.get("name", candidate),
        )

    def _print_active_metadata_filters(self, metadata_filters: Dict[str, Any]) -> None:
        if metadata_filters.get("item_types"):
            print(f"Item type filter: {', '.join(metadata_filters['item_types'])}")

        collection = metadata_filters.get("collection")
        if collection:
            collection_label = collection.get("name") or collection.get("input") or "N/A"
            collection_key = collection.get("key")
            if collection_key:
                print(f"Collection filter: {collection_label} [{collection_key}]")
            else:
                print(f"Collection filter: {collection_label}")

        if metadata_filters.get("tags"):
            print(
                f"Tag filter ({metadata_filters['tag_match_mode']}): "
                f"{', '.join(metadata_filters['tags'])}"
            )

        if metadata_filters.get("publication_titles"):
            print(
                "Publication title filter: "
                + ", ".join(metadata_filters["publication_titles"])
            )

    def _filter_items_by_publication_title(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter items by publication title (client-side).
        """
        filters = self._normalize_metadata_filters().publication_titles
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

    def _filter_items_by_item_type(
        self,
        items: List[Dict[str, Any]],
        item_types: List[str],
    ) -> List[Dict[str, Any]]:
        if not item_types:
            return items

        filtered_items = [
            item
            for item in items
            if item.get("data", {}).get("itemType") in item_types
        ]
        print(f"Filtered {len(items)} items to {len(filtered_items)} by item type.")
        return filtered_items

    def _filter_items_by_tags(
        self,
        items: List[Dict[str, Any]],
        tags: List[str],
        tag_match_mode: str,
    ) -> List[Dict[str, Any]]:
        if not tags:
            return items

        filtered_items: List[Dict[str, Any]] = []
        tag_set = set(tags)
        for item in items:
            item_tags = {
                str(tag.get("tag", "")).strip()
                for tag in item.get("data", {}).get("tags", [])
                if str(tag.get("tag", "")).strip()
            }
            if tag_match_mode == "any":
                if item_tags.intersection(tag_set):
                    filtered_items.append(item)
                continue
            if tag_set.issubset(item_tags):
                filtered_items.append(item)

        print(
            f"Filtered {len(items)} items to {len(filtered_items)} by tags "
            f"({tag_match_mode})."
        )
        return filtered_items
    
    def _process_item_pdfs(self, item_data: Dict[str, Any],
                          full_text_query: FullTextQuery,
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
                print(
                    f"  --- Stage 2: Searching PDF(s) for '{item_title}' for: "
                    f"'{', '.join(full_text_query.leaf_terms)}' ---"
                )
                found_text_in_item = True
            
            # Search each page
            page_findings, page_counter = self._search_pdf_pages(
                text_by_page, full_text_query, item_data, pdf_info,
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
    
    def _search_pdf_pages(self, text_by_page: Dict[int, str], full_text_query: FullTextQuery | List[str],
                         item_data: Dict[str, Any], pdf_info: Dict[str, str],
                         include_abstract: bool = False,
                         verbose: bool = False) -> Tuple[List[Dict[str, Any]], dict]:
        """
        Search for terms in PDF pages.
        
        Args:
            text_by_page: Dictionary mapping page numbers to text
            full_text_query: Parsed query or list of full-text terms
            item_data: Zotero item data
            pdf_info: PDF information dictionary
            include_abstract: Whether to include item abstracts in results
            verbose: If True, print detailed output. If False, only count for summary.
            
        Returns:
            Tuple: (List of findings, dict of {term: count})
        """
        query = parse_full_text_query(full_text_query)
        findings = []
        term_counter = {}  # {term: count}
        
        for page_num, page_text in text_by_page.items():
            if not page_text.strip():
                continue

            page_contexts = self.text_analyzer.build_page_contexts(
                page_text,
                query,
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
                    unhighlighted_ctx, terms_in_context, query=query
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

    def get_metadata_filters_for_output(self) -> Dict[str, Any]:
        return dict(self.metadata_filters_for_output)


# Convenience function for backward compatibility
def search_zotero_and_full_text(zot_conn, base_attachment_dir: str,
                               metadata_search_terms: str, full_text_search_terms: List[str] | str,
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
