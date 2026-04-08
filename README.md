# ZotGrep - Enhanced Zotero Library and Full-Text PDF Search

ZotGrep is a Python package that enables users to search their local Zotero library using the API and then search for full-text content within PDFs. It includes multiple output formats (CSV and Markdown) and Zotero URL integration for direct access to search results.

Credits: ZotGrep builds on [pyzotero](https://github.com/urschrei/pyzotero) by Stephan Hugel.

Disclaimer: The project was largely vibe-coded using Claude and ChatGPT.

The package was originally designed around ZotMoov and a linked file structure, where PDFs sit in a linked folder (e.g., OneDrive) rather than in the Zotero library folder. It now also works with Zotero-stored PDF attachments by downloading the attachment bytes via `pyzotero`.

The general workflow involves a) including search terms for references in the Zotero library, b) full-text search among the results for a new set of keywords. The output will contain all hits among the references. 

## Features

### Core Functionality
- Search Zotero library metadata (titles, authors, etc.)
- Full-text search within PDF attachments (both linked and imported files)
- Support for both local linked files and Zotero-stored PDFs
- Context-aware text extraction with highlighted search terms
- **Multiple Output Formats**: Save search results to CSV or Markdown files
- **CSV Export**: Structured data format with comprehensive metadata for analysis
- **Markdown Export**: Research-friendly format with YAML frontmatter for note-taking apps
- **Zotero URLs**: Direct links to open items and specific PDF pages in Zotero
- **Enhanced Metadata**: Author names, publication years, and timestamps
- **Command-line Options**: Automation-friendly with argument parsing
- **Interactive Output Choice**: Choose between CSV, Markdown, or no file output

## Installation

### Install with uv
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

This installs the project locally in editable mode and exposes the `zotgrep` shell command.

If you want to install it as a uv-managed tool instead of inside a project virtual environment:

```bash
uv tool install .
```

## Usage

### Web Interface

Launch the local web interface with:

```bash
zotgrep --web
```

By default the web UI runs on `http://127.0.0.1:23120`. You can override that with `--port`, for example:

```bash
zotgrep --web --port 23121
```

ZotGrep supports a user config file for persistent defaults. You can manage the most important settings via the web UI under `General Settings`. Use that page to save defaults such as linked-file paths, result limits, and context-window size. The main search page then uses those saved defaults and keeps only per-search inputs in the form. See `Advanced` for configuring settings via a JSON file.

### Interactive Search via Command Line Interface

You can use ZotGrep via the `zotgrep` shell command or the module interface, which provides an interactive shell:

```bash
zotgrep
```

Equivalent module form:

```bash
python -m zotgrep
```

This will prompt you for:
- Metadata search terms (searches titles, authors, etc.)
- Full-text search terms (comma-separated list)

After displaying results, you'll be offered output format choices:

```
Output options:
1. CSV file (spreadsheet format)
2. Markdown file (research notes format)
3. No file output
Choose output format (1/2/3):
```

### Direct Search via Command Line

You can specify search terms directly via command line arguments for non-interactive use:

```bash
zotgrep --zotero "career engagement"
zotgrep --zotero "career engagement" --fulltext "barriers"
zotgrep --zotero "career engagement" --metadata-only
zotgrep --zotero "career engagement" --no-abstract
zotgrep --zotero "AI ethics" --item-type "journalArticle, bookSection" --tags "privacy, fairness" --tag-match any
zotgrep --zotero "measurement invariance" --collection "Focused Review"
```
- `--zotero` specifies the metadata search string (e.g., title, author, etc.).
- `--fulltext` optionally specifies the full-text search terms (comma-separated).
- `--metadata-only` / `--no-fulltext` runs only the metadata search and skips PDF/full-text processing.
- abstracts are included by default; `--no-abstract` omits them.
- `--publication` / `--publication-title` filters results by publication title (comma-separated for multiple).
- `--item-type` / `--itemtype` filters by Zotero item type (comma-separated for multiple).
- `--collection` filters by a Zotero collection key or exact collection name.
- `--tag` / `--tags` filters by Zotero tag (comma-separated for multiple).
- `--tag-match {all,any}` controls whether all supplied tags are required or any single tag is enough.

