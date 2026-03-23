Suggest a new structure for the .md output that is useful for machine and humans readers.
Things I have considered (please expand)

Of course. This is an excellent problem to solve. A well-structured output file is key to making a tool like ZotSearch genuinely useful for research workflows. Your considerations are spot on. Multiple YAML frontmatters are indeed a problem for most parsers, and documenting inputs and providing a summary are crucial for reproducibility and usability.

Let's design a new Markdown output structure that addresses these points, balancing human readability with machine-parsable data.

The core principle will be:
**One file, one YAML frontmatter.** All structured data for the entire search will be placed in a single, comprehensive YAML block at the very top of the file. The rest of the Markdown document will be a human-friendly presentation of that data.

---

### Proposed New Markdown Output Structure

Here is a complete example of the new output format. I will break down the rationale for each section below.

```markdown
---
# zotsearch-results/v1  (A version for the schema, allows future-proofing)
search_details:
  zotero_query: "bifactor models"
  full_text_query: ["invariance", "longitudinal"]
  search_timestamp: "2025-06-08 16:36:37"
  context_window: 2
summary:
  total_papers_found: 2
  total_annotations_found: 3
papers:
  - title: "Measurement Invariance in Longitudinal Bifactor Models: Review and Application Based on the p Factor"
    authors:
      - "Neufeld, Sharon A. S."
      - "St Clair, Michelle"
      - "Brodbeck, Jeannette"
      - "Wilkinson, Paul O."
      - "Goodyer, Ian M."
      - "Jones, Peter B."
    year: 2024
    citekey: "73ZD2D7S"
    zotero_item_key: "73ZD2D7S"
    zotero_select_url: "zotero://select/library/items/73ZD2D7S"
  - title: "Appropriate Use of Bifactor Analysis in Psychopathology Research: Appreciating Benefits and Limitations"
    authors:
      - "Bornovalova, Marina A."
      - "Choate, Alexandria M."
      - "Fatimah, Haya"
      - "Petersen, Karl J."
      - "Wiernik, Brenton M."
    year: 2020
    citekey: "EM4A3LNZ"
    zotero_item_key: "EM4A3LNZ"
    zotero_select_url: "zotero://select/library/items/EM4A3LNZ"
---

# ZotSearch Results

## Search Summary

- **Search Date:** 2025-06-08 16:36:37
- **Zotero Library Query:** `bifactor models`
- **Full-Text Query:** `invariance`, `longitudinal`
- **Results:** Found **3** annotations across **2** papers.

### Reference List

1.  Neufeld, S. A. S., St Clair, M., Brodbeck, J., Wilkinson, P. O., Goodyer, I. M., & Jones, P. B. (2024). *Measurement Invariance in Longitudinal Bifactor Models: Review and Application Based on the p Factor*.
2.  Bornovalova, M. A., Choate, A. M., Fatimah, H., Petersen, K. J., & Wiernik, B. M. (2020). *Appropriate Use of Bifactor Analysis in Psychopathology Research: Appreciating Benefits and Limitations*.

---

## Detailed Findings

### Measurement Invariance in Longitudinal Bifactor Models: Review and Application Based on the p Factor

- **Authors**: Neufeld, Sharon A. S.; St Clair, Michelle; Brodbeck, Jeannette; Wilkinson, Paul O.; Goodyer, Ian M.; Jones, Peter B.
- **Year**: 2024
- **Citekey**: `73ZD2D7S`
- **Zotero Link**: [Open Item in Zotero](zotero://select/library/items/73ZD2D7S)

#### Annotations

> "Text text."
> — Highlight on [Page 4](zotero://open-pdf/library/items/KGDL8AWR?page=4)

> "Lorem ipsum."
> — Highlight on [Page 4](zotero://open-pdf/library/items/KGDL8AWR?page=4)

---

### Appropriate Use of Bifactor Analysis in Psychopathology Research: Appreciating Benefits and Limitations

- **Authors**: Bornovalova, Marina A.; Choate, Alexandria M.; Fatimah, Haya; Petersen, Karl J.; Wiernik, Brenton M.
- **Year**: 2020
- **Citekey**: `EM4A3LNZ`
- **Zotero Link**: [Open Item in Zotero](zotero://select/library/items/EM4A3LNZ)

#### Annotations

> "Lorem Ipsum."
> — Highlight on [Page 7](zotero://open-pdf/library/items/A8JPRQRV?page=7)
```

---

### Rationale and Breakdown of the New Structure

#### 1. The Single, Comprehensive YAML Frontmatter (for Machines)

This is the most important change. It solves the primary issue of multiple frontmatters and creates a single, machine-readable source of truth for the entire search.

-   **`zotsearch-results/v1`**: A schema key. This is a best practice for data files. It allows you to version your output format. If you ever change the structure in the future, a program can check this key to know how to parse the file.
-   **`search_details`**: An object that explicitly documents the inputs to the search, addressing one of your key requirements for reproducibility.
    -   `zotero_query`: The exact string used for the metadata search.
    -   `full_text_query`: A list of strings, which is a more structured way to store the comma-separated terms.
    -   `search_timestamp`: Kept from the original.
    -   `context_window`: Storing parameters like this makes the results fully understandable.
-   **`summary`**: A high-level overview.
    -   `total_papers_found` / `total_annotations_found`: Clear, simple stats.
-   **`papers`**: This is the core data. It's a **list of objects**, where each object represents a paper. This is how you represent multiple papers in a single valid YAML structure.
    -   **Each paper object contains:**
        -   `title`, `year`, `citekey`, `zotero_item_key`, `zotero_select_url`: Clean, atomic metadata.
        -   `authors`: Stored as a **list of strings**. This is far superior for machine processing than a single, semi-colon-separated string.
        -   `annotations`: Nested within the paper object is a list of its annotations. This maintains the relationship between a paper and its text snippets.
            -   **Each annotation object contains:** `text`, `page`, `pdf_attachment_key`, and the `zotero_pdf_url`. All data is preserved and structured.

#### 2. The Human-Readable Markdown Body

This part of the file is generated *from* the data in the YAML frontmatter. It's designed for a researcher to read and use directly.

-   **`# ZotSearch Results`**: A clear top-level heading.
-   **`## Search Summary`**: This section provides an immediate, human-readable overview. It directly mirrors the data in `search_details` and `summary` from the YAML block, making it easy to see the search context at a glance.
-   **`### Reference List`**: This directly addresses your desire for a summary reference list.
    -   It can be formatted in a standard citation style (like APA, as shown). This is extremely useful for quickly copying and pasting into a document or getting an overview of the literature found.
    -   Because the structured data is in the YAML, you are not losing machine readability. You are simply *adding* a human-readable representation.
-   **`---` (Horizontal Rule)**: A clear visual separator between the summary and the detailed results.
-   **`## Detailed Findings`**: The main section for the results.
    -   **Paper Sections (`### Title`)**: Each paper gets its own clear section, headed by its title. This is much cleaner than the old `cssclass` YAML block.
    -   **Metadata Block**: A simple, bulleted list provides key metadata. `citekey` is formatted as code for easy copying. The Zotero link is a proper Markdown link.
    -   **`#### Annotations`**:
        -   Using **blockquote (`>`)** formatting for the extracted text makes it visually stand out as a quotation.
        -   The attribution line (`— Highlight on [Page 4](...)`) is clean, semantic, and provides the direct link to the PDF page.

### Pros of this New Structure

1.  **Valid & Parsable**: It's a single, valid Markdown file with a standard YAML frontmatter that can be parsed by any tool (Obsidian, Jekyll, Python `yaml` libraries, etc.).
2.  **Machine-Readable & Structured**: All the data is available in a predictable, nested structure within the YAML. You could easily write a script to, for example, "extract all annotations for papers published after 2021."
3.  **Human-Readable & Scannable**: The body of the document is clean, well-organized, and prioritizes the information a researcher needs to see first (summary, references), followed by details.
4.  **Reproducible**: The search inputs are explicitly stored, making any search fully reproducible.
5.  **Extensible**: The versioned schema and structured YAML make it easy to add new fields in the future without breaking existing parsers. For example, you could add a `journal` field to each paper object.
6.  **No "Weird" Hacks**: This avoids non-standard solutions like embedding JSON chunks in Markdown, which have poor tooling support. This approach uses the best features of YAML and Markdown for what they are good at.