import os
import sys
import tempfile
import types
import unittest
import json
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

from zotgrep.config import ZotGrepConfig
from zotgrep.config import get_config
from zotgrep.config import get_user_config_path
from zotgrep.config import load_config_from_env
from zotgrep.config import load_config_from_file
from zotgrep.config import save_config_to_file


class TestZotGrepConfig(unittest.TestCase):
    def test_base_attachment_path_is_optional(self):
        config = ZotGrepConfig(base_attachment_path="")
        self.assertEqual(config.base_attachment_path, "")

    def test_existing_base_attachment_path_is_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ZotGrepConfig(base_attachment_path=temp_dir)
            self.assertEqual(config.base_attachment_path, temp_dir)

    def test_nonexistent_base_attachment_path_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "BASE_ATTACHMENT_PATH does not exist"):
            ZotGrepConfig(base_attachment_path="/definitely/not/a/real/path")

    def test_load_config_from_env_leaves_base_path_empty_when_env_var_missing(self):
        original = os.environ.pop("ZOTERO_BASE_ATTACHMENT_PATH", None)
        try:
            config = load_config_from_env()
        finally:
            if original is not None:
                os.environ["ZOTERO_BASE_ATTACHMENT_PATH"] = original

        self.assertEqual(config.base_attachment_path, "")

    def test_save_and_load_config_file_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            attachments_dir = os.path.join(temp_dir, "attachments")
            os.mkdir(attachments_dir)

            config = ZotGrepConfig(
                base_attachment_path=attachments_dir,
                max_results_stage1=42,
                context_sentence_window=5,
            )
            saved_path = save_config_to_file(config, config_path=config_path)
            loaded = load_config_from_file(config_path=config_path)

        self.assertEqual(saved_path, os.path.abspath(config_path))
        self.assertEqual(loaded.base_attachment_path, attachments_dir)
        self.assertEqual(loaded.max_results_stage1, 42)
        self.assertEqual(loaded.context_sentence_window, 5)

    def test_get_config_applies_file_then_env_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            attachments_dir = os.path.join(temp_dir, "attachments")
            os.mkdir(attachments_dir)

            save_config_to_file(
                ZotGrepConfig(
                    base_attachment_path=attachments_dir,
                    max_results_stage1=42,
                ),
                config_path=config_path,
            )

            with patch.dict(
                os.environ,
                {
                    "ZOTGREP_CONFIG_PATH": config_path,
                    "ZOTERO_MAX_RESULTS": "77",
                },
                clear=False,
            ):
                config = get_config()
                resolved_path = get_user_config_path()

        self.assertEqual(config.base_attachment_path, attachments_dir)
        self.assertEqual(config.max_results_stage1, 77)
        self.assertEqual(resolved_path, os.path.abspath(config_path))

    def test_non_local_api_flags_from_file_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "use_local_api": False,
                        "zotero_user_id": "12345",
                        "zotero_api_key": "secret",
                    },
                    handle,
                )

            loaded = load_config_from_file(config_path=config_path)

        self.assertTrue(loaded.use_local_api)

    def test_non_local_api_flags_from_env_are_ignored(self):
        with patch.dict(os.environ, {"ZOTERO_USE_LOCAL_API": "false"}, clear=False):
            config = load_config_from_env()

        self.assertTrue(config.use_local_api)
