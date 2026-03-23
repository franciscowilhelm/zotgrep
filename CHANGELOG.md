# Changelog

## 2.1.0 - 2026-03-23

### Added

- Explicit metadata-only search mode via `--metadata-only` and `--no-fulltext`.
- Default JSON export, with `--json` for custom filenames and `--no-json` to disable it.
- DOI support in result objects and exports.
- Default abstract inclusion, with `--no-abstract` to omit abstracts.
- `suggested_changes.md` to track deferred work such as item-type filtering.

### Changed

- CLI searches with `--zotero` now stay non-interactive unless the user explicitly chooses the interactive workflow.
- Metadata-only searches now stop after Zotero metadata retrieval and do not touch PDFs or attachments.
- Markdown output now uses compact YAML frontmatter and a fuller APA-style reference list to avoid duplicating abstracts and reference metadata.
- CSV output now adapts to metadata-only mode while including DOI and, by default, abstract fields.
- Version metadata has been updated from `2.0.0` to `2.1.0`.

### Notes

- `BASE_ATTACHMENT_PATH` validation is still retained even for metadata-only runs.
