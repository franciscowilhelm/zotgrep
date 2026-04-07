import unittest
from unittest.mock import patch

from zotgrep.text_analyzer import TextAnalyzer


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
                "ignored",
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


if __name__ == "__main__":
    unittest.main()
