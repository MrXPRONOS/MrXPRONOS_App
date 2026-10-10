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

    def test_photo_payload_ne_contient_pas_text(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {"message_id": 201}}
        sample = m.programme([event(17, NOW + timedelta(hours=3))], NOW.date(),
                             as_of=NOW)
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-10010000222",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
        }):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            result = sender.send(sample)
        self.assertEqual(result, 201)
        kwargs = sender.session.post.call_args.kwargs
        self.assertIn("photo", kwargs["files"])
        self.assertIn("caption", kwargs["data"])
        self.assertNotIn("text", kwargs["data"])
        self.assertNotIn("parse_mode", kwargs["data"])
        self.assertLessEqual(len(kwargs["data"]["caption"]), 1024)

    def test_programme_exclut_un_match_deja_commence(self):
        sample = [event(1, NOW - timedelta(hours=1)),
                  event(2, NOW + timedelta(hours=2))]
        post = m.programme(sample, NOW.date(), as_of=NOW)
        self.assertEqual(len(post.card["matches"]), 1)

    def test_live_test_exige_un_canal(self):
        import os
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
        }):
            with self.assertRaises(RuntimeError):
                m.run_live_test(NOW)


    def test_commentaires_exigent_linked_chat_id(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {"id": -1001, "title": "Canal"}}
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "1",
        }):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            with self.assertRaises(RuntimeError):
                sender.verify_discussion()

    def test_commentaires_detectent_le_groupe_lie(self):
        import os
        from unittest.mock import Mock
        fake = Mock()
        fake.status_code = 200
        fake.json.return_value = {"ok": True, "result": {
            "id": -1001, "linked_chat_id": -100999
        }}
        with patch.dict(os.environ, {
            "FOOTBALL_NEWS_CHAT_ID": "-1001",
            "FOOTBALL_NEWS_BOT_TOKEN": "123:fake",
            "FOOTBALL_REQUIRE_COMMENTS": "1",
        }):
            sender = m.Sender()
            sender.session.post = Mock(return_value=fake)
            self.assertEqual(sender.verify_discussion(), -100999)
            self.assertEqual(sender.verify_discussion(), -100999)
            self.assertEqual(sender.session.post.call_count, 1)

    def test_appel_aux_commentaires_dans_les_posts(self):
        post = m.programme([event(31, NOW + timedelta(hours=2))], NOW.date(), as_of=NOW)
        self.assertIn("Donne ton avis dans les commentaires", post.text)
        poll = m.sondage([event(32, NOW + timedelta(hours=3))], self.history, NOW)
        self.assertIn("commente", poll.poll[0].lower())


    def test_rotation_programme_lundi_dimanche(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        self.assertEqual(mod.style_for_day("12/10/2026"), 1)  # lundi
        self.assertEqual(mod.style_for_day("18/10/2026"), 7)  # dimanche

    def test_les_sept_styles_programme_se_generent(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        payload = {"day": "10/10/2026", "matches": [
            {"home": "Club Sportif International de Test", "away": "Olympique Exemple", "time": "17h30"},
            {"home": "Real Madrid", "away": "FC Barcelona", "time": "20h00"},
            {"home": "PSG", "away": "Marseille", "time": "21h00"},
            {"home": "Bayern Munich", "away": "Borussia Dortmund", "time": "15h30"},
            {"home": "Inter Milan", "away": "AC Milan", "time": "19h45"},
        ]}
        for style in range(1, 8):
            image = mod.render_programme(payload, style=style)
            self.assertEqual(image.size, (1080, 1080))
            self.assertEqual(image.mode, "RGB")

    def test_style_programme_invalide_refuse(self):
        import importlib.util
        cards = Path(__file__).resolve().parents[1] / "scripts" / "programme_styles.py"
        spec2 = importlib.util.spec_from_file_location("programme_styles", cards)
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
        with self.assertRaises(ValueError):
            mod.render_programme({"day": "10/10/2026", "matches": [
                {"home": "A", "away": "B", "time": "12h00"}
            ]}, style=8)


if __name__ == "__main__":
    unittest.main()