This allows for scripting and automation without interactive prompts. All other output and configuration options remain available.

Example with output:
```bash
zotgrep --zotero "AI ethics" --fulltext "privacy, fairness" --csv results.csv
```

Example with publication filter (list via comma-separated values):
```bash
zotgrep --zotero "AI ethics" --fulltext "privacy, fairness" --publication "Nature, Science"
```

Example with metadata filters:
```bash
zotgrep --zotero "AI ethics" --fulltext "privacy, fairness" --item-type "journalArticle" --collection "Focused Review" --tags "privacy, fairness" --tag-match all
```

### Output Format Options

#### CSV Export
Save results to CSV format for data analysis and spreadsheet applications:

```bash
# Save to specific CSV file
zotgrep --csv results.csv

# Save to CSV only (no console output)
zotgrep --csv results.csv --csv-only
```

#### Markdown Export
Save results to Markdown format for research notes and documentation:

```bash
# Save to specific Markdown file
zotgrep --md results.md
zotgrep --markdown results.md

# Save to Markdown only (no console output)
zotgrep --md results.md --md-only
zotgrep --markdown results.md --markdown-only
```

#### JSON Export
Structured JSON output is saved by default unless `--no-json` is used. You can also specify a filename explicitly:

```bash
zotgrep --zotero "career engagement" --json results.json
zotgrep --zotero "career engagement" --no-json
```

JSON and Markdown frontmatter both record the applied metadata filters inside `search_details.metadata_filters`.

#### Interactive Output Choice

When no output format is specified, the script offers an interactive menu to choose between CSV, Markdown, or no file output.

## Output Formats

### CSV Output Format

The CSV file includes the following columns for structured data analysis:

| Column | Description |
|--------|-------------|
| `reference_title` | Title of the reference |
| `authors` | Author names (Last, First; format) |
| `publication_year` | Publication year |
| `publication_title` | Journal or publication title |
| `doi` | DOI when available |
| `reference_key` | Zotero item key |
| `abstract` | Abstract text unless `--no-abstract` is requested |
| `pdf_filename` | PDF file name |
| `pdf_key` | PDF attachment key |
| `page_number` | Page where term was found |
| `search_term_found` | The specific search term that matched |
| `context` | Text context around the found term |
| `zotero_item_url` | URL to open item in Zotero |
| `zotero_pdf_url` | URL to open specific PDF page in Zotero |
| `search_timestamp` | When the search was performed |

Notes:
- Metadata-only runs include only reference-level columns.
- Full-text columns such as `pdf_filename`, `page_number`, `search_term_found`, `context`, and `zotero_pdf_url` are included only when full-text hits exist.
- The `abstract` column is omitted when `--no-abstract` is used.
- CSV uses plain `context`; the Markdown-only highlighted variant is not written to CSV.

### Markdown Output Format

The Markdown output is designed for research note-taking and literature review workflows, and is structured as follows:

- **YAML Frontmatter Block**: At the top, a compact YAML block stores the format version, `search_details`, and a `summary`.
- **Search Summary and Reference List**: A summary of the search and a numbered reference list for all papers.
- **Abstracts Section**: By default, a separate abstracts section appears after the reference list unless `--no-abstract` is supplied.
- **Detailed Findings Section**:
  - In full-text mode, each paper includes metadata, a per-term occurrence summary, and numbered annotation excerpts with Zotero PDF links.
  - In metadata-only mode, the file still includes the reference list and abstracts, but the detailed findings section states that no annotation-level findings were generated.
- **Detailed Paper Sections in Full-Text Mode**: For each paper:
  - The paper title as a heading.
  - Metadata bullets: authors, year, publication, DOI, citekey, and a direct Zotero link.
  - A `Term Summary` subheading with occurrence counts per search term.
  - An `Annotations` subheading with numbered occurrences and page-specific Zotero links.
  - A horizontal rule (`---`) separates each paper section.

This format is compatible with note-taking applications like Obsidian and supports direct navigation to Zotero items and PDF pages.

