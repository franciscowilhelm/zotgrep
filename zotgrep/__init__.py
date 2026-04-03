"""
ZotGrep - Enhanced Zotero Library and Full-Text PDF Search

A modular Python package for searching Zotero libraries and full-text PDFs.
"""

__version__ = "3.0.0"
__author__ = "ZotGrep Contributors"

# Import main classes for easy access
from .search_engine import ZoteroSearchEngine
from .config import ZotGrepConfig
from .result_handler import ResultHandler

__all__ = [
    'ZoteroSearchEngine',
    'ZotGrepConfig', 
    'ResultHandler'
]
