"""
ZotSearch - Enhanced Zotero Library and Full-Text PDF Search

A modular Python package for searching Zotero libraries and full-text PDFs.
"""

__version__ = "2.1.0"
__author__ = "ZotSearch Contributors"

# Import main classes for easy access
from .search_engine import ZoteroSearchEngine
from .config import ZotSearchConfig
from .result_handler import ResultHandler

__all__ = [
    'ZoteroSearchEngine',
    'ZotSearchConfig', 
    'ResultHandler'
]
