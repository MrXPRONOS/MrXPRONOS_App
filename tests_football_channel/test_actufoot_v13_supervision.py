"""Offline coverage for Actu Foot V1.3, without D1/Telegram network access."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scripts import actufoot_v13_supervision as v13

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
CHANNELS = {
    "flash": "@FootFlashActuFR",
    "mercato": "@MercatoFootInfosFR",
    "champions": "@LDCActuFootFR",
    "premier": "@PremierLeagueActuFR",
    "liga": "@LigaFootActuFR",
    "ligue1": "@Ligue1FootActuFR",
    "africa": "@FootAfriqueInfosFR",
    "national": "@SelectionsFootActu",
    "scores": "@ScoresFootClassements",
    "debrief": "@DebriefFootAnalyses",
}


def record(role, lane, status, total, day="2026-11-23", stale=0):
    kind = {
        "rss": v13.RSS, "live": v13.LIVE, "v12": v13.LIVE,
        "rss_quota": v13.RSS_QUOTA, "live_quota": v13.LIVE_QUOTA,
    }[lane]
    return {"channel": CHANNELS[role], "ref_date": day, "kind": kind,
            "lane": lane, "delivery_status": status, "total": total,
            "stale": stale,
            "latest_sent": NOW.isoformat() if status == "sent" else None}


class SupervisionTests(unittest.TestCase):
    def test_exact_ten_roles(self):
        v13.validate_channels(CHANNELS)
        with self.assertRaises(ValueError):
            v13.validate_channels({**CHANNELS, "extra": "@OtherFootFR"})
        with self.assertRaises(ValueError):
            v13.validate_channels({**CHANNELS, "flash": CHANNELS["scores"]})
        with self.assertRaises(ValueError):
            v13.validate_channels({**CHANNELS, "flash": "-10012345"})

    def test_metrics_aggregate_sql_is_read_only_and_bounded(self):
        ledger = MagicMock()
        ledger.query.return_value = {"results": []}
        result = v13.read_aggregates(ledger, NOW)
        self.assertEqual(result, [])
        sql, params = ledger.query.call_args.args
        self.assertTrue(sql.startswith("SELECT"))
        self.assertNotIn("DELETE", sql)
        self.assertNotIn("INSERT", sql)
        self.assertEqual(params[-4:], v13.KINDS)
        self.assertEqual(params[-6:-4], ("2026-11-22", "2026-11-23"))

    def test_counts_per_role_and_delivery_lane(self):
        data = [
            record("flash", "rss", "sent", 3),
            record("flash", "rss", "sent", 2, "2026-11-22"),
            record("flash", "rss_quota", "reserved", 3),
            record("scores", "live", "sent", 6),
            record("scores", "v12", "sent", 1),
            record("scores", "live_quota", "reserved", 7),
            record("debrief", "v12", "sent", 2),
            record("flash", "rss", "failed", 1),
        ]
        report = v13.build_report(NOW, CHANNELS, data, set(CHANNELS), [])
        self.assertEqual(report["channels"]["flash"]["today"]["rss"], 3)
        self.assertEqual(report["channels"]["flash"]["yesterday"]["rss"], 2)
        self.assertEqual(report["channels"]["scores"]["today"]["live"], 6)
        self.assertEqual(report["channels"]["scores"]["today"]["v12"], 1)
        self.assertEqual(report["channels"]["debrief"]["today"]["v12"], 2)
        self.assertEqual(report["channels"]["scores"]["quota"]["live"], 7)
        self.assertEqual(report["summary"]["messages_today"], 12)
        self.assertIn("FAILED_PUBLICATIONS", [
            a["code"] for a in report["channels"]["flash"]["alerts"]])
        self.assertEqual(report["channels"]["liga"]["level"], "ok")

    def test_silent_channel_does_not_raise_false_alert(self):
        report = v13.build_report(NOW, CHANNELS, [], set(CHANNELS), [])
        self.assertEqual(report["alerts"], [])
        self.assertEqual(report["summary"]["critical"], 0)
        self.assertEqual(report["channels"]["mercato"]["today"]["rss"], 0)
        self.assertIn("Canal", v13.markdown(report))

    def test_missing_telegram_rights_reported(self):
        report = v13.build_report(NOW, CHANNELS, [], set(CHANNELS) - {"flash"}, ["flash"])
        self.assertEqual(report["channels"]["flash"]["level"], "critical")
        self.assertEqual(report["summary"]["critical"], 1)
        self.assertEqual(report["roles_verified"], 9)

    def test_main_permission_failure_is_critical(self):
        report = v13.build_report(NOW, CHANNELS, [], set(CHANNELS), [], main_verified=False)
        self.assertIn("MAIN_UNVERIFIED", [a["code"] for a in report["alerts"]])

    def test_pending_and_uncertain_are_not_replayed(self):
        data = [record("scores", "live", "reserved", 2, stale=2),
                record("scores", "live", "uncertain", 1, stale=1),
                record("scores", "live", "rejected", 1)]
        report = v13.build_report(NOW, CHANNELS, data, set(CHANNELS), [])
        codes = [a["code"] for a in report["channels"]["scores"]["alerts"]]
        self.assertIn("STUCK_RESERVATIONS", codes)
        self.assertIn("UNCERTAIN_DELIVERIES", codes)
        self.assertIn("TELEGRAM_REJECTIONS", codes)
        self.assertEqual(report["channels"]["scores"]["stale_pending"], 3)

    def test_warning_quota_thresholds(self):
        rows = [record("flash", "rss_quota", "reserved", 22),
                record("scores", "live_quota", "reserved", 48)]
        report = v13.build_report(NOW, CHANNELS, rows, set(CHANNELS), [])
        self.assertIn("QUOTA_NEAR_RSS", [
            a["code"] for a in report["channels"]["flash"]["alerts"]])
        self.assertIn("QUOTA_EXHAUSTED_LIVE", [
            a["code"] for a in report["channels"]["scores"]["alerts"]])

    def test_invalid_and_unrelated_metrics_are_ignored_or_rejected(self):
        data = [record("flash", "rss", "sent", 7, "2026-11-20"),
                {**record("flash", "rss", "sent", 7), "channel": "@OtherFootFR"}]
        report = v13.build_report(NOW, CHANNELS, data, set(CHANNELS), [])
        self.assertEqual(report["summary"]["messages_today"], 0)
        with self.assertRaises(ValueError):
            v13.build_report(NOW, CHANNELS,
                             [record("flash", "rss", "sent", -1)], set(CHANNELS), [])

    def test_stale_or_missing_timestamps_are_not_invented(self):
        report = v13.build_report(NOW, CHANNELS,
                                   [record("flash", "rss", "sent", 1)],
                                   set(CHANNELS), [])
        self.assertEqual(report["channels"]["flash"]["last_sent"], NOW.isoformat())
        bad = record("flash", "rss", "sent", 1)
        bad["latest_sent"] = "bogus"
        report = v13.build_report(NOW, CHANNELS, [bad], set(CHANNELS), [])
        self.assertIsNone(report["channels"]["flash"]["last_sent"])

    def test_alert_privacy_requires_numeric_destination(self):
        report = v13.build_report(NOW, CHANNELS, [],
                                   set(CHANNELS) - {"flash"}, ["flash"])
        ledger, session = MagicMock(), MagicMock()
        self.assertEqual(v13.send_private_alert(
            report, ledger, session, "token", "@FootFlashActuFR",
            dry_run=False), "disabled_private_destination")
        self.assertEqual(v13.send_private_alert(
            report, ledger, session, "token", "-1001234567890",
            dry_run=True), "dry_run")
        ledger.claim.assert_not_called()
        session.post.assert_not_called()

    def test_exact_alert_fingerprint_claim_and_receipt(self):
        report = v13.build_report(NOW, CHANNELS, [],
                                   set(CHANNELS) - {"flash"}, ["flash"])
        ledger, session = MagicMock(), MagicMock()
        ledger.claim.return_value = True
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {
            "ok": True, "result": {"message_id": 42}}
        state = v13.send_private_alert(
            report, ledger, session, "token", "-1001234567890", dry_run=False)
        self.assertEqual(state, "sent")
        ledger.mark.assert_called_once()
        self.assertEqual(ledger.mark.call_args.kwargs["message_id"], 42)
        self.assertEqual(ledger.claim.call_args.args[0], v13.ALERT_KIND)

        ledger.claim.return_value = False
        self.assertEqual(v13.send_private_alert(
            report, ledger, session, "token", "-1001234567890",
            dry_run=False), "already_reserved")
        self.assertEqual(session.post.call_count, 1)

    def test_ambiguous_telegram_response_quarantined(self):
        report = v13.build_report(NOW, CHANNELS, [],
                                   set(CHANNELS) - {"flash"}, ["flash"])
        ledger, session = MagicMock(), MagicMock()
        ledger.claim.return_value = True
        session.post.side_effect = requests_timeout()
        self.assertEqual(v13.send_private_alert(
            report, ledger, session, "token", "-1001234567890", dry_run=False),
            "uncertain")
        self.assertEqual(ledger.set_status.call_args.args[-1], "uncertain")
        ledger.mark.assert_not_called()

    def test_run_refuses_missing_permissions_credentials(self):
        with self.assertRaises(RuntimeError):
            v13.run(NOW, ledger=MagicMock(), session=MagicMock(),
                    token="", main_chat="", channels=CHANNELS)
        ledger = MagicMock()
        ledger.query.return_value = {"results": []}
        with patch.object(v13, "verify_channels", return_value=(
                {k: v for k, v in CHANNELS.items()}, [])) as check:
            report = v13.run(NOW, ledger=ledger, session=MagicMock(),
                             token="safe", main_chat="@actufoot_mrxp",
                             channels=CHANNELS, dry_run=True)
        self.assertEqual(report["roles_verified"], 10)
        self.assertEqual(report["private_alert_delivery"], "disabled")
        check.assert_called_once()
        self.assertEqual(ledger.query.call_count, 1)


def requests_timeout():
    import requests
    return requests.Timeout("No delivery receipt")


if __name__ == "__main__":
    unittest.main()
