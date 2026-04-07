import sys
import types
import unittest


def _install_dependency_stubs():
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

from zotgrep.pdf_processor import PDFProcessor


class TestPDFProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = PDFProcessor()

    def test_clean_pdf_text_reflows_soft_wrapped_lines(self):
        raw_text = (
            "This is a sentence that wraps\n"
            "onto the next line before it ends\n"
            "and then finishes here."
        )

        cleaned = self.processor._clean_pdf_text(raw_text)

        self.assertEqual(
            cleaned,
            "This is a sentence that wraps onto the next line before it ends and then finishes here.",
        )

    def test_clean_pdf_text_preserves_blank_line_paragraph_breaks(self):
        raw_text = "First paragraph wraps\nonto a second line.\n\nSecond paragraph starts here."

        cleaned = self.processor._clean_pdf_text(raw_text)

        self.assertEqual(
            cleaned,
            "First paragraph wraps onto a second line.\n\nSecond paragraph starts here.",
        )

    def test_clean_pdf_text_preserves_structural_lines(self):
        raw_text = "INTRODUCTION\nThis paragraph wraps\nonto another line.\n\n- Bullet one\n- Bullet two"

        cleaned = self.processor._clean_pdf_text(raw_text)

        self.assertEqual(
            cleaned,
            "INTRODUCTION\nThis paragraph wraps onto another line.\n\n- Bullet one\n- Bullet two",
        )

    def test_clean_pdf_text_repairs_hyphenated_line_breaks(self):
        raw_text = "This inter-\nnational collaboration succeeded."

        cleaned = self.processor._clean_pdf_text(raw_text)

        self.assertEqual(cleaned, "This international collaboration succeeded.")


if __name__ == "__main__":
    unittest.main()
