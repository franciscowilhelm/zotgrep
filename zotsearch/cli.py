"""
Command-line interface module for ZotSearch.

This module handles argument parsing, user interaction, and CLI-specific functionality.
"""

import argparse
import sys
from typing import List, Tuple, Optional

from .config import ZotSearchConfig, get_config, print_config_info
from .search_engine import ZoteroSearchEngine
from .result_handler import ResultHandler


class ZotSearchCLI:
    """Command-line interface for ZotSearch."""
    
    def __init__(self):
        """Initialize CLI."""
        self.result_handler = ResultHandler()
    
    def parse_arguments(self) -> argparse.Namespace:
        """
        Parse command-line arguments.
        
        Returns:
            Parsed arguments namespace
        """
        parser = argparse.ArgumentParser(
            description='Search Zotero library and full-text PDFs',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python main.py
  python main.py --csv results.csv
  python main.py --md results.md
  python main.py --csv results.csv --csv-only
  python main.py --markdown results.md --markdown-only
            """
        )
        
        parser.add_argument(
            '--csv',
            type=str,
            help='Save results to CSV file (specify filename)'
        )
        
        parser.add_argument(
            '--md', '--markdown',
            type=str,
            dest='markdown',
            help='Save results to Markdown file (specify filename)'
        )
        
        parser.add_argument(
            '--csv-only',
            action='store_true',
            help='Only save to CSV, do not print to console'
        )
        
        parser.add_argument(
            '--md-only', '--markdown-only',
            action='store_true',
            dest='markdown_only',
            help='Only save to Markdown, do not print to console'
        )
        
        parser.add_argument(
            '--config',
            type=str,
            help='Path to configuration file (JSON format)'
        )
        
        parser.add_argument(
            '--base-path',
            type=str,
            help='Override base attachment path'
        )
        
        parser.add_argument(
            '--max-results',
            type=int,
            default=100,
            help='Maximum results for metadata search (default: 100)'
        )
        
        parser.add_argument(
            '--context-window',
            type=int,
            default=2,
            help='Context sentence window size (default: 2)'
        )
        
        parser.add_argument(
            '--version',
            action='version',
            version='ZotSearch 2.0.0'
        )
        
        return parser.parse_args()
    
    def get_search_terms_interactive(self) -> Tuple[str, List[str]]:
        """
        Get search terms from user input interactively.
        
        Returns:
            Tuple of (metadata_query, full_text_terms_list)
        """
        print("\n=== ZotSearch - Interactive Mode ===")
        
        metadata_query = input("Enter Zotero metadata search terms (e.g., 'machine learning health'): ").strip()
        if not metadata_query:
            print("Error: Metadata search terms cannot be empty.")
            sys.exit(1)
        
        full_text_query_str = input("Enter full-text search terms, comma-separated (e.g., 'algorithm, bias'): ").strip()
        if not full_text_query_str:
            print("Error: Full-text search terms cannot be empty.")
            sys.exit(1)
        
        full_text_terms_list = [term.strip() for term in full_text_query_str.split(',')]
        full_text_terms_list = [term for term in full_text_terms_list if term]  # Remove empty terms
        
        if not full_text_terms_list:
            print("Error: No valid full-text search terms provided.")
            sys.exit(1)
        
        return metadata_query, full_text_terms_list
    
    def validate_config(self, config: ZotSearchConfig) -> bool:
        """
        Validate configuration and show helpful error messages.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            config.validate()
            return True
        except ValueError as e:
            print(f"Configuration Error: {e}")
            
            if "BASE_ATTACHMENT_PATH" in str(e):
                print("\nPlease set the BASE_ATTACHMENT_PATH to your Zotero attachments directory.")
                print("This is typically something like:")
                print("  - macOS: /Users/yourname/Zotero/storage")
                print("  - Windows: C:\\Users\\yourname\\Zotero\\storage")
                print("  - Linux: /home/yourname/Zotero/storage")
                print("\nOr if using linked files with zotmoov:")
                print("  - The directory where your linked PDFs are stored")
            
            elif "ZOTERO_USER_ID" in str(e) or "ZOTERO_API_KEY" in str(e):
                print("\nFor remote Zotero API access, please configure:")
                print("  - ZOTERO_USER_ID: Your Zotero user ID")
                print("  - ZOTERO_API_KEY: Your Zotero API key")
                print("\nFor local API access (default), these can remain as defaults.")
            
            return False
    
    def create_config_from_args(self, args: argparse.Namespace) -> ZotSearchConfig:
        """
        Create configuration from command-line arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Configuration object
        """
        # Start with default config
        config = get_config()
        
        # Override with command-line arguments
        if args.base_path:
            config.base_attachment_path = args.base_path
        
        if args.max_results:
            config.max_results_stage1 = args.max_results
        
        if args.context_window:
            config.context_sentence_window = args.context_window
        
        return config
    
    def handle_output(self, results: List[dict], args: argparse.Namespace) -> None:
        """
        Handle output based on command-line arguments.
        
        Args:
            results: Search results
            args: Parsed command-line arguments
        """
        # Save to CSV if specified
        if args.csv:
            self.result_handler.save_results_to_csv(results, args.csv)
        
        # Save to Markdown if specified
        if args.markdown:
            self.result_handler.save_results_to_markdown(results, args.markdown)
        
        # Print to console unless output-only is specified
        should_print = not (args.csv_only or args.markdown_only)
        if should_print:
            self.result_handler.print_results(results)
        
        # Interactive output choice if no output format specified and results exist
        if not args.csv and not args.markdown and results and should_print:
            filename, output_format = self.result_handler.get_interactive_output_choice()
            if filename and output_format:
                if output_format == 'csv':
                    self.result_handler.save_results_to_csv(results, filename)
                elif output_format == 'md':
                    self.result_handler.save_results_to_markdown(results, filename)
    
    def run(self) -> int:
        """
        Run the CLI application.
        
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Parse arguments
            args = self.parse_arguments()
            
            # Create configuration
            config = self.create_config_from_args(args)
            
            # Validate configuration
            if not self.validate_config(config):
                return 1
            
            # Print configuration info
            print_config_info(config)
            
            # Get search terms
            metadata_query, full_text_terms = self.get_search_terms_interactive()
            
            # Create and run search engine
            search_engine = ZoteroSearchEngine(config)
            
            if not search_engine.connect_to_zotero():
                return 1
            
            print("\nStarting search...")
            results = search_engine.search_zotero_and_full_text(
                metadata_query, full_text_terms
            )
            
            # Handle output
            self.handle_output(results, args)
            
            # Print summary
            if results:
                print(f"\n{search_engine.get_search_summary(results)}")
            
            return 0
            
        except KeyboardInterrupt:
            print("\n\nSearch interrupted by user.")
            return 1
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            return 1


def main() -> int:
    """
    Main entry point for CLI.
    
    Returns:
        Exit code
    """
    cli = ZotSearchCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())