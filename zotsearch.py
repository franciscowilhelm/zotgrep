import io
import os
import re # Optional, for more advanced text searching
from pyzotero import zotero
import pypdfium2 as pdfium

# --- Configuration ---
ZOTERO_USER_ID = '0'  # Replace with your Zotero User ID
ZOTERO_API_KEY = '0' # Replace with your Zotero API Key
LIBRARY_TYPE = 'user' # Or 'group' if it's a group library
# not used as we use local.
# !!! IMPORTANT: SET THIS TO YOUR ZOTERO LINKED ATTACHMENT BASE DIRECTORY !!!
# This is the root folder where Zotero (and zotmoov) stores your linked PDFs.
# Example: 'D:\\ZoteroAttachments' or '/Users/yourname/ZoteroAttachments'
BASE_ATTACHMENT_PATH = '/Users/francisco/Library/CloudStorage/OneDrive-UniversitaetBern/ZoteroAttachments' # <--- USER MUST SET THIS

# --- Helper Functions (extract_text_from_pdf_bytes and find_context remain the same) ---
def extract_text_from_pdf_bytes(pdf_bytes_io): # Changed input to file-like object
    """Extracts text from PDF bytes, page by page."""
    text_by_page = {}
    try:
        # pdfium.PdfDocument can take a file path, bytes, or a file-like object
        pdf_doc = pdfium.PdfDocument(pdf_bytes_io)
        for i, page in enumerate(pdf_doc):
            text_by_page[i + 1] = page.get_textpage().get_text_range()
            page.close()
        pdf_doc.close()
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None
    return text_by_page

def find_context(text, term, window_chars=150):
    """Finds a term in text and returns a snippet around it."""
    contexts = []
    for match in re.finditer(re.escape(term), text, re.IGNORECASE):
        start, end = match.span()
        context_start = max(0, start - window_chars)
        context_end = min(len(text), end + window_chars)
        
        para_start_search = text.rfind('\n', 0, start)
        if para_start_search != -1 and start - para_start_search < window_chars * 1.5 :
             context_start = max(context_start, para_start_search +1)

        para_end_search = text.find('\n', end)
        if para_end_search != -1 and para_end_search - end < window_chars * 1.5:
            context_end = min(context_end, para_end_search)
            
        snippet = text[context_start:context_end]
        term_pattern = re.compile(re.escape(term), re.IGNORECASE)
        highlighted_snippet = term_pattern.sub(f"***{match.group(0)}***", snippet)
        contexts.append(f"...{highlighted_snippet}...")
    return contexts

