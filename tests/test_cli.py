import io
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
