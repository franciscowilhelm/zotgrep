import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

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

    def test_connection_uses_ipv4_before_first_request(self):
        engine = self.search_engine_module.ZoteroSearchEngine(ZotGrepConfig())
        connection = Mock()
        connection.endpoint = "http://localhost:23119/api"

        def check_endpoint(**kwargs):
            self.assertEqual(connection.endpoint, "http://127.0.0.1:23119/api")
            self.assertEqual(kwargs, {"limit": 1})
            return []

        connection.top.side_effect = check_endpoint
        with patch.object(self.search_engine_module.zotero, "Zotero", return_value=connection) as factory:
            self.assertTrue(engine.connect_to_zotero())
        self.assertTrue(factory.call_args.kwargs["local"])
        connection.top.assert_called_once()

    def test_connection_failure_is_reported(self):
        engine = self.search_engine_module.ZoteroSearchEngine(ZotGrepConfig())
        connection = Mock()
        connection.top.side_effect = ConnectionError("Zotero is unavailable")
        with patch.object(self.search_engine_module.zotero, "Zotero", return_value=connection):
            self.assertFalse(engine.connect_to_zotero())

    def test_unquoted_metadata_alternative_keeps_words_in_separate_fields(self):
        engine = self.search_engine_module.ZoteroSearchEngine(ZotGrepConfig())
        engine.zot_conn = Mock()
        item = {"data": {"key": "ITEM1", "title": "Career development",
                         "creators": [{"name": "Engagement Institute"}]}}
        engine.zot_conn.items.side_effect = [[item], []]

        self.assertEqual(engine._search_metadata("career engagement OR motivation"), [item])
        self.assertEqual(engine.zot_conn.items.call_args_list[0].kwargs["q"], "career engagement")

    def test_quoted_and_unquoted_versions_of_same_words_keep_distinct_semantics(self):
        engine = self.search_engine_module.ZoteroSearchEngine(ZotGrepConfig())
        engine.zot_conn = Mock()
        item = {"data": {"key": "ITEM1", "title": "Career development and engagement"}}
        engine.zot_conn.items.side_effect = [[item], [item]]

        self.assertEqual(engine._search_metadata('"career engagement" OR career engagement'), [item])

    def test_metadata_phrase_asterisk_is_literal(self):
        engine = self.search_engine_module.ZoteroSearchEngine(ZotGrepConfig())
        self.assertFalse(engine._item_matches_phrase(
            {"data": {"title": "Career engagement"}}, "career engage*"))
        self.assertTrue(engine._item_matches_phrase(
            {"data": {"title": "Career engage*"}}, "career engage*"))

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

    def test_publication_title_filter_is_applied_client_side(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(
                base_attachment_path="",
                publication_title_filter=["Human Resource Management Review"],
            )
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {
                "data": {
                    "key": "ITEM1",
                    "itemType": "journalArticle",
                    "publicationTitle": "Human Resource Management Review",
                }
            },
            {
                "data": {
                    "key": "ITEM2",
                    "itemType": "journalArticle",
                    "publicationTitle": "Academy of Management Journal",
                }
            },
        ]

        items = engine._search_metadata("review")

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])
        engine.zot_conn.items.assert_called_once_with(
            q="review",
            itemType="-attachment",
            limit=100,
            qmode="titleCreatorYear",
        )

    def test_stage1_limit_warning_mentions_client_side_publication_filter(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(
                base_attachment_path="",
                max_results_stage1=2,
                publication_title_filter=["Human Resource Management Review"],
            )
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {
                "data": {
                    "key": "ITEM1",
                    "itemType": "journalArticle",
                    "publicationTitle": "Human Resource Management Review",
                }
            },
            {
                "data": {
                    "key": "ITEM2",
                    "itemType": "journalArticle",
                    "publicationTitle": "Academy of Management Journal",
                }
            },
        ]

        engine._search_metadata("review")

        self.assertEqual(len(engine.warnings), 1)
        self.assertIn("Publication title filtering is applied client-side", engine.warnings[0])

    def test_operator_free_metadata_query_makes_single_call(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle"}},
        ]

        items = engine._search_metadata("career engagement")

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])
        engine.zot_conn.items.assert_called_once_with(
            q="career engagement",
            itemType="-attachment",
            limit=100,
            qmode="titleCreatorYear",
        )

    def test_comma_query_makes_two_calls_and_unions_deduped_results(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.side_effect = [
            [
                {"data": {"key": "ITEM1", "itemType": "journalArticle", "title": "Career engagement study"}},
                {
                    "data": {
                        "key": "ITEM2",
                        "itemType": "journalArticle",
                        "title": "Career engagement and career orientation",
                    }
                },
            ],
            [
                {
                    "data": {
                        "key": "ITEM2",
                        "itemType": "journalArticle",
                        "title": "Career engagement and career orientation",
                    }
                },
                {"data": {"key": "ITEM3", "itemType": "journalArticle", "title": "Career orientation study"}},
            ],
        ]

        items = engine._search_metadata('"career engagement", "career orientation"')

        self.assertEqual(
            [item["data"]["key"] for item in items],
            ["ITEM1", "ITEM2", "ITEM3"],
        )
        self.assertEqual(engine.zot_conn.items.call_count, 2)
        first_call_kwargs = engine.zot_conn.items.call_args_list[0].kwargs
        second_call_kwargs = engine.zot_conn.items.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs["q"], "career engagement")
        self.assertEqual(second_call_kwargs["q"], "career orientation")

    def test_and_query_makes_one_call_with_space_joined_terms(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {"data": {"key": "ITEM1", "itemType": "journalArticle"}},
        ]

        items = engine._search_metadata("alpha AND beta")

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])
        engine.zot_conn.items.assert_called_once_with(
            q="alpha beta",
            itemType="-attachment",
            limit=100,
            qmode="titleCreatorYear",
        )

    def test_mixed_and_or_query_produces_two_branches(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.side_effect = [
            [{"data": {"key": "ITEM1", "itemType": "journalArticle"}}],
            [{"data": {"key": "ITEM2", "itemType": "journalArticle"}}],
        ]

        items = engine._search_metadata("a AND b, c")

        self.assertEqual(
            [item["data"]["key"] for item in items],
            ["ITEM1", "ITEM2"],
        )
        self.assertEqual(engine.zot_conn.items.call_count, 2)
        first_call_kwargs = engine.zot_conn.items.call_args_list[0].kwargs
        second_call_kwargs = engine.zot_conn.items.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs["q"], "a b")
        self.assertEqual(second_call_kwargs["q"], "c")

    def test_branch_hitting_limit_adds_warning_naming_branch(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", max_results_stage1=1)
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.side_effect = [
            [{"data": {"key": "ITEM1", "itemType": "journalArticle"}}],
            [],
        ]

        engine._search_metadata("alpha, beta")

        self.assertEqual(len(engine.warnings), 1)
        self.assertIn("alpha", engine.warnings[0])
        self.assertIn("equals the current limit of 1", engine.warnings[0])

    def test_phrase_verification_drops_non_matching_item_in_title_creator_year_mode(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {
                "data": {
                    "key": "ITEM1",
                    "itemType": "journalArticle",
                    "title": "A study of career engagement",
                    "creators": [],
                    "date": "2020",
                }
            },
            {
                "data": {
                    "key": "ITEM2",
                    "itemType": "journalArticle",
                    "title": "Unrelated title",
                    "creators": [{"firstName": "Career", "lastName": "Smith"}],
                    "date": "2020",
                }
            },
        ]

        items = engine._search_metadata('"career engagement"')

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])

    def test_phrase_verification_skipped_in_everything_mode(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", metadata_search_mode="everything")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.items.return_value = [
            {
                "data": {
                    "key": "ITEM1",
                    "itemType": "journalArticle",
                    "title": "Unrelated title",
                    "creators": [],
                    "date": "2020",
                }
            },
        ]

        items = engine._search_metadata('"career engagement"')

        self.assertEqual([item["data"]["key"] for item in items], ["ITEM1"])

    def test_boolean_query_routes_via_collection_items_top_when_collection_resolved(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="", collection_filter="ABCD1234")
        )
        engine.zot_conn = Mock()
        engine.zot_conn.collection.return_value = {
            "data": {"key": "ABCD1234", "name": "Focused Review"}
        }
        engine.zot_conn.collection_items_top.side_effect = [
            [{"data": {"key": "ITEM1", "itemType": "journalArticle"}}],
            [{"data": {"key": "ITEM2", "itemType": "journalArticle"}}],
        ]

        items = engine._search_metadata("alpha, beta")

        self.assertEqual(
            [item["data"]["key"] for item in items],
            ["ITEM1", "ITEM2"],
        )
        self.assertEqual(engine.zot_conn.collection_items_top.call_count, 2)
        engine.zot_conn.items.assert_not_called()
        first_call = engine.zot_conn.collection_items_top.call_args_list[0]
        second_call = engine.zot_conn.collection_items_top.call_args_list[1]
        self.assertEqual(first_call.args[0], "ABCD1234")
        self.assertEqual(first_call.kwargs["q"], "alpha")
        self.assertEqual(second_call.args[0], "ABCD1234")
        self.assertEqual(second_call.kwargs["q"], "beta")

    def test_unparseable_boolean_query_raises_value_error(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotGrepConfig(base_attachment_path="")
        )
        engine.zot_conn = Mock()

        with self.assertRaisesRegex(ValueError, "could not be parsed as a boolean query"):
            engine._search_metadata('alpha, "unterminated')
