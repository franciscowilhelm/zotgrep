"""
Configuration management for ZotSearch.

This module handles all configuration settings, validation, and environment setup.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ZotSearchConfig:
    """Configuration class for ZotSearch application."""
    
    # Zotero API Configuration
    zotero_user_id: str = '0'
    zotero_api_key: str = 'local'
    library_type: str = 'user'
    
    # File Paths
    base_attachment_path: str = ''
    
    # Search Parameters
    max_results_stage1: int = 100
    context_sentence_window: int = 2
    
    # Local API flag
    use_local_api: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate all configuration settings."""
        self._validate_zotero_config()
        self._validate_paths()
        self._validate_search_params()
    
    def _validate_zotero_config(self) -> None:
        """Validate Zotero API configuration."""
        if not self.use_local_api:
            if self.zotero_user_id in ['your_user_id', '']:
                raise ValueError("ZOTERO_USER_ID must be set for remote API usage")
            if self.zotero_api_key in ['your_api_key', '']:
                raise ValueError("ZOTERO_API_KEY must be set for remote API usage")
        
        if self.library_type not in ['user', 'group']:
            raise ValueError("LIBRARY_TYPE must be either 'user' or 'group'")
    
    def _validate_paths(self) -> None:
        """Validate file paths."""
        if not self.base_attachment_path:
            raise ValueError("BASE_ATTACHMENT_PATH must be set")
        
        if self.base_attachment_path == 'YOUR_BASE_ATTACHMENT_DIRECTORY_PATH':
            raise ValueError("Please configure BASE_ATTACHMENT_PATH to a valid directory path")
        
        if not os.path.isdir(self.base_attachment_path):
            raise ValueError(f"BASE_ATTACHMENT_PATH does not exist: {self.base_attachment_path}")
    
    def _validate_search_params(self) -> None:
        """Validate search parameters."""
        if self.max_results_stage1 <= 0:
            raise ValueError("max_results_stage1 must be positive")
        
        if self.context_sentence_window < 0:
            raise ValueError("context_sentence_window must be non-negative")


def load_config_from_env() -> ZotSearchConfig:
    """Load configuration from environment variables."""
    return ZotSearchConfig(
        zotero_user_id=os.getenv('ZOTERO_USER_ID', '0'),
        zotero_api_key=os.getenv('ZOTERO_API_KEY', 'local'),
        library_type=os.getenv('ZOTERO_LIBRARY_TYPE', 'user'),
        base_attachment_path=os.getenv('ZOTERO_BASE_ATTACHMENT_PATH', ''),
        max_results_stage1=int(os.getenv('ZOTERO_MAX_RESULTS', '100')),
        context_sentence_window=int(os.getenv('ZOTERO_CONTEXT_WINDOW', '2')),
        use_local_api=os.getenv('ZOTERO_USE_LOCAL_API', 'true').lower() == 'true'
    )


def create_default_config() -> ZotSearchConfig:
    """Create default configuration matching original script."""
    return ZotSearchConfig(
        zotero_user_id='0',
        zotero_api_key='local',
        library_type='user',
        base_attachment_path='/Users/francisco/Library/CloudStorage/OneDrive-UniversitaetBern/ZoteroAttachments',
        max_results_stage1=100,
        context_sentence_window=2,
        use_local_api=True
    )


def get_config(config_dict: Optional[Dict[str, Any]] = None) -> ZotSearchConfig:
    """
    Get configuration from various sources.
    
    Priority order:
    1. Provided config_dict
    2. Environment variables
    3. Default configuration
    
    Args:
        config_dict: Optional dictionary with configuration values
        
    Returns:
        ZotSearchConfig: Validated configuration object
    """
    if config_dict:
        return ZotSearchConfig(**config_dict)
    
    # Try to load from environment first
    try:
        return load_config_from_env()
    except ValueError:
        # Fall back to default config
        return create_default_config()


def print_config_info(config: ZotSearchConfig) -> None:
    """Print configuration information for debugging."""
    print(f"Using base attachment path: {config.base_attachment_path}")
    print(f"Zotero API: {'Local' if config.use_local_api else 'Remote'}")
    print(f"Library type: {config.library_type}")
    print(f"Max results (stage 1): {config.max_results_stage1}")
    print(f"Context sentence window: {config.context_sentence_window}")