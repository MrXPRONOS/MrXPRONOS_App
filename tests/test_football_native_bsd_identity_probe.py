import unittest
from datetime import datetime,timezone

from scripts.football_native_bsd_identity_probe import prove,positive_native_id,native_parts,candidate_official_league_ids,audit_official_consensus_quotes

NOW=datetime(2026,10,14,12,tzinfo=timezone.utc)

def ext(*,home="Arsenal",away="Chelsea",league="Premier League",
        start="2026-10-15T19:00:00Z",cc0=True):
    return {
        "_schedule_verified_by":"openfootball_cc0" if cc0 else None,
        "league_verified":cc0,
        "home_team":home,"away_team":away,
        "kickoff_utc":start,"status":"prematch",
        "league_labels":[league],
        "ambiguous_match":False,"league_conflict":False,"scores_conflict":False,
    }

def native(*,ident=123,home="Arsenal",away="Chelsea",league="Premier League",
           start="2026-10-15T19:05:00Z",status="notstarted"):
    return {
        "id":ident,"league_id":8,"home_team_id":10,"away_team_id":12,
        "league_name":league,"home_team":{"name":home,"id":10},
        "away_team":{"name":away,"id":12},
        "event_date":start,"status":status,
    }

class IdentityBridgeTests(unittest.TestCase):
    def test_exact_15_min_verified_native_link(self):
        result=prove([ext()],[native()],at=NOW)
        self.assertEqual(result["one_to_one_native_event_links"],1)
        self.assertFalse(result["native_event_ids_exported"])
        self.assertFalse(result["actual_bookmaker_quote_or_market_verified"])
        self.assertFalse(result["original_production_publication_enabled"])
        self.assertNotIn("Arsenal",str(result))
        self.assertNotIn("123",str(result))

    def test_no_cross_league_alias_reverse_side_or_nearest_name_guessing(self):
        inputs=[native(league="Women's Premier League"),
                native(home="Chelsea",away="Arsenal"),
                native(home="Arsenal U21"),
                native(start="2026-10-15T19:20:00Z")]
        result=prove([ext()],inputs,at=NOW)
        self.assertEqual(result["one_to_one_native_event_links"],0)

    def test_duplicate_native_or_external_matches_are_quarantined(self):
        one=prove([ext()],[native(ident=5),native(ident=7)],at=NOW)
        self.assertEqual(one["one_to_one_native_event_links"],0)
        self.assertEqual(one["rejected_reasons"]["external_ambiguous_native_matches"],1)
        two=prove([ext(),ext()],[native()],at=NOW)
        self.assertEqual(two["one_to_one_native_event_links"],0)
        self.assertEqual(two["rejected_reasons"]["native_ambiguous_external_matches"],1)
        three=prove([ext()],[native(ident=5),native(ident=5)],at=NOW)
        self.assertEqual(three["one_to_one_native_event_links"],0)

    def test_synthetic_and_unverified_ids_cannot_match(self):
        for value in (0,True,7_500_000_000_000_100,"0123","0","bad"):
            with self.subTest(value=value):
                self.assertIsNone(positive_native_id(value))
        result=prove([ext(cc0=False),ext()],[native(ident=7_500_000_000_000_100)],at=NOW)
        self.assertEqual(result["one_to_one_native_event_links"],0)
        self.assertEqual(result["external_cc0_verified"],1)

    def test_time_requirements_and_status_strict(self):
        invalids=[native(start="2026-10-15T19:16:00Z"),
                  native(status="finished"),
                  native(start="2026-10-13T19:01:00Z")]
        result=prove([ext()],invalids,at=NOW)
        self.assertEqual(result["one_to_one_native_event_links"],0)
        with self.assertRaises(ValueError):
            prove([],[],at=datetime(2026,10,14,12))

    def test_nested_native_competition_schema_is_recognized_without_guessing(self):
        event=native()
        event.pop("league_name")
        event.pop("league_id")
        event["league"]={"id":8,"name":"Premier League"}
        key,issue=native_parts(event)
        self.assertIsNone(issue)
        self.assertIsNotNone(key)
        self.assertEqual(prove([ext()],[event],at=NOW)["one_to_one_native_event_links"],1)

    def test_current_utc_day_unstarted_match_is_eligible_for_strict_identity(self):
        future="2026-10-14T18:05:00Z"
        fixture=ext(start="2026-10-14T18:00:00Z")
        match=native(start=future)
        verified=prove([fixture],[match],at=NOW)
        self.assertEqual(verified["one_to_one_native_event_links"],1)
        started=prove(
            [ext(start="2026-10-14T10:00:00Z")],
            [native(start="2026-10-14T10:05:00Z")],at=NOW)
        self.assertEqual(started["one_to_one_native_event_links"],0)

    def test_historical_coupons_are_excluded_before_odds_queries(self):
        class FakeBSD:
            def __init__(self):
                self.requests_made=0
                self.seen=[]
            def get_json(self,path,params,ttl=0):
                self.requests_made+=1
                self.seen.append(params["event_id"])
                return {"count":0,"results":[]}
        # More than 8 linked events: the first 8 are already published,
        # while the newly discoverable event must receive the only quote call.
        matches=[
            native(ident=100+i,start=f"2026-10-15T{10+i:02d}:05:00Z")
            for i in range(8)
        ]
        matches.append(native(ident=900,start="2026-10-15T20:05:00Z"))
        client=FakeBSD()
        history={str(100+i) for i in range(8)}
        audit=audit_official_consensus_quotes(
            client,matches,[x["id"] for x in matches],{},at=NOW,
            historical_published_ids=history)
        self.assertEqual(client.seen,[900])
        self.assertEqual(audit["historically_published_native_links_excluded"],8)
        self.assertEqual(audit["unpublished_native_links_available"],1)
        self.assertEqual(audit["unpublished_native_links_in_48h_window"],1)
        self.assertEqual(audit["actual_48h_publication_window_quote_attempts"],1)
        self.assertEqual(audit["official_native_events_quoted_attempts"],1)
        self.assertNotIn("900",str(audit))
        for forbidden in ("100","101","102","103","104","105","106","107"):
            self.assertNotIn(forbidden,str(audit))

    def test_verified_native_event_can_only_audit_real_fresh_consensus_market(self):
        class FakeBSD:
            requests_made=0
            def get_json(self,path,params,ttl=0):
                self.requests_made+=1
                self.last_path=path
                self.last_params=params
                return {"count":1,"results":[{
                    "event_id":123,"market":"over_under_15","outcome":"over",
                    "period":"FT","bookmaker_slug":"consensus",
                    "decimal_odds":1.76,
                    "updated_at":"2026-10-14T11:50:00+00:00",
                }]}
        linked=[]
        report=prove([ext()],[native()],at=NOW,verified_id_sink=linked)
        self.assertEqual(report["one_to_one_native_event_links"],1)
        self.assertEqual(linked,[123])
        fake=FakeBSD()
        audit=audit_official_consensus_quotes(fake,[native()],linked,{},at=NOW)
        self.assertEqual(fake.last_path,"/odds/")
        self.assertEqual(fake.last_params["event_id"],123)
        self.assertEqual(audit["events_with_fresh_consensus_market_prices"],1)
        self.assertEqual(audit["fresh_consensus_market_prices"],1)
        self.assertTrue(audit["consensus_is_not_executable_bookmaker_offer"])
        self.assertEqual(audit["independent_bookmaker_selection_codes_verified"],0)
        self.assertFalse(audit["production_market_policy_approved"])
        self.assertNotIn("123",str(audit))
        self.assertNotIn("1.76",str(audit))

    def test_quote_probe_prioritizes_earlier_real_kickoff_over_native_number(self):
        class FakeBSD:
            requests_made=0
            def __init__(self):
                self.seen=[]
            def get_json(self,path,params,ttl=0):
                self.requests_made+=1
                self.seen.append(params["event_id"])
                return {"count":0,"results":[]}
        first=native(ident=900,start="2026-10-15T16:00:00Z")
        later=native(ident=100,start="2026-10-17T19:00:00Z")
        fake=FakeBSD()
        result=audit_official_consensus_quotes(fake,[first,later],[100,900],{},at=NOW)
        self.assertEqual(fake.seen,[900,100])
        self.assertEqual(result["official_native_events_quoted_attempts"],2)
        self.assertEqual(result["fresh_consensus_market_prices"],0)

    def test_odds_entitlement_failure_is_fail_closed(self):
        class ForbiddenClient:
            requests_made=0
            def get_json(self,path,params,ttl=0):
                self.requests_made+=1
                ex=Exception("paid add-on required")
                ex.status=402
                raise ex
        client=ForbiddenClient()
        audit=audit_official_consensus_quotes(client,[native()],[123],{},at=NOW)
        self.assertEqual(audit["issues"]["bsd_odds_entitlement_required"],1)
        self.assertEqual(audit["fresh_consensus_market_prices"],0)

    def test_official_league_detail_can_verify_name_without_inferring_identity(self):
        match=native()
        match.pop("league_name")
        self.assertEqual(candidate_official_league_ids([ext()],[match],at=NOW),[8])
        original=prove([ext()],[match],at=NOW)
        self.assertEqual(original["one_to_one_native_event_links"],0)
        resolved=prove([ext()],[match],at=NOW,official_leagues={8:"Premier League"})
        self.assertEqual(resolved["one_to_one_native_event_links"],1)
        mismatch=prove([ext()],[match],at=NOW,official_leagues={8:"Bundesliga"})
        self.assertEqual(mismatch["one_to_one_native_event_links"],0)
        self.assertNotIn("Arsenal",str(resolved))
        self.assertNotIn("123",str(resolved))

    def test_never_lookup_league_id_from_unverified_or_wrong_kickoff(self):
        mismatch=native(start="2026-10-15T20:00:00Z")
        self.assertEqual(candidate_official_league_ids([ext()],[mismatch],at=NOW),[])
        self.assertEqual(candidate_official_league_ids([ext(cc0=False)],[native()],at=NOW),[])

    def test_invalid_native_schema_is_explained_without_exposing_ids(self):
        malformed=native()
        malformed.pop("league_name")
        result=prove([ext()],[malformed],at=NOW)
        self.assertEqual(result["native_invalid_breakdown"]["missing_native_competition_name"],1)
        self.assertNotIn("Arsenal",str(result))
        self.assertNotIn("Chelsea",str(result))

    def test_requires_native_league_team_identifiers(self):
        row=native()
        row.pop("league_id")
        self.assertEqual(prove([ext()],[row],at=NOW)["one_to_one_native_event_links"],0)
        row=native()
        row["home_team_id"]=None
        row["home_team"]["id"]=None
        self.assertEqual(prove([ext()],[row],at=NOW)["one_to_one_native_event_links"],0)

if __name__=="__main__":
    unittest.main()
