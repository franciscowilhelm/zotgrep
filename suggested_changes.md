# Suggested Changes

## Deferred

### Attachment Selection For Full-Text Search

Suggested future modes:

```bash
zotsearch --zotero "measurement invariance" --fulltext "bifactor" --attachment-scope all-pdfs
zotsearch --zotero "measurement invariance" --fulltext "bifactor" --attachment-scope default
zotsearch --zotero "measurement invariance" --fulltext "bifactor" --attachment-scope first-pdf
```

Recommended behavior:

- Keep the current broad strategy as the default: search across all child attachments returned by `children(item_key)` that have a useful searchable `contentType`.
- Start with PDFs (`application/pdf`) and keep the design open for other searchable attachment types later.
- Add an alternative mode that targets Zotero's default or primary attachment if that can be identified reliably through the API.
- Do not assume the first child is the default attachment unless Zotero or `pyzotero` exposes that explicitly.
- If Zotero does not expose a canonical default attachment, keep `first-pdf` as an explicit heuristic mode rather than silent default behavior.

Implementation note:

- Centralize attachment selection in a dedicated helper so search scope is configurable independently from PDF parsing.

### Zotero Indexed Full Text Via `fulltext_item()`

Suggested future mode:

```bash
zotsearch --zotero "measurement invariance" --fulltext "bifactor" --fulltext-source zotero-index
```

Recommended behavior:

- Explore `pyzotero`'s `fulltext_item()` as an alternative full-text backend for attachment searches.
- Compare Zotero-indexed content against local PDF extraction for coverage, page information, speed, and failure cases.
- Treat this as complementary to direct PDF parsing rather than an automatic replacement.
- Record whether `fulltext_item()` returns enough structure for context windows and page-specific result links.

### Item-Type Filtering

Suggested CLI shape:

```bash
zotsearch --zotero "measurement invariance longitudinal SEM" --metadata-only --item-type journalArticle
```

Recommended behavior:

- Allow repeated `--item-type` flags and/or comma-separated values.
- Filter on Zotero `itemType` after metadata retrieval, similar to the current publication-title filter.
- Keep this available in both metadata-only and full-text modes.

Recommended output note:

- Include the applied item-type filter in JSON, Markdown frontmatter, and console/config summaries.
