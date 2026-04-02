# Changelog

## 3.0.0 - Unreleased

### Added

- A dedicated Flask-based web interface with a separate `General Settings` page, persistent user settings, and export actions for CSV, JSON, and Markdown.
- User config file support via `~/.config/zotsearch/config.json`, plus `--config` and `ZOTSEARCH_CONFIG_PATH` for custom config locations.
- Focused regression tests for config behavior, search-engine attachment handling, web settings persistence, and richer Markdown output.
- Deferred feature notes for future attachment-selection modes and Zotero `fulltext_item()` support in `suggested_changes.md`.

### Changed

- Full-text attachment handling now supports both linked attachments and Zotero-stored PDFs, including `imported_url` attachments retrieved through `pyzotero`.
- `BASE_ATTACHMENT_PATH` is now optional and only required for linked-file workflows.
- Web search results are grouped by reference, show per-term occurrence summaries, and collapse to the first 10 hits per paper with an expand control.
- Markdown output now summarizes per-reference full-text term counts before numbered occurrence sections.
- Documentation now reflects the config-file workflow, linked-vs-stored attachment behavior, and web UI usage.

### Internal

- Removed tracked Python bytecode caches from the release commit and reinforced cache ignores in `.gitignore`.

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
