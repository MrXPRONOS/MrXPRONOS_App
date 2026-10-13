import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "bsd"))

import football_community_engine as community
import football_channel as channel


NOW = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload=None):
        self._payload = payload or {"ok": True, "result": {"message_id": 77}}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.posts = []

    def post(self, url, data=None, timeout=None):
        self.posts.append({"url": url, "data": data, "timeout": timeout})
        return FakeResponse()


class CommunityEngineTests(unittest.TestCase):
    def test_match_vote_prefers_important_fixture(self):
        events = [
            {
                "id": 1,
                "event_date": (NOW + timedelta(hours=5)).isoformat(),
                "home_team": {"name": "Small FC"},
                "away_team": {"name": "Other FC"},
                "league_name": "League",
                "status": "notstarted",
            },
            {
                "id": 2,
                "event_date": (NOW + timedelta(hours=6)).isoformat(),
                "home_team": {"name": "Arsenal"},
                "away_team": {"name": "Chelsea"},
                "league_name": "Premier League",
                "status": "notstarted",
            },
        ]
        vote = community.build_match_vote(
            events, NOW, lambda e: 100 if e["id"] == 2 else 1
        )
        self.assertIsNotNone(vote)
        self.assertIn("Arsenal", vote["question"])
        self.assertEqual(len(vote["options"]), 3)

    @patch("football_community_engine.collect_snapshot")
    def test_stats_quiz_has_one_verified_answer(self, snapshot):
        snapshot.return_value = {
            "league": "Premier League",
            "league_key": "premier-league",
            "sources": ["ESPN"],
            "confidence": 90,
            "table": [
                {"team": "Arsenal", "rank": 1, "points": 24, "goals_for": 20, "goals_against": 7},
                {"team": "Liverpool", "rank": 2, "points": 22, "goals_for": 18, "goals_against": 8},
                {"team": "Chelsea", "rank": 3, "points": 20, "goals_for": 17, "goals_against": 9},
                {"team": "Manchester City", "rank": 4, "points": 19, "goals_for": 16, "goals_against": 10},
            ],
            "top_scorers": [],
        }
        quiz = community.build_stats_quiz(FakeSession(), date(2026, 10, 13))
        self.assertIsNotNone(quiz)
        self.assertEqual(len(quiz["options"]), 4)
        self.assertEqual(len(quiz["correct_option_ids"]), 1)
        index = quiz["correct_option_ids"][0]
        self.assertGreaterEqual(index, 0)
        self.assertLess(index, 4)
        self.assertIn(quiz["options"][index], quiz["explanation"])

    @patch("football_community_engine.fetch_tsdb_team_metadata")
    def test_tsdb_fallback_quiz_has_verified_answer(self, metadata):
        metadata.return_value = {
            "source": "TheSportsDB",
            "team": "Arsenal",
            "stadium": "Emirates Stadium",
            "formed_year": "1886",
            "country": "England",
        }
        quiz = community.build_tsdb_club_quiz(FakeSession(), date(2026, 10, 14))
        self.assertIsNotNone(quiz)
        self.assertEqual(quiz["source"], "TheSportsDB")
        index = quiz["correct_option_ids"][0]
        self.assertIn(quiz["options"][index], quiz["explanation"])

    def test_news_debate_requires_real_recent_news(self):
        news = [{
            "slug": "abc",
            "title": "Un entraîneur annonce sa décision",
            "summary_short": "Le club a confirmé la décision dans un communiqué.",
            "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "source": "RFI",
            "site_url": "https://mrxpronos.github.io/MrXPRONOS_App/infos.html?news=abc",
            "editorial_score": 4,
        }]
        debate = community.build_news_debate(news, date.today())
        self.assertIsNotNone(debate)
        self.assertEqual(debate["source"], "RFI")
        self.assertIn("commentaire", debate["question"])

    def test_postmatch_reaction_requires_finished_important_match(self):
        events = [{
            "id": 90,
            "event_date": (NOW - timedelta(hours=2)).isoformat(),
            "home_team": {"name": "Real Madrid"},
            "away_team": {"name": "Barcelona"},
            "home_score": 3,
            "away_score": 2,
            "league_name": "La Liga",
            "status": "finished",
        }]
        reaction = community.build_postmatch_reaction(events, NOW, lambda _: 100)
        self.assertIsNotNone(reaction)
        self.assertIn("3-2", reaction["question"])
        self.assertEqual(len(reaction["options"]), 4)

    def test_sender_uses_current_telegram_quiz_fields(self):
        sender = channel.Sender(dry_run=True)
        sender.dry_run = False
        sender.token = "test-token"
        sender.chat = "@test"
        sender.session = FakeSession()
        sender._discussion_checked = True
        sender.linked_chat_id = -1001

        post = channel.Publication(
            "quiz",
            "quiz:test",
            "Quiz",
            poll=("Qui est leader ?", ["Arsenal", "Chelsea", "Liverpool", "City"]),
            poll_type="quiz",
            correct_option_ids=[0],
            poll_explanation="Arsenal est leader.",
            poll_description="Quiz Mr XPRONOS",
            poll_shuffle=True,
            poll_allows_revoting=False,
        )
        message_id = sender.send(post)
        self.assertEqual(message_id, 77)
        data = sender.session.posts[-1]["data"]
        self.assertEqual(data["type"], "quiz")
        self.assertEqual(json.loads(data["correct_option_ids"]), [0])
        self.assertEqual(json.loads(data["options"])[0]["text"], "Arsenal")
        self.assertEqual(data["shuffle_options"], "true")
        self.assertEqual(data["allows_revoting"], "false")


if __name__ == "__main__":
    unittest.main()
