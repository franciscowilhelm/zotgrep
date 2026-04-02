"""
Configuration management for ZotSearch.

This module handles defaults, user config files, environment overrides,
and runtime validation.
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


CONFIG_PATH_ENV_VAR = "ZOTSEARCH_CONFIG_PATH"
DEFAULT_CONFIG_PATH = os.path.join("~", ".config", "zotsearch", "config.json")


@dataclass
class ZotSearchConfig:
    """Configuration class for ZotSearch application."""

    # Zotero API Configuration
    zotero_user_id: str = "0"
    zotero_api_key: str = "local"
    library_type: str = "user"

    # File Paths
    base_attachment_path: str = ""

    # Search Parameters
    max_results_stage1: int = 100
    context_sentence_window: int = 2
    publication_title_filter: Optional[List[str]] = None
    debug_publication_filter: bool = False

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

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the config."""
        return asdict(self)

    def _validate_zotero_config(self) -> None:
        """Validate Zotero API configuration."""
        if not self.use_local_api:
            if self.zotero_user_id in ["your_user_id", ""]:
                raise ValueError("ZOTERO_USER_ID must be set for remote API usage")
            if self.zotero_api_key in ["your_api_key", ""]:
                raise ValueError("ZOTERO_API_KEY must be set for remote API usage")

        if self.library_type not in ["user", "group"]:
            raise ValueError("LIBRARY_TYPE must be either 'user' or 'group'")

    def _validate_paths(self) -> None:
        """Validate file paths."""
        if not self.base_attachment_path:
            return

        if self.base_attachment_path == "YOUR_BASE_ATTACHMENT_DIRECTORY_PATH":
            raise ValueError("Please configure BASE_ATTACHMENT_PATH to a valid directory path")

        if not os.path.isdir(self.base_attachment_path):
            raise ValueError(f"BASE_ATTACHMENT_PATH does not exist: {self.base_attachment_path}")

    def _validate_search_params(self) -> None:
        """Validate search parameters."""
        if self.max_results_stage1 <= 0:
            raise ValueError("max_results_stage1 must be positive")

        if self.context_sentence_window < 0:
            raise ValueError("context_sentence_window must be non-negative")


def get_user_config_path(config_path: Optional[str] = None) -> str:
    """Resolve the on-disk path for the user config file."""
    raw_path = config_path or os.getenv(CONFIG_PATH_ENV_VAR) or DEFAULT_CONFIG_PATH
    return os.path.abspath(os.path.expanduser(raw_path))


def load_config_from_file(config_path: Optional[str] = None) -> ZotSearchConfig:
    """Load configuration from the user config file only."""
    config = create_default_config()
    _apply_config_values(config, _load_config_file_values(config_path, missing_ok=True))
    config.validate()
    return config


def save_config_to_file(config: ZotSearchConfig, config_path: Optional[str] = None) -> str:
    """Persist configuration to disk as JSON."""
    path = get_user_config_path(config_path)
    config.validate()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def load_config_from_env() -> ZotSearchConfig:
    """Load configuration from environment variables."""
    config = create_default_config()
    _apply_env_overrides(config)
    config.validate()
    return config


def create_default_config() -> ZotSearchConfig:
    """Create default configuration."""
    return ZotSearchConfig(
        zotero_user_id="0",
        zotero_api_key="local",
        library_type="user",
        base_attachment_path="",
        max_results_stage1=100,
        context_sentence_window=2,
        publication_title_filter=None,
        debug_publication_filter=False,
        use_local_api=True,
    )


def get_config(
    config_dict: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
) -> ZotSearchConfig:
    """
    Get configuration from defaults, file, environment, and explicit overrides.

    Priority order:
    1. Defaults
    2. User config file
    3. Environment variables
    4. Explicit config_dict overrides
    """
    config = create_default_config()
    _apply_config_values(config, _load_config_file_values(config_path, missing_ok=True))
    _apply_env_overrides(config)
    if config_dict:
        _apply_config_values(config, config_dict)
    config.validate()
    return config


def print_config_info(config: ZotSearchConfig) -> None:
    """Print configuration information for debugging."""
    print(f"Using base attachment path: {config.base_attachment_path}")
    print(f"Zotero API: {'Local' if config.use_local_api else 'Remote'}")
    print(f"Library type: {config.library_type}")
    print(f"Max results (stage 1): {config.max_results_stage1}")
    print(f"Context sentence window: {config.context_sentence_window}")
    if config.publication_title_filter:
        print(f"Publication title filter: {', '.join(config.publication_title_filter)}")
    if config.debug_publication_filter:
        print("Publication title debug: enabled")


def _parse_csv_env(value: str) -> Optional[List[str]]:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def _load_config_file_values(
    config_path: Optional[str] = None,
    missing_ok: bool = False,
) -> Dict[str, Any]:
    path = get_user_config_path(config_path)
    if not os.path.exists(path):
        if missing_ok:
            return {}
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8") as handle:
        values = json.load(handle)

    if not isinstance(values, dict):
        raise ValueError("Config file must contain a JSON object")

    if isinstance(values.get("publication_title_filter"), str):
        values["publication_title_filter"] = _parse_csv_env(values["publication_title_filter"])

    return {
        key: value
        for key, value in values.items()
        if key in ZotSearchConfig.__dataclass_fields__
    }


def _apply_config_values(config: ZotSearchConfig, values: Dict[str, Any]) -> None:
    for key, value in values.items():
        if key not in ZotSearchConfig.__dataclass_fields__:
            continue
        setattr(config, key, value)


def _apply_env_overrides(config: ZotSearchConfig) -> None:
    """
    Apply env overrides without forcing users to set every field.
    """
    zotero_user_id = os.getenv("ZOTERO_USER_ID")
    if zotero_user_id is not None:
        config.zotero_user_id = zotero_user_id

    zotero_api_key = os.getenv("ZOTERO_API_KEY")
    if zotero_api_key is not None:
        config.zotero_api_key = zotero_api_key

    library_type = os.getenv("ZOTERO_LIBRARY_TYPE")
    if library_type is not None:
        config.library_type = library_type

    base_attachment_path = os.getenv("ZOTERO_BASE_ATTACHMENT_PATH")
    if base_attachment_path is not None:
        config.base_attachment_path = base_attachment_path

    max_results = os.getenv("ZOTERO_MAX_RESULTS")
    if max_results:
        config.max_results_stage1 = int(max_results)

    context_window = os.getenv("ZOTERO_CONTEXT_WINDOW")
    if context_window:
        config.context_sentence_window = int(context_window)

    publication_filter = _parse_csv_env(os.getenv("ZOTERO_PUBLICATION_TITLE_FILTER", ""))
    if publication_filter is not None:
        config.publication_title_filter = publication_filter

    debug_publication = os.getenv("ZOTERO_DEBUG_PUBLICATION_FILTER")
    if debug_publication:
        config.debug_publication_filter = debug_publication.lower() in ["1", "true", "yes"]

    use_local_api = os.getenv("ZOTERO_USE_LOCAL_API")
    if use_local_api is not None:
        config.use_local_api = use_local_api.lower() == "true"
