"""Tests offline : ActuFoot autonome, aucune requête API ou Telegram."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from scripts import actu_foot_independent as mod

NOW = datetime(2026, 10, 29, 7, 0, tzinfo=timezone.utc)

def fixture(home, away, id, hour=18, league="Premier League"):
    return dict(id=str(id), home_team=home, away_team=away, league_name=league,
                event_date=NOW.replace(hour=hour).isoformat(), status="scheduled",
                home_logo="https://example.org/home.png",
                away_logo="https://example.org/away.png")

class TestActuFootIndependent(unittest.TestCase):
    def test_time_window(self):
        self.assertTrue(mod.within_programme_window(NOW))
        self.assertFalse(mod.within_programme_window(NOW.replace(hour=8)))
    def test_rank_clubs_before_final_without_clubs(self):
        club=fixture("Real Madrid","Getafe",101)
        final=fixture("Oxford United","Portsmouth",102)
        final["round_name"]="Final"
        self.assertGreater(mod.event_priority(club),mod.event_priority(final))
    def test_programme_verifiable_and_priority(self):
        events=[fixture("Oxford United","Portsmouth",101),
                fixture("Real Madrid","Getafe",102),
                fixture("Arsenal","Chelsea",103)]
        events[0]["round_name"]="Final"
        with patch.object(mod.channel,"has_two_team_logos",return_value=True):
            post,tracked=mod.selected_fixtures(events,NOW)
        self.assertIsNotNone(post)
        self.assertTrue(tracked)
        self.assertIn(tracked[0]["home"], {"Arsenal","Real Madrid"})
        self.assertTrue(all(str(t["id"]).isdigit() for t in tracked))
        self.assertEqual(post.category,"programme")
    def test_no_programme_for_missing_games(self):
        post, tracked=mod.selected_fixtures([], NOW)
        self.assertIsNone(post)
        self.assertEqual(tracked,[])
    def test_two_distinct_goals_and_result(self):
        row=dict(id="12345",home="Arsenal",away="Chelsea",league="Premier League",rank=1)
        info=dict(id="12345",state="in",minute=55,home_score=2,away_score=0,status_detail="55'")
        goals=[dict(id="goal1",minute_total=52,home_score=1,away_score=0),
               dict(id="goal2",minute_total=54,home_score=2,away_score=0)]
        with patch.object(mod,"extract_goals",return_value=goals):
            signals=mod.live_signals(row,info,{},NOW)
        self.assertEqual(len([s for s in signals if s["kind"]=="goal"]),2)
        self.assertEqual(len({s["key"] for s in signals}),2)
        info["state"]="post"
        with patch.object(mod,"extract_match_enrichment",return_value={}):
            final=mod.live_signals(row,info,{},NOW)
        self.assertEqual(len([s for s in final if s["kind"]=="resultat_final"]),1)
    def test_unchanged_score_no_post(self):
        row=dict(id="12345",home="Arsenal",away="Chelsea",league="Premier League",rank=1)
        info=dict(state="in",minute=60,home_score=1,away_score=0,status_detail="60'")
        with patch.object(mod,"extract_goals",return_value=[]):
            self.assertEqual(mod.live_signals(row,info,{},NOW),[])
    def test_duplicate_suppression(self):
        ledger=MagicMock()
        ledger.claim.side_effect=[True,False]
        ledger.mark.return_value=True
        sender=MagicMock()
        sender.chat="@test"
        sender.send.return_value=99
        post=MagicMock(category="goal")
        self.assertTrue(mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",post,dry_run=False))
        self.assertFalse(mod.confirmed_message(ledger,sender,"2026-10-29","goal:x",post,dry_run=False))
        sender.send.assert_called_once()
    def test_no_live_api_when_no_plan(self):
        ledger=MagicMock()
        ledger.query.return_value={"results":[]}
        sender=MagicMock()
        sender.chat="@test"
        with patch.object(mod,"fetch_espn_summary") as fetch:
            mod.lifecycle_cycle(NOW,sender,ledger,False)
            fetch.assert_not_called()

if __name__=="__main__":
    unittest.main()
