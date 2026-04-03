"""
Command-line interface module for ZotGrep.

This module handles argument parsing, user interaction, and CLI-specific functionality.
"""

import argparse
import sys
from typing import List, Tuple, Optional

from .config import ZotGrepConfig, get_config, print_config_info
from .search_engine import ZoteroSearchEngine
from .result_handler import ResultHandler


class ZotGrepCLI:
    """Command-line interface for ZotGrep."""
    
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
            description='Search Zotero library metadata and optionally full-text PDFs',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python main.py
  python main.py --csv results.csv
  python main.py --md results.md
  python main.py --csv results.csv --csv-only
  python main.py --markdown results.md --markdown-only
  python main.py --zotero "machine learning health"
  python main.py --zotero "machine learning health" --fulltext "algorithm, bias"
  python main.py --zotero "AI ethics" --fulltext "privacy, fairness" --csv results.csv
            """
        )

        parser.add_argument(
            '--zotero',
            type=str,
            help='Zotero metadata search terms (e.g., "machine learning health")'
        )

        parser.add_argument(
            '--fulltext',
            type=str,
            help='Full-text search terms, comma-separated (e.g., "algorithm, bias")'
        )

        parser.add_argument(
            '--metadata-only', '--no-fulltext',
            action='store_true',
            dest='metadata_only',
            help='Run only the Zotero metadata search and skip all PDF/full-text processing'
        )

        parser.add_argument(
            '--no-abstract',
            action='store_true',
            help='Omit abstracts from output'
        )

        parser.add_argument(
            '--publication', '--publication-title',
            type=str,
            dest='publication_title',
            help='Filter results by publication title (comma-separated for multiple)'
        )

        parser.add_argument(
            '--debug-publication',
            action='store_true',
            help='Print publication titles of matched items before filtering'
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
            '--json',
            type=str,
            help='Save results to JSON file (specify filename). If omitted, JSON is still saved by default.'
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
            '--no-json',
            action='store_true',
            help='Do not save the default JSON output'
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
            '--web',
            action='store_true',
            help='Launch web interface instead of CLI'
        )

        parser.add_argument(
            '--port',
            type=int,
            default=23120,
            help='Port for web interface (default: 23120)'
        )

        parser.add_argument(
            '--version',
            action='version',
            version='ZotGrep 2.1.0'
        )

        return parser.parse_args()
    
    def get_search_terms_interactive(self) -> Tuple[str, List[str]]:
        """
        Get search terms from user input interactively.
        
        Returns:
            Tuple of (metadata_query, full_text_terms_list)
        """
        print("\n=== ZotGrep - Interactive Mode ===")
        
        metadata_query = input("Enter Zotero metadata search terms (e.g., 'machine learning health'): ").strip()
        if not metadata_query:
            print("Error: Metadata search terms cannot be empty.")
            sys.exit(1)
        
        full_text_query_str = input(
            "Enter full-text search terms, comma-separated (optional; leave blank to skip): "
        ).strip()
        
        full_text_terms_list = [term.strip() for term in full_text_query_str.split(',') if term.strip()]
        
        return metadata_query, full_text_terms_list
    
    def validate_config(self, config: ZotGrepConfig) -> bool:
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
                print("\nBASE_ATTACHMENT_PATH is only needed for linked-file workflows.")
                print("Set it to the directory where your linked PDFs live.")
                print("Examples:")
                print("  - macOS: /Users/yourname/OneDrive/ZoteroAttachments")
                print("  - Windows: C:\\Users\\yourname\\OneDrive\\ZoteroAttachments")
                print("  - Linux: /home/yourname/ZoteroAttachments")
                print("\nIf you use Zotero-stored files only, you can leave BASE_ATTACHMENT_PATH unset.")
            
            return False
    
    def create_config_from_args(self, args: argparse.Namespace) -> ZotGrepConfig:
        """
        Create configuration from command-line arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Configuration object
        """
        # Start with default config
        config = get_config(config_path=args.config)
        
        # Override with command-line arguments
        if args.base_path:
            config.base_attachment_path = args.base_path
        
        if args.max_results:
            config.max_results_stage1 = args.max_results
        
        if args.context_window:
            config.context_sentence_window = args.context_window

        if args.publication_title:
            publication_titles = [t.strip() for t in args.publication_title.split(',') if t.strip()]
            config.publication_title_filter = publication_titles or None

        if args.debug_publication:
            config.debug_publication_filter = True
        
        return config
    
    def handle_output(
        self,
        results: List[dict],
        args: argparse.Namespace,
        metadata_query: Optional[str] = None,
        full_text_terms: Optional[List[str]] = None,
        include_abstract: bool = False,
        allow_interactive_output: bool = True,
        context_window: Optional[int] = None,
        search_timestamp: Optional[str] = None,
    ) -> None:
        """
        Handle output based on command-line arguments.

        Args:
            results: Search results
            args: Parsed command-line arguments
            metadata_query: Zotero metadata search query
            full_text_terms: List of full-text search terms
            allow_interactive_output: Whether to prompt for output format when none was supplied
            context_window: Context window size
            search_timestamp: Search timestamp (optional)
        """
        if results and not args.no_json:
            json_filename = args.json or self.result_handler.get_default_json_filename(search_timestamp)
            self.result_handler.save_results_to_json(
                results,
                json_filename,
                zotero_query=metadata_query,
                full_text_query=full_text_terms,
                include_abstract=include_abstract,
                context_window=context_window,
                search_timestamp=search_timestamp,
            )

        # Save to CSV if specified
        if args.csv:
            self.result_handler.save_results_to_csv(results, args.csv, include_abstract=include_abstract)

        # Save to Markdown if specified
        if args.markdown:
            print(f"Attempting to save {len(results)} results to Markdown.") # Added logging
            self.result_handler.save_results_to_markdown(
                results,
                args.markdown,
                zotero_query=metadata_query,
                full_text_query=full_text_terms,
                include_abstract=include_abstract,
                context_window=context_window,
                search_timestamp=search_timestamp,
            )

        # Print to console unless output-only is specified
        should_print = not (args.csv_only or args.markdown_only)
        if should_print:
            self.result_handler.print_results(results)

        # Interactive output choice if no output format specified and results exist
        if allow_interactive_output and not args.csv and not args.markdown and results and should_print:
            filename, output_format = self.result_handler.get_interactive_output_choice()
            if filename and output_format:
                if output_format == 'csv':
                    self.result_handler.save_results_to_csv(results, filename, include_abstract=include_abstract)
                elif output_format == 'md':
                    print(f"Attempting to save {len(results)} results to Markdown.") # Added logging
                    self.result_handler.save_results_to_markdown(
                        results,
                        filename,
                        zotero_query=metadata_query,
                        full_text_query=full_text_terms,
                        include_abstract=include_abstract,
                        context_window=context_window,
                        search_timestamp=search_timestamp,
                    )
    
    def run(self) -> int:
        """
        Run the CLI application.
        
        Returns:
            Exit code (0 for success, 1 for error)
        """
        try:
            # Parse arguments
            args = self.parse_arguments()

            # Launch web interface if requested
            if args.web:
                from .web import create_app
                app = create_app()
                print(f"Starting ZotGrep web interface at http://localhost:{args.port}")
                app.run(host="127.0.0.1", port=args.port, debug=False)
                return 0

            # Create configuration
            config = self.create_config_from_args(args)
            
            # Validate configuration
            if not self.validate_config(config):
                return 1
            
            # Print configuration info
            print_config_info(config)

            if args.json and args.no_json:
                print("Error: Cannot use --json and --no-json together.")
                return 1
            
            # Get search terms: prefer CLI args, else interactive
            if args.zotero:
                metadata_query = args.zotero.strip()
                full_text_terms = [term.strip() for term in args.fulltext.split(',') if term.strip()] if args.fulltext else []
                if not metadata_query:
                    print("Error: --zotero argument cannot be empty.")
                    return 1
                if args.metadata_only and args.fulltext:
                    print("Error: --metadata-only/--no-fulltext cannot be combined with --fulltext.")
                    return 1
                if args.fulltext is not None and not full_text_terms:
                    print(
                        "Error: --fulltext argument must provide at least one term. "
                        "If you want metadata-only results, omit --fulltext or pass "
                        "--metadata-only/--no-fulltext."
                    )
                    return 1
            else:
                metadata_query, full_text_terms = self.get_search_terms_interactive()
            
            # Create and run search engine
            search_engine = ZoteroSearchEngine(config)
            
            if not search_engine.connect_to_zotero():
                return 1
            
            print("\nStarting search...")
            results = search_engine.search_zotero_and_full_text(
                metadata_query,
                full_text_terms,
                include_abstract=not args.no_abstract,
                metadata_only=args.metadata_only,
            )

            # Handle output, passing search metadata
            self.handle_output(
                results,
                args,
                metadata_query=metadata_query,
                full_text_terms=full_text_terms,
                include_abstract=not args.no_abstract,
                allow_interactive_output=not bool(args.zotero),
                context_window=config.context_sentence_window,
                search_timestamp=None,  # Could be set to now or from results if needed
            )

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
    cli = ZotGrepCLI()
    return cli.run()


if __name__ == "__main__":
    print(
        "\n[DEPRECATION WARNING]\n"
        "Direct execution of 'cli.py' as a script is deprecated and will be removed in a future release.\n"
        "Please use the package interface instead:\n"
        "    zotgrep\n"
    )
    sys.exit(main())
