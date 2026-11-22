"""Offline checks: consistent Telegram typography across every Actu Foot pipeline."""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "scripts", ROOT / "bsd"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from scripts.actufoot_telegram_format import (
    editorial_markup, news_markup, normalize_paragraphs,
    quote_excerpt, source_footer,
)
from scripts.telegram_rich import legacy_caption


class EditorialTelegramFormatTests(unittest.TestCase):
    def test_news_title_quote_and_italic_source_have_blank_lines(self):
        rendered = news_markup("Titre", "Deux phrases.\n\nAutre paragraphe.",
                               "Mercato", "Foot Mercato")
        self.assertEqual(rendered,
                         "<b>Titre</b>\n\n"
                         "<blockquote>Deux phrases.\n\nAutre paragraphe.</blockquote>\n\n"
                         "<i>🏷 Catégorie : Mercato\n📰 Source : Foot Mercato</i>")

    def test_quote_escapes_html(self):
        result = quote_excerpt("L'entraîneur <confirme> 2 & 2")
        self.assertIn("&lt;confirme&gt;", result)
        self.assertIn("2 &amp; 2", result)
        self.assertNotIn("<confirme>", result)

    def test_main_channel_plain_template_gets_real_quote(self):
        result = editorial_markup("<b>📅 MATCHS DU JOUR</b>\n"
                                  "<i>Match du jour : Arsenal - Chelsea</i>\n\n"
                                  "<b>💬 Quel match ?</b>", source="ESPN")
        self.assertIn("</b>\n\n<blockquote>", result)
        self.assertIn("</blockquote>\n\n<i>📰 Source : ESPN</i>", result)

    def test_existing_quote_is_preserved_without_nesting(self):
        value = editorial_markup("🌟 <b>BUUUT</b>\n\n"
                                 "<blockquote>⚽ Arsenal 1–0 Chelsea</blockquote>",
                                 source="ESPN")
        self.assertEqual(value.count("<blockquote>"), 1)
        self.assertTrue(value.startswith("🌟 <b>BUUUT</b>\n\n"))
        self.assertIn("</blockquote>\n\n<i>📰 Source : ESPN</i>", value)

    def test_fallback_title_applies_to_existing_quoted_body(self):
        value = editorial_markup("<blockquote>⚽ 1–0</blockquote>",
                                 source="ESPN", title_fallback="⚽ BUT")
        self.assertTrue(value.startswith("<b>⚽ BUT</b>\n\n<blockquote>"))

    def test_existing_source_is_not_duplicated_even_when_reformatted(self):
        once = editorial_markup("<b>📊 SCORE</b>\n\n"
                                "<blockquote>2–1</blockquote>\n\n"
                                "<i>📰 Source : ESPN</i>", source="ESPN")
        twice = editorial_markup(once, source="ESPN")
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("Source : ESPN"), 1)

    def test_paragraph_tags_become_blank_lines_and_quotes_survive_legacy(self):
        raw = "<p><b>Titre</b></p><p>Paragraphe 1<br/>Paragraphe 2</p>"
        cleaned = normalize_paragraphs(raw)
        self.assertIn("</b>\n\nParagraphe", cleaned)
        self.assertIn("Paragraphe 1\nParagraphe 2", cleaned)
        quote = news_markup("Titre", "Un passage sourcé.", "Actu", "RFI")
        legacy = legacy_caption(quote)
        self.assertIn("<blockquote>Un passage sourcé.</blockquote>", legacy)
        self.assertIn("</blockquote>\n\n<i>", legacy)

    def test_source_escapes_provider_and_does_not_create_link(self):
        source = source_footer('Média <important> & partenaire')
        self.assertIn("&lt;important&gt;", source)
        self.assertIn("&amp;", source)
        self.assertNotIn("http", source)


if __name__ == "__main__":
    unittest.main()
