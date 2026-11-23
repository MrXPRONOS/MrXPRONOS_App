"""Offline checks: consistent Telegram typography across every Actu Foot pipeline."""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "scripts", ROOT / "bsd"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from scripts.actufoot_telegram_format import (
    editorial_markup, editorial_bottom_markup, match_header,
    news_markup, normalize_paragraphs, quote_excerpt, source_footer,
)
from scripts.telegram_rich import legacy_caption


class EditorialTelegramFormatTests(unittest.TestCase):
    def test_news_title_quote_and_italic_source_have_blank_lines(self):
        rendered = news_markup("Titre", "Deux phrases.\n\nAutre paragraphe.",
                               "Mercato", "Foot Mercato")
        self.assertEqual(rendered,
                         "<b>Titre</b>\n\n"
                         "<blockquote>Deux phrases.\n\nAutre paragraphe.</blockquote>\n\n"
                         "<b>🏷 Mercato</b>\n<i>📰 Source : Foot Mercato</i>")

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
        self.assertIn("</blockquote>\n\n<b>🏷 Actu</b>\n<i>", legacy)

    def test_new_editorial_layout_starts_with_verified_match_not_own_title(self):
        result = editorial_bottom_markup(
            "📊 <b>SCORE LIVE 90'</b>\n\n<b>River Plate 3–1 Lanús</b>",
            category="🔥 NOUVEAU SCORE CONFIRMÉ", source="ESPN",
            card={"home": "River Plate", "away": "Lanús",
                  "score": "3-1", "minute": 90},
        )
        self.assertTrue(result.startswith(
            "<b>⚽ River Plate 3–1 Lanús · 90'</b>\n\n"))
        self.assertIn("<blockquote>", result)
        self.assertIn("</blockquote>\n\n<b>🏷 🔥 NOUVEAU SCORE CONFIRMÉ</b>\n"
                      "<i>📰 Source : ESPN</i>", result)
        self.assertEqual(result.count("Source : ESPN"), 1)
        self.assertNotIn("SCORE LIVE", result)

    def test_goal_hook_is_first_and_scorer_follows_verified_match(self):
        result = editorial_bottom_markup(
            "🌟 <b>BUUUT - SALAH 74'</b>\n\n<b>Liverpool 2–1 Chelsea</b>",
            category="⚽ BUUUT !", source="ESPN",
            card={"home": "Liverpool", "away": "Chelsea",
                  "score": "2-1", "minute": 74},
        )
        self.assertTrue(result.startswith("<b>⚽ BUUUT ! Le score est désormais de 2–1.</b>"))
        self.assertIn("<blockquote><b>⚽ Liverpool 2–1 Chelsea · 74'</b>", result)
        self.assertIn("👤 <b>SALAH 74'</b>", result)
        self.assertIn("<b>🏷 ⚽ BUT CONFIRMÉ</b>\n<i>📰 Source : ESPN</i>", result)

    def test_goal_confirms_league_and_scorer_and_is_idempotent(self):
        card = {"home": "River Plate", "away": "Lanús", "score": "3-1",
                "minute": 90, "league": "Liga Profesional Argentina",
                "goal": {"player": "Joueur confirmé"}}
        first = editorial_bottom_markup(
            "<b>BUUUT !</b>", category="⚽ BUUUT !",
            source="ESPN", card=card)
        self.assertTrue(first.startswith(
            "<b>⚽ BUUUT ! Le score est désormais de 3–1.</b>\n\n"))
        self.assertIn("<b>⚽ River Plate 3–1 Lanús · 90'</b>", first)
        self.assertIn("🏆 Liga Profesional Argentina", first)
        self.assertIn("👤 <b>Joueur confirmé</b>", first)
        self.assertEqual(first.count("<blockquote>"), 1)
        self.assertEqual(first.count("Source : ESPN"), 1)
        self.assertEqual(editorial_bottom_markup(
            first, category="⚽ BUUUT !", source="ESPN", card=card), first)

    def test_goal_missing_scorer_or_score_does_not_invent_it(self):
        result = editorial_bottom_markup(
            "<b>⚽ BUUUT !</b>", category="⚽ BUUUT !", source="ESPN",
            card={"home": "River Plate", "away": "Lanús"})
        self.assertTrue(result.startswith("<b>⚽ BUUUT !</b>"))
        self.assertNotIn("désormais de", result)
        self.assertNotIn("👤", result)
        self.assertIn("River Plate — Lanús", result)

    def test_score_correction_remains_score_first_and_never_buuut(self):
        result = editorial_bottom_markup(
            "<b>SCORE LIVE</b>", category="🔥 NOUVEAU SCORE CONFIRMÉ",
            source="ESPN", card={"home": "River Plate", "away": "Lanús",
                                "minute": 90, "score": "3-1"})
        self.assertTrue(result.startswith("<b>⚽ River Plate 3–1 Lanús · 90'</b>"))
        self.assertNotIn("BUUUT", result)

    def test_bottom_editorial_label_is_idempotent(self):
        first = editorial_bottom_markup(
            "<b>▶️ COUP D’ENVOI</b>\n\n"
            "<blockquote>Match lancé.</blockquote>",
            category="▶️ C’EST PARTI !", source="ESPN",
            card={"home": "Togo", "away": "Bénin", "score": "0-0"})
        self.assertEqual(editorial_bottom_markup(
            first, category="▶️ C’EST PARTI !", source="ESPN"), first)
        self.assertEqual(first.count("<blockquote>"), 1)
        self.assertEqual(first.count("<i>📰 Source : ESPN</i>"), 1)

    def test_source_headline_remains_first_and_category_is_last(self):
        item = editorial_bottom_markup(
            "<b>🚨 Une annonce officielle</b>\n\n"
            "Le média confirme une opération de transfert.",
            category="📰 FLASH FOOT", source="Foot Mercato",
            genuine_news_headline=True)
        self.assertTrue(item.startswith("<b>🚨 Une annonce officielle</b>\n\n"))
        self.assertIn("<blockquote>Le média confirme", item)
        self.assertTrue(item.endswith(
            "<b>🏷 📰 FLASH FOOT</b>\n<i>📰 Source : Foot Mercato</i>"))

    def test_match_header_without_score_never_fabricates_a_result(self):
        actual = match_header({"home": "River Plate", "away": "Lanús",
                               "time": "21h00"})
        self.assertIn("River Plate — Lanús", actual)
        self.assertNotIn("3–1", actual)

    def test_source_escapes_provider_and_does_not_create_link(self):
        source = source_footer('Média <important> & partenaire')
        self.assertIn("&lt;important&gt;", source)
        self.assertIn("&amp;", source)
        self.assertNotIn("http", source)


if __name__ == "__main__":
    unittest.main()
