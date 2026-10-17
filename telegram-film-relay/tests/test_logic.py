import asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from film_relay.matching import document_key, is_poster, is_video, match_pairs
from film_relay.text import clean_caption, caption_with_link, private_message_link
from film_relay.state import State

NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


def poster(id, text="🎬 Mon Film : une belle histoire 2026", mins=0):
    return NS(id=id, photo=object(), document=None, video=None,
              raw_text=text, date=NOW + timedelta(minutes=mins), grouped_id=None,
              reply_to=None, entities=None)


def movie(id, mins=1, *, seconds=7200, docid=77, name="film.mp4", mime="video/mp4"):
    doc = NS(id=docid, size=650_000_000, mime_type=mime)
    return NS(id=id, photo=None, document=doc, video=doc, raw_text="", date=NOW + timedelta(minutes=mins),
              grouped_id=None, reply_to=None, file=NS(duration=seconds, size=doc.size, name=name))


class MatchTests(unittest.TestCase):
    def test_regular_pair(self):
        p, m = poster(10), movie(11)
        result = match_pairs([m, p])
        self.assertEqual([(x.poster.id, x.movie.id) for x in result], [(10, 11)])

    def test_poster_boundary(self):
        a, b, v = poster(10), poster(11, "🎬 Deuxième Film en français 2026"), movie(12)
        self.assertEqual([(x.poster.id, x.movie.id) for x in match_pairs([a,b,v])], [(11,12)])

    def test_distance_time_and_trailer(self):
        self.assertFalse(is_video(movie(11, seconds=100)))
        self.assertFalse(is_poster(poster(10, "https://t.me/spam")))
        self.assertEqual(match_pairs([poster(10), movie(11, mins=300)]), [])

    def test_unique_media(self):
        self.assertEqual(document_key(movie(11)), "doc:77")

    def test_link_cleanup_and_truncation(self):
        x = clean_caption("🎬 Mon film\nActeurs : A et B\n👉 https://t.me/xyz\nAbonnez-vous à notre canal\n@pub_telegram")
        self.assertIn("Mon film", x)
        self.assertNotIn("t.me", x)
        self.assertNotIn("Abonnez", x)
        self.assertNotIn("@pub_telegram", x)
        self.assertEqual(private_message_link(-1001234567890, 54), "https://t.me/c/1234567890/54")
        self.assertLessEqual(len(caption_with_link("abc " * 600, "https://t.me/c/123/99")), 1024)

    def test_state(self):
        with TemporaryDirectory() as temp:
            state = State(str(Path(temp) / "state.json"))
            self.assertFalse(state.recorded("x:1:2", "doc:77"))
            state.stage("x:1:2", 32)
            state.advance("x", 10)
            state.add("x:1:2", "doc:77", 32, 33)
            loaded = State(str(Path(temp) / "state.json"))
            self.assertEqual(loaded.seen("x"), 10)
            self.assertEqual(loaded.get_stage("x:1:2"), None)
            self.assertTrue(loaded.recorded("else:3:4", "doc:77"))


# Tests for the v2 read-only discovery and private layout.
from film_relay.discovery import evaluate_messages, normalize_username, is_public_broadcast, load_config, candidate_window
from film_relay.text import private_poster_caption, private_video_caption


