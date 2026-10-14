import unittest
from datetime import datetime,timezone
from scripts.football_cc0_calendar_verification import corroborate,download_schedules
from scripts.football_multisource_channel_test import build,test_post,audit_no_quote_gate
from scripts.football_external_bsd_v2_adapter import normalize_history,adapt_daily

AT=datetime(2026,10,14,17,tzinfo=timezone.utc)

def fixture(**updates):
    row={"fixture_key":"X","discovered_by":"espn","home_team":"Arsenal FC",
         "away_team":"Chelsea FC","kickoff_utc":"2026-10-17T15:00:00Z",
         "status":"prematch","league_labels":[],"league_verified":False,
         "sources":{"espn":{"id":"E99","state":"pre"}},
         "ambiguous_match":False,"scores_conflict":False,"league_conflict":False}
    row.update(updates)
    return row

class Response:
    def __init__(self,data):
        self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data

class SyntheticSession:
    def get(self,url,timeout):
        league=url.rsplit("/",1)[-1]
        return Response({"matches":[
            {"date":"2026-10-17","team1":"Arsenal FC","team2":"Chelsea FC"}]
            if league=="en.1.json" else []})

class OpenScheduleAndTelegramTests(unittest.TestCase):
    def test_public_domain_calendars_are_fixed_paths_and_accounted(self):
        schedules,health=download_schedules(SyntheticSession())
        self.assertEqual(health["files_attempted"],8)
        self.assertEqual(health["files_ok"],8)
        self.assertEqual(health["schedule_rows"],1)

    def test_strict_calendar_resolves_missing_competition(self):
        public=[{"day":"2026-10-17","league":"Premier League",
                 "home":"arsenal","away":"chelsea"}]
        rows,health=corroborate([fixture()],public,as_of=AT)
        self.assertTrue(rows[0]["league_verified"])
        self.assertEqual(rows[0]["league_labels"],["premier league"])
        self.assertEqual(health["schedule_matches_confirmed"],1)

    def test_per_provider_calendar_identity_report_is_aggregate(self):
        public=[{"day":"2026-10-17","league":"Premier League",
                 "home":"arsenal","away":"chelsea"}]
        rows,health=corroborate([
            fixture(discovered_by="espn"),
            fixture(discovered_by="sportscore",away_team="Unknown Reserve"),
            fixture(discovered_by="thesportsdb",status="not_prematch")
        ],public,as_of=AT)
        self.assertEqual(health["by_discovery_source"]["espn"]["confirmed"],1)
        self.assertEqual(health["by_discovery_source"]["sportscore"]["no_calendar_match"],1)
        self.assertEqual(health["by_discovery_source"]["thesportsdb"]["not_eligible_prematch"],1)
        self.assertEqual(sum(v["input"] for v in health["by_discovery_source"].values()),3)
        self.assertNotIn("arsenal",str(health).lower())
        self.assertFalse(rows[1]["league_verified"])

    def test_unmatched_calendar_causes_are_only_diagnostic(self):
        schedules=[
            {"day":"2026-10-17","league":"Premier League",
             "home":"arsenal","away":"chelsea"},
            {"day":"2026-10-18","league":"La Liga",
             "home":"real madrid","away":"barcelona"},
        ]
        cases=[
            fixture(discovered_by="sportscore",home_team="Chelsea",away_team="Arsenal"),
            fixture(discovered_by="espn",home_team="Real Madrid",away_team="Barcelona"),
            fixture(discovered_by="thesportsdb",home_team="Arsenal",away_team="Lyon"),
            fixture(discovered_by="openligadb",home_team="Unknown A",away_team="Unknown B"),
        ]
        rows,health=corroborate(cases,schedules,as_of=AT)
        by=health["by_discovery_source"]
        self.assertEqual(by["sportscore"]["unmatched_reversed_home_away_same_day"],1)
        self.assertEqual(by["espn"]["unmatched_exact_pair_on_other_calendar_day"],1)
        self.assertEqual(by["thesportsdb"]["unmatched_one_club_on_day"],1)
        self.assertEqual(by["openligadb"]["unmatched_no_clubs_on_day"],1)
        self.assertEqual(health["schedule_matches_confirmed"],0)
        for row in rows:
            self.assertFalse(row["league_verified"])
            self.assertNotIn("_schedule_verified_by",row)
        self.assertNotIn("unknown",str(health).lower())

    def test_missing_calendar_day_never_infers_kickoff_or_league(self):
        future=fixture(home_team="Arsenal",away_team="Chelsea",
                       kickoff_utc="2026-10-19T18:30:00Z")
        rows,health=corroborate([future],[
            {"day":"2026-10-17","league":"Premier League",
             "home":"arsenal","away":"chelsea"}],as_of=AT)
        self.assertFalse(rows[0]["league_verified"])
        self.assertEqual(rows[0]["kickoff_utc"],"2026-10-19T18:30:00Z")
        self.assertEqual(health["by_discovery_source"]["espn"]["unmatched_exact_pair_on_other_calendar_day"],1)

    def test_no_calendar_match_never_invents_league(self):
        rows,health=corroborate([fixture(away_team="Arsenal Women")],[
            {"day":"2026-10-17","league":"Premier League",
             "home":"arsenal","away":"chelsea"}],as_of=AT)
        self.assertFalse(rows[0]["league_verified"])
        self.assertEqual(health["schedule_matches_confirmed"],0)

    def test_calendar_conflicts_quarantined(self):
        rows,health=corroborate([
            fixture(league_labels=["Serie A"],league_verified=True)
        ],[{"day":"2026-10-17","league":"Premier League",
            "home":"arsenal","away":"chelsea"}],as_of=AT)
        self.assertTrue(rows[0]["league_conflict"])
        self.assertFalse(rows[0]["league_verified"])

    def test_unchanged_bsd_v2_skips_unqualified_fixture(self):
        messages,report=build([fixture()],[],at=AT)
        self.assertEqual(messages,[])
        self.assertEqual(report["calibrated_production_coupons"],0)
        self.assertTrue(report["no_odds_invented"])
        self.assertEqual(report["no_bookmaker_quote_gate"]["accepted_with_no_bookmaker_quotes"],0)

    def test_original_bsd_v2_require_odds_rejects_unpriced_known_fixture(self):
        history=[]
        for i in range(1,8):
            for team,suffix in (("Arsenal","A"),("Chelsea","C")):
                history.append({
                    "source":"openfootball","source_id":f"{team}-{i}",
                    "status":"finished","match_date":f"2026-09-{i:02d}",
                    "league":"Premier League",
                    "home_team":team,"away_team":f"Opponent {suffix}{i}",
                    "home_score":2,"away_score":1,
                })
        archived,_=normalize_history(history)
        upcoming=fixture(
            league_labels=["Premier League"],league_verified=True,
            _schedule_verified_by="openfootball_cc0")
        ready,coverage=adapt_daily([upcoming],archived,as_of=AT)
        self.assertEqual(coverage["ready_for_unchanged_core"],1)
        guarded=audit_no_quote_gate(ready,archived,at=AT)
        self.assertEqual(guarded["fixtures_checked"],1)
        self.assertEqual(guarded["accepted_with_no_bookmaker_quotes"],0)
        self.assertGreater(guarded["missing_or_low_odds_market_rejections"],0)
        self.assertTrue(guarded["used_original_predict_v2"])
        self.assertFalse(guarded["full_publication_policy_checked"])
        self.assertFalse(guarded["publication_enabled"])

    def test_empty_audit_never_claims_any_qualified_prices(self):
        guarded=audit_no_quote_gate([],[],at=AT)
        self.assertEqual(guarded["accepted_with_no_bookmaker_quotes"],0)
        self.assertEqual(guarded["fixtures_checked"],0)
        self.assertFalse(guarded["actual_bookmaker_quotes_supplied"])

    def test_test_channel_sends_diagnostic_only_when_no_v2_pick(self):
        payloads=[]
        def fake_get(url,params,timeout):
            if url.endswith("/getChat"):return Response({"ok":True,"result":{
                "id":-10099,"type":"channel","username":"predict_mrxp"}})
            if url.endswith("/getMe"):return Response({"ok":True,"result":{"id":2}})
            if url.endswith("/getChatMember"):return Response({"ok":True,"result":{
                "status":"administrator","can_post_messages":True}})
            raise AssertionError("Unexpected endpoint")
        def fake_post(url,json,timeout):
            payloads.append(json)
            return Response({"ok":True,"result":{"message_id":1}})
        outcome=test_post([],{"qualified_external_fixtures":0,
                            "raw_v2_candidates":0},
                          token="FAKE-BOT",chat="@predict_mrxp",
                          get=fake_get,post=fake_post)
        self.assertEqual(outcome["messages_sent"],1)
        self.assertEqual(payloads[0]["chat_id"],-10099)
        self.assertIn("Aucun pronostic",payloads[0]["text"])
        self.assertEqual(outcome["production_posts"],0)

    def test_unrecognized_channel_never_gets_messages(self):
        did=[]
        def fake_get(url,params,timeout):
            return Response({"ok":True,"result":{"id":-1001,
                "type":"channel","username":"mrxpronos_public"}})
        def fake_post(*args,**kwargs):
            did.append(True)
            return Response({"ok":True})
        with self.assertRaises(Exception):
            test_post(["test"],{"qualified_external_fixtures":1},
                      token="FAKE",chat="@mrxpronos_public",
                      get=fake_get,post=fake_post)
        self.assertEqual(did,[])

if __name__=="__main__":
    unittest.main()