#### Example Markdown Structure:
```markdown
---
zotgrep-results/v1:
  search_details:
    zotero_query: bifactor
    full_text_query:
    - psycho
    search_mode: fulltext
    search_timestamp: '2025-06-08 17:15:00'
    context_window: 2
  summary:
    total_papers_found: 3
    total_annotations_found: 17
---

# ZotGrep Results

## Search Summary

- **Search Date:** 2025-06-08 17:15:00
- **Zotero Library Query:** `bifactor`
- **Full-Text Query:** `psycho`
- **Results:** Found **17** annotations across **3** papers.

### Reference List

1. Neufeld, S., St Clair, M., Brodbeck, J., Wilkinson, P., Goodyer, I., & Jones, P. (2024). *Measurement Invariance in Longitudinal Bifactor Models: Review and Application Based on the p Factor*.
2. Bornovalova, M., Choate, A., Fatimah, H., Petersen, K., & Wiernik, B. (2020). *Appropriate Use of Bifactor Analysis in Psychopathology Research: Appreciating Benefits and Limitations*.
3. Watts, A., Poore, H., & Waldman, I. (2019). *Riskier Tests of the Validity of the Bifactor Model of Psychopathology*.

---

## Detailed Findings

### Measurement Invariance in Longitudinal Bifactor Models: Review and Application Based on the p Factor

- **Authors**: Neufeld, Sharon A. S.; St Clair, Michelle; Brodbeck, Jeannette; Wilkinson, Paul O.; Goodyer, Ian M.; Jones, Peter B.
- **Year**: 2024
- **Publication**: Psychological Assessment
- **DOI**: https://doi.org/10.1037/pas0000564
- **Citekey**: `73ZD2D7S`
- **Zotero Link**: [Open Item in Zotero](zotero://select/library/items/73ZD2D7S)

#### Term Summary

- `psycho`: 2 occurrences

#### Annotations

##### Occurrence #1, Page 8

> Thus far we have reviewed the importance of establishing longitudinal MI in bifactor models, provided guidance on MI cut-offs to employ when ordered-categorical indicators are utilized, and outlined estimator choices and missing data considerations. ...
> - Highlight on [Page 8](zotero://open-pdf/library/items/KGDL8AWR?page=8)

##### Occurrence #2, Page 18

> Psychological Assessment, 30(9), 1174–1185. https://doi.org/10.1037/pas0000564 ...
> - Highlight on [Page 18](zotero://open-pdf/library/items/KGDL8AWR?page=18)

---

# ... Additional paper sections follow the same structure ...
```

## Quick Start Examples

### Example 1: Basic Search with Interactive Output Choice
```bash
zotgrep
# Enter search terms when prompted
# Choose output format from the interactive menu
```

### Example 2: Direct Search via Command Line (Non-Interactive)
```bash
zotgrep --zotero "deep learning" --fulltext "convolution, neural network"
# Runs search directly with specified terms, no prompts
```

### Example 3: Direct CSV Export
```bash
zotgrep --zotero "AI ethics" --fulltext "privacy, fairness" --csv my_research_results.csv
# Results saved to CSV for data analysis
```

### Example 4: Direct Markdown Export for Note-Taking
```bash
zotgrep --zotero "literature review" --fulltext "systematic, meta-analysis" --md literature_review.md
# Results saved to Markdown for research notes
```

### Example 5: Silent Export (No Console Output)
```bash
zotgrep --zotero "machine learning" --fulltext "algorithm, bias" --markdown research_notes.md --markdown-only
# Only creates the Markdown file, no console output
```

### Open Item in Zotero
```
zotero://select/library/items/ITEM_KEY
```

### Open PDF at Specific Page
```
zotero://open-pdf/library/items/PDF_KEY?page=PAGE_NUMBER
```

These URLs can be clicked in spreadsheet applications or used programmatically to jump directly to relevant content in your Zotero library.

## Example Output

### Console Output
```
Reference: Machine Learning in Healthcare (Key: SMITH2023)
  Authors: Smith, John; Doe, Jane
  Year: 2023
  PDF: smith_2023_ml_healthcare.pdf
  Found 'algorithm' on Page: 15
  Context: ...The machine learning ***algorithm*** demonstrated significant improvements...
  Zotero PDF URL: zotero://open-pdf/library/items/PDF123?page=15
```

