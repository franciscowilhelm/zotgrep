"""
Configuration management for ZotGrep.

This module handles defaults, user config files, environment overrides,
and runtime validation.
"""

import json
import os
import stat
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


CONFIG_PATH_ENV_VAR = "ZOTGREP_CONFIG_PATH"
DEFAULT_CONFIG_PATH = os.path.join("~", ".config", "zotgrep", "config.json")


@dataclass
class ZotGrepConfig:
    """Configuration class for ZotGrep application."""

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
    item_type_filter: Optional[List[str]] = None
    collection_filter: Optional[str] = None
    tag_filter: Optional[List[str]] = None
    tag_match_mode: str = "all"

    # Metadata search mode: controls Zotero API qmode parameter.
    # "titleCreatorYear" searches title, author, and year fields (default).
    # "everything" also searches Zotero's indexed attachment content.
    metadata_search_mode: str = "titleCreatorYear"

    # Fulltext extraction source for Stage 2.
    # "pdf" (default): download and extract text from the PDF file.
    # "zotero-index": fetch pre-indexed text via pyzotero fulltext_item() — experimental.
    #   No page-level information is available in this mode; all hits are reported on page 0.
    fulltext_source: str = "pdf"

    # Internal compatibility flag. ZotGrep only supports the local Zotero API.
    use_local_api: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()

    def validate(self) -> None:
        """Validate all configuration settings."""
        self._validate_zotero_config()
        self._validate_paths()
        self._validate_search_params()

    def to_dict(self, *, include_secrets: bool = True) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the config.

        Args:
            include_secrets: When False, the API key is redacted. Pass False
                for logging or any context where the value might be exposed.
        """
        values = asdict(self)
        values.pop("use_local_api", None)
        if not include_secrets:
            values["zotero_api_key"] = "***"
        return values

    def _validate_zotero_config(self) -> None:
        """Validate Zotero API configuration."""
        # Full-text search relies on Zotero's local API. Ignore any stale config/env
        # attempts to switch this off after the project rename.
        self.use_local_api = True

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

        if self.tag_match_mode not in {"all", "any"}:
            raise ValueError("tag_match_mode must be either 'all' or 'any'")

        if self.metadata_search_mode not in {"titleCreatorYear", "everything"}:
            raise ValueError(
                "metadata_search_mode must be either 'titleCreatorYear' or 'everything'"
            )

        if self.fulltext_source not in {"pdf", "zotero-index"}:
            raise ValueError("fulltext_source must be either 'pdf' or 'zotero-index'")


def get_user_config_path(config_path: Optional[str] = None) -> str:
    """Resolve the on-disk path for the user config file."""
    raw_path = config_path or os.getenv(CONFIG_PATH_ENV_VAR) or DEFAULT_CONFIG_PATH
    return os.path.abspath(os.path.expanduser(raw_path))


def load_config_from_file(config_path: Optional[str] = None) -> ZotGrepConfig:
    """Load configuration from the user config file only."""
    config = create_default_config()
    _apply_config_values(config, _load_config_file_values(config_path, missing_ok=True))
    config.validate()
    return config


def save_config_to_file(config: ZotGrepConfig, config_path: Optional[str] = None) -> str:
    """Persist configuration to disk as JSON."""
    path = get_user_config_path(config_path)
    config.validate()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Write with restricted permissions (owner read/write only) to protect
    # the API key in case users configure a real Zotero Web API key.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def load_config_from_env() -> ZotGrepConfig:
    """Load configuration from environment variables."""
    config = create_default_config()
    _apply_env_overrides(config)
    config.validate()
    return config


def create_default_config() -> ZotGrepConfig:
    """Create default configuration."""
    return ZotGrepConfig(
        zotero_user_id="0",
        zotero_api_key="local",
        library_type="user",
        base_attachment_path="",
        max_results_stage1=100,
        context_sentence_window=2,
        publication_title_filter=None,
        debug_publication_filter=False,
        item_type_filter=None,
        collection_filter=None,
        tag_filter=None,
        tag_match_mode="all",
        metadata_search_mode="titleCreatorYear",
        fulltext_source="pdf",
        use_local_api=True,
    )


def get_config(
    config_dict: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
) -> ZotGrepConfig:
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


def print_config_info(config: ZotGrepConfig) -> None:
    """Print configuration information for debugging."""
    print(f"Using base attachment path: {config.base_attachment_path}")
    print("Zotero API: Local")
    print(f"Library type: {config.library_type}")
    print(f"Max results (stage 1): {config.max_results_stage1}")
    print(f"Context sentence window: {config.context_sentence_window}")
    if config.publication_title_filter:
        print(f"Publication title filter: {', '.join(config.publication_title_filter)}")
    if config.debug_publication_filter:
        print("Publication title debug: enabled")
    if config.item_type_filter:
        print(f"Item type filter: {', '.join(config.item_type_filter)}")
    if config.collection_filter:
        print(f"Collection filter: {config.collection_filter}")
    if config.tag_filter:
        print(f"Tag filter ({config.tag_match_mode}): {', '.join(config.tag_filter)}")
    if config.metadata_search_mode != "titleCreatorYear":
        print(f"Metadata search mode: {config.metadata_search_mode}")
    if config.fulltext_source != "pdf":
        print(f"Fulltext source: {config.fulltext_source} (experimental)")


def _parse_csv_env(value: str) -> Optional[List[str]]:
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


def _normalize_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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
    if isinstance(values.get("item_type_filter"), str):
        values["item_type_filter"] = _parse_csv_env(values["item_type_filter"])
    if isinstance(values.get("tag_filter"), str):
        values["tag_filter"] = _parse_csv_env(values["tag_filter"])
    if "collection_filter" in values:
        values["collection_filter"] = _normalize_optional_string(values["collection_filter"])
    if "tag_match_mode" in values and values["tag_match_mode"] is not None:
        values["tag_match_mode"] = str(values["tag_match_mode"]).strip().lower()

    return {
        key: value
        for key, value in values.items()
        if key in ZotGrepConfig.__dataclass_fields__
    }


def _apply_config_values(config: ZotGrepConfig, values: Dict[str, Any]) -> None:
    for key, value in values.items():
        if key not in ZotGrepConfig.__dataclass_fields__:
            continue
        if key == "use_local_api":
            continue
        setattr(config, key, value)


def _apply_env_overrides(config: ZotGrepConfig) -> None:
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

    item_type_filter = _parse_csv_env(os.getenv("ZOTERO_ITEM_TYPE_FILTER", ""))
    if item_type_filter is not None:
        config.item_type_filter = item_type_filter

    collection_filter = os.getenv("ZOTERO_COLLECTION_FILTER")
    if collection_filter is not None:
        config.collection_filter = _normalize_optional_string(collection_filter)

    tag_filter = _parse_csv_env(os.getenv("ZOTERO_TAG_FILTER", ""))
    if tag_filter is not None:
        config.tag_filter = tag_filter

    tag_match_mode = os.getenv("ZOTERO_TAG_MATCH_MODE")
    if tag_match_mode is not None:
        config.tag_match_mode = tag_match_mode.strip().lower() or "all"

    metadata_search_mode = os.getenv("ZOTERO_METADATA_SEARCH_MODE")
    if metadata_search_mode is not None:
        config.metadata_search_mode = metadata_search_mode.strip() or "titleCreatorYear"

    fulltext_source = os.getenv("ZOTERO_FULLTEXT_SOURCE")
    if fulltext_source is not None:
        config.fulltext_source = fulltext_source.strip() or "pdf"
