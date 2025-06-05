"""
Result handling module for ZotSearch.

This module handles search result formatting, CSV export, console output,
and Zotero URL generation.
"""

import csv
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
                      highlighted_context: str) -> Dict[str, Any]:
        """
        Create a finding dictionary from search results.
        
        Args:
            item_data: Zotero item metadata
            pdf_info: PDF information dictionary
            page_num: Page number where terms were found
            terms_found: List of search terms found
            context: Unhighlighted context text
            highlighted_context: Context text with highlighted terms
            
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
        
        # Generate URLs
        item_url = self.generate_zotero_url(item_key)
        pdf_page_url = self.generate_zotero_url(item_key, pdf_info['key'], page_num)
        
        return {
            'reference_title': item_title,
            'authors': authors_str,
            'publication_year': publication_year,
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
    
    def save_results_to_csv(self, results: List[Dict[str, Any]], filename: str) -> None:
        """
        Save search results to a CSV file.
        
        Args:
            results: List of result dictionaries
            filename: Output CSV filename
        """
        if not results:
            print("No results to save.")
            return
        
        fieldnames = [
            'reference_title',
            'authors',
            'publication_year',
            'reference_key',
            'pdf_filename',
            'pdf_key',
            'page_number',
            'search_term_found',
            'context',
            'zotero_item_url',
            'zotero_pdf_url',
            'search_timestamp'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    # Create a copy without the highlighted context for CSV
                    csv_result = {k: v for k, v in result.items() if k != 'context_highlighted'}
                    writer.writerow(csv_result)
            
            print(f"\nResults saved to: {filename}")
            print(f"Total entries: {len(results)}")
            
        except Exception as e:
            print(f"Error saving CSV file: {e}")
    
    def save_results_to_markdown(self, results: List[Dict[str, Any]], filename: str) -> None:
        """
        Save search results to a Markdown file with sections for each paper.
        
        Args:
            results: List of result dictionaries
            filename: Output Markdown filename
        """
        if not results:
            print("No results to save.")
            return
        
        try:
            # Group results by reference
            papers = {}
            for result in results:
                ref_key = result['reference_key']
                if ref_key not in papers:
                    papers[ref_key] = {
                        'title': result['reference_title'],
                        'authors': result['authors'],
                        'year': result['publication_year'],
                        'citekey': ref_key,
                        'zotero_url': result['zotero_item_url'],
                        'pdf_filename': result['pdf_filename'],
                        'sections': []
                    }
                
                # Create section entry
                section = {
                    'context': result['context'],
                    'page': result['page_number'],
                    'terms_found': result['search_term_found'],
                    'pdf_url': result['zotero_pdf_url']
                }
                papers[ref_key]['sections'].append(section)
            
            # Generate markdown content
            with open(filename, 'w', encoding='utf-8') as mdfile:
                # Write header with search metadata
                mdfile.write("# ZotSearch Results\n\n")
                mdfile.write(f"**Search Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                mdfile.write(f"**Total Papers:** {len(papers)}\n")
                mdfile.write(f"**Total Sections:** {len(results)}\n\n")
                mdfile.write("---\n\n")
                
                # Write each paper
                for ref_key, paper in papers.items():
                    # Paper header with YAML-like frontmatter
                    mdfile.write("---\n")
                    mdfile.write("cssclass: research-note\n")
                    mdfile.write(f"title: {paper['title']}\n")
                    if paper['year'] != 'N/A':
                        mdfile.write(f"Year: {paper['year']}\n")
                    if paper['authors'] != 'N/A':
                        mdfile.write(f"Authors: {paper['authors']}\n")
                    mdfile.write(f"citekey: {ref_key}\n")
                    mdfile.write("tags: Source\n")
                    mdfile.write(f"Zotero Link: [{paper['pdf_filename']}]({paper['zotero_url']})\n")
                    mdfile.write("---\n\n")
                    
                    # Paper title as main heading
                    mdfile.write(f"## {paper['title']}\n\n")
                    
                    # Annotations section
                    mdfile.write("## Annotations\n\n")
                    
                    # Write each section/annotation
                    for section in paper['sections']:
                        # Clean and format the context
                        context = self._clean_context_for_markdown(section['context'])
                        
                        # Create annotation entry similar to the example
                        mdfile.write(f'"{context}" Highlight [Page {section["page"]}]({section["pdf_url"]}) \n \n')
                    
                    mdfile.write("\n")
            
            print(f"\nResults saved to: {filename}")
            print(f"Total papers: {len(papers)}")
            print(f"Total sections: {len(results)}")
            
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
                
                print(f"  PDF: {res['pdf_filename']}")
                print(f"  Found '{res['search_term_found']}' on Page: {res['page_number']}")
                print(f"  Context: {res['context_highlighted']}")
                print(f"  Zotero PDF URL: {res['zotero_pdf_url']}")
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
        print("\nOutput options:")
        print("1. CSV file (spreadsheet format)")
        print("2. Markdown file (research notes format)")
        print("3. No file output")
        
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


def save_results_to_csv(results: List[Dict[str, Any]], filename: str) -> None:
    """Save results to CSV (backward compatibility function)."""
    handler = ResultHandler()
    handler.save_results_to_csv(results, filename)


def save_results_to_markdown(results: List[Dict[str, Any]], filename: str) -> None:
    """Save results to Markdown (backward compatibility function)."""
    handler = ResultHandler()
    handler.save_results_to_markdown(results, filename)


def print_results(results: List[Dict[str, Any]]) -> None:
    """Print results (backward compatibility function)."""
    handler = ResultHandler()
    handler.print_results(results)