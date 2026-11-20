"""Static dashboard, data privacy, merge/restart integration tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from film_relay.anime_catalog import read_catalog
from scripts.anime_health_report import summarize
from scripts.generate_anime_dashboard import dashboard_snapshot
from scripts.merge_anime_catalog import merge

from test_anime_identity_migration import history


class DashboardIntegrationTests(unittest.TestCase):
    def test_export_contains_no_private_links_or_telegram_ids(self):
        catalogue = history()
        d = dashboard_snapshot(catalogue)
        blob = json.dumps(d, ensure_ascii=False)
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["stats"]["titles"], 1)
        self.assertEqual(d["stats"]["private_episodes"], 2)
        self.assertEqual(d["series"][0]["legacy_cards_to_review"], 1)
        for sensitive in ("t.me/", "message_id", "private_poster_id",
                          "source_items", "-100123", "4416009337", "main_index_id"):
            with self.subTest(field=sensitive):
                self.assertNotIn(sensitive, blob)

    def test_reader_migrates_with_zero_write_and_legacy_receipts_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "anime_catalog.json"
            original = history()
            path.write_text(json.dumps(original), encoding="utf8")
            with patch("film_relay.anime_catalog.CATALOG", path):
                updated = read_catalog()
            self.assertEqual(len(updated["series"]), 1)
            self.assertEqual(len(updated["series"][
                "mangas-fv-death-parade-ep05"]["episodes"]["1"]), 2)
            self.assertEqual(json.loads(path.read_text(encoding="utf8")),
                             original)

    def test_merge_protects_against_resurrected_aliases(self):
        older = history()
        merged_local = read_catalog_from_dict(older)
        merged = merge(older, merged_local, consolidate_anime=True)
        self.assertEqual(len(merged["series"]), 1)
        self.assertEqual(len(merged["legacy_series_records"]), 2)
        self.assertIn("death-parade", merged["series_aliases"])
        self.assertEqual(merged["series"][
            "mangas-fv-death-parade-ep05"]["episodes"]["1"]["6"]["message_id"],
            111)

    def test_tv_series_merges_remain_unmodified(self):
        older = history()
        merged = merge(older, {}, consolidate_anime=False)
        self.assertEqual(len(merged["series"]), 2)

    def test_dashboard_html_is_present_and_has_no_untrusted_html_insertion(self):
        html = (Path(__file__).resolve().parents[2] / "anime-dashboard.html")
        text = html.read_text(encoding="utf8")
        self.assertIn('id="chart"', text)
        self.assertIn('id="series-list"', text)
        self.assertIn('id="local-file"', text)
        self.assertIn("textContent", text)
        self.assertNotIn(".innerHTML", text)
        self.assertNotIn("https://t.me/", text)


def read_catalog_from_dict(value):
    from film_relay.anime_identity import consolidate_catalog
    return consolidate_catalog(value)[0]


if __name__ == "__main__":
    unittest.main()
