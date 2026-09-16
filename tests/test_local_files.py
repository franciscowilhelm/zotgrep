import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import httpx2

from zotgrep.local_files import read_local_file_url, read_stored_attachment


class TestLocalAttachments(unittest.TestCase):
    def connection(self, handler, library_type="users", library_id="0"):
        client = httpx2.Client(transport=httpx2.MockTransport(handler))
        self.addCleanup(client.close)
        return SimpleNamespace(
            endpoint="http://127.0.0.1:23119/api",
            library_type=library_type, library_id=library_id,
            request=httpx2.Response(200, headers={"Zotero-Server-ID": "test-instance"}),
            client=client,
        )

    def test_file_redirect_reads_encoded_path_without_following_http_redirect(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Paper \u6c49 #100%.pdf"
            path.write_bytes(b"%PDF-1.7 test")
            requests = []

            def handler(request):
                requests.append(request)
                self.assertEqual(request.headers["Zotero-Server-ID"], "test-instance")
                self.assertEqual(str(request.url), "http://127.0.0.1:23119/api/groups/42/items/ATTACH01/file")
                return httpx2.Response(302, headers={"Location": path.as_uri()})

            connection = self.connection(handler, "groups", "42")
            self.assertEqual(read_stored_attachment(connection, "ATTACH01"), b"%PDF-1.7 test")
            self.assertEqual(len(requests), 1)

    def test_missing_file_redirect_raises_file_not_found(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.pdf"
            connection = self.connection(lambda _: httpx2.Response(302, headers={"Location": path.as_uri()}))
            with self.assertRaises(FileNotFoundError):
                read_stored_attachment(connection, "MISSING1")

    def test_direct_pdf_response_is_supported(self):
        connection = self.connection(lambda _: httpx2.Response(200, content=b"%PDF-data"))
        connection.request = None
        self.assertEqual(read_stored_attachment(connection, "ATTACH01"), b"%PDF-data")

    def test_http_errors_are_not_treated_as_pdf_content(self):
        connection = self.connection(lambda _: httpx2.Response(403, text="Access denied"))
        with self.assertRaises(httpx2.HTTPStatusError):
            read_stored_attachment(connection, "ATTACH01")

    def test_nonlocal_and_invalid_urls_are_rejected(self):
        for url in ["https://example.org/a.pdf", "file://server/share/a.pdf", "file:////server/a.pdf", "", "file:relative.pdf"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                read_local_file_url(url)
