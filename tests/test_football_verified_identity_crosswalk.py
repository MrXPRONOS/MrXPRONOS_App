import unittest
from datetime import datetime, timezone
from scripts.football_verified_identity_crosswalk import generate, resolve
from scripts.football_external_bsd_v2_adapter import normalize_history,adapt_daily, evaluate_existing_v2

AS_OF=datetime(2025,3,1,10,tzinfo=timezone.utc)

def row(source, tag, date, home, away, result, clock="15:00:00"):
    return {"source":source,"source_id":f"{source}-{tag}",
            "status":"finished","league":"Premier League",
            "match_date":date,"kickoff_utc":f"{date}T{clock}Z",
            "home_team":home,"away_team":away,
            "home_score":result[0],"away_score":result[1]}

def pairs():
    return [
        row("openfootball","a","2025-01-12","Arsenal","Manchester United",(2,1)),
        row("sportscore","a","2025-01-12","Arsenal","Man Utd",(2,1),"15:10:00"),
        row("openfootball","b","2025-01-26","Chelsea","Manchester United",(1,2)),
        row("sportscore","b","2025-01-26","Chelsea","Man Utd",(1,2),"14:50:00"),
    ]

class CrosswalkSafetyTests(unittest.TestCase):
    def test_two_cross_source_matches_confirm_once(self):
        registry,report=generate(pairs())
        self.assertEqual(report["confirmed_aliases"],1)
        self.assertEqual(resolve("Premier League","Man Utd",registry),"manchester united")
        self.assertEqual(resolve("Premier League","Man Utd",{}),"man utd")
        self.assertEqual(resolve("La Liga","Man Utd",registry),"man utd")
        archive,quality=normalize_history(
            pairs(),accepted_sources=frozenset({"openfootball","sportscore"}),
            team_aliases=registry)
        self.assertEqual(len(archive),2)
        self.assertEqual(quality["multi_provider_corroborated"],2)
        self.assertEqual(archive[0]["_original_provider_ids"].keys(),{"openfootball","sportscore"})

    def test_one_match_is_not_evidence(self):
        cross,quality=generate(pairs()[:2])
        self.assertEqual(cross,{})
        self.assertEqual(quality["confirmed_aliases"],0)

    def test_different_scores_kickoff_or_league_refuse_alias(self):
        for changed in (
            {"away_score":0},{"kickoff_utc":"2025-01-26T19:30:00Z"},
            {"league":"La Liga"},{"source":"openfootball"},
        ):
            changed_rows=pairs()
            changed_rows[-1]=dict(changed_rows[-1],**changed)
            cross,_=generate(changed_rows)
            self.assertEqual(cross,{},changed)

    def test_ambiguous_multiple_matching_fixtures_refuses(self):
        data=pairs()
        data.append(dict(data[1],source_id="another-same-provider-fixture"))
        cross,_=generate(data)
        self.assertEqual(cross,{})

    def test_existing_bsd_prediction_uses_exact_same_v2_core_after_alias(self):
        data=pairs()
        for i in range(1,7):
            dt=f"2025-02-{i:02d}"
            data.append(row("openfootball",f"g1-{i}",dt,"Arsenal",f"Rival {i}",(2,1)))
            data.append(row("openfootball",f"g2-{i}",dt,"Manchester United",f"Opponent {i}",(1,1)))
        mapping,_=generate(data)
        hist,_=normalize_history(data,accepted_sources=frozenset({"openfootball","sportscore"}),team_aliases=mapping)
        fixture={"fixture_key":"tonight","discovered_by":"sportscore",
                 "home_team":"Arsenal","away_team":"Man Utd",
                 "kickoff_utc":"2025-03-02T18:00:00Z",
                 "league_labels":["Premier League"],"league_verified":True,
                 "status":"prematch","sources":{"sportscore":{"id":"new_match"}},
                 "ambiguous_match":False,"league_conflict":False,"scores_conflict":False}
        ready,report=adapt_daily([fixture],hist,as_of=AS_OF,team_aliases=mapping)
        self.assertEqual(report["ready_for_unchanged_core"],1)
        self.assertEqual(ready[0]["away_team_id"],hist[0]["away_team_id"])
        _,result=evaluate_existing_v2(ready,hist,as_of=AS_OF)
        self.assertTrue(result["core_predict_v2_function_used"])
        self.assertEqual(result["h2h_nonzero_fixtures"],1)
        self.assertFalse(result["production_published"])

if __name__=="__main__":
    unittest.main()
