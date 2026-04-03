"""
Result handling module for ZotGrep.

This module handles search result formatting, CSV export, console output,
and Zotero URL generation.
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import re


class ResultHandler:
    """Handles search results formatting and export."""
    
    def __init__(self):
        """Initialize result handler."""
        pass
    
    def generate_zotero_url(self, item_key: str, pdf_key: Optional[str] = None, 
                          page_number: Optional[int] = None) -> str:
        """
        Generate a Zotero URL to open an item or specific PDF page.
        
        Args:
            item_key: Zotero item key
            pdf_key: PDF attachment key (optional)
            page_number: Page number (optional)
            
        Returns:
            Zotero URL string
        """
        if pdf_key and page_number:
            # URL to open specific PDF page in Zotero
            return f"zotero://open-pdf/library/items/{pdf_key}?page={page_number}"
        elif pdf_key:
            # URL to open PDF attachment
            return f"zotero://select/library/items/{pdf_key}"
        else:
            # URL to open the main item
            return f"zotero://select/library/items/{item_key}"
    
    def create_finding(self, item_data: Dict[str, Any], pdf_info: Dict[str, str],
                      page_num: int, terms_found: List[str], context: str,
                      highlighted_context: str, include_abstract: bool = False) -> Dict[str, Any]:
        """
        Create a finding dictionary from search results.
        
        Args:
            item_data: Zotero item metadata
            pdf_info: PDF information dictionary
            page_num: Page number where terms were found
            terms_found: List of search terms found
            context: Unhighlighted context text
            highlighted_context: Context text with highlighted terms
            include_abstract: Whether to include the Zotero abstract in the result
            
        Returns:
            Finding dictionary with all relevant information
        """
        # Extract metadata
        item_title = item_data.get('title', 'N/A')
        item_key = item_data.get('key', 'N/A')
        
        # Process authors
        authors_str = self._format_authors(item_data.get('creators', []))
        
        # Process publication year
        publication_year = self._extract_publication_year(item_data.get('date', 'N/A'))
        publication_title = item_data.get('publicationTitle', 'N/A')
        doi = self._extract_doi(item_data)
        abstract = self._extract_abstract(item_data) if include_abstract else ''
        
        # Generate URLs
        item_url = self.generate_zotero_url(item_key)
        pdf_page_url = self.generate_zotero_url(item_key, pdf_info['key'], page_num)
        
        return {
            'reference_title': item_title,
            'authors': authors_str,
            'publication_year': publication_year,
            'publication_title': publication_title,
            'doi': doi,
            'abstract': abstract,
            'reference_key': item_key,
            'pdf_filename': pdf_info['filename'],
            'pdf_key': pdf_info['key'],
            'page_number': page_num,
            'search_term_found': ", ".join(terms_found),
            'context': context,
            'context_highlighted': highlighted_context,
            'zotero_item_url': item_url,
            'zotero_pdf_url': pdf_page_url,
            'search_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def create_reference_result(self, item_data: Dict[str, Any], include_abstract: bool = False) -> Dict[str, Any]:
        """
        Create a metadata-only result dictionary for searches without full-text terms.

        Args:
            item_data: Zotero item metadata
            include_abstract: Whether to include the Zotero abstract in the result

        Returns:
            Result dictionary with reference metadata only
        """
        item_title = item_data.get('title', 'N/A')
        item_key = item_data.get('key', 'N/A')
        authors_str = self._format_authors(item_data.get('creators', []))
        publication_year = self._extract_publication_year(item_data.get('date', 'N/A'))
        publication_title = item_data.get('publicationTitle', 'N/A')
        doi = self._extract_doi(item_data)
        abstract = self._extract_abstract(item_data) if include_abstract else ''
        item_url = self.generate_zotero_url(item_key)

        return {
            'reference_title': item_title,
            'authors': authors_str,
            'publication_year': publication_year,
            'publication_title': publication_title,
            'doi': doi,
            'abstract': abstract,
            'reference_key': item_key,
            'pdf_filename': '',
            'pdf_key': '',
            'page_number': '',
            'search_term_found': '',
            'context': '',
            'context_highlighted': '',
            'zotero_item_url': item_url,
            'zotero_pdf_url': '',
            'search_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _extract_abstract(self, item_data: Dict[str, Any]) -> str:
        """
        Extract the abstract text from Zotero item metadata.

        Zotero exposes abstracts on top-level items as `abstractNote`, which pyzotero
        passes through in the item's `data` payload.
        """
        abstract = item_data.get('abstractNote', '')
        if not abstract:
            return ''
        return re.sub(r'\s+', ' ', abstract).strip()

    def _extract_doi(self, item_data: Dict[str, Any]) -> str:
        """
        Extract the DOI from Zotero item metadata.
        """
        doi = item_data.get('DOI', '')
        if not doi:
            return ''
        return doi.strip()
    
    def _format_authors(self, creators: List[Dict[str, Any]]) -> str:
        """
        Format author information from Zotero creators data.
        
        Args:
            creators: List of creator dictionaries from Zotero
            
        Returns:
            Formatted author string
        """
        author_names = []
        
        for creator in creators:
            if creator.get('creatorType') == 'author':
                first_name = creator.get('firstName', '')
                last_name = creator.get('lastName', '')
                
                if first_name and last_name:
                    author_names.append(f"{last_name}, {first_name}")
                elif last_name:
                    author_names.append(last_name)
        
        return '; '.join(author_names) if author_names else 'N/A'
    
    def _extract_publication_year(self, date_str: str) -> str:
        """
        Extract publication year from date string.
        
        Args:
            date_str: Date string from Zotero
            
        Returns:
            Publication year or original string if no year found
        """
        if date_str == 'N/A' or not date_str:
            return 'N/A'
        
        if len(date_str) >= 4:
            import re
            year_match = re.search(r'\b(1[89]|20)\d{2}\b', date_str)
            return year_match.group(0) if year_match else date_str
        
        return date_str
    
    def save_results_to_csv(
        self,
        results: List[Dict[str, Any]],
        filename: str,
        include_abstract: bool = True
    ) -> None:
        """
        Save search results to a CSV file.
        
        Args:
            results: List of result dictionaries
            filename: Output CSV filename
            include_abstract: Whether to include the abstract column
        """
        if not results:
            print("No results to save.")
            return
        
        base_fieldnames = [
            'reference_title',
            'authors',
            'publication_year',
            'publication_title',
            'doi',
            'reference_key',
            'abstract',
            'zotero_item_url',
            'search_timestamp'
        ]
        full_text_fieldnames = [
            'pdf_filename',
            'pdf_key',
            'page_number',
            'search_term_found',
            'context',
            'zotero_pdf_url',
        ]
        include_full_text_fields = any(
            any(result.get(field) not in ('', None) for field in full_text_fieldnames)
            for result in results
        )
        fieldnames = list(base_fieldnames)
        if not include_abstract:
            fieldnames.remove('abstract')
        fieldnames.extend(full_text_fieldnames if include_full_text_fields else [])
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    # Create a copy without the highlighted context for CSV
                    csv_result = {
                        field: result.get(field, '')
                        for field in fieldnames
                    }
                    writer.writerow(csv_result)
            
            print(f"\nResults saved to: {filename}")
            print(f"Total entries: {len(results)}")
            
        except Exception as e:
            print(f"Error saving CSV file: {e}")

    def _group_results_by_reference(
        self,
        results: List[Dict[str, Any]],
        has_full_text_results: bool,
        full_text_query: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group flat result rows by Zotero reference key.
        """
        papers: Dict[str, Dict[str, Any]] = {}

        for result in results:
            ref_key = result['reference_key']
            if ref_key not in papers:
                authors_list = [a.strip() for a in result['authors'].split(';')] if result['authors'] != 'N/A' else []
                term_counts = {
                    term: 0 for term in (full_text_query or []) if term
                }
                papers[ref_key] = {
                    'title': result['reference_title'],
                    'authors': authors_list,
                    'year': result['publication_year'],
                    'publication_title': result.get('publication_title', 'N/A'),
                    'doi': result.get('doi', ''),
                    'abstract': result.get('abstract', ''),
                    'citekey': ref_key,
                    'zotero_item_key': ref_key,
                    'zotero_select_url': result['zotero_item_url'],
                    'term_counts': term_counts,
                    'annotations': []
                }

            if has_full_text_results and (
                result.get('context') or result.get('page_number') or result.get('zotero_pdf_url')
            ):
                terms_found = self._parse_terms_found(result.get('search_term_found', ''))
                for term in terms_found:
                    current = papers[ref_key]['term_counts'].get(term, 0)
                    papers[ref_key]['term_counts'][term] = current + 1
                papers[ref_key]['annotations'].append({
                    'text': result['context'],
                    'page': result['page_number'],
                    'pdf_attachment_key': result['pdf_key'],
                    'zotero_pdf_url': result['zotero_pdf_url'],
                    'terms_found': ', '.join(terms_found),
                })

        for paper in papers.values():
            paper['term_counts'] = [
                {'term': term, 'count': count}
                for term, count in paper['term_counts'].items()
            ]

        return papers

    def _build_structured_payload(
        self,
        results: List[Dict[str, Any]],
        zotero_query: Optional[str] = None,
        full_text_query: Optional[List[str]] = None,
        include_abstract: bool = True,
        context_window: Optional[int] = None,
        search_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the structured representation used for JSON and Markdown frontmatter.
        """
        has_full_text_results = any(
            result.get('search_term_found') or result.get('context') or result.get('zotero_pdf_url')
            for result in results
        )
        papers = self._group_results_by_reference(
            results,
            has_full_text_results,
            full_text_query=full_text_query,
        )
        total_papers = len(papers)
        total_annotations = sum(len(p['annotations']) for p in papers.values())

        if not search_timestamp and results:
            search_timestamp = results[0].get('search_timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        paper_list: List[Dict[str, Any]] = []
        for paper in papers.values():
            paper_copy = dict(paper)
            if not include_abstract:
                paper_copy.pop('abstract', None)
            paper_list.append(paper_copy)

        return {
            'zotgrep_results_version': 1,
            'search_details': {
                'zotero_query': zotero_query or "",
                'full_text_query': full_text_query or [],
                'search_mode': 'fulltext' if has_full_text_results else 'metadata_only',
                'search_timestamp': search_timestamp,
                'context_window': context_window if context_window is not None else "",
            },
            'summary': {
                'total_papers_found': total_papers,
                'total_annotations_found': total_annotations,
            },
            'papers': paper_list,
        }

    def save_results_to_json(
        self,
        results: List[Dict[str, Any]],
        filename: str,
        zotero_query: Optional[str] = None,
        full_text_query: Optional[List[str]] = None,
        include_abstract: bool = True,
        context_window: Optional[int] = None,
        search_timestamp: Optional[str] = None,
    ) -> None:
        """
        Save search results to a structured JSON file.
        """
        if not results:
            print("No results to save.")
            return

        try:
            payload = self._build_structured_payload(
                results,
                zotero_query=zotero_query,
                full_text_query=full_text_query,
                include_abstract=include_abstract,
                context_window=context_window,
                search_timestamp=search_timestamp,
            )

            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(payload, jsonfile, indent=2, ensure_ascii=False)

            print(f"\nJSON results saved to: {filename}")
        except Exception as e:
            print(f"Error saving JSON file: {e}")
    
    def save_results_to_markdown(
        self,
        results: List[Dict[str, Any]],
        filename: str,
        zotero_query: Optional[str] = None,
        full_text_query: Optional[List[str]] = None,
        include_abstract: bool = True,
        context_window: Optional[int] = None,
        search_timestamp: Optional[str] = None,
    ) -> None:
        """
        Save search results to a Markdown file with a single YAML frontmatter and a human-friendly body.

        Args:
            results: List of result dictionaries
            filename: Output Markdown filename
            zotero_query: The Zotero library search query (optional)
            full_text_query: List of full-text search terms (optional)
            include_abstract: Whether to include abstracts in the Markdown output
            context_window: Context window size (optional)
            search_timestamp: Search timestamp (optional)
        """
        if not results:
            print("No results to save.")
            return

        try:
            payload = self._build_structured_payload(
                results,
                zotero_query=zotero_query,
                full_text_query=full_text_query,
                include_abstract=include_abstract,
                context_window=context_window,
                search_timestamp=search_timestamp,
            )
            papers = payload['papers']
            search_details = payload['search_details']
            summary = payload['summary']
            total_papers = summary['total_papers_found']
            total_annotations = summary['total_annotations_found']
            has_full_text_results = search_details['search_mode'] == 'fulltext'
            search_timestamp = search_details['search_timestamp']

            # Compose compact YAML frontmatter to avoid duplicating the full reference list
            import yaml
            yaml_dict = {
                'zotgrep-results/v1': None,
                'search_details': search_details,
                'summary': summary,
            }
            # Custom YAML dumper to avoid 'null' for version key
            class NoAliasDumper(yaml.SafeDumper):
                def ignore_aliases(self, data):
                    return True
            def represent_none(self, _):
                return self.represent_scalar('tag:yaml.org,2002:null', '')
            NoAliasDumper.add_representer(type(None), represent_none)

            yaml_frontmatter = yaml.dump(
                yaml_dict,
                Dumper=NoAliasDumper,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
            # Remove the 'null' after the version key for aesthetic
            yaml_frontmatter = yaml_frontmatter.replace("'zotgrep-results/v1': ''", "# zotgrep-results/v1")

            with open(filename, 'w', encoding='utf-8') as mdfile:
                # Write YAML frontmatter
                mdfile.write('---\n')
                mdfile.write(yaml_frontmatter)
                mdfile.write('---\n\n')

                # Markdown body
                mdfile.write("# ZotGrep Results\n\n")
                mdfile.write("## Search Summary\n\n")
                mdfile.write(f"- **Search Date:** {search_timestamp}\n")
                mdfile.write(f"- **Zotero Library Query:** `{zotero_query or ''}`\n")
                full_text_query_display = ', '.join([f'`{t}`' for t in (full_text_query or [])])
                mdfile.write(
                    f"- **Full-Text Query:** {full_text_query_display if full_text_query_display else 'None supplied'}\n"
                )
                if has_full_text_results:
                    mdfile.write(f"- **Results:** Found **{total_annotations}** annotations across **{total_papers}** papers.\n\n")
                else:
                    mdfile.write(f"- **Results:** Found **{total_papers}** papers. No full-text terms were supplied.\n\n")

                mdfile.write("### Reference List\n\n")
                for idx, paper in enumerate(papers, 1):
                    mdfile.write(f"{idx}.  {self._format_reference_entry(paper)}\n")
                mdfile.write("\n---\n\n")

                if include_abstract:
                    mdfile.write("## Abstracts\n\n")
                    for paper in papers:
                        author_label = self._format_reference_heading(paper['authors'], paper['year'], paper['title'])
                        mdfile.write(f"### Abstract for {author_label}\n\n")
                        abstract_text = paper.get('abstract', '').strip()
                        if abstract_text:
                            mdfile.write(f"{abstract_text}\n\n")
                        else:
                            mdfile.write("No abstract available.\n\n")
                    mdfile.write("---\n\n")

                if has_full_text_results:
                    mdfile.write("## Detailed Findings\n\n")
                    for paper in papers:
                        mdfile.write(f"### {paper['title']}\n\n")
                        mdfile.write(f"- **Authors**: {'; '.join(paper['authors'])}\n")
                        mdfile.write(f"- **Year**: {paper['year']}\n")
                        if paper.get('publication_title') and paper['publication_title'] != 'N/A':
                            mdfile.write(f"- **Publication**: {paper['publication_title']}\n")
                        if paper.get('doi'):
                            mdfile.write(f"- **DOI**: {self._format_doi_url(paper['doi'])}\n")
                        mdfile.write(f"- **Citekey**: `{paper['citekey']}`\n")
                        mdfile.write(f"- **Zotero Link**: [Open Item in Zotero]({paper['zotero_select_url']})\n\n")
                        mdfile.write("#### Term Summary\n\n")
                        for term_info in paper.get('term_counts', []):
                            label = 'occurrence' if term_info['count'] == 1 else 'occurrences'
                            mdfile.write(f"- `{term_info['term']}`: {term_info['count']} {label}\n")
                        mdfile.write("\n")
                        mdfile.write("#### Annotations\n\n")
                        highlight_terms = self._build_highlight_terms(zotero_query, full_text_query)
                        for annotation_index, annotation in enumerate(paper['annotations'], 1):
                            context = self._clean_context_for_markdown(annotation['text'])
                            context = self._highlight_terms_for_markdown(context, highlight_terms)
                            mdfile.write(
                                f"##### Occurrence #{annotation_index}, Page {annotation['page']}\n\n"
                            )
                            mdfile.write(f"> {context}\n")
                            mdfile.write(f"> - Highlight on [Page {annotation['page']}]({annotation['zotero_pdf_url']})\n\n")
                        mdfile.write("---\n\n")
                else:
                    mdfile.write("## Detailed Findings\n\n")
                    mdfile.write("No full-text terms were supplied, so no annotation-level findings were generated.\n")

            print(f"\nResults saved to: {filename}")
            print(f"Total papers: {total_papers}")
            print(f"Total annotations: {total_annotations}")

        except Exception as e:
            print(f"Error saving Markdown file: {e}")
    
    def _escape_markdown(self, text: str) -> str:
        """
        Escape special markdown characters in text.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        if not text or text == 'N/A':
            return text
        
        # Escape common markdown special characters
        special_chars = ['*', '_', '`', '[', ']', '(', ')', '#', '+', '-', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def _clean_context_for_markdown(self, context: str) -> str:
        """
        Clean and format context text for markdown output.
        
        Args:
            context: Raw context text
            
        Returns:
            Cleaned context text
        """
        if not context:
            return ""
        
        # Remove extra whitespace and normalize
        context = re.sub(r'\s+', ' ', context.strip())
        
        # Remove any existing markdown highlighting
        context = re.sub(r'\*\*(.*?)\*\*', r'\1', context)
        
        # Escape quotes that might break the markdown
        context = context.replace('"', '\\"')
        
        return context

    def _build_highlight_terms(
        self,
        zotero_query: Optional[str],
        full_text_query: Optional[List[str]],
    ) -> List[str]:
        """
        Build a list of terms to highlight from metadata and full-text queries.
        """
        terms: List[str] = []

        if zotero_query:
            for chunk in zotero_query.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                terms.append(chunk)
                # Also add individual words from the chunk for broad matching.
                for word in chunk.split():
                    if word:
                        terms.append(word)

        if full_text_query:
            for term in full_text_query:
                term = term.strip()
                if term:
                    terms.append(term)

        # De-duplicate while preserving order (case-insensitive).
        seen = set()
        deduped: List[str] = []
        for term in terms:
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(term)

        return deduped

    def _format_doi_url(self, doi: str) -> str:
        """
        Normalize a DOI into a canonical URL when possible.
        """
        doi = (doi or '').strip()
        if not doi:
            return ''
        if doi.lower().startswith('http://') or doi.lower().startswith('https://'):
            return doi
        return f"https://doi.org/{doi}"

    def _format_reference_entry(self, paper: Dict[str, Any]) -> str:
        """
        Format a fuller APA-like reference entry for Markdown reports.
        """
        apa_authors = self._format_apa_authors(paper.get('authors', []))
        parts = [f"{apa_authors} ({paper['year']}). *{paper['title']}*."]

        publication_title = paper.get('publication_title')
        if publication_title and publication_title != 'N/A':
            parts.append(f"{publication_title}.")

        doi = self._format_doi_url(paper.get('doi', ''))
        if doi:
            parts.append(doi)

        return ' '.join(parts)

    def _format_reference_heading(self, authors: List[str], year: str, fallback_title: str) -> str:
        """
        Format a short reference heading for Markdown sections.
        """
        if not authors:
            return f"{fallback_title}, {year}"

        surnames = []
        for author in authors:
            surname = author.split(',')[0].strip() if ',' in author else author.strip().split()[-1]
            if surname:
                surnames.append(surname)

        if not surnames:
            return f"{fallback_title}, {year}"
        if len(surnames) == 1:
            author_part = surnames[0]
        elif len(surnames) == 2:
            author_part = f"{surnames[0]} and {surnames[1]}"
        else:
            author_part = f"{surnames[0]} et al."

        return f"{author_part}, {year}"

    def _format_apa_authors(self, authors: List[str]) -> str:
        """
        Format author names into a compact APA-like string.
        """
        if not authors:
            return ""

        names = []
        for author in authors:
            parts = author.split(',')
            if len(parts) == 2:
                names.append(f"{parts[0].strip()}, {parts[1].strip()[0]}." if parts[1].strip() else parts[0].strip())
            else:
                names.append(author.strip())

        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} & {names[1]}"
        return f"{', '.join(names[:-1])}, & {names[-1]}"

    def _highlight_terms_for_markdown(self, text: str, terms: List[str]) -> str:
        """
        Highlight terms in text for Markdown output using bold markers.
        """
        if not text or not terms:
            return text

        # Prefer longer terms first to avoid partial matches.
        terms_sorted = sorted(terms, key=len, reverse=True)
        pattern = re.compile("|".join(re.escape(t) for t in terms_sorted), re.IGNORECASE)

        return pattern.sub(lambda m: f"**{m.group(0)}**", text)

    def _parse_terms_found(self, terms_found: str) -> List[str]:
        """
        Parse the serialized terms list stored on a result row.
        """
        if not terms_found:
            return []
        return [term.strip() for term in terms_found.split(',') if term.strip()]
    
    def print_results(self, results: List[Dict[str, Any]]) -> None:
        """
        Print search results to console.
        
        Args:
            results: List of result dictionaries
        """
        print("\n\n--- Search Complete. Results: ---")
        
        if results:
            for res in results:
                print(f"\nReference: {res['reference_title']} (Key: {res['reference_key']})")
                
                if res['authors'] != 'N/A':
                    print(f"  Authors: {res['authors']}")
                
                if res['publication_year'] != 'N/A':
                    print(f"  Year: {res['publication_year']}")
                if res.get('publication_title') and res['publication_title'] != 'N/A':
                    print(f"  Publication: {res['publication_title']}")
                if res.get('doi'):
                    print(f"  DOI: {self._format_doi_url(res['doi'])}")

                if res.get('search_term_found'):
                    print(f"  PDF: {res['pdf_filename']}")
                    print(f"  Found '{res['search_term_found']}' on Page: {res['page_number']}")
                    print(f"  Context: {res['context_highlighted']}")
                    print(f"  Zotero PDF URL: {res['zotero_pdf_url']}")
                else:
                    if res.get('abstract'):
                        print(f"  Abstract: {res['abstract']}")
                    print("  Full-text search: not run")
                    print(f"  Zotero Item URL: {res['zotero_item_url']}")
        else:
            print("No matches found based on your criteria.")
    
    def format_result_summary(self, results: List[Dict[str, Any]]) -> str:
        """
        Create a summary of search results.
        
        Args:
            results: List of result dictionaries
            
        Returns:
            Summary string
        """
        if not results:
            return "No results found."

        has_full_text_results = any(res.get('search_term_found') for res in results)

        if not has_full_text_results:
            unique_references = len(set(res['reference_key'] for res in results))
            return f"Found {unique_references} references from the Zotero metadata search."
        
        total_results = len(results)
        unique_references = len(set(res['reference_key'] for res in results))
        unique_pdfs = len(set(res['pdf_key'] for res in results))
        
        return (f"Found {total_results} matches across {unique_references} references "
                f"in {unique_pdfs} PDF files.")
    
    def get_interactive_output_choice(self) -> Tuple[Optional[str], str]:
        """
        Get output format choice and filename from user input.
        
        Returns:
            Tuple of (filename, format) where format is 'csv' or 'md', or (None, '') if user declines
        """
        print("\nAdditional output options:")
        print("JSON output is saved by default unless disabled with --no-json.")
        print("1. CSV file (spreadsheet format)")
        print("2. Markdown file (research notes format)")
        print("3. No additional file output")
        
        choice = input("Choose output format (1/2/3): ").strip()
        
        if choice == '1':
            return self._get_csv_filename(), 'csv'
        elif choice == '2':
            return self._get_markdown_filename(), 'md'
        else:
            return None, ''
    
    def _get_csv_filename(self) -> str:
        """Get CSV filename from user input."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"zotero_search_results_{timestamp}.csv"
        filename = input(f"Enter CSV filename (default: {default_filename}): ").strip()
        
        if not filename:
            filename = default_filename
        
        return filename
    
    def _get_markdown_filename(self) -> str:
        """Get Markdown filename from user input."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"zotero_search_results_{timestamp}.md"
        filename = input(f"Enter Markdown filename (default: {default_filename}): ").strip()
        
        if not filename:
            filename = default_filename
        
        return filename

    def get_default_json_filename(self, search_timestamp: Optional[str] = None) -> str:
        """
        Get the default JSON filename for a search result set.
        """
        if search_timestamp:
            timestamp = re.sub(r'[^0-9]', '', search_timestamp)[:14]
            if timestamp:
                return f"zotero_search_results_{timestamp}.json"

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"zotero_search_results_{timestamp}.json"
    
    def get_interactive_csv_filename(self) -> Optional[str]:
        """
        Get CSV filename from user input (backward compatibility).
        
        Returns:
            Filename string or None if user declines
        """
        save_csv = input("\nWould you like to save results to a CSV file? (y/n): ").lower().strip()
        
        if save_csv in ['y', 'yes']:
            return self._get_csv_filename()
        
        return None


# Convenience functions for backward compatibility
def generate_zotero_url(item_key: str, pdf_key: Optional[str] = None, 
                       page_number: Optional[int] = None) -> str:
    """Generate Zotero URL (backward compatibility function)."""
    handler = ResultHandler()
    return handler.generate_zotero_url(item_key, pdf_key, page_number)


def save_results_to_csv(
    results: List[Dict[str, Any]],
    filename: str,
    include_abstract: bool = True
) -> None:
    """Save results to CSV (backward compatibility function)."""
    handler = ResultHandler()
    handler.save_results_to_csv(results, filename, include_abstract=include_abstract)


def save_results_to_json(
    results: List[Dict[str, Any]],
    filename: str,
    zotero_query: Optional[str] = None,
    full_text_query: Optional[List[str]] = None,
    include_abstract: bool = True,
    context_window: Optional[int] = None,
    search_timestamp: Optional[str] = None,
) -> None:
    """Save results to JSON (backward compatibility function)."""
    handler = ResultHandler()
    handler.save_results_to_json(
        results,
        filename,
        zotero_query=zotero_query,
        full_text_query=full_text_query,
        include_abstract=include_abstract,
        context_window=context_window,
        search_timestamp=search_timestamp,
    )


def save_results_to_markdown(
    results: List[Dict[str, Any]],
    filename: str,
    zotero_query: Optional[str] = None,
    full_text_query: Optional[List[str]] = None,
    include_abstract: bool = True,
    context_window: Optional[int] = None,
    search_timestamp: Optional[str] = None,
) -> None:
    """Save results to Markdown (backward compatibility function)."""
    handler = ResultHandler()
    handler.save_results_to_markdown(
        results,
        filename,
        zotero_query=zotero_query,
        full_text_query=full_text_query,
        include_abstract=include_abstract,
        context_window=context_window,
        search_timestamp=search_timestamp,
    )


def print_results(results: List[Dict[str, Any]]) -> None:
    """Print results (backward compatibility function)."""
    handler = ResultHandler()
    handler.print_results(results)
