import importlib
import sys
import types
import unittest
from unittest.mock import Mock

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


_install_dependency_stubs()

from zotgrep.config import ZotGrepConfig
from zotgrep.text_analyzer import FullTextQuery, parse_full_text_query


class TestZoteroSearchEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search_engine_module = importlib.import_module("zotgrep.search_engine")

    def test_stored_pdf_uses_file_download_for_imported_url(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.file.return_value = b"%PDF-1.7"
        engine.pdf_processor.process_imported_pdf = Mock(return_value={1: "page text"})

        result = engine._extract_pdf_text(
            {
                "key": "PDF123",
                "filename": "paper.pdf",
                "link_mode": "imported_url",
                "path": "",
            },
            "Test Item",
        )

        self.assertEqual(result, {1: "page text"})
        engine.zot_conn.file.assert_called_once_with("PDF123")
        engine.pdf_processor.process_imported_pdf.assert_called_once_with(b"%PDF-1.7")

    def test_linked_pdf_without_base_path_is_skipped(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.pdf_processor.process_linked_pdf = Mock()

        result = engine._extract_pdf_text(
            {
                "key": "PDF123",
                "filename": "paper.pdf",
                "link_mode": "linked_file",
                "path": "attachments:paper.pdf",
            },
            "Test Item",
        )

        self.assertIsNone(result)
        engine.pdf_processor.process_linked_pdf.assert_not_called()

    def test_search_pdf_pages_passes_item_language_to_tokenizer(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.text_analyzer.build_page_contexts = Mock(return_value=[])

        findings, counter = engine._search_pdf_pages(
            text_by_page={1: "alpha sentence"},
            full_text_query=parse_full_text_query("alpha"),
            item_data={"language": "de-DE"},
            pdf_info={"key": "PDF123", "filename": "paper.pdf"},
        )

        self.assertEqual(findings, [])
        self.assertEqual(counter, {})
        called_query = engine.text_analyzer.build_page_contexts.call_args.args[1]
        self.assertIsInstance(called_query, FullTextQuery)
        self.assertEqual(called_query.leaf_terms, ["alpha"])
        self.assertEqual(
            engine.text_analyzer.build_page_contexts.call_args.kwargs,
            {"language": "de-DE"},
        )

    def test_search_engine_accepts_raw_full_text_query_string(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine._search_metadata = Mock(return_value=[{"data": {"title": "Title", "key": "ITEM1"}}])
        engine._process_item_pdfs = Mock(return_value=([], []))

        engine.search_zotero_and_full_text("alpha", "beta OR gamma")

        called_query = engine._process_item_pdfs.call_args.args[1]
        self.assertIsInstance(called_query, FullTextQuery)
        self.assertEqual(called_query.leaf_terms, ["beta", "gamma"])

    def test_plain_metadata_search_uses_items_endpoint(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [{"data": {"key": "ITEM1", "itemType": "journalArticle"}}]

        items = engine._search_metadata("alpha")

        self.assertEqual(len(items), 1)
        engine.zot_conn.items.assert_called_once_with(
            q="alpha",
            itemType="-attachment",
            limit=100,
            qmode="titleCreatorYear",
        )
        engine.zot_conn.top.assert_not_called()
        engine.zot_conn.collection_items_top.assert_not_called()

    def test_item_type_filter_routes_search_via_top_level_items(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", item_type_filter=["journalArticle"])
        )
        engine.zot_conn = Mock()
        engine.zot_conn.top.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle"}},
        ]

        items = engine._search_metadata("alpha")

        self.assertEqual(len(items), 1)
        engine.zot_conn.top.assert_called_once_with(
            q="alpha",
            limit=100,
            qmode="titleCreatorYear",
            itemType="journalArticle",
        )
        engine.zot_conn.items.assert_not_called()

    def test_collection_filter_routes_search_via_collection_top_items(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", collection_filter="ABCD1234")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.collection.return_value = {
            "data": {"key": "ABCD1234", "name": "Focused Review"}
        }
        engine.zot_conn.collection_items_top.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle"}},
        ]

        items = engine._search_metadata("alpha")

        self.assertEqual(len(items), 1)
        engine.zot_conn.collection.assert_called_once_with("ABCD1234")
        engine.zot_conn.collection_items_top.assert_called_once_with(
            "ABCD1234",
            q="alpha",
            limit=100,
            qmode="titleCreatorYear",
        )
        engine.zot_conn.items.assert_not_called()

    def test_collection_and_item_type_filters_route_with_server_side_item_type(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(
                base_attachment_path="",
                collection_filter="Focused Review",
                item_type_filter=["journalArticle"],
            )
        )
        engine.zot_conn = Mock()
        engine.zot_conn.all_collections.return_value = [
            {"data": {"key": "ABCD1234", "name": "Focused Review"}},
        ]
        engine.zot_conn.collection_items_top.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle"}},
        ]

        items = engine._search_metadata("alpha")

        self.assertEqual(len(items), 1)
        engine.zot_conn.collection_items_top.assert_called_once_with(
            "ABCD1234",
            q="alpha",
            limit=100,
            qmode="titleCreatorYear",
            itemType="journalArticle",
        )

    def test_collection_resolution_succeeds_by_unique_name(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", collection_filter="Focused Review")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.all_collections.return_value = [
            {"data": {"key": "ABCD1234", "name": "Focused Review"}},
        ]

        resolved = engine._resolve_collection_filter("Focused Review")

        self.assertEqual(resolved.key, "ABCD1234")
        self.assertEqual(resolved.name, "Focused Review")

    def test_collection_resolution_rejects_missing_name(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.all_collections.return_value = []

        with self.assertRaisesRegex(ValueError, "was not found"):
            engine._resolve_collection_filter("Missing Collection")

    def test_collection_resolution_rejects_ambiguous_name(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.all_collections.return_value = [
            {"data": {"key": "ABCD1234", "name": "Focused Review"}},
            {"data": {"key": "WXYZ9876", "name": "Focused Review"}},
        ]

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            engine._resolve_collection_filter("Focused Review")

    def test_tag_filter_supports_all_matching(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(
                base_attachment_path="",
                tag_filter=["alpha", "beta"],
                tag_match_mode="all",
            )
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle", "tags": [{"tag": "alpha"}, {"tag": "beta"}]}},
            {"data": {"key": "ITEM2", "itemType": "journalArticle", "tags": [{"tag": "alpha"}]}},
        ]

        items = engine._search_metadata("alpha")

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])

    def test_tag_filter_supports_any_matching(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(
                base_attachment_path="",
                tag_filter=["alpha", "beta"],
                tag_match_mode="any",
            )
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle", "tags": [{"tag": "alpha"}]}},
            {"data": {"key": "ITEM2", "itemType": "journalArticle", "tags": [{"tag": "beta"}]}},
            {"data": {"key": "ITEM3", "itemType": "journalArticle", "tags": [{"tag": "gamma"}]}},
        ]

        items = engine._search_metadata("alpha")

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1", "ITEM2"])
