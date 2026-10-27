"""Offline checks: Telegram audit reports aggregate evidence, never messages."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from scripts.channel_audit import summarize_sample, recent_public_summary, aggregate_samples, source_options, audit_overall_status, requested_channels


def photo(title, n=1):
    return NS(id=n, raw_text=title, photo=object(), media=NS(photo=object()),
              noforwards=False, document=None, video=None, date=datetime.now(timezone.utc),
              grouped_id=None, reply_to=None, file=None)


def video(filename, n=2, caption=""):
    doc=NS(mime_type="video/mp4",size=200_000_000,attributes=[])
    return NS(id=n, raw_text=caption, photo=None, media=NS(document=doc),
              noforwards=False, document=doc, video=doc, date=datetime.now(timezone.utc),
              grouped_id=None, reply_to=None, file=NS(name=filename,size=200_000_000,
                                                      duration=3600))


class ChannelAuditTests(unittest.TestCase):
    def test_audit_code_does_not_invoke_mutating_telegram_methods(self):
        from pathlib import Path
        import scripts.channel_audit as audit
        source=Path(audit.__file__).read_text(encoding="utf-8")
        for method in ("send_message(", "send_file(", "forward_messages(",
                       "delete_messages(", "edit_message(", "join_channel("):
            self.assertNotIn(method, source)

    def test_audit_status_rejects_empty_and_unknown_categories(self):
        self.assertEqual(audit_overall_status({}),"needs_attention")
        names=["films","series","desir","comedie","anime","other"]
        result={name:{"status":"ok"} for name in names}
        self.assertEqual(audit_overall_status(result),"needs_attention")

    def test_invalid_category_configuration_keeps_other_entries(self):
        from unittest.mock import patch
        with patch("scripts.channel_audit.config_from",side_effect=ValueError("invalid")):
            with patch("scripts.channel_audit.series_config",side_effect=ValueError("invalid")):
                with patch("scripts.channel_audit.category_config",
                           side_effect=ValueError("invalid")):
                    entries=requested_channels()
        self.assertEqual([name for name,_,_ in entries],
                         ["films","series","desir","comedie","anime"])
        self.assertIsNone(entries[0][1])
        self.assertIsNone(entries[1][1])
        self.assertIsNotNone(entries[2][1])
        self.assertIsNone(entries[3][1])

    def test_overall_audit_requires_every_category(self):
        names=["films","series","desir","comedie","anime"]
        statuses={name:{"status":"ok"} for name in names}
        self.assertEqual(audit_overall_status(statuses),"ok")
        self.assertEqual(audit_overall_status({k:v for k,v in statuses.items() if k!="anime"}),"needs_attention")
        statuses["series"]={"status":"needs_attention"}
        self.assertEqual(audit_overall_status(statuses),"needs_attention")

    def test_source_policy_handle_matching_is_case_insensitive(self):
        cfg={"sources":["@Film_source"],"source_modes":["authorized_mkv"],
             "source_pairings":[{"max_gap":1}]}
        mode, opts=source_options(cfg,NS(username="FILM_SOURCE"),"films")
        self.assertEqual(mode,"authorized_mkv")
        self.assertEqual(opts["max_gap"],1)

    def test_source_rules_survive_filtered_or_reordered_sources(self):
        cfg={"sources":["@first_source","@second_source"],
             "source_modes":["standard","authorized_mkv"],
             "source_pairings":[{"max_gap":2},{"max_gap":4}]}
        mode, rules=source_options(cfg,NS(username="second_source"),"films")
        self.assertEqual(mode,"authorized_mkv")
        self.assertEqual(rules["max_gap"],4)

    def test_unconfigured_source_never_borrows_rules(self):
        cfg={"sources":["@first_source"],"source_modes":["standard"],
             "source_pairings":[{}]}
        with self.assertRaisesRegex(ValueError,"Cannot associate"):
            source_options(cfg,NS(username="unknown_source"),"films")

    def test_source_missing_rules_rejected(self):
        cfg={"sources":["@first_source"],"source_modes":[],"source_pairings":[]}
        with self.assertRaisesRegex(ValueError,"Matching rules"):
            source_options(cfg,NS(username="first_source"),"films")

    def test_verified_pair(self):
        result=summarize_sample([photo("La Grande Aventure - film VF 2024"),video("La.Grande.Aventure.mp4")],"films")
        self.assertEqual(result["pairs_found"],1)
        self.assertEqual(result["pairs_verified"],1)
        self.assertEqual(result["quarantined_mismatch"],0)

    def test_quarantines_wrong_title(self):
        result=summarize_sample([photo("La Grande Aventure - film VF 2024"),video("Voyage.Sur.Mars.mp4")],"films")
        self.assertEqual(result["pairs_found"],1)
        self.assertEqual(result["quarantined_mismatch"],1)

    def test_missing_artwork_is_not_counted_as_verified(self):
        result=summarize_sample([video("La.Grande.Aventure.mp4")],"desir")
        self.assertEqual(result["pairs_verified"],0)
        self.assertGreaterEqual(result["unpaired_video_files"],1)

    def test_orphan_video_not_in_quarantine_denominator(self):
        result=summarize_sample([video("Orphan.Movie.mp4")],"desir")
        self.assertEqual(result["pairs_found"],0)
        self.assertEqual(result["quarantined_uncertain"],0)
        self.assertEqual(result["unpaired_video_files"],1)

    def test_protected_poster_not_counted_as_valid_pair(self):
        image=photo("La Grande Aventure - film VF 2024")
        image.noforwards=True
        result=summarize_sample([image,video("La.Grande.Aventure.mp4")],"comedie")
        self.assertEqual(result["pairs_found"],0)
        self.assertEqual(result["pairs_verified"],0)

    def test_public_report_excludes_message_and_media_contents(self):
        item=photo("Secret personnel",5)
        summary=recent_public_summary([item])
        self.assertEqual(summary["sampled_posts"],1)
        self.assertNotIn("Secret personnel",str(summary))
        self.assertNotIn("id",summary)
        self.assertIn("last_post_at",summary)

    def test_anime_catalog_not_counted_as_unmatched_film(self):
        result=summarize_sample([video("Episode.01.mp4")],"anime")
        self.assertFalse(result["pairing_evaluated"])
        self.assertIsNone(result["unpaired_video_files"])
        self.assertEqual(result["pairs_found"],0)

    def test_standard_film_audit_applies_production_size_limit(self):
        media=video("La.Grande.Aventure.mp4")
        media.file.size=100_000_000
        media.document.size=100_000_000
        result=summarize_sample(
            [photo("La Grande Aventure - film VF 2024"),media],"films")
        self.assertEqual(result["pairs_found"],0)
        self.assertEqual(result["pairs_verified"],0)
        self.assertEqual(result["pairs_verified"],0)

    def test_standard_film_audit_accepts_large_valid_movie(self):
        image=photo("La Grande Aventure - film VF 2024")
        media=video("La.Grande.Aventure.mp4")
        media.file.size=200_000_000
        media.document.size=200_000_000
        result=summarize_sample([image,media],"films")
        self.assertEqual(result["pairs_found"],1)
        self.assertEqual(result["pairs_verified"],1)

    def test_authorized_mkv_uses_its_distinct_pairing(self):
        media=video("Grand.Film.mkv")
        media.document.mime_type="video/x-matroska"
        result=summarize_sample([photo("Titre du film : Grand Film. Genre : aventure"),
                                 media],"films","authorized_mkv")
        self.assertTrue(result["pairing_evaluated"])
        self.assertEqual(result["pairs_found"],1)

    def test_episodic_aggregate_preserves_not_applicable(self):
        a=summarize_sample([video("Episode.01.mp4")],"series")
        total=aggregate_samples([a,a])
        self.assertIsNone(total["unpaired_video_files"])
        self.assertFalse(total["pairing_evaluated"])

    def test_samples_aggregate_without_ids(self):
        a=summarize_sample([photo("La Grande Aventure - film VF 2024"),video("La.Grande.Aventure.mp4")],"films")
        totals=aggregate_samples([a,a])
        self.assertEqual(totals["pairs_verified"],2)
        self.assertNotIn("channel_id",str(totals))


if __name__ == "__main__":
    unittest.main()
