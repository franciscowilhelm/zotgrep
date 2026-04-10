"""Runtime package metadata helpers."""

from functools import lru_cache
from importlib import metadata
from pathlib import Path
import tomllib


@lru_cache(maxsize=1)
def get_runtime_version() -> str:
    """Return the package version from installed metadata, with a local fallback."""
    try:
        return metadata.version("zotgrep")
    except metadata.PackageNotFoundError:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        try:
            with pyproject_path.open("rb") as handle:
                return tomllib.load(handle)["project"]["version"]
        except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
            return "0+unknown"