class DiscoveryTests(unittest.TestCase):
    def test_public_root_urls_only(self):
        self.assertEqual(normalize_username('https://t.me/cinema_test?single'), 'cinema_test')
        self.assertEqual(normalize_username('@filmgroup2026'), 'filmgroup2026')
        self.assertIsNone(normalize_username('https://t.me/+invitation'))
        self.assertIsNone(normalize_username('https://t.me/c/123456/99'))
        self.assertIsNone(normalize_username('https://t.me/cinema_test/44'))

    def test_only_public_broadcast_channels(self):
        self.assertTrue(is_public_broadcast(NS(broadcast=True, username='cine_legal')))
        self.assertFalse(is_public_broadcast(NS(broadcast=False, username='cine_legal')))
        self.assertFalse(is_public_broadcast(NS(broadcast=True, username=None)))

    def test_discovery_finds_pattern_without_media_copy(self):
        data = evaluate_messages([
            movie(45), poster(44, '🎬 Un beau film en français'),
            movie(47, mins=3, docid=78), poster(46, '🎬 Un autre film fantastique', mins=2),
        ])
        self.assertEqual(data['matching_pairs'], 2)
        self.assertEqual(data['sample_post_ids'], [44, 46])
        self.assertEqual(data['format'], 'photo_texte_puis_video')
        self.assertEqual(evaluate_messages([poster(44)])['matching_pairs'], 0)
        self.assertFalse(evaluate_messages([poster(44), movie(45)])['format_verified'])

    def test_private_posts_keep_title_no_link(self):
        raw = '🎬 Une histoire fantastique 2026\nUn film très spécial\nhttps://t.me/exemple'
        cleaned = clean_caption(raw)
        self.assertIn('Une histoire', private_poster_caption(cleaned))
        self.assertNotIn('t.me', private_poster_caption(cleaned))
        self.assertEqual(private_video_caption(cleaned), '🎬 Une histoire fantastique 2026')
        self.assertLessEqual(len(private_poster_caption('a' * 2400)), 1024)

    def test_checkpoint_resumes_after_poster(self):
        with TemporaryDirectory() as temp:
            state = State(str(Path(temp) / 'test.json'))
            state.stage_poster('c:1:2', 30)
            self.assertEqual(State(str(Path(temp) / 'test.json')).get_staged_posts('c:1:2'), {'poster': 30})
            state.stage('c:1:2', 31)
            self.assertEqual(state.get_staged_posts('c:1:2'), {'poster': 30, 'video': 31})
            state.add('c:1:2', 'doc:88', 31, 32)
            self.assertEqual(state.get_staged_posts('c:1:2'), {})

    def test_original_checkpoint_compatible(self):
        with TemporaryDirectory() as temp:
            state = State(str(Path(temp) / 'test.json'))
            state.data['staged']['old'] = 29
            state.save()
            self.assertEqual(State(str(Path(temp) / 'test.json')).get_staged_posts('old'), {'video': 29})

    def test_discovery_rotates_candidate_window(self):
        self.assertEqual(candidate_window([1,2,3,4,5], 2, 0), [1,2])
        self.assertEqual(candidate_window([1,2,3,4,5], 2, 2), [3,4])
        self.assertEqual(candidate_window([1,2,3,4,5], 2, 4), [5,1])

    def test_discovery_notifications_go_to_saved_messages_only(self):
        from film_relay.discovery import notification_text, notify_saved_messages
        channel = {"username": "cinema_test", "title": "Cinema & Films",
                   "matching_pairs": 3}
        rendered = notification_text(channel)
        self.assertIn("https://t.me/cinema_test", rendered)
        self.assertIn("Droits de redistribution non vérifiés", rendered)
        self.assertIn("\\n", rendered)
        client = NS(send_message=AsyncMock())
        sent = set()
        result = asyncio.run(notify_saved_messages(client, [channel, channel], sent))
        self.assertEqual(result, (["cinema_test"], 0))
        self.assertEqual(client.send_message.await_count, 1)
        args, kwargs = client.send_message.await_args
        self.assertEqual(args[0], "me")
        self.assertEqual(kwargs["parse_mode"], "html")
        self.assertEqual(asyncio.run(notify_saved_messages(client, [channel], sent)),
                         ([], 0))

    def test_discovery_never_auto_imports_sources(self):
        from film_relay.runner import config_from
        import json
        import os
        from unittest.mock import patch
        with TemporaryDirectory() as temp:
            root = Path(temp)
            manual = root / "channels.json"
            auto = root / "auto_sources.json"
            manual.write_text(json.dumps({
                "sources": [{"channel": "@manual_source", "redistribution_authorized": True}],
                "private_channel": "-100123", "public_channel": "@cinex_public"
            }))
            auto.write_text(json.dumps({"sources": [{"channel": "@auto_discovered"}]}))
            with patch.dict(os.environ, {"AUTO_SOURCES_PATH": str(auto)}, clear=False):
                result = config_from(str(manual))
            self.assertEqual([v["channel"] for v in result["sources"]], ["@manual_source"])

    def test_schedules(self):
        root = Path(__file__).resolve().parent.parent
        relay = (root.parent / '.github/workflows/telegram-film-relay.yml').read_text()
        discovery = (root.parent / '.github/workflows/telegram-film-discovery.yml').read_text()
        self.assertIn("17 */2 * * *", relay)
        self.assertIn("23 3 * * *", discovery)
        self.assertNotIn('7,37 * * * *', relay)

    def test_public_discovery_config_is_bounded(self):
        root = Path(__file__).resolve().parent.parent
        cfg = load_config(str(root / 'config/discovery.json'))
        self.assertLessEqual(cfg['max_channels_per_run'], 30)
        self.assertGreaterEqual(cfg['request_pause_seconds'], 2)


if __name__ == "__main__":
    unittest.main()
