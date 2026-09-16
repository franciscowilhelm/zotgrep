import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from zotgrep import cli


class TestConsoleOutput(unittest.TestCase):
    def test_unencodable_progress_does_not_abort_search(self):
        output = io.BytesIO()
        errors = io.BytesIO()
        stdout = io.TextIOWrapper(output, encoding="cp1252")
        stderr = io.TextIOWrapper(errors, encoding="cp1252")

        def run():
            print("Career\u2010orientation \u6c49")
            print("Warning: \u6c49", file=stderr)
            return 0

        with patch.object(cli.sys, "stdout", stdout), patch.object(cli.sys, "stderr", stderr):
            with patch.object(cli.ZotGrepCLI, "run", side_effect=run):
                self.assertEqual(cli.main(), 0)
        stdout.flush()
        stderr.flush()
        self.assertIn(b"Career\\u2010orientation \\u6c49", output.getvalue())
        self.assertIn(b"Warning: \\u6c49", errors.getvalue())
        self.assertEqual(stdout.encoding, "cp1252")

    def test_embedded_streams_without_reconfigure_are_supported(self):
        with patch.object(cli.sys, "stdout", io.StringIO()):
            with patch.object(cli.sys, "stderr", io.StringIO()):
                with patch.object(cli.ZotGrepCLI, "run", return_value=0):
                    self.assertEqual(cli.main(), 0)


class TestConfigPrecedence(unittest.TestCase):
    def _config_for(self, argv, env=None, file_values=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            if file_values is not None:
                with open(config_path, "w", encoding="utf-8") as handle:
                    json.dump(file_values, handle)
            environment = {"ZOTGREP_CONFIG_PATH": config_path, **(env or {})}
            with patch.dict(os.environ, environment, clear=False):
                for name in ("ZOTERO_MAX_RESULTS", "ZOTERO_CONTEXT_WINDOW"):
                    if name not in environment:
                        os.environ.pop(name, None)
                with patch.object(cli.sys, "argv", ["zotgrep", *argv]):
                    zotgrep_cli = cli.ZotGrepCLI()
                    return zotgrep_cli.create_config_from_args(zotgrep_cli.parse_arguments())

    def test_package_defaults_apply_without_file_env_or_arguments(self):
        config = self._config_for([])

        self.assertEqual(config.max_results_stage1, 100)
        self.assertEqual(config.context_sentence_window, 2)

    def test_config_file_values_apply_when_arguments_are_omitted(self):
        config = self._config_for(
            [],
            file_values={"max_results_stage1": 42, "context_sentence_window": 5},
        )

        self.assertEqual(config.max_results_stage1, 42)
        self.assertEqual(config.context_sentence_window, 5)

    def test_environment_values_apply_when_arguments_are_omitted(self):
        config = self._config_for(
            [],
            env={"ZOTERO_MAX_RESULTS": "77", "ZOTERO_CONTEXT_WINDOW": "4"},
            file_values={"max_results_stage1": 42, "context_sentence_window": 5},
        )

        self.assertEqual(config.max_results_stage1, 77)
        self.assertEqual(config.context_sentence_window, 4)

    def test_arguments_override_environment_and_config_file(self):
        config = self._config_for(
            ["--max-results", "10", "--context-window", "1"],
            env={"ZOTERO_MAX_RESULTS": "77", "ZOTERO_CONTEXT_WINDOW": "4"},
            file_values={"max_results_stage1": 42, "context_sentence_window": 5},
        )

        self.assertEqual(config.max_results_stage1, 10)
        self.assertEqual(config.context_sentence_window, 1)

    def test_zero_context_window_argument_is_applied(self):
        config = self._config_for(
            ["--context-window", "0"],
            file_values={"context_sentence_window": 5},
        )

        self.assertEqual(config.context_sentence_window, 0)
