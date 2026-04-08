import unittest
import sys
import types
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

from zotgrep.text_analyzer import TextAnalyzer, parse_full_text_query


class FakePysbdModule:
    def __init__(self, failing_languages=None, segment_raises=False):
        self.failing_languages = set(failing_languages or [])
        self.segment_raises = segment_raises
        self.created_languages = []

    def Segmenter(self, language, clean=False):
        self.created_languages.append((language, clean))
        if language in self.failing_languages:
            raise ValueError(f"unsupported language: {language}")

        segment_raises = self.segment_raises

        class Segmenter:
            def __init__(self, current_language):
                self.current_language = current_language

            def segment(self, text):
                if segment_raises:
                    raise RuntimeError("segmentation failed")
                return [f"{self.current_language}:{text.strip()}"]

        return Segmenter(language)


class TestTextAnalyzer(unittest.TestCase):
    def test_parse_full_text_query_treats_commas_as_or(self):
        query = parse_full_text_query("alpha, beta")

        self.assertEqual(query.leaf_terms, ["alpha", "beta"])
        self.assertEqual(query.matching_terms("alpha beta"), ["alpha", "beta"])

    def test_parse_full_text_query_gives_and_higher_precedence_than_or(self):
        query = parse_full_text_query("alpha AND beta OR gamma")

        self.assertEqual(query.leaf_terms, ["alpha", "beta", "gamma"])
        self.assertEqual(query.matching_terms("alpha beta"), ["alpha", "beta"])
        self.assertEqual(query.matching_terms("gamma only"), ["gamma"])
        self.assertEqual(query.matching_terms("alpha only"), [])

    def test_parse_full_text_query_keeps_quoted_phrase_as_single_leaf(self):
        query = parse_full_text_query('"two part"')

        self.assertEqual(query.leaf_terms, ["two part"])
        self.assertEqual(query.matching_terms("A two part model."), ["two part"])

    def test_parse_full_text_query_rejects_parentheses(self):
        with self.assertRaisesRegex(ValueError, "Parentheses are not supported"):
            parse_full_text_query("(alpha OR beta)")

    def test_parse_full_text_query_rejects_dangling_operator(self):
        with self.assertRaisesRegex(ValueError, "cannot end with an operator"):
            parse_full_text_query("alpha AND")

    def test_tokenize_sentences_returns_empty_list_for_blank_input(self):
        analyzer = TextAnalyzer()

        self.assertEqual(analyzer.tokenize_sentences("   "), [])

    def test_regex_fallback_handles_abbreviations_and_decimals(self):
        analyzer = TextAnalyzer()
        text = "Dr. Smith wrote this. See p. 55. The value was 3.14. Another sentence!"

        with patch.object(analyzer, "_load_pysbd", return_value=None):
            sentences = analyzer.tokenize_sentences(text)

        self.assertEqual(
            sentences,
            [
                "Dr. Smith wrote this.",
                "See p. 55.",
                "The value was 3.14.",
                "Another sentence!",
            ],
        )

    def test_tokenize_sentences_normalizes_language_before_using_pysbd(self):
        analyzer = TextAnalyzer()
        fake_module = FakePysbdModule()

        with patch.object(analyzer, "_load_pysbd", return_value=fake_module):
            sentences = analyzer.tokenize_sentences("Hallo Welt.", language="de-DE")

        self.assertEqual(sentences, ["de:Hallo Welt."])
        self.assertEqual(fake_module.created_languages, [("de", False)])

    def test_tokenize_sentences_defaults_to_english_when_language_missing(self):
        analyzer = TextAnalyzer()
        fake_module = FakePysbdModule()

        with patch.object(analyzer, "_load_pysbd", return_value=fake_module):
            sentences = analyzer.tokenize_sentences("Hello world.", language=None)

        self.assertEqual(sentences, ["en:Hello world."])
        self.assertEqual(fake_module.created_languages, [("en", False)])

    def test_tokenize_sentences_falls_back_to_english_for_unsupported_language(self):
        analyzer = TextAnalyzer()
        fake_module = FakePysbdModule(failing_languages={"zz"})

        with patch.object(analyzer, "_load_pysbd", return_value=fake_module):
            sentences = analyzer.tokenize_sentences("Hello world.", language="zz-ZZ")

        self.assertEqual(sentences, ["en:Hello world."])
        self.assertEqual(fake_module.created_languages, [("zz", False), ("en", False)])

    def test_tokenize_sentences_uses_regex_fallback_when_pysbd_segmentation_fails(self):
        analyzer = TextAnalyzer()
        fake_module = FakePysbdModule(segment_raises=True)
        text = "Dr. Smith wrote this. Another sentence follows."

        with patch.object(analyzer, "_load_pysbd", return_value=fake_module):
            sentences = analyzer.tokenize_sentences(text, language="en-US")

        self.assertEqual(
            sentences,
            [
                "Dr. Smith wrote this.",
                "Another sentence follows.",
            ],
        )

    def test_build_page_contexts_merges_overlapping_sentence_windows(self):
        analyzer = TextAnalyzer(context_sentence_window=1)

        with patch.object(
            analyzer,
            "tokenize_sentences",
            return_value=[
                "Alpha is in the first sentence.",
                "Beta appears in the second sentence.",
                "The final sentence closes the paragraph.",
            ],
        ), patch.object(analyzer, "_page_looks_noisy", return_value=False):
            contexts = analyzer.build_page_contexts(
                "Alpha is in the first sentence. Beta appears in the second sentence.",
                ["Alpha", "Beta"],
                language="en",
            )

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["Alpha", "Beta"])
        self.assertIn("Alpha is in the first sentence.", contexts[0]["context_text_unhighlighted"])
        self.assertIn("Beta appears in the second sentence.", contexts[0]["context_text_unhighlighted"])

    def test_build_page_contexts_falls_back_to_paragraphs_for_noisy_page(self):
        analyzer = TextAnalyzer()
        text = "Noisy page paragraph with target term.\n\nSecond paragraph without a hit."

        with patch.object(analyzer, "tokenize_sentences", return_value=["noisy", "page"]), patch.object(
            analyzer,
            "_page_looks_noisy",
            return_value=True,
        ):
            contexts = analyzer.build_page_contexts(text, ["target"], language="en")

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["target"])
        self.assertEqual(
            contexts[0]["context_text_unhighlighted"],
            "Noisy page paragraph with target term.",
        )

    def test_build_page_contexts_falls_back_to_character_snippets_when_paragraphs_fail(self):
        analyzer = TextAnalyzer()
        text = "Before the target match comes a lot of fragmented text after it."

        with patch.object(analyzer, "tokenize_sentences", return_value=["frag", "ments"]), patch.object(
            analyzer,
            "_page_looks_noisy",
            return_value=True,
        ), patch.object(analyzer, "_split_paragraphs", return_value=[]):
            contexts = analyzer.build_page_contexts(text, ["target"], language="en", char_window=10)

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["target"])
        self.assertIn("***", analyzer.highlight_multiple_terms(contexts[0]["context_text_unhighlighted"], ["target"]))
        self.assertIn("target", contexts[0]["context_text_unhighlighted"])

    def test_build_page_contexts_supports_unquoted_phrase_queries(self):
        analyzer = TextAnalyzer()
        text = "The two part model was retained. A later sentence does not matter."

        contexts = analyzer.build_page_contexts(text, parse_full_text_query("two part"), language="en")

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["two part"])

    def test_build_page_contexts_supports_wildcard_queries(self):
        analyzer = TextAnalyzer()
        text = "Adolescent development differs from adolescent outcomes."

        contexts = analyzer.build_page_contexts(text, parse_full_text_query("adolescen*"), language="en")

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["adolescen*"])

    def test_build_page_contexts_requires_same_page_for_and_queries(self):
        analyzer = TextAnalyzer()
        query = parse_full_text_query("alpha AND beta")

        self.assertEqual(analyzer.build_page_contexts("alpha only", query, language="en"), [])
        contexts = analyzer.build_page_contexts("alpha and beta both appear here", query, language="en")
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["terms_found"], ["alpha", "beta"])

    def test_highlight_multiple_terms_uses_compiled_query_patterns(self):
        analyzer = TextAnalyzer()
        query = parse_full_text_query("adolescen*")

        highlighted = analyzer.highlight_multiple_terms(
            "Adolescents were sampled.",
            ["adolescen*"],
            query=query,
        )

        self.assertIn("***Adolescents***", highlighted)


if __name__ == "__main__":
    unittest.main()
