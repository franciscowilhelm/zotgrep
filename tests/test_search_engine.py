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

    if "nltk" not in sys.modules:
        nltk_module = types.ModuleType("nltk")

        class Downloader:
            DownloadError = LookupError

        class Data:
            @staticmethod
            def find(_path):
                return True

        nltk_module.downloader = Downloader
        nltk_module.data = Data()
        nltk_module.download = lambda _name: True
        nltk_module.sent_tokenize = lambda text: [text]
        sys.modules["nltk"] = nltk_module

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

from zotsearch.config import ZotSearchConfig


class TestZoteroSearchEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search_engine_module = importlib.import_module("zotsearch.search_engine")

    def test_stored_pdf_uses_file_download_for_imported_url(self):
        engine = self.search_engine_module.ZoteroSearchEngine(
            ZotSearchConfig(base_attachment_path="")
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
            ZotSearchConfig(base_attachment_path="")
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
