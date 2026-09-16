"""Read stored attachments from Zotero's local API without HTTP file redirects."""

from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from urllib.request import url2pathname


def read_local_file_url(url: str) -> bytes:
    """Decode a local file URI using the host platform's path conventions."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "file"
        or parsed.netloc.lower() not in {"", "localhost"}
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Zotero returned an unsupported local attachment URL")
    return Path(url2pathname(parsed.path)).read_bytes()


def read_stored_attachment(connection: Any, key: str) -> bytes:
    """Handle Zotero's file response before HTTP redirect handling changes it.

    Pyzotero 1.15.1 still passes file redirects through its HTTP client, which
    can misroute them or inherit the HTTP hostname. Reading the original
    Location also lets us distinguish missing files from protocol errors.
    """
    url = (
        f"{connection.endpoint.rstrip('/')}/{connection.library_type}/"
        f"{connection.library_id}/items/{quote(key, safe='')}/file"
    )
    headers = {}
    # Preserve the server identity established by the preceding metadata read.
    if connection.request is not None:
        server_id = connection.request.headers.get("Zotero-Server-ID")
        if server_id:
            headers["Zotero-Server-ID"] = server_id
    response = connection.client.get(
        url, headers=headers, follow_redirects=False, timeout=30,
    )
    if response.status_code in {301, 302, 303, 307, 308}:
        return read_local_file_url(response.headers.get("Location", ""))
    response.raise_for_status()
    return response.content
