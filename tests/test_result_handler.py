#!/usr/bin/env python3
"""
Test suite for the result_handler module.

This demonstrates the testing approach for the modular ZotGrep components.
"""

import unittest
import tempfile
import os
import csv
import types
from datetime import datetime
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_dependency_stubs():
    if "pyzotero" not in sys.modules:
        pyzotero_module = types.ModuleType("pyzotero")
        zotero_module = types.ModuleType("zotero")

        class DummyZotero:
            pass

        zotero_module.Zotero = DummyZotero
        pyzotero_module.zotero = zotero_module
        sys.modules["pyzotero"] = pyzotero_module
        sys.modules["pyzotero.zotero"] = zotero_module

    if "pypdfium2" not in sys.modules:
        pdfium_module = types.ModuleType("pypdfium2")

        class PdfDocument:
            def __init__(self, *_args, **_kwargs):
                pass

            def __iter__(self):
                return iter([])

            def close(self):
                return None

        pdfium_module.PdfDocument = PdfDocument
        sys.modules["pypdfium2"] = pdfium_module

    if "yaml" not in sys.modules:
        yaml_module = types.ModuleType("yaml")

        class SafeDumper:
            @classmethod
            def add_representer(cls, *_args, **_kwargs):
                return None

        def dump(data, Dumper=None, default_flow_style=False, sort_keys=False, allow_unicode=True):
            def render(value, indent=0):
                prefix = "  " * indent
                if isinstance(value, dict):
                    lines = []
                    items = value.items()
                    if sort_keys:
                        items = sorted(items)
                    for key, item in items:
                        if item == []:
                            lines.append(f"{prefix}{key}: []")
                            continue
                        if isinstance(item, (dict, list)):
                            lines.append(f"{prefix}{key}:")
                            lines.extend(render(item, indent + 1))
                        else:
                            rendered = "[]" if item == [] else ("" if item is None else str(item))
                            lines.append(f"{prefix}{key}: {rendered}".rstrip())
                    return lines
                if isinstance(value, list):
                    lines = []
                    for item in value:
                        if isinstance(item, (dict, list)):
                            lines.append(f"{prefix}-")
                            lines.extend(render(item, indent + 1))
                        else:
                            lines.append(f"{prefix}- {item}")
                    return lines
                return [f"{prefix}{value}"]

            return "\n".join(render(data)) + "\n"

        yaml_module.SafeDumper = SafeDumper
        yaml_module.dump = dump
        sys.modules["yaml"] = yaml_module


_install_dependency_stubs()

