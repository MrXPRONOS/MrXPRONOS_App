"""Existing BSD V2 core stays untouched; external OpenFootball history is adapted only."""
import unittest
from datetime import datetime, timezone

from scripts.football_external_bsd_v2_adapter import (
    HISTORY_START,FIXTURE_START,TEAM_START,LEAGUE_START,
    adapt_daily,normalize_history,h2h_report,evaluate_existing_v2,
)
from bsd.bsd_v2_core import V2History,estimate_goals

AS_OF=datetime(2025,3,1,12,tzinfo=timezone.utc)


def history():
    rows=[]
    matches=[]
    # 7 prior games for each club plus two H2H in the same league.
    for i in range(1,8):
        matches.append((f"2025-02-{i:02d}","Arsenal FC",f"Opponent A{i}",2,1))
        matches.append((f"2025-02-{i+8:02d}","Chelsea FC",f"Opponent B{i}",1,1))
    matches.extend([
        ("2025-01-20","Arsenal FC","Chelsea FC",3,2),
        ("2025-01-25","Chelsea FC","Arsenal FC",1,0),
    ])
    for i,(when,h,a,hg,ag) in enumerate(matches):
        rows.append({
            "source":"openfootball","source_id":f"{i:064x}",
            "status":"finished","match_date":when,"league":"Premier League",
            "home_team":h,"away_team":a,"home_score":hg,"away_score":ag,
        })
    return rows


def daily(**changes):
    x={
      "fixture_key":"fixture-123","discovered_by":"espn",
      "sources":{"espn":{"id":"espn123"}},
      "league_labels":["English Premier League"],"league_verified":True,
      "home_team":"Arsenal","away_team":"Chelsea",
      "kickoff_utc":"2025-03-02T18:00:00+00:00",
      "ambiguous_match":False,"scores_conflict":False,"league_conflict":False,
      "status":"prematch",
    }
    x.update(changes)
    return x


class ExistingBSDV2AdapterTests(unittest.TestCase):
    def test_history_becomes_native_compatible_without_touching_core(self):
        archived,summary=normalize_history(history())
        self.assertEqual(len(archived),16)
        self.assertTrue(all(e["status"]=="finished" for e in archived))
        index=V2History(archived)
        fixtures,report=adapt_daily([daily()],archived,as_of=AS_OF)
        self.assertEqual(report["ready_for_unchanged_core"],1)
        self.assertEqual(fixtures[0]["_original_fixture_refs"]["espn"]["id"],"espn123")
        self.assertEqual(fixtures[0]["_external_source"],"espn")
        self.assertGreater(fixtures[0]["id"],FIXTURE_START)
        self.assertGreater(fixtures[0]["home_team_id"],TEAM_START)
        self.assertGreater(fixtures[0]["league_id"],LEAGUE_START)
        self.assertLess(fixtures[0]["league_id"],2**53)
        expected,reason=estimate_goals(fixtures[0],index)
        self.assertEqual(reason,"ok")
        self.assertIsNotNone(expected)
        self.assertGreaterEqual(expected["home_recent_matches"],4)
        self.assertGreaterEqual(expected["away_recent_matches"],4)
        h2h=h2h_report(fixtures[0],archived)
        self.assertEqual(h2h["total_previous_meetings"],2)

    def test_existing_predict_v2_invoked_no_new_market_logic(self):
        archived,_=normalize_history(history())
        fixtures,_=adapt_daily([daily()],archived,as_of=AS_OF)
        outcomes,summary=evaluate_existing_v2(fixtures,archived,as_of=AS_OF)
        self.assertEqual(len(outcomes),1)
        self.assertTrue(summary["core_predict_v2_function_used"])
        self.assertFalse(summary["calculation_module_modified"])
        self.assertFalse(summary["production_published"])
        self.assertEqual(summary["h2h_nonzero_fixtures"],1)
        self.assertIn(outcomes[0]["status"],("model_candidate","model_abstained"))

    def test_duplicate_existing_bsd_fixture_excluded(self):
        archived,_=normalize_history(history())
        f=daily(sources={"espn":{"id":"a"},"bsd":{"id":"42"}})
        fixtures,report=adapt_daily([f],archived,as_of=AS_OF)
        self.assertEqual(fixtures,[])
        self.assertEqual(report["ignored"]["already_in_bsd_do_not_duplicate"],1)

    def test_future_or_same_day_history_never_influences(self):
        base=history()
        plus=base+[{
            "source":"openfootball","source_id":"a"*64,
            "status":"finished","match_date":"2025-03-02","league":"Premier League",
            "home_team":"Arsenal","away_team":"Chelsea","home_score":30,"away_score":0,
        }]
        all_hist,_=normalize_history(plus)
        old_hist,_=normalize_history(base)
        fixture,_=adapt_daily([daily()],all_hist,as_of=AS_OF)
        self.assertEqual(len(fixture),1)
        past=V2History(old_hist)
        future=V2History(all_hist)
        self.assertEqual(estimate_goals(fixture[0],past),estimate_goals(fixture[0],future))
        self.assertEqual(h2h_report(fixture[0],old_hist),h2h_report(fixture[0],all_hist))

    def test_h2h_from_multiple_past_seasons_stays_available(self):
        rows=history()
        rows.extend([
            {"source":"openfootball","source_id":"e"*64,"status":"finished",
             "match_date":"2023-05-07","league":"Premier League",
             "home_team":"Arsenal FC","away_team":"Chelsea FC","home_score":3,"away_score":1},
            {"source":"openfootball","source_id":"f"*64,"status":"finished",
             "match_date":"2024-03-06","league":"Premier League",
             "home_team":"Chelsea FC","away_team":"Arsenal FC","home_score":2,"away_score":2},
        ])
        archived,_=normalize_history(rows)
        fixtures,_=adapt_daily([daily()],archived,as_of=AS_OF)
        report=h2h_report(fixtures[0],archived)
        self.assertEqual(report["total_previous_meetings"],4)
        self.assertEqual(report["draws"],1)
        self.assertTrue(report["available_for_diagnostics_only"])

    def test_conflict_quarantines_same_game(self):
        values=history()
        extra=dict(values[0],source_id="c"*64,home_score=5)
        archived,quality=normalize_history(values+[extra])
        self.assertEqual(quality["quarantined_reasons"]["conflicting_duplicate_quarantined"],1)
        self.assertEqual(len(archived),15)

    def test_wrong_league_and_missing_alias_or_ambiguous_guard(self):
        archived,_=normalize_history(history())
        for replacement in (
            {"league_labels":[]},{"league_labels":["Copa del Rey"]},
            {"league_labels":["Premier League","Serie A"]},
            {"ambiguous_match":True},{"status":"not_prematch"},
            {"home_team":"Arsenal Women"},
        ):
            fixtures,report=adapt_daily([daily(**replacement)],archived,as_of=AS_OF)
            self.assertEqual(fixtures,[],replacement)

    def test_identifiers_stable_across_provider_discovery_order(self):
        archived,_=normalize_history(history())
        x,_=adapt_daily([daily(sources={"espn":{"id":"1"}})],archived,as_of=AS_OF)
        y,_=adapt_daily([daily(sources={"sportscore":{"id":"2"}})],archived,as_of=AS_OF)
        self.assertEqual(x[0]["id"],y[0]["id"])
        self.assertNotEqual(x[0]["_original_fixture_refs"],y[0]["_original_fixture_refs"])

if __name__=="__main__":
    unittest.main()
