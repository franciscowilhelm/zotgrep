import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


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

try:
    from zotgrep.web import create_app
except ModuleNotFoundError as exc:
    if exc.name == "flask":
        create_app = None
    else:
        raise


@unittest.skipIf(create_app is None, "flask is not installed in this test environment")
class TestWebSettings(unittest.TestCase):
    def test_settings_page_saves_config_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "settings.json")
            attachments_dir = os.path.join(temp_dir, "attachments")
            os.mkdir(attachments_dir)

            with patch.dict(
                os.environ,
                {"ZOTGREP_CONFIG_PATH": config_path},
                clear=False,
            ):
                app = create_app()
                client = app.test_client()

                response = client.post(
                    "/settings",
                    data={
                        "zotero_user_id": "0",
                        "zotero_api_key": "local",
                        "library_type": "user",
                        "base_attachment_path": attachments_dir,
                        "max_results_stage1": "55",
                        "context_sentence_window": "4",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(os.path.exists(config_path))

            with open(config_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)

        self.assertEqual(saved["base_attachment_path"], attachments_dir)
        self.assertEqual(saved["max_results_stage1"], 55)
        self.assertEqual(saved["context_sentence_window"], 4)
        self.assertNotIn("use_local_api", saved)

    def test_settings_page_does_not_expose_local_api_toggle(self):
        app = create_app()
        client = app.test_client()

        response = client.get("/settings")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn('name="use_local_api"', html)
        self.assertIn("always uses Zotero's local API", html)

    def test_search_page_rejects_invalid_fulltext_query(self):
        app = create_app()
        client = app.test_client()

        response = client.post(
            "/search",
            data={
                "zotero_query": "alpha",
                "fulltext_terms": "(beta OR gamma)",
                "include_abstract": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Invalid full-text query", html)

    def test_search_page_hides_advanced_settings_by_default(self):
        app = create_app()
        client = app.test_client()

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("<summary>Advanced Search Settings</summary>", html)
        self.assertNotIn('details class="advanced-search" open', html)

    @patch("zotgrep.web.ZoteroSearchEngine")
    def test_search_page_shows_metadata_operator_warning(self, mock_engine):
        mock_engine_instance = mock_engine.return_value
        mock_engine_instance.connect_to_zotero.return_value = True
        mock_engine_instance.search_zotero_and_full_text.return_value = []
        mock_engine_instance.get_search_summary.return_value = "No results found."
        mock_engine_instance.warnings = []

        app = create_app()
        client = app.test_client()

        response = client.post(
            "/search",
            data={
                "zotero_query": "alpha AND beta",
                "fulltext_terms": "gamma",
                "include_abstract": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Metadata search still uses Zotero quick-search semantics", html)

    def test_search_page_preserves_filter_values_on_fulltext_validation_error(self):
        app = create_app()
        client = app.test_client()

        response = client.post(
            "/search",
            data={
                "zotero_query": "alpha",
                "fulltext_terms": "(beta OR gamma)",
                "item_type_filter": "journalArticle, book",
                "collection_filter": "Focused Review",
                "tag_filter": "alpha, beta",
                "tag_match_mode": "any",
                "include_abstract": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('value="journalArticle, book"', html)
        self.assertIn('value="Focused Review"', html)
        self.assertIn('value="alpha, beta"', html)
        self.assertIn('<option value="any" selected>', html)
        self.assertIn('details class="advanced-search" open', html)

    @patch("zotgrep.web.ZoteroSearchEngine")
    def test_search_page_applies_metadata_filters_to_config(self, mock_engine):
        mock_engine_instance = mock_engine.return_value
        mock_engine_instance.connect_to_zotero.return_value = True
        mock_engine_instance.search_zotero_and_full_text.return_value = []
        mock_engine_instance.get_search_summary.return_value = "No results found."
        mock_engine_instance.get_metadata_filters_for_output.return_value = {
            "item_types": ["journalArticle"],
            "collection": {"input": "Focused Review", "key": "ABCD1234", "name": "Focused Review"},
            "tags": ["alpha", "beta"],
            "tag_match_mode": "any",
            "publication_titles": [],
        }
        mock_engine_instance.warnings = []

        app = create_app()
        client = app.test_client()

        response = client.post(
            "/search",
            data={
                "zotero_query": "alpha",
                "fulltext_terms": "gamma",
                "item_type_filter": "journalArticle",
                "collection_filter": "Focused Review",
                "tag_filter": "alpha, beta",
                "tag_match_mode": "any",
                "include_abstract": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        passed_config = mock_engine.call_args.args[0]
        self.assertEqual(passed_config.item_type_filter, ["journalArticle"])
        self.assertEqual(passed_config.collection_filter, "Focused Review")
        self.assertEqual(passed_config.tag_filter, ["alpha", "beta"])
        self.assertEqual(passed_config.tag_match_mode, "any")
