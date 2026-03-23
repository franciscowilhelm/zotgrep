# Suggested Changes

## Deferred

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
