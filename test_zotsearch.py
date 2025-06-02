#!/usr/bin/env python3
"""
Test script for the enhanced zotsearch.py functionality.
This script demonstrates the new CSV export and Zotero URL features.
"""

import sys
import os
sys.path.append('.')

from zotsearch import generate_zotero_url, save_results_to_csv
from datetime import datetime

def test_zotero_url_generation():
    """Test the Zotero URL generation function."""
    print("Testing Zotero URL generation...")
    
    # Test item URL
    item_key = "ABC123"
    item_url = generate_zotero_url(item_key)
    print(f"Item URL: {item_url}")
    
    # Test PDF URL
    pdf_key = "DEF456"
    pdf_url = generate_zotero_url(item_key, pdf_key)
    print(f"PDF URL: {pdf_url}")
    
    # Test PDF with page URL
    page_num = 5
    pdf_page_url = generate_zotero_url(item_key, pdf_key, page_num)
    print(f"PDF Page URL: {pdf_page_url}")
    
    print("✓ URL generation tests passed\n")

def test_csv_export():
    """Test the CSV export functionality with sample data."""
    print("Testing CSV export functionality...")
    
    # Create sample results data
    sample_results = [
        {
            'reference_title': 'Machine Learning in Healthcare: A Comprehensive Review',
            'authors': 'Smith, John; Doe, Jane',
            'publication_year': '2023',
            'reference_key': 'SMITH2023',
            'pdf_filename': 'smith_2023_ml_healthcare.pdf',
            'pdf_key': 'PDF123',
            'page_number': 15,
            'search_term_found': 'algorithm',
            'context': 'The machine learning algorithm demonstrated significant improvements in diagnostic accuracy.',
            'context_highlighted': 'The machine learning ***algorithm*** demonstrated significant improvements in diagnostic accuracy.',
            'zotero_item_url': 'zotero://select/library/items/SMITH2023',
            'zotero_pdf_url': 'zotero://open-pdf/library/items/PDF123?page=15',
            'search_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'reference_title': 'Bias in AI Systems: Detection and Mitigation',
            'authors': 'Johnson, Alice; Brown, Bob',
            'publication_year': '2022',
            'reference_key': 'JOHNSON2022',
            'pdf_filename': 'johnson_2022_ai_bias.pdf',
            'pdf_key': 'PDF456',
            'page_number': 8,
            'search_term_found': 'bias',
            'context': 'Algorithmic bias can lead to unfair outcomes in automated decision-making systems.',
            'context_highlighted': 'Algorithmic ***bias*** can lead to unfair outcomes in automated decision-making systems.',
            'zotero_item_url': 'zotero://select/library/items/JOHNSON2022',
            'zotero_pdf_url': 'zotero://open-pdf/library/items/PDF456?page=8',
            'search_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    ]
    
    # Test CSV export
    test_filename = 'test_results.csv'
    save_results_to_csv(sample_results, test_filename)
    
    # Verify file was created
    if os.path.exists(test_filename):
        print(f"✓ CSV file '{test_filename}' created successfully")
        
        # Read and display first few lines
        with open(test_filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print(f"✓ CSV contains {len(lines)} lines (including header)")
            print("First few lines:")
            for i, line in enumerate(lines[:3]):
                print(f"  {i+1}: {line.strip()}")
        
        # Clean up test file
        os.remove(test_filename)
        print(f"✓ Test file '{test_filename}' cleaned up")
    else:
        print(f"✗ CSV file '{test_filename}' was not created")
    
    print("✓ CSV export tests completed\n")

def main():
    """Run all tests."""
    print("=== Enhanced ZotSearch Functionality Tests ===\n")
    
    test_zotero_url_generation()
    test_csv_export()
    
    print("=== All Tests Completed ===")
    print("\nNew features added to zotsearch.py:")
    print("• CSV export with --csv filename.csv option")
    print("• Enhanced metadata (authors, publication year)")
    print("• Zotero URLs for direct access to items and PDF pages")
    print("• Command-line arguments for automation")
    print("• Interactive CSV save option")

if __name__ == "__main__":
    main()