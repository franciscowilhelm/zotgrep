# ZotSearch - Enhanced Zotero Library and Full-Text PDF Search

ZotSearch is a Python script that enables users to search their local Zotero library using the API and then search for full-text content within PDFs. The enhanced version now includes CSV export functionality and Zotero URL integration for direct access to search results.

## Features

### Core Functionality
- Search Zotero library metadata (titles, authors, etc.)
- Full-text search within PDF attachments (both linked and imported files)
- Support for both local linked files and Zotero-stored PDFs
- Context-aware text extraction with highlighted search terms

### Enhanced Features (New)
- **CSV Export**: Save search results to CSV files with comprehensive metadata
- **Zotero URLs**: Direct links to open items and specific PDF pages in Zotero
- **Enhanced Metadata**: Author names, publication years, and timestamps
- **Command-line Options**: Automation-friendly with argument parsing
- **Interactive CSV Save**: Option to save results after viewing console output

## Installation

### Prerequisites
```bash
pip install pyzotero pypdfium2
```

### Configuration
1. Set your Zotero User ID and API Key in the script:
   ```python
   ZOTERO_USER_ID = 'your_user_id'
   ZOTERO_API_KEY = 'your_api_key'
   ```

By default, `local = True` for local API usage. Adapt the respective line for Web API usage.
For local API usage, user ID should be set to 0. API key is not used and can take on any value.

2. Configure the base attachment path for linked files:
   ```python
   BASE_ATTACHMENT_PATH = '/path/to/your/zotero/attachments'
   ```

## Usage

### Basic Usage
```bash
python zotsearch.py
```
The script will prompt you for:
- Metadata search terms (searches titles, authors, etc.)
- Full-text search terms (comma-separated list)

### CSV Export Options

#### Save to specific CSV file
```bash
python zotsearch.py --csv results.csv
```

#### Save to CSV only (no console output)
```bash
python zotsearch.py --csv results.csv --csv-only
```

#### Interactive CSV save
After running a search, the script will offer to save results to CSV:
```
Would you like to save results to a CSV file? (y/n): y
Enter filename (default: zotero_search_results_20250602_111804.csv):
```

## CSV Output Format

The CSV file includes the following columns:

| Column | Description |
|--------|-------------|
| `reference_title` | Title of the reference |
| `authors` | Author names (Last, First; format) |
| `publication_year` | Publication year |
| `reference_key` | Zotero item key |
| `pdf_filename` | PDF file name |
| `pdf_key` | PDF attachment key |
| `page_number` | Page where term was found |
| `search_term_found` | The specific search term that matched |
| `context` | Text context around the found term |
| `zotero_item_url` | URL to open item in Zotero |
| `zotero_pdf_url` | URL to open specific PDF page in Zotero |
| `search_timestamp` | When the search was performed |

## Zotero URL Integration

The enhanced version generates Zotero URLs that allow direct access to:

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

## Command Line Arguments

- `--csv FILENAME`: Save results to specified CSV file
- `--csv-only`: Only save to CSV, suppress console output
- `--help`: Show help message

## Error Handling

The script includes comprehensive error handling for:
- Missing or invalid Zotero credentials
- Network connectivity issues
- PDF processing errors
- File system access problems
- CSV writing errors

## Testing

Run the test suite to verify functionality:
```bash
python test_zotsearch.py
```

This will test:
- Zotero URL generation
- CSV export functionality
- Sample data processing

## Use Cases

### Research and Literature Review
- Export search results for systematic literature reviews
- Create bibliographic databases with full-text search capabilities
- Generate reports with direct links to source materials

### Academic Writing
- Quickly locate and cite relevant passages
- Build evidence tables with page-specific references
- Share search results with collaborators

### Knowledge Management
- Create searchable databases of research findings
- Track mentions of specific concepts across literature
- Build citation networks with context

## Troubleshooting

### Common Issues

1. **PDF not found errors**: Verify `BASE_ATTACHMENT_PATH` is correctly set
2. **API connection failures**: Check Zotero credentials and internet connection
3. **Empty search results**: Try broader search terms or check PDF text extraction
4. **CSV encoding issues**: The script uses UTF-8 encoding for international characters

### Debug Tips

- Check Zotero sync status
- Verify PDF files are accessible at the specified paths
- Test with simple search terms first
- Review console output for detailed error messages

## License

This project is open source. Please refer to the license file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.