### CSV Output

The same information is saved in structured CSV format for further analysis, reporting, or integration with other tools.

### Markdown Output

Results are organized by paper with YAML frontmatter and annotations sections, perfect for research note-taking and literature review workflows.

## Command Line Arguments

### Output Options

- `--json FILENAME`: Save results to specified JSON file
- `--no-json`: Disable the default JSON export
- `--csv FILENAME`: Save results to specified CSV file
- `--csv-only`: Only save to CSV, suppress console output
- `--md FILENAME` or `--markdown FILENAME`: Save results to specified Markdown file
- `--md-only` or `--markdown-only`: Only save to Markdown, suppress console output

### Search Term Options

- `--zotero "SEARCH TERMS"`: Specify Zotero metadata search terms directly (e.g., `"machine learning health"`)
- `--fulltext "TERM1, TERM2"`: Optionally specify full-text search terms as a comma-separated list (e.g., `"algorithm, bias"`)
- `--metadata-only` or `--no-fulltext`: Skip PDF/full-text processing and return metadata-only results
- `--no-abstract`: Omit abstracts from output
- `--publication "TITLE1, TITLE2"` or `--publication-title "TITLE1, TITLE2"`: Filter results by publication title (comma-separated list). Example: `"Nature, Science"`
- `--item-type "TYPE1, TYPE2"` or `--itemtype "TYPE1, TYPE2"`: Filter by Zotero item type. Example: `"journalArticle, book"`
- `--collection "COLLECTION"`: Filter by Zotero collection key or exact collection name. Example: `"ABCD1234"` or `"Focused Review"`
- `--tag "TAG1, TAG2"` or `--tags "TAG1, TAG2"`: Filter by Zotero tags. Example: `"privacy, fairness"`
- `--tag-match {all,any}`: Control how multiple tags are matched. `all` requires every supplied tag; `any` accepts at least one.

### Other Options

- `--config CONFIG`: Path to configuration file (JSON format)
- `--base-path PATH`: Override base attachment path
- `--max-results N`: Maximum results for metadata search (default: 100)
- `--context-window N`: Context sentence window size (default: 2). The default means 2 sentences before and after the keyword is found will be returned. Larger window sizes will return more sentences. Sentence splitting uses the Zotero item language when available, with a built-in fallback if no language-aware tokenizer is available at runtime.
- `--port PORT`: Port for the local web interface when using `--web` (default: 23120)
- `--version`: Show version information
- `--help`: Show help message

### Environment Variables

- `ZOTGREP_CONFIG_PATH`: Use a custom user config file path
- `ZOTERO_BASE_ATTACHMENT_PATH`: Base directory for linked-file attachments
- `ZOTERO_PUBLICATION_TITLE_FILTER`: Filter results by publication title (comma-separated list). Example: `Nature, Science`
- `ZOTERO_ITEM_TYPE_FILTER`: Filter by Zotero item type (comma-separated list). Example: `journalArticle, book`
- `ZOTERO_COLLECTION_FILTER`: Filter by Zotero collection key or exact collection name
- `ZOTERO_TAG_FILTER`: Filter by Zotero tags (comma-separated list). Example: `privacy, fairness`
- `ZOTERO_TAG_MATCH_MODE`: Control multi-tag matching with `all` or `any`


## Use Cases

### Research and Literature Review

- **CSV Export**: Create structured datasets for systematic literature reviews and meta-analyses
- **Markdown Export**: Generate research notes with proper citations and page references
- **Direct Zotero Integration**: Jump directly to source materials from search results

### Academic Writing

- **Evidence Collection**: Quickly locate and cite relevant passages with page-specific references
- **Collaborative Research**: Share search results in both structured (CSV, JSON) and readable (Markdown) formats
- **Literature Synthesis**: Build comprehensive literature reviews with organized annotations

### Knowledge Management

- **Research Databases**: Create searchable databases of research findings in CSV format
- **Note-Taking Integration**: Import Markdown results into Obsidian, Notion, or other note-taking apps
- **Concept Tracking**: Monitor mentions of specific concepts across your entire literature collection
- **Citation Networks**: Build interconnected knowledge bases with contextual references

### Workflow Integration

- **Data Analysis**: Use CSV exports with R, Python, or Excel for quantitative literature analysis
- **Documentation**: Generate Markdown reports for research documentation and sharing
- **Reference Management**: Seamlessly integrate with existing Zotero workflows
- **Agentic Workflows**: Let AI agents use the CLI and use JSON (highly structured and machine-readable, less human-readable) output formats.

## Troubleshooting

### Common Issues

1. **PDF not found errors**: For linked files, verify `BASE_ATTACHMENT_PATH` is correctly set; for Zotero-stored files, verify the attachment is available through Zotero
2. **API connection failures**: Check Zotero credentials and internet connection
3. **Empty search results**: Try broader search terms or check PDF text extraction
4. **File encoding issues**: Both CSV and Markdown files use UTF-8 encoding for international characters
5. **Markdown formatting issues**: Special characters are automatically escaped in Markdown output
6. **Output format conflicts**: Cannot use both `--csv-only` and `--md-only` simultaneously

### Debug Tips

- Check Zotero sync status
- For linked files, verify PDF files are accessible at the specified paths
- Test with simple search terms first
- Review console output for detailed error messages
- For Markdown issues, check that special characters are properly handled
- Use `--help` to see all available command-line options

### Output Format Selection Guide

**Choose CSV when:**
- Performing quantitative analysis of search results
- Importing data into spreadsheet applications
- Conducting systematic literature reviews requiring structured data
- Integrating with data analysis tools (R, Python, etc.)

**Choose Markdown when:**
- Taking research notes and building knowledge bases
- Using note-taking applications like Obsidian or Notion
- Creating readable research documentation
- Building interconnected literature reviews
- Sharing results in a human-readable format

## Advanced 

### Modifying settings via JSON file

Additional to configuring basic settings via the Web UI, settings can be modified in these ways:

- manually by creating that JSON file
- by pointing to another file with `--config PATH` or `ZOTGREP_CONFIG_PATH`

The recommended file path is:

```bash
~/.config/zotgrep/config.json
```

Typical persistent settings include:

```json
{
  "zotero_user_id": "0",
  "zotero_api_key": "local",
  "library_type": "user",
  "base_attachment_path": "/path/to/your/linked/pdfs",
  "max_results_stage1": 100,
  "context_sentence_window": 2,
  "item_type_filter": ["journalArticle"],
  "collection_filter": "Focused Review",
  "tag_filter": ["privacy", "fairness"],
  "tag_match_mode": "all"
}
```

If you use only Zotero-stored files, leave `base_attachment_path` empty.

Environment variables override config-file values at runtime. The most relevant ones are:

```bash
export ZOTERO_BASE_ATTACHMENT_PATH='/path/to/your/zotero/attachments'
export ZOTGREP_CONFIG_PATH='/path/to/custom/config.json'
export ZOTERO_ITEM_TYPE_FILTER='journalArticle,book'
export ZOTERO_COLLECTION_FILTER='Focused Review'
export ZOTERO_TAG_FILTER='privacy,fairness'
export ZOTERO_TAG_MATCH_MODE='any'
```

### Testing

Run the test suite to verify functionality:
```bash
pytest
```
or
```bash
python -m unittest discover
```

This will test:
- Zotero URL generation
- CSV export functionality
- Sample data processing

**Deprecation Notice:**
Running `python test_zotgrep.py` is deprecated. Please use the package-based test suite in the `tests/` directory as shown above.

## License

This project is open source published, like Zotero itself, under a GPL license. Please refer to the license file for details.

## Acknowledgments

ZotGrep depends on several upstream open-source projects. In particular:

- [pyzotero](https://github.com/urschrei/pyzotero) for Zotero API access
- [Flask](https://github.com/pallets/flask) for the local web interface
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) and [PDFium](https://pdfium.googlesource.com/pdfium/) for PDF text extraction
- [pySBD](https://github.com/nipunsadvilkar/pySBD) for sentence boundary detection
- [PyYAML](https://github.com/yaml/pyyaml) for YAML serialization in Markdown exports

See [`NOTICE`](NOTICE) for license attributions and upstream license links.

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.
