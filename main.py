#!/usr/bin/env python3
"""
ZotSearch - Enhanced Zotero Library and Full-Text PDF Search

Main entry point for the modular ZotSearch application.
This script provides the same functionality as the original zotsearch.py
but with a clean, modular architecture.

Usage:
    python main.py
    python main.py --csv results.csv
    python main.py --csv results.csv --csv-only
"""

import sys
import os

# Add the current directory to Python path to import zotsearch package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zotsearch.cli import main

if __name__ == "__main__":
    sys.exit(main())