def search_zotero_and_full_text(
    zot_conn,
    base_attachment_dir, # New parameter
    metadata_search_terms,
    full_text_search_terms,
    max_results_stage1=10
):
    print(f"--- Stage 1: Searching Zotero metadata for: '{metadata_search_terms}' ---")
    try:
        items = zot_conn.items(q=metadata_search_terms, itemType='-attachment', limit=max_results_stage1)
    except Exception as e:
        print(f"Error during Zotero metadata search: {e}")
        return []

    if not items:
        print("No references found matching metadata search terms.")
        return []

    print(f"Found {len(items)} references matching metadata search.")
    all_findings = []

    for item in items:
        item_data = item.get('data', {})
        item_title = item_data.get('title', 'N/A')
        item_key = item_data.get('key', 'N/A')
        print(f"\nProcessing: '{item_title}' (Key: {item_key})")

        try:
            attachments = zot_conn.children(item_key)
        except Exception as e:
            print(f"  Error fetching attachments for {item_key}: {e}")
            continue
            
        pdf_attachments = [
            att for att in attachments
            if att.get('data', {}).get('itemType') == 'attachment' and
               att.get('data', {}).get('contentType') == 'application/pdf'
        ]

        if not pdf_attachments:
            print("  No PDF attachments found for this item (checking linkMode next).")
            continue

        for pdf_att in pdf_attachments:
            pdf_att_data = pdf_att.get('data', {})
            pdf_key = pdf_att_data.get('key')
            link_mode = pdf_att_data.get('linkMode')
            pdf_filename_display = pdf_att_data.get('filename', f"{pdf_key}.pdf") # Default filename

            if link_mode == 'linked_file':
                relative_path_from_zotero_raw = pdf_att_data.get('path')
                if not relative_path_from_zotero_raw:
                    print(f"    Attachment {pdf_key} is a linked file but has no path information in Zotero.")
                    continue

                # --- FIX: Strip "attachments:" prefix if present ---
                path_prefix_to_strip = "attachments:"
                actual_relative_path = relative_path_from_zotero_raw
                if relative_path_from_zotero_raw.startswith(path_prefix_to_strip):
                    actual_relative_path = relative_path_from_zotero_raw[len(path_prefix_to_strip):]
                    # print(f"    Stripped '{path_prefix_to_strip}' prefix. Original: '{relative_path_from_zotero_raw}', Cleaned: '{actual_relative_path}'")
                # --- END OF FIX ---

                # Construct the full local path using the cleaned path
                full_local_path = os.path.normpath(os.path.join(base_attachment_dir, actual_relative_path))
                
                # Update pdf_filename_display if it was generic and we have a better one from path
                if pdf_filename_display == f"{pdf_key}.pdf":
                    pdf_filename_display = os.path.basename(full_local_path)


                print(f"  Found linked PDF attachment: '{pdf_att_data.get('filename', pdf_filename_display)}' (Raw path from Zotero: '{relative_path_from_zotero_raw}')")
                print(f"    Cleaned relative path: '{actual_relative_path}'")
                print(f"    Attempting to access at: {full_local_path}")


                if not os.path.exists(full_local_path):
                    print(f"    ERROR: PDF file not found at {full_local_path}")
                    print(f"    Please check your BASE_ATTACHMENT_PATH ('{base_attachment_dir}') and Zotero's path for this item.")
                    print(f"    Zotero stores raw path: '{relative_path_from_zotero_raw}' for this attachment.")
                    continue
                
                try:
                    print(f"    Extracting text from PDF: {pdf_filename_display}...")
                    text_by_page = extract_text_from_pdf_bytes(full_local_path)
                except Exception as e:
                    print(f"    Error reading or processing local PDF {full_local_path}: {e}")
                    continue

            elif link_mode == 'imported_file':
                # This part remains the same
                print(f"  Found imported PDF: '{pdf_filename_display}'")
                print(f"    Downloading PDF (Key: {pdf_key})...")
                try:
                    pdf_bytes_content = zot_conn.file(pdf_key)
                    if not pdf_bytes_content:
                        print("    Failed to download PDF or PDF is empty.")
                        continue
                    pdf_bytes_io = io.BytesIO(pdf_bytes_content)
                    text_by_page = extract_text_from_pdf_bytes(pdf_bytes_io)
                except Exception as e:
                    print(f"    Error downloading or processing imported PDF {pdf_key}: {e}")
                    continue
            else:
                print(f"    Skipping attachment {pdf_key} with unhandled linkMode: '{link_mode}' or it's not a PDF.")
                continue

            if not text_by_page:
                print(f"    Could not extract text from PDF: {pdf_filename_display}")
                continue

            print(f"    --- Stage 2: Searching PDF text for: '{', '.join(full_text_search_terms)}' ---")
            for page_num, page_text in text_by_page.items():
                for term in full_text_search_terms:
                    contexts = find_context(page_text, term)
                    if contexts:
                        for context_snippet in contexts:
                            finding = {
                                'reference_title': item_title,
                                'reference_key': item_key,
                                'pdf_filename': pdf_filename_display,
                                'page_number': page_num,
                                'search_term_found': term,
                                'context': context_snippet
                            }
                            all_findings.append(finding)
                            print(f"      Found '{term}' on page {page_num}")
    return all_findings

# --- Main Execution ---
if __name__ == "__main__":
    if ZOTERO_USER_ID == 'YOUR_USER_ID' or ZOTERO_API_KEY == 'YOUR_API_KEY':
        print("Please configure ZOTERO_USER_ID and ZOTERO_API_KEY in the script.")
        exit()
    
    if BASE_ATTACHMENT_PATH == 'YOUR_BASE_ATTACHMENT_DIRECTORY_PATH' or not os.path.isdir(BASE_ATTACHMENT_PATH):
        print("Please configure 'BASE_ATTACHMENT_PATH' to a valid directory path in the script.")
        print("This should be the root directory where your Zotero linked PDF attachments are stored.")
        print(f"(Currently set to: '{BASE_ATTACHMENT_PATH}')")
        exit()
    else:
        print(f"Using base attachment path: {BASE_ATTACHMENT_PATH}")


    try:
        zot = zotero.Zotero(ZOTERO_USER_ID, LIBRARY_TYPE, ZOTERO_API_KEY, local= True)
        zot.top(limit=1) 
        print("Successfully connected to Zotero API.")
    except Exception as e:
        print(f"Failed to connect to Zotero API: {e}")
        exit()

    metadata_query = input("Enter Zotero metadata search terms (e.g., 'machine learning health'): ")
    full_text_query_str = input("Enter full-text search terms, comma-separated (e.g., 'algorithm, bias'): ")
    full_text_terms_list = [term.strip() for term in full_text_query_str.split(',')]

    print("\nStarting search...")
    results = search_zotero_and_full_text(
        zot,
        BASE_ATTACHMENT_PATH, # Pass the base path
        metadata_query,
        full_text_terms_list
    )

    print("\n\n--- Search Complete. Results: ---")
    if results:
        for res in results:
            print(f"\nReference: {res['reference_title']} (Key: {res['reference_key']})")
            print(f"  PDF: {res['pdf_filename']}")
            print(f"  Found '{res['search_term_found']}' on Page: {res['page_number']}")
            print(f"  Context: {res['context']}")
    else:
        print("No matches found based on your criteria.")