# Pyzotero 1.15.1 compatibility review

Reviewed on 2026-09-16 for Zotgrep 3.2.0, upgrading the lockfile from 1.11.0.

Sources: [PyPI release](https://pypi.org/project/pyzotero/1.15.1/),
[upstream changes](https://github.com/urschrei/pyzotero/compare/v1.11.0...v1.15.1),
[API documentation](https://pyzotero.readthedocs.io/en/latest/).

## Compatibility and new features

- Python minimum rose from 3.9 to 3.10. Zotgrep already requires 3.11+, so its supported Python range is unchanged.
- The HTTP dependency changed from `httpx` to `httpx2` in 1.15.0. Custom clients, transports, and HTTP exception handlers must use the new package. Zotgrep had no direct dependency on the old HTTP package; the refreshed lockfile uses `httpx2`, and attachment transport tests use its `MockTransport`.
- Local API reads now capture and resend `Zotero-Server-ID`. Local writes add separate key authorization, an `authorize_local()` method, and dedicated local authentication/server-ID exceptions. Zotgrep does not write to Zotero or need an authorization prompt. Its attachment reader preserves the server-ID header from the preceding API response.
- Rate-limited reads and uploads now retry with bounded attempts; exhausted retries raise `TooManyRetriesError`. Existing search error handling still catches these failures.
- `follow()` now returns `None` when pagination is exhausted; `last_modified_version()` preserves pagination state. Zotgrep does not call either directly. The existing `all_collections()` usage remains supported.
- Upload fixes, configurable write/upload timeouts, `moveto_collection()`, expanded optional CLI commands, and MCP 2 support do not require changes to Zotgrep's read-only workflow. Optional CLI/MCP extras are not installed.
- The deprecated `preserve_json_order` constructor option is not used. The public `from pyzotero import zotero` facade remains available. No new use of private Pyzotero methods is introduced.
- The dependency's license remains Blue Oak 1.0.0; its packaging switched to PEP 639 metadata.

## Stored attachment diagnosis

Zotero returns a 302 response from the local attachment `/file` endpoint, with a percent-encoded `file:///...` Location. Both Pyzotero 1.11.0 and 1.15.1 failed while routing such redirects on this Windows machine. The exception occurs before reliable file existence checking; it is not evidence that the file is absent.

Of five previously failing attachment keys checked locally, three target files were missing and two existed. Reading the original Location with `urlsplit()` and platform-native `url2pathname()` recovered the two existing PDFs (20 and 17 pages). Missing files remained missing; this change cannot restore them.

Zotgrep now requests the local attachment endpoint without following redirects, decodes only local file URLs, and reads the bytes directly. Direct HTTP 200 PDF responses are also supported. HTTP errors and missing files remain distinct, and the UI receives incomplete-results warnings. Linked attachment failures also produce a visible warning.

Tests cover percent-encoded spaces, Unicode, `#` and `%` in filenames; group-library routing; server-ID propagation; direct PDF responses; missing files; rejected non-local URLs; HTTP errors; and visible missing-versus-unreadable warnings. Live checks verify that the two previously skipped but present PDFs are readable and extract text under Pyzotero 1.15.1.
