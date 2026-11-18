"""Offline editorial tests: no partial RSS teasers, no hallucination, English via NIM."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import football_rss_editor as editor


FR_ITEM = {
    "title": "FIFA : le tacle glissé de Diallo à Infantino",
    "content": ("Philippe Diallo a répondu aux questions concernant ses relations "
                "avec Gianni Infantino. Les deux dirigeants se sont rencontrés "
                "à Paris et ont discuté de leurs responsabilités, mais (...)"),
    "source_feed": "https://www.footmercato.net/flux-rss",
}
EN_ITEM = {
    "title": "Arsenal announce a new five-year contract",
    "content": "Arsenal have announced that the player has signed a new five-year contract.",
    "source_feed": "https://feeds.bbci.co.uk/sport/football/rss.xml",
}


class RSSFrenchEditorialTests(unittest.TestCase):
    def test_cut_footmercato_source_without_nim_keeps_only_complete_sentence(self):
        item = editor.prepare(FR_ITEM, api_key="")
        self.assertEqual(item["telegram_title_fr"], FR_ITEM["title"])
        self.assertEqual(item["telegram_content_fr"],
                         "Philippe Diallo a répondu aux questions concernant ses relations avec Gianni Infantino.")
        self.assertFalse(item["telegram_content_fr"].endswith("…"))
        self.assertTrue(item["editorial_verified_fr"])

    def test_cut_quote_without_complete_sentence_is_not_published(self):
        article = {**FR_ITEM, "content": "Le joueur a déclaré : «Je suis (…) "}
        with self.assertRaises(editor.EditorialHold):
            editor.prepare(article, api_key="")

    def test_unfinished_headline_is_rejected_without_model(self):
        article = {**FR_ITEM, "title": "Une grosse nouvelle (…) "}
        with self.assertRaises(editor.EditorialHold):
            editor.prepare(article, api_key="")

    def test_english_never_published_untranslated_without_nim(self):
        with self.assertRaisesRegex(editor.EditorialHold, "english_translation_unavailable"):
            editor.prepare(EN_ITEM, api_key="")

    def test_verified_nim_french_translation_preserves_factual_number(self):
        english = {**EN_ITEM, "title": "Arsenal announce a five-year contract in 2026"}
        translated = {
            "title_fr": "Arsenal annonce un contrat de cinq ans en 2026",
            "summary_fr": "Arsenal a annoncé la signature d'un nouveau contrat de cinq ans. Le club confirme ainsi cet accord.",
        }
        # The headline's 2026 must survive, while no new figures are added.
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(translated, ensure_ascii=False)}}]
        }
        session.post.return_value = response
        with patch.object(editor, "_french", return_value=True):
            result = editor.prepare(english, api_key="fake", session=session)
        self.assertIn("2026", result["telegram_title_fr"])
        self.assertEqual(result["telegram_content_fr"], translated["summary_fr"])
        self.assertEqual(session.post.call_args.kwargs["json"]["model"], editor.MODEL)

    def test_nim_cannot_invent_numbers(self):
        with patch.object(editor, "_french", return_value=True), self.assertRaisesRegex(editor.EditorialHold, "new_number"):
            editor._valid_result(
                "Arsenal signe un joueur",
                "Le club prépare un accord.",
                "Arsenal annonce un transfert officiel",
                "Arsenal signe un joueur pour 100 millions d'euros, selon le club."
            )

    def test_nim_ellipsis_fails_closed(self):
        with self.assertRaisesRegex(editor.EditorialHold, "unfinished"):
            editor._valid_result(
                "Un joueur rejoint Arsenal",
                "Arsenal annonce la signature du joueur.",
                "Un joueur rejoint Arsenal",
                "Arsenal annonce la signature du joueur mais les détails…"
            )

    def test_source_facts_never_modified(self):
        result = editor.prepare(FR_ITEM, api_key="")
        for name in ("title", "content", "source_feed"):
            self.assertEqual(result[name], FR_ITEM[name])

    def test_english_failed_http_never_returns_raw_english(self):
        session = Mock()
        session.post.side_effect = editor.requests.Timeout("timeout")
        with self.assertRaises(editor.EditorialHold):
            editor.prepare(EN_ITEM, api_key="fake", session=session)

    def test_unfinished_french_excerpt_does_not_guess_next_sentence(self):
        summary = "La défaite a laissé des traces au sein de la sélection. Une nouvelle étape de (...)"
        cleaned = editor.complete_sentences(summary)
        self.assertEqual(cleaned, "La défaite a laissé des traces au sein de la sélection.")


if __name__ == "__main__":
    unittest.main()
