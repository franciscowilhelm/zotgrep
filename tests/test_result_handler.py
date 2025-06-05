#!/usr/bin/env python3
"""
Test suite for the result_handler module.

This demonstrates the testing approach for the modular ZotSearch components.
"""

import unittest
import tempfile
import os
import csv
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zotsearch.result_handler import ResultHandler, generate_zotero_url, save_results_to_csv, save_results_to_markdown


class TestResultHandler(unittest.TestCase):
    """Test cases for ResultHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = ResultHandler()
        self.sample_item_data = {
            'title': 'Machine Learning in Healthcare: A Comprehensive Review',
            'key': 'SMITH2023',
            'creators': [
                {
                    'creatorType': 'author',
                    'firstName': 'John',
                    'lastName': 'Smith'
                },
                {
                    'creatorType': 'author',
                    'firstName': 'Jane',
                    'lastName': 'Doe'
                }
            ],
            'date': '2023-05-15'
        }
        
        self.sample_pdf_info = {
            'key': 'PDF123',
            'filename': 'smith_2023_ml_healthcare.pdf'
        }
    
    def test_generate_zotero_url_item_only(self):
        """Test Zotero URL generation for item only."""
        url = self.handler.generate_zotero_url('ITEM123')
        expected = 'zotero://select/library/items/ITEM123'
        self.assertEqual(url, expected)
    
    def test_generate_zotero_url_with_pdf(self):
        """Test Zotero URL generation with PDF."""
        url = self.handler.generate_zotero_url('ITEM123', 'PDF456')
        expected = 'zotero://select/library/items/PDF456'
        self.assertEqual(url, expected)
    
    def test_generate_zotero_url_with_page(self):
        """Test Zotero URL generation with PDF and page."""
        url = self.handler.generate_zotero_url('ITEM123', 'PDF456', 5)
        expected = 'zotero://open-pdf/library/items/PDF456?page=5'
        self.assertEqual(url, expected)
    
    def test_format_authors(self):
        """Test author formatting."""
        creators = [
            {'creatorType': 'author', 'firstName': 'John', 'lastName': 'Smith'},
            {'creatorType': 'author', 'firstName': 'Jane', 'lastName': 'Doe'},
            {'creatorType': 'editor', 'firstName': 'Bob', 'lastName': 'Editor'}  # Should be ignored
        ]
        
        result = self.handler._format_authors(creators)
        expected = 'Smith, John; Doe, Jane'
        self.assertEqual(result, expected)
    
    def test_format_authors_last_name_only(self):
        """Test author formatting with last name only."""
        creators = [
            {'creatorType': 'author', 'lastName': 'Smith'},
            {'creatorType': 'author', 'firstName': 'Jane', 'lastName': 'Doe'}
        ]
        
        result = self.handler._format_authors(creators)
        expected = 'Smith; Doe, Jane'
        self.assertEqual(result, expected)
    
    def test_format_authors_empty(self):
        """Test author formatting with no authors."""
        result = self.handler._format_authors([])
        self.assertEqual(result, 'N/A')
    
    def test_extract_publication_year(self):
        """Test publication year extraction."""
        test_cases = [
            ('2023-05-15', '2023'),
            ('May 2023', '2023'),
            ('2023', '2023'),
            ('1995-12-01', '1995'),
            ('N/A', 'N/A'),
            ('', 'N/A'),
            ('invalid', 'invalid')
        ]
        
        for date_str, expected in test_cases:
            with self.subTest(date_str=date_str):
                result = self.handler._extract_publication_year(date_str)
                self.assertEqual(result, expected)
    
    def test_create_finding(self):
        """Test finding creation."""
        terms_found = ['algorithm', 'machine learning']
        context = 'The machine learning algorithm demonstrated significant improvements.'
        highlighted_context = 'The ***machine learning*** ***algorithm*** demonstrated significant improvements.'
        
        finding = self.handler.create_finding(
            self.sample_item_data,
            self.sample_pdf_info,
            15,
            terms_found,
            context,
            highlighted_context
        )
        
        # Check required fields
        self.assertEqual(finding['reference_title'], 'Machine Learning in Healthcare: A Comprehensive Review')
        self.assertEqual(finding['reference_key'], 'SMITH2023')
        self.assertEqual(finding['authors'], 'Smith, John; Doe, Jane')
        self.assertEqual(finding['publication_year'], '2023')
        self.assertEqual(finding['pdf_filename'], 'smith_2023_ml_healthcare.pdf')
        self.assertEqual(finding['pdf_key'], 'PDF123')
        self.assertEqual(finding['page_number'], 15)
        self.assertEqual(finding['search_term_found'], 'algorithm, machine learning')
        self.assertEqual(finding['context'], context)
        self.assertEqual(finding['context_highlighted'], highlighted_context)
        self.assertTrue(finding['zotero_item_url'].startswith('zotero://'))
        self.assertTrue(finding['zotero_pdf_url'].startswith('zotero://'))
        self.assertIsInstance(finding['search_timestamp'], str)
    
    def test_save_results_to_csv(self):
        """Test CSV saving functionality."""
        # Create sample results
        results = [
            {
                'reference_title': 'Test Paper 1',
                'authors': 'Smith, John',
                'publication_year': '2023',
                'reference_key': 'SMITH2023',
                'pdf_filename': 'test1.pdf',
                'pdf_key': 'PDF1',
                'page_number': 1,
                'search_term_found': 'test',
                'context': 'This is a test context.',
                'context_highlighted': 'This is a ***test*** context.',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': 'zotero://open-pdf/library/items/PDF1?page=1',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        try:
            # Save results
            self.handler.save_results_to_csv(results, tmp_filename)
            
            # Verify file exists and has correct content
            self.assertTrue(os.path.exists(tmp_filename))
            
            with open(tmp_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)
                
                self.assertEqual(len(rows), 1)
                row = rows[0]
                
                self.assertEqual(row['reference_title'], 'Test Paper 1')
                self.assertEqual(row['authors'], 'Smith, John')
                self.assertEqual(row['page_number'], '1')
                # context_highlighted should not be in CSV
                self.assertNotIn('context_highlighted', row)
        
        finally:
            # Clean up
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)
    
    def test_save_empty_results(self):
        """Test saving empty results."""
        # This should not create a file and should print a message
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        # Remove the file so we can test it's not created
        os.unlink(tmp_filename)
        
        self.handler.save_results_to_csv([], tmp_filename)
        
        # File should not exist
        self.assertFalse(os.path.exists(tmp_filename))
    
    def test_format_result_summary(self):
        """Test result summary formatting."""
        # Test empty results
        summary = self.handler.format_result_summary([])
        self.assertEqual(summary, "No results found.")
        
        # Test with results
        results = [
            {'reference_key': 'REF1', 'pdf_key': 'PDF1'},
            {'reference_key': 'REF1', 'pdf_key': 'PDF2'},
            {'reference_key': 'REF2', 'pdf_key': 'PDF3'},
        ]
        
        summary = self.handler.format_result_summary(results)
        expected = "Found 3 matches across 2 references in 3 PDF files."
        self.assertEqual(summary, expected)
    
    def test_save_results_to_markdown(self):
        """Test Markdown saving functionality."""
        # Create sample results
        results = [
            {
                'reference_title': 'Test Paper: A Study',
                'authors': 'Smith, John; Doe, Jane',
                'publication_year': '2023',
                'reference_key': 'SMITH2023',
                'pdf_filename': 'test_paper.pdf',
                'pdf_key': 'PDF123',
                'page_number': 5,
                'search_term_found': 'algorithm, machine learning',
                'context': 'The machine learning algorithm demonstrated significant improvements.',
                'context_highlighted': 'The ***machine learning*** ***algorithm*** demonstrated significant improvements.',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': 'zotero://open-pdf/library/items/PDF123?page=5',
                'search_timestamp': '2023-01-01 12:00:00'
            },
            {
                'reference_title': 'Test Paper: A Study',
                'authors': 'Smith, John; Doe, Jane',
                'publication_year': '2023',
                'reference_key': 'SMITH2023',
                'pdf_filename': 'test_paper.pdf',
                'pdf_key': 'PDF123',
                'page_number': 7,
                'search_term_found': 'neural network',
                'context': 'Neural networks have shown promising results in this domain.',
                'context_highlighted': '***Neural networks*** have shown promising results in this domain.',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': 'zotero://open-pdf/library/items/PDF123?page=7',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        try:
            # Save results
            self.handler.save_results_to_markdown(results, tmp_filename)
            
            # Verify file exists and has correct content
            self.assertTrue(os.path.exists(tmp_filename))
            
            with open(tmp_filename, 'r', encoding='utf-8') as mdfile:
                content = mdfile.read()
                
                # Check for expected content
                self.assertIn('# ZotSearch Results', content)
                self.assertIn('**Total Papers:** 1', content)
                self.assertIn('**Total Sections:** 2', content)
                self.assertIn('cssclass: research-note', content)
                self.assertIn('title: Test Paper: A Study', content)
                self.assertIn('Year: 2023', content)
                self.assertIn('Authors: Smith, John; Doe, Jane', content)
                self.assertIn('citekey: SMITH2023', content)
                self.assertIn('## Annotations', content)
                self.assertIn('The machine learning algorithm demonstrated significant improvements.', content)
                self.assertIn('Neural networks have shown promising results in this domain.', content)
                self.assertIn('[Page 5](zotero://open-pdf/library/items/PDF123?page=5)', content)
                self.assertIn('[Page 7](zotero://open-pdf/library/items/PDF123?page=7)', content)
        
        finally:
            # Clean up
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)
    
    def test_save_empty_results_markdown(self):
        """Test saving empty results to markdown."""
        # This should not create a file and should print a message
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        # Remove the file so we can test it's not created
        os.unlink(tmp_filename)
        
        self.handler.save_results_to_markdown([], tmp_filename)
        
        # File should not exist
        self.assertFalse(os.path.exists(tmp_filename))
    
    def test_escape_markdown(self):
        """Test markdown escaping functionality."""
        test_cases = [
            ('Normal text', 'Normal text'),
            ('Text with *asterisk*', 'Text with \\*asterisk\\*'),
            ('Text with [brackets]', 'Text with \\[brackets\\]'),
            ('Text with (parentheses)', 'Text with \\(parentheses\\)'),
            ('Text with # hash', 'Text with \\# hash'),
            ('N/A', 'N/A'),
            ('', ''),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.handler._escape_markdown(input_text)
                self.assertEqual(result, expected)
    
    def test_clean_context_for_markdown(self):
        """Test context cleaning for markdown output."""
        test_cases = [
            ('Normal text', 'Normal text'),
            ('Text with   multiple   spaces', 'Text with multiple spaces'),
            ('Text with **bold** formatting', 'Text with bold formatting'),
            ('Text with "quotes"', 'Text with \\"quotes\\"'),
            ('  Leading and trailing spaces  ', 'Leading and trailing spaces'),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.handler._clean_context_for_markdown(input_text)
                self.assertEqual(result, expected)


class TestBackwardCompatibilityFunctions(unittest.TestCase):
    """Test backward compatibility functions."""
    
    def test_generate_zotero_url_function(self):
        """Test standalone generate_zotero_url function."""
        url = generate_zotero_url('ITEM123', 'PDF456', 5)
        expected = 'zotero://open-pdf/library/items/PDF456?page=5'
        self.assertEqual(url, expected)
    
    def test_save_results_to_csv_function(self):
        """Test standalone save_results_to_csv function."""
        results = [
            {
                'reference_title': 'Test',
                'authors': 'Author',
                'publication_year': '2023',
                'reference_key': 'KEY',
                'pdf_filename': 'test.pdf',
                'pdf_key': 'PDF',
                'page_number': 1,
                'search_term_found': 'term',
                'context': 'context',
                'zotero_item_url': 'url1',
                'zotero_pdf_url': 'url2',
                'search_timestamp': '2023-01-01'
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        try:
            save_results_to_csv(results, tmp_filename)
            self.assertTrue(os.path.exists(tmp_filename))
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)
    
    def test_save_results_to_markdown_function(self):
        """Test standalone save_results_to_markdown function."""
        results = [
            {
                'reference_title': 'Test',
                'authors': 'Author',
                'publication_year': '2023',
                'reference_key': 'KEY',
                'pdf_filename': 'test.pdf',
                'pdf_key': 'PDF',
                'page_number': 1,
                'search_term_found': 'term',
                'context': 'context',
                'context_highlighted': 'highlighted context',
                'zotero_item_url': 'url1',
                'zotero_pdf_url': 'url2',
                'search_timestamp': '2023-01-01'
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        try:
            save_results_to_markdown(results, tmp_filename)
            self.assertTrue(os.path.exists(tmp_filename))
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)


if __name__ == '__main__':
    unittest.main()