from zotgrep.result_handler import (
    ResultHandler,
    generate_zotero_url,
    save_results_to_csv,
    save_results_to_json,
    save_results_to_markdown,
)
from zotgrep.config import ZotGrepConfig


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
            'date': '2023-05-15',
            'DOI': '10.1000/example-doi',
            'abstractNote': 'This review summarizes machine learning applications in healthcare.'
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
        self.assertEqual(finding['doi'], '10.1000/example-doi')
        self.assertEqual(finding['abstract'], '')
        self.assertTrue(finding['zotero_item_url'].startswith('zotero://'))
        self.assertTrue(finding['zotero_pdf_url'].startswith('zotero://'))
        self.assertIsInstance(finding['search_timestamp'], str)

    def test_create_reference_result(self):
        """Test metadata-only result creation."""
        result = self.handler.create_reference_result(self.sample_item_data)

        self.assertEqual(result['reference_title'], 'Machine Learning in Healthcare: A Comprehensive Review')
        self.assertEqual(result['reference_key'], 'SMITH2023')
        self.assertEqual(result['authors'], 'Smith, John; Doe, Jane')
        self.assertEqual(result['publication_year'], '2023')
        self.assertEqual(result['publication_title'], 'N/A')
        self.assertEqual(result['doi'], '10.1000/example-doi')
        self.assertEqual(result['pdf_filename'], '')
        self.assertEqual(result['pdf_key'], '')
        self.assertEqual(result['page_number'], '')
        self.assertEqual(result['search_term_found'], '')
        self.assertEqual(result['context'], '')
        self.assertEqual(result['context_highlighted'], '')
        self.assertEqual(result['abstract'], '')
        self.assertEqual(result['zotero_pdf_url'], '')
        self.assertTrue(result['zotero_item_url'].startswith('zotero://'))

    def test_create_reference_result_with_abstract(self):
        """Test metadata-only result creation with abstract included."""
        result = self.handler.create_reference_result(self.sample_item_data, include_abstract=True)
        self.assertEqual(
            result['abstract'],
            'This review summarizes machine learning applications in healthcare.'
        )
        self.assertEqual(result['doi'], '10.1000/example-doi')

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

    def test_save_results_to_csv_without_fulltext_columns(self):
        """Test CSV export omits full-text columns for metadata-only results."""
        results = [
            {
                'reference_title': 'Test Paper 1',
                'authors': 'Smith, John',
                'publication_year': '2023',
                'publication_title': 'Journal of Tests',
                'reference_key': 'SMITH2023',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            self.handler.save_results_to_csv(results, tmp_filename)

            with open(tmp_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.assertEqual(
                    reader.fieldnames,
                    [
                        'reference_title',
                        'authors',
                        'publication_year',
                        'publication_title',
                        'doi',
                        'reference_key',
                        'abstract',
                        'zotero_item_url',
                        'search_timestamp'
                    ]
                )
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['reference_title'], 'Test Paper 1')
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

    def test_save_results_to_csv_with_abstract_column(self):
        """Test CSV export includes abstract column when requested."""
        results = [
            {
                'reference_title': 'Test Paper 1',
                'authors': 'Smith, John',
                'publication_year': '2023',
                'publication_title': 'Journal of Tests',
                'doi': '10.1000/abstract-test',
                'abstract': 'A concise abstract.',
                'reference_key': 'SMITH2023',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            self.handler.save_results_to_csv(results, tmp_filename, include_abstract=True)

            with open(tmp_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.assertIn('abstract', reader.fieldnames)
                rows = list(reader)
                self.assertEqual(rows[0]['abstract'], 'A concise abstract.')
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

    def test_format_result_summary(self):
        """Test result summary formatting."""
        # Test empty results
        summary = self.handler.format_result_summary([])
        self.assertEqual(summary, "No results found.")

        # Test with results
        results = [
            {'reference_key': 'REF1', 'pdf_key': 'PDF1', 'search_term_found': 'term'},
            {'reference_key': 'REF1', 'pdf_key': 'PDF2', 'search_term_found': 'term'},
            {'reference_key': 'REF2', 'pdf_key': 'PDF3', 'search_term_found': 'term'},
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
            self.handler.save_results_to_markdown(
                results,
                tmp_filename,
                full_text_query=['algorithm', 'machine learning', 'neural network'],
                metadata_filters={
                    'item_types': ['journalArticle'],
                    'collection': {'input': 'Focused Review', 'key': 'ABCD1234', 'name': 'Focused Review'},
                    'tags': ['alpha', 'beta'],
                    'tag_match_mode': 'any',
                    'publication_titles': [],
                },
            )

            # Verify file exists and has correct content
            self.assertTrue(os.path.exists(tmp_filename))

            with open(tmp_filename, 'r', encoding='utf-8') as mdfile:
                content = mdfile.read()

                # Extract YAML frontmatter (between first two '---')
                yaml_split = content.split('---')
                if len(yaml_split) > 2:
                    yaml_frontmatter = yaml_split[1]
                else:
                    yaml_frontmatter = ""
                # Check that 'annotations:' is NOT present in YAML frontmatter
                self.assertNotIn('annotations:', yaml_frontmatter)
                self.assertIn('metadata_filters:', yaml_frontmatter)
                self.assertIn('item_types:', yaml_frontmatter)
                self.assertIn('tag_match_mode: any', yaml_frontmatter)
                self.assertIn('Focused Review', yaml_frontmatter)

                # Check for expected content
                self.assertIn('# ZotGrep Results', content)
                self.assertIn('**Results:** Found **2** annotations across **1** papers.', content)
                self.assertIn('total_papers_found: 1', content)
                self.assertIn('total_annotations_found: 2', content)
                self.assertNotIn('title: \'Test Paper: A Study\'', yaml_frontmatter)
                self.assertIn('**Year**: 2023', content)
                self.assertIn('**Authors**: Smith, John; Doe, Jane', content)
                self.assertIn('**Citekey**: `SMITH2023`', content)
                self.assertIn('## Abstracts', content)
                self.assertIn('No abstract available.', content)
                self.assertIn('#### Term Summary', content)
                self.assertIn('- `algorithm`: 1 occurrence', content)
                self.assertIn('- `machine learning`: 1 occurrence', content)
                self.assertIn('- `neural network`: 1 occurrence', content)
                self.assertIn('#### Annotations', content)
                self.assertIn('##### Occurrence #1, Page 5', content)
                self.assertIn('##### Occurrence #2, Page 7', content)
                self.assertIn('The **machine learning** **algorithm** demonstrated significant improvements.', content)
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

    def test_save_results_to_markdown_without_fulltext_terms(self):
        """Test Markdown output stays coherent for metadata-only results."""
        results = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Smith, John',
                'publication_year': '2023',
                'publication_title': 'Journal of Tests',
                'doi': '10.1000/metadata-test',
                'abstract': 'A concise abstract.',
                'reference_key': 'SMITH2023',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            self.handler.save_results_to_markdown(
                results,
                tmp_filename,
                zotero_query='metadata query',
                full_text_query=[],
                include_abstract=True,
                context_window=2,
                search_timestamp='2023-01-01 12:00:00',
                metadata_filters={
                    'item_types': ['journalArticle'],
                    'collection': {'input': 'Focused Review', 'key': 'ABCD1234', 'name': 'Focused Review'},
                    'tags': ['alpha'],
                    'tag_match_mode': 'all',
                    'publication_titles': [],
                },
            )

            with open(tmp_filename, 'r', encoding='utf-8') as mdfile:
                content = mdfile.read()

            self.assertIn('full_text_query: []', content)
            self.assertIn('metadata_filters:', content)
            self.assertIn('tag_match_mode: all', content)
            self.assertNotIn('abstract: A concise abstract.', content)
            self.assertIn('total_papers_found: 1', content)
            self.assertIn('total_annotations_found: 0', content)
            self.assertIn('**Full-Text Query:** None supplied', content)
            self.assertIn('**Results:** Found **1** papers. No full-text terms were supplied.', content)
            self.assertIn('## Abstracts', content)
            self.assertIn('### Abstract for Smith, 2023', content)
            self.assertIn('A concise abstract.', content)
            self.assertIn('Journal of Tests.', content)
            self.assertIn('https://doi.org/10.1000/metadata-test', content)
            self.assertIn('## Detailed Findings', content)
            self.assertIn('No full-text terms were supplied, so no annotation-level findings were generated.', content)
            self.assertNotIn('#### Annotations', content)
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

    def test_save_results_to_json(self):
        """Test JSON output uses the structured payload shape."""
        results = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Smith, John',
                'publication_year': '2023',
                'publication_title': 'Journal of Tests',
                'doi': '10.1000/json-test',
                'abstract': 'A concise abstract.',
                'reference_key': 'SMITH2023',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://select/library/items/SMITH2023',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            self.handler.save_results_to_json(
                results,
                tmp_filename,
                zotero_query='metadata query',
                full_text_query=[],
                include_abstract=True,
                context_window=2,
                search_timestamp='2023-01-01 12:00:00',
                metadata_filters={
                    'item_types': ['journalArticle'],
                    'collection': {'input': 'Focused Review', 'key': 'ABCD1234', 'name': 'Focused Review'},
                    'tags': ['alpha'],
                    'tag_match_mode': 'all',
                    'publication_titles': [],
                },
            )

            with open(tmp_filename, 'r', encoding='utf-8') as jsonfile:
                content = jsonfile.read()

            self.assertIn('"zotgrep_results_version": 1', content)
            self.assertIn('"search_mode": "metadata_only"', content)
            self.assertIn('"metadata_filters"', content)
            self.assertIn('"tag_match_mode": "all"', content)
            self.assertIn('"doi": "10.1000/json-test"', content)
            self.assertIn('"abstract": "A concise abstract."', content)
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

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

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_markdown_output(self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler):
        """Test CLI with --md argument generates markdown output."""
        # Mock the config and search engine
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2 # Set a default value

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        # Simulate search results
        mock_search_engine_instance.search_zotero_and_full_text.return_value = [
            { # Sample result dictionary
                'reference_title': 'Test Paper',
                'authors': 'Test Author',
                'publication_year': '2023',
                'reference_key': 'TESTKEY',
                'pdf_filename': 'test.pdf',
                'pdf_key': 'PDFKEY',
                'page_number': 1,
                'search_term_found': 'test term',
                'context': 'This is a test context.',
                'context_highlighted': 'This is a ***test term*** context.',
                'zotero_item_url': 'zotero://item/TESTKEY',
                'zotero_pdf_url': 'zotero://pdf/PDFKEY?page=1',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        mock_search_engine_instance.get_search_summary.return_value = "Found 1 match."

        # Mock the ResultHandler instance
        mock_result_handler_instance = mock_result_handler.return_value

        # Simulate command line arguments
        test_args = ['--zotero', 'test zotero', '--fulltext', 'test term', '--md', 'test_output.md']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        # Assert that main exited successfully
        self.assertEqual(exit_code, 0)

        # Assert that save_results_to_markdown was called with the correct filename
        mock_result_handler_instance.save_results_to_markdown.assert_called_once()
        # Check the filename argument specifically
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[0][1], 'test_output.md')
        # Optionally, check other arguments passed to save_results_to_markdown
        self.assertIsNotNone(mock_result_handler_instance.save_results_to_markdown.call_args[0][0]) # Check results are passed
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['zotero_query'], 'test zotero')
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['full_text_query'], ['test term'])
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['include_abstract'], True)
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['context_window'], 2)
        mock_result_handler_instance.save_results_to_json.assert_called_once()

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_allows_metadata_only_search(self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler):
        """Test CLI allows metadata-only search when --fulltext is omitted."""
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Test Author',
                'publication_year': '2023',
                'publication_title': 'Journal',
                'reference_key': 'TESTKEY',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://item/TESTKEY',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        mock_search_engine_instance.get_search_summary.return_value = "Found 1 reference."
        mock_result_handler_instance = mock_result_handler.return_value

        test_args = ['--zotero', 'test zotero', '--md', 'test_output.md']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mock_search_engine_instance.search_zotero_and_full_text.assert_called_once_with(
            'test zotero', '', include_abstract=True, metadata_only=False
        )
        mock_result_handler_instance.save_results_to_markdown.assert_called_once()
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['full_text_query'], [])
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['include_abstract'], True)
        mock_result_handler_instance.save_results_to_json.assert_called_once()

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_includes_abstracts_by_default(self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler):
        """Test CLI includes abstracts by default in metadata-only mode."""
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Test Author',
                'publication_year': '2023',
                'publication_title': 'Journal',
                'abstract': 'Abstract text.',
                'reference_key': 'TESTKEY',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://item/TESTKEY',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        mock_search_engine_instance.get_search_summary.return_value = "Found 1 reference."
        mock_result_handler_instance = mock_result_handler.return_value

        test_args = ['--zotero', 'test zotero', '--md', 'test_output.md']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mock_search_engine_instance.search_zotero_and_full_text.assert_called_once_with(
            'test zotero', '', include_abstract=True, metadata_only=False
        )
        mock_result_handler_instance.save_results_to_markdown.assert_called_once()
        self.assertEqual(mock_result_handler_instance.save_results_to_markdown.call_args[1]['include_abstract'], True)
        mock_result_handler_instance.save_results_to_json.assert_called_once()

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_no_abstract_flag_disables_abstracts(self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler):
        """Test CLI passes --no-abstract through to output handlers."""
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Test Author',
                'publication_year': '2023',
                'publication_title': 'Journal',
                'abstract': '',
                'reference_key': 'TESTKEY',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://item/TESTKEY',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        mock_search_engine_instance.get_search_summary.return_value = "Found 1 reference."

        test_args = ['--zotero', 'test zotero', '--no-abstract', '--md', 'test_output.md']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mock_search_engine_instance.search_zotero_and_full_text.assert_called_once_with(
            'test zotero', '', include_abstract=False, metadata_only=False
        )
        self.assertEqual(
            mock_result_handler.return_value.save_results_to_markdown.call_args[1]['include_abstract'],
            False
        )

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_search_args_do_not_trigger_interactive_output_prompt(
        self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler
    ):
        """CLI search args should not fall back to the interactive output chooser."""
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = [
            {
                'reference_title': 'Metadata Only Paper',
                'authors': 'Test Author',
                'publication_year': '2023',
                'publication_title': 'Journal',
                'abstract': '',
                'reference_key': 'TESTKEY',
                'pdf_filename': '',
                'pdf_key': '',
                'page_number': '',
                'search_term_found': '',
                'context': '',
                'context_highlighted': '',
                'zotero_item_url': 'zotero://item/TESTKEY',
                'zotero_pdf_url': '',
                'search_timestamp': '2023-01-01 12:00:00'
            }
        ]
        mock_search_engine_instance.get_search_summary.return_value = "Found 1 reference."

        mock_result_handler_instance = mock_result_handler.return_value

        test_args = ['--zotero', 'test zotero']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mock_result_handler_instance.get_interactive_output_choice.assert_not_called()
        mock_result_handler_instance.save_results_to_json.assert_called_once()

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_metadata_only_flag_is_explicit(self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler):
        """Explicit metadata-only mode should be passed through to the search engine."""
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = []

        test_args = ['--zotero', 'test zotero', '--metadata-only', '--no-json']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        mock_search_engine_instance.search_zotero_and_full_text.assert_called_once_with(
            'test zotero', '', include_abstract=True, metadata_only=True
        )
        mock_result_handler.return_value.save_results_to_json.assert_not_called()

    @patch('builtins.print')
    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_warns_for_metadata_operator_like_syntax(
        self,
        mock_print_config,
        mock_get_config,
        mock_search_engine,
        mock_result_handler,
        mock_print,
    ):
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        mock_search_engine_instance = mock_search_engine.return_value
        mock_search_engine_instance.connect_to_zotero.return_value = True
        mock_search_engine_instance.search_zotero_and_full_text.return_value = []

        test_args = ['--zotero', 'alpha AND beta', '--no-json']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args):
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertTrue(
            any(
                "metadata search still uses Zotero quick-search semantics" in call.args[0]
                for call in mock_print.call_args_list
                if call.args
            )
        )

    @patch('zotgrep.cli.ResultHandler')
    @patch('zotgrep.cli.ZoteroSearchEngine')
    @patch('zotgrep.cli.get_config')
    @patch('zotgrep.cli.print_config_info')
    def test_cli_rejects_invalid_fulltext_query(
        self, mock_print_config, mock_get_config, mock_search_engine, mock_result_handler
    ):
        mock_config_instance = mock_get_config.return_value
        mock_config_instance.validate.return_value = True
        mock_config_instance.context_sentence_window = 2

        test_args = ['--zotero', 'test zotero', '--fulltext', '(alpha OR beta)']
        with patch.object(sys, 'argv', ['zotgrep'] + test_args), patch('builtins.print') as mock_print:
            from zotgrep.cli import main
            exit_code = main()

        self.assertEqual(exit_code, 1)
        mock_search_engine.return_value.search_zotero_and_full_text.assert_not_called()
        self.assertTrue(
            any("invalid --fulltext query" in call.args[0] for call in mock_print.call_args_list if call.args)
        )

    @patch('zotgrep.cli.get_config')
    def test_cli_create_config_from_filter_args(self, mock_get_config):
        from argparse import Namespace
        from zotgrep.cli import ZotGrepCLI

        mock_get_config.return_value = ZotGrepConfig(base_attachment_path="")
        cli = ZotGrepCLI()

        config = cli.create_config_from_args(
            Namespace(
                config=None,
                base_path=None,
                max_results=100,
                context_window=2,
                publication_title=None,
                debug_publication=False,
                item_type="journalArticle, book",
                collection="Focused Review",
                tag_filter="alpha, beta",
                tag_match="any",
            )
        )

        self.assertEqual(config.item_type_filter, ["journalArticle", "book"])
        self.assertEqual(config.collection_filter, "Focused Review")
        self.assertEqual(config.tag_filter, ["alpha", "beta"])
        self.assertEqual(config.tag_match_mode, "any")


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
