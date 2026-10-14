"""Offline multi-API historical ingester: provider formats, rights and BSD V2 reuse."""
import unittest
from datetime import datetime, timedelta, timezone

from scripts.football_multi_api_history_inputs import ingest, flat_records
from scripts.football_external_bsd_v2_adapter import (
    normalize_history, adapt_daily, h2h_report, evaluate_existing_v2,
)

AS_OF=datetime(2025,3,1,12,tzinfo=timezone.utc)


def license_for(source):
    return {source:{"approved":True, "historical_model_use":True,
                    "commercial_product":True,"legal_basis":"synthetic-fixture-test-only-not-a-real-license",
                    "attribution_compliant":True}}


def snapshot(source, rows):
    return {"provider":source,"observed_at":"2025-03-01T08:00:00Z","rows":rows}


def flat(source, i, home="Arsenal", away="Chelsea", date="2025-02-01T14:00:00Z",
         goals=(2,0), status="finished"):
    return {"id":i,"provider_event_id":f"{source}{i}","home_team":home,
            "away_team":away, "event_date":date,"league_name":"Premier League",
            "home_score":goals[0],"away_score":goals[1],"status":status}


class ProviderHistoricalInputsTests(unittest.TestCase):
    def test_zero_scores_are_not_missing(self):
        f=flat("sportscore",1,goals=(0,1))
        raw=flat_records("sportscore",[f])
        self.assertEqual(raw[0]["home_score"],0)
        rows,report=ingest([snapshot("sportscore",[f])],license_for("sportscore"),as_of=AS_OF)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["home_score"],0)

    def test_rights_are_a_hard_gate_instead_of_implicit_free_access(self):
        data=[snapshot("espn",[flat("espn",1)])]
        for manifest in ({}, {"espn":{"approved":True}}, {"espn":{"approved":True,"historical_model_use":True,
                          "commercial_product":True,"legal_basis":"", "attribution_compliant":True}}):
            rows,report=ingest(data,manifest,as_of=AS_OF)
            self.assertEqual(rows,[])
            self.assertEqual(report["rejections"]["rights_not_confirmed"],1)

    def test_future_and_unfinished_outcomes_rejected(self):
        items=[snapshot("sportscore",[flat("sportscore",1,status="NS"),
            flat("sportscore",2,date="2025-03-01T10:00:00Z",goals=(1,0)),
            flat("sportscore",3,date="2025-03-02T14:00:00Z",goals=(2,0))])]
        rows,health=ingest(items,license_for("sportscore"),as_of=AS_OF)
        self.assertEqual(rows,[])
        self.assertEqual(health["rejections"]["not_confirmed_final"],1)
        self.assertEqual(health["rejections"]["not_settled_as_of"],2)

    def test_snapshot_observed_after_prediction_cannot_backfill_history(self):
        bad=snapshot("espn",[flat("espn",1)])
        bad["observed_at"]="2025-03-02T14:00:00Z"
        rows,stats=ingest([bad],license_for("espn"),as_of=AS_OF)
        self.assertEqual(rows,[])
        self.assertEqual(stats["rejections"]["snapshot_not_available_at_analysis"],1)

    def test_all_six_formats_supported_when_explicitly_authorized(self):
        examples={
            "espn":{"events":[{"id":"e1","date":"2025-02-02T13:00:00Z",
                 "league":{"name":"Premier League"},
                 "status":{"type":{"completed":True}},
                 "competitions":[{"competitors":[
                    {"homeAway":"home","team":{"name":"Arsenal"},"score":"1"},
                    {"homeAway":"away","team":{"name":"Chelsea"},"score":"0"}]}]}]},
            "sportscore":{"fixtures":[{"id":"s1","home":{"name":"Arsenal"},"away":{"name":"Chelsea"},
                 "time":"2025-02-03T13:00:00Z","competition":"Premier League",
                 "home_score":0,"away_score":2,"status":"FT"}]},
            "thesportsdb":{"events":[{"idEvent":"t1","strHomeTeam":"Arsenal",
                 "strAwayTeam":"Chelsea","strLeague":"Premier League",
                 "strTimestamp":"2025-02-04T13:00:00Z",
                 "intHomeScore":"3","intAwayScore":"2","strStatus":"Match Finished"}]},
            "openligadb":[{"matchID":19,"team1":{"teamName":"Arsenal"},
                 "team2":{"teamName":"Chelsea"},"leagueName":"Premier League",
                 "matchDateTimeUTC":"2025-02-05T13:00:00Z","matchIsFinished":True,
                 "matchResults":[{"resultTypeID":2,"pointsTeam1":2,"pointsTeam2":0}]}],
            "api_football":{"response":[{"fixture":{"id":88,"date":"2025-02-06T13:00:00Z",
                 "status":{"short":"FT"}},"teams":{"home":{"name":"Arsenal"},
                 "away":{"name":"Chelsea"}},"league":{"name":"Premier League"},
                 "goals":{"home":2,"away":2}}]},
            "bsd":[{"id":99,"home_team":{"name":"Arsenal"},"away_team":{"name":"Chelsea"},
                 "league_name":"Premier League","event_date":"2025-02-07T13:00:00Z",
                 "home_score":1,"away_score":0,"status":"finished"}],
        }
        rights={p:license_for(p)[p] for p in examples}
        snapshots=[{"provider":p,"observed_at":"2025-03-01T08:00:00Z","data":raw}
                   for p,raw in examples.items()]
        rows,health=ingest(snapshots,rights,as_of=AS_OF)
        self.assertEqual(len(rows),6,health)
        self.assertEqual(set(health["permitted_provider_rows"]),set(examples))
        self.assertEqual(sum(r["home_score"]==0 for r in rows),1)
        archive,quality=normalize_history(rows,accepted_sources=frozenset(examples))
        self.assertEqual(len(archive),6,quality)
        self.assertTrue(all(x["home_team_id"]>0 and x["league_id"]>0 for x in archive))

    def test_deduplicate_equal_scores_and_quarantine_conflicts(self):
        two=[
            {"source":"espn","match_date":"2025-02-01","home_team":"Arsenal","away_team":"Chelsea",
             "league":"Premier League","home_score":2,"away_score":1,"status":"finished",
             "kickoff_utc":"2025-02-01T14:00:00Z","source_id":"E1"},
            {"source":"sportscore","match_date":"2025-02-01","home_team":"Arsenal FC","away_team":"Chelsea",
             "league":"English Premier League","home_score":2,"away_score":1,"status":"finished",
             "kickoff_utc":"2025-02-01T14:15:00Z","source_id":"S1"},
        ]
        archive,stats=normalize_history(two,accepted_sources=frozenset({"espn","sportscore"}))
        self.assertEqual(len(archive),1)
        self.assertEqual(stats["multi_provider_corroborated"],1)
        self.assertEqual(archive[0]["_original_provider_ids"]["espn"],"E1")
        conflict=dict(two[1],away_score=0)
        archive,report=normalize_history([two[0],conflict],accepted_sources=frozenset({"espn","sportscore"}))
        self.assertEqual(archive,[])
        self.assertEqual(report["quarantined_reasons"]["conflicting_duplicate_quarantined"],1)

    def test_same_teams_conflicting_kickoff_abstains(self):
        one={"source":"espn","match_date":"2025-02-01","home_team":"Arsenal","away_team":"Chelsea",
             "league":"Premier League","home_score":1,"away_score":1,"status":"finished",
             "kickoff_utc":"2025-02-01T12:00:00Z","source_id":"e"}
        two=dict(one,source="sportscore",source_id="s",kickoff_utc="2025-02-01T20:00:00Z")
        archive,report=normalize_history([one,two],accepted_sources=frozenset({"espn","sportscore"}))
        self.assertEqual(len(archive),0)
        self.assertEqual(report["quarantined_reasons"]["conflicting_kickoff_quarantined"],1)

    def test_multiple_independent_provider_rows_feed_same_original_bsd_engine(self):
        history=[]
        for n in range(1,10):
            date=f"2025-02-{n:02d}T12:00:00Z"
            history.extend([flat("espn",n,home="Arsenal",away=f"Rival A{n}",date=date,goals=(2,1)),
                            flat("sportscore",n,home="Chelsea",away=f"Rival B{n}",date=date,goals=(1,0))])
        history.extend([flat("api_football",50,home="Arsenal",away="Chelsea",
                            date="2025-02-21T12:00:00Z",goals=(3,1)),
                        flat("thesportsdb",51,home="Chelsea",away="Arsenal",
                            date="2025-02-25T12:00:00Z",goals=(0,0))])
        snapshots=[snapshot("espn",[r for r in history if str(r["provider_event_id"]).startswith("espn")]),
                   snapshot("sportscore",[r for r in history if str(r["provider_event_id"]).startswith("sportscore")]),
                   snapshot("api_football",[r for r in history if str(r["provider_event_id"]).startswith("api_football")]),
                   snapshot("thesportsdb",[r for r in history if str(r["provider_event_id"]).startswith("thesportsdb")])]
        rights={p:license_for(p)[p] for p in ("espn","sportscore","api_football","thesportsdb")}
        history_rows,health=ingest(snapshots,rights,as_of=AS_OF)
        archive,report=normalize_history(history_rows,accepted_sources=frozenset(rights))
        fixture={"fixture_key":"X","home_team":"Arsenal","away_team":"Chelsea",
                 "league_labels":["Premier League"],"league_verified":True,
                 "kickoff_utc":"2025-03-02T19:00:00Z","status":"prematch",
                 "sources":{"sportscore":{"id":"NEW01"}},"discovered_by":"sportscore",
                 "ambiguous_match":False,"league_conflict":False,"scores_conflict":False}
        ready,ready_health=adapt_daily([fixture],archive,as_of=AS_OF)
        self.assertEqual(ready_health["ready_for_unchanged_core"],1)
        self.assertEqual(h2h_report(ready[0],archive,as_of=AS_OF)["total_previous_meetings"],2)
        result,model=evaluate_existing_v2(ready,archive,as_of=AS_OF)
        self.assertTrue(model["core_predict_v2_function_used"])
        self.assertFalse(model["calculation_module_modified"])
        self.assertFalse(model["production_published"])
        self.assertEqual(model["h2h_nonzero_fixtures"],1)


if __name__=="__main__":
    unittest.main()
