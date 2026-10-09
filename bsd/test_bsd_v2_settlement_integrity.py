"""Telegram BSD settlement integrity tests. No network access."""
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from bsd_v2_telegram_ledger import snapshot,selection_for_result
from bsd_v2_verify_telegram import validate,validate_combos,verdict

NOW=datetime(2026,10,9,18,tzinfo=timezone.utc)
def leg(n,market="UNDER_25"):
    return {"id":f"bsd:{n}","source":"bsd","date":"2026-10-08",
            "event_date":"2026-10-08T12:00:00+00:00",
            "prediction":{"selection_key":market,"odds":1.8},
            "home_team":"Club A","away_team":"Club B"}

def event(home,away,offset_days=0):
    return {"status":"finished",
            "event_date":f"2026-10-{8+offset_days:02d}T12:00:00+00:00",
            "home_score":home,"away_score":away}

class IntegrityTests(unittest.TestCase):
    def test_frozen_snapshot_is_independent_from_mutating_source(self):
        match=leg(77)
        frozen=snapshot(match)
        match["prediction"]["selection_key"]="OVER_25"
        self.assertEqual(selection_for_result(frozen)["prediction"]["selection_key"],"UNDER_25")

    def test_rescheduled_kickoff_still_settles_by_event_id(self):
        self.assertEqual(verdict(leg(7),event(0,0,1),NOW)[0],True)

    def test_single_is_not_sent_twice_after_claim(self):
        row={"id":5,"ref_id":"-1001:bsd:7","selection_snapshot":snapshot(leg(7)),
             "settlement_status":"pending","delivery_status":"sent"}
        with patch("bsd_v2_verify_telegram.claim_settlement",return_value=False),patch(
            "bsd_v2_verify_telegram.post_gain"
        ) as send:
            result=validate({"matches":[]},[row],{"7":event(0,0)},NOW,
                            None,"tok","url","key")
        send.assert_not_called()
        self.assertEqual(result["already_claimed"],1)

    def test_combo_success_requires_both_legs(self):
        combo={"id":"combo:test","combined_odds":2.56,
               "legs":[leg(7),leg(8)]}
        row={"id":5,"ref_id":"-1001:combo:test","selection_snapshot":snapshot(combo,combo=True),
             "settlement_status":"pending","delivery_status":"sent"}
        with patch("bsd_v2_verify_telegram.claim_settlement",return_value=True),patch(
            "bsd_v2_verify_telegram.finalize_settlement"
        ) as finish:
            result=validate_combos([row],{"7":event(0,0),"8":event(4,0)},NOW,
                                   None,"tok","url","key")
        self.assertEqual(result["combos_losses_silent"],1)
        self.assertEqual(finish.call_args.kwargs["status"],"lost")

    def test_cancelled_combo_never_posts_and_is_voided(self):
        combo={"id":"combo:test","combined_odds":2.56,
               "legs":[leg(7),leg(8)]}
        row={"id":9,"ref_id":"-1001:combo:test","selection_snapshot":snapshot(combo,combo=True),
             "settlement_status":"pending","delivery_status":"sent"}
        with patch("bsd_v2_verify_telegram.claim_settlement",return_value=True),patch(
            "bsd_v2_verify_telegram.finalize_settlement"
        ) as finish:
            result=validate_combos([row],{
                "7":{"status":"cancelled"},"8":event(1,1)},NOW,
                None,"tok","url","key")
        self.assertEqual(result["combos_void_silent"],1)
        self.assertEqual(finish.call_args.kwargs["status"],"void")

    def test_combo_without_original_snapshot_waits_for_review(self):
        row={"id":5,"ref_id":"-1001:combo:test","delivery_status":"legacy"}
        result=validate_combos([row],{},NOW,None,"tok","url","key")
        self.assertEqual(result["legacy_combo_no_snapshot"],1)

    def test_diagnostic_reasons_for_unfinished_and_missing_result(self):
        row={"id":5,"ref_id":"-1001:bsd:7","selection_snapshot":snapshot(leg(7)),
             "settlement_status":"pending","delivery_status":"sent"}
        a=validate({"matches":[]},[row],{},NOW,None,"tok","url","key")
        self.assertEqual(a["official_result_unavailable"],1)
        b=validate({"matches":[]},[row],{"7":{"status":"postponed"}},NOW,
                   None,"tok","url","key")
        self.assertEqual(b["official_not_finished"],1)

if __name__=="__main__": unittest.main()
