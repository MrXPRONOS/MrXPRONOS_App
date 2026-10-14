"""Offline fail-closed tests for optional documented SportScore filtered probe."""
import unittest

from scripts.football_sportscore_filtered_audit import inspect_filtered

DAY = "2026-10-17"
LATER = "2026-10-18"


def source_health(*, first=200, second=None):
    days = [DAY] if second is None else [DAY, LATER]
    records = {DAY: {"provider_health": {"sportscore": {"reported": first}}}}
    if second is not None:
        records[LATER] = {"provider_health": {"sportscore": {"reported": second}}}
    return {"days": days, "sources": records}


def base_fixture():
    return [{"home_team": "Arsenal", "away_team": "Chelsea",
             "sources": {"sportscore": {"id": "existing-id"}}}]


def match(source_id, *, home="Arsenal", away="Chelsea",
          when="2026-10-17T18:00:00Z", status="upcoming"):
    return {"id": source_id, "home": home, "away": away,
            "time": when, "status": status,
            "competition": "Premier League"}


class Reply:
    status_code = 200

    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError("HTTP error")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.replies.pop(0)


class SportScoreFilteredAuditTests(unittest.TestCase):
    def test_only_saturated_days_trigger_documented_status_filter(self):
        original = base_fixture()
        fake = FakeSession([Reply({"matches": [
            match("existing-id"), match("new-id"),
            match("different-day", when="2026-10-18T19:00:00Z"),
            match("finished-id", status="finished"),
        ]})])
        result = inspect_filtered(original, source_health(first=200, second=199),
                                  session=fake, max_requests=2)
        self.assertEqual(len(fake.calls), 1)
        url, params = fake.calls[0]
        self.assertTrue(url.endswith("/api/v1/fixtures/"))
        self.assertEqual(params["params"],
                         {"sport": "football", "date": DAY,
                          "status": "upcoming", "limit": 200})
        self.assertFalse(params["allow_redirects"])
        self.assertIsNone(params["headers"]["Authorization"])
        day = result["per_day"][DAY]
        self.assertTrue(day["successful"])
        self.assertEqual(day["filtered_pre_match"], 2)
        self.assertEqual(day["matched_general_source_ids"], 1)
        self.assertEqual(day["not_in_general_source_ids"], 1)
        self.assertFalse(result["undocumented_pagination_used"])
        self.assertEqual(result["new_events_added_to_prediction_pipeline"], 0)
        self.assertEqual(original, base_fixture())
        self.assertFalse(result["calendar_matching_or_odds_approved"])

    def test_page_limit_and_request_budget_are_not_bypassed(self):
        fake = FakeSession([Reply({"matches": [match(f"m{i}") for i in range(200)]})])
        result = inspect_filtered([], source_health(second=200),
                                  session=fake, max_requests=1)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["reasons"]["budget_exhausted"], 1)
        self.assertTrue(result["per_day"][DAY]["filtered_also_at_cap"])
        self.assertFalse(result["per_day"][LATER]["attempted"])
        self.assertTrue(result["possible_incomplete_coverage"])

    def test_not_capped_days_require_no_calls(self):
        fake = FakeSession()
        result = inspect_filtered([], source_health(first=40),
                                  session=fake, max_requests=1)
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(fake.calls, [])
        self.assertFalse(result["possible_incomplete_coverage"])

    def test_unexpected_redirect_or_schema_stays_diagnostic(self):
        for response in (Reply({"matches": []}, status=302),
                         Reply({"fixtures": []}), Reply([])):
            with self.subTest(payload=response.payload):
                fake = FakeSession([response])
                result = inspect_filtered(base_fixture(), source_health(),
                                          session=fake, max_requests=1)
                self.assertFalse(result["per_day"][DAY]["successful"])
                self.assertEqual(result["reasons"]["fetch_or_schema_failure"], 1)
                self.assertEqual(result["new_events_added_to_prediction_pipeline"], 0)
                self.assertNotIn("existing-id", str(result))

    def test_source_id_conflicts_cannot_count_as_new_valid_ids(self):
        fake = FakeSession([Reply({"matches": [
            match("same-id", home="Arsenal", away="Chelsea"),
            match("same-id", home="Arsenal", away="Tottenham")
        ]})])
        result = inspect_filtered([], source_health(), session=fake,
                                  max_requests=1)
        day = result["per_day"][DAY]
        self.assertTrue(day["successful"])
        self.assertEqual(day["unusable_or_conflicting_source_ids"], 1)
        self.assertEqual(day["not_in_general_source_ids"], 0)

    def test_invalid_clock_or_duplicate_days_fail_closed(self):
        with self.assertRaises(ValueError):
            inspect_filtered([], {"days": [DAY, DAY]}, session=FakeSession())
        with self.assertRaises(ValueError):
            inspect_filtered([], source_health(), max_requests=5)


if __name__ == "__main__":
    unittest.main()
