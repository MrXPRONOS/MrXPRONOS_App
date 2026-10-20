"""BSD multi-source zero-candidate diagnostics never substitute identity evidence."""
import unittest
from scripts.football_multisource_apply_qualified import apply


def stats(calendar, links, staged=0):
    return {
        "external_total":864,
        "independent_cc0_calendar_confirmed":calendar,
        "one_to_one_native_event_links":links,
        "qualified_candidate_rows_staged":staged,
        "read_only_native_consensus_price_audit":{
            "historically_published_native_links_excluded":0,
            "unpublished_native_links_in_48h_window":0,
            "official_native_events_quoted_attempts":0,
            "actual_48h_publication_window_quote_attempts":0,
            "fresh_consensus_market_prices":0,
        },
        "full_model_selected_market_consensus_audit":{
            "aggregate":{},
            "native_full_assembler_canary":{"events_within_native_48h_window":0}
        }
    }


class VolumeDiagnosticTests(unittest.TestCase):
    def test_no_calendar_matches_is_explained_and_not_published(self):
        feed={"source":"bsd","matches":[],"diagnostics":{}}
        apply(feed,[],now=__import__("datetime").datetime(2026,10,20,
            tzinfo=__import__("datetime").timezone.utc),
            publication_ledger={"schema":"bsd-v2-publication-ledger-1","entries":[]},
            aggregate_report=stats(0,0))
        ms=feed["diagnostics"]["multisource_generation"]
        self.assertEqual(ms["bottleneck_stage"],"no_independent_calendar_confirmation")
        self.assertEqual(ms["added_rows"],0)
        self.assertTrue(ms["unverified_external_matches_never_published"])

    def test_calendar_without_unique_native_identity_is_explained(self):
        feed={"source":"bsd","matches":[],"diagnostics":{}}
        from datetime import datetime,timezone
        apply(feed,[],now=datetime(2026,10,20,tzinfo=timezone.utc),
            publication_ledger={"schema":"bsd-v2-publication-ledger-1","entries":[]},
            aggregate_report=stats(3,0))
        self.assertEqual(feed["diagnostics"]["multisource_generation"]["bottleneck_stage"],
                         "no_unique_official_bsd_fixture_identity")


if __name__=="__main__":
    unittest.main()
