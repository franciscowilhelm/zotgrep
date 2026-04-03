#!/usr/bin/env python3
"""
ZotGrep - Enhanced Zotero Library and Full-Text PDF Search

Main entry point for the modular ZotGrep application.
This script provides the package CLI in a simple top-level entry point.

Usage:
    python main.py
    python main.py --csv results.csv
    python main.py --csv results.csv --csv-only
"""

import sys
import os

# Add the current directory to Python path to import zotgrep package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zotgrep.cli import main

if __name__ == "__main__":
    sys.exit(main())
