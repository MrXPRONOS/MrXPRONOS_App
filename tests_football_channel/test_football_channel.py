"""Tests hors réseau du média football Mr XPRONOS."""
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).resolve().parents[1] / "scripts" / "football_channel.py"
spec = importlib.util.spec_from_file_location("football_channel", TARGET)
import sys
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
m = module

NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)


def event(ident, start=NOW, status="notstarted", hs=None, a_s=None):
    return {
        "id": ident, "event_date": start.isoformat(), "status": status,
        "home_team": {"id": 1, "name": "Arsenal"},
        "away_team": {"id": 2, "name": "Chelsea"},
        "league_name": "Premier League",
        "home_score": hs, "away_score": a_s,
    }


class FootballChannelTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.history = m.History(Path(self.directory.name) / "history.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_rss_sans_image_ni_url_invalide(self):
        xml = b"""<rss><channel>
        <item><title>Le grand match</title><link>https://example.com/a</link>
        <description>Une nouvelle &amp; des reactions.</description>
        <pubDate>Sat, 10 Oct 2026 14:00:00 GMT</pubDate></item>
        <item><title>Danger</title><link>javascript:alert(1)</link></item>
        </channel></rss>"""
        articles = m.parse_rss(xml)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["summary"], "Une nouvelle & des reactions.")
        post = m.flash(articles, self.history, NOW)
        self.assertIsNotNone(post)
        self.assertIn("Source : Foot Mercato", post.text)
        self.assertIn("Lire l’article complet", post.text)
        self.history.mark(post.key, post.category, NOW)
        self.assertIsNone(m.flash(articles, self.history, NOW))

    def test_programme_et_horaires_togo(self):
        post = m.programme([event(1, NOW + timedelta(hours=4))], NOW.date())
        self.assertIsNotNone(post)
        self.assertIn("19h00", post.text)
        self.assertIn("Arsenal", post.text)

    def test_resultat_uniquement_apres_confirmation(self):
        sample = [
            event(1, NOW - timedelta(hours=3), "notstarted", 2, 1),
            event(2, NOW - timedelta(hours=3), "finished", 2, 1),
        ]
        post = m.resultat(sample, self.history, NOW)
        self.assertEqual(post.key, "resultat:2")
        self.assertIn("2 – 1", post.text)
        self.history.mark(post.key, post.category, NOW)
        self.assertIsNone(m.resultat(sample, self.history, NOW))

    def test_avant_match_sans_inventer_forme(self):
        post = m.avant_match([event(4, NOW + timedelta(hours=2))],
                             self.history, NOW, [])
        self.assertIn("forme récente non disponible", post.text)
        self.assertEqual(post.key, "avant_match:4")

    def test_statistique_issue_de_scores_termines(self):
        old = NOW - timedelta(days=1, hours=4)
        post = m.statistique([event(1, old, "finished", 4, 3),
                              event(2, old, "notstarted", 9, 8)], old.date())
        self.assertIn("7 buts", post.text)
        self.assertNotIn("17 buts", post.text)

    def test_sondage_fournit_options(self):
        post = m.sondage([event(12, NOW + timedelta(hours=3))],
                         self.history, NOW)
        self.assertEqual(post.category, "sondage")
        self.assertEqual(len(post.poll[1]), 3)
        self.assertIn("Match nul", post.poll[1])

    def test_historique_persistant(self):
        self.history.mark("flash:unique", "flash", NOW)
        self.history.save(NOW)
        second = m.History(self.history.path)
        self.assertTrue(second.seen("flash:unique"))
        self.assertEqual(second.count("flash", NOW.date()), 1)

    def test_ne_jamais_publier_sans_canal_specifique(self):
        with patch.dict("os.environ", {"FOOTBALL_NEWS_CHAT_ID": "",
                                       "FOOTBALL_NEWS_BOT_TOKEN": "fake"}, clear=True):
            with self.assertRaises(RuntimeError):
                m.Sender()
            m.Sender(dry_run=True)


if __name__ == "__main__":
    unittest.main()
