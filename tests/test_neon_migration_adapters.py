#!/usr/bin/env python3
"""Offline regression checks for the Supabase -> Neon importer migrations."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILES={
    "future":"scripts/api_football_scheduled_fixtures.py",
    "live":"scripts/api_football_live_stats.py",
}
WORKFLOWS={
    "future":".github/workflows/api-football-scheduled-fixtures.yml",
    "live":".github/workflows/enrich-live-market-statistics.yml",
}

class NeonImportContract(unittest.TestCase):
    def test_syntax_valid(self):
        for p in FILES.values():
            with self.subTest(file=p):
                ast.parse((ROOT/p).read_text(encoding="utf-8"),filename=p)
    def test_no_supabase_runtime(self):
        for p in [*FILES.values(),*WORKFLOWS.values()]:
            with self.subTest(file=p):
                content=(ROOT/p).read_text(encoding="utf-8")
                self.assertNotIn("SUPABASE_URL",content)
                self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY",content)
                self.assertNotIn("/rest/v1/",content)
                self.assertIn("NEON_DATABASE_URL",content)
    def test_upsert_preserves_ids(self):
        for p in FILES.values():
            with self.subTest(file=p):
                content=(ROOT/p).read_text(encoding="utf-8")
                self.assertIn("ON CONFLICT",content)
                self.assertIn("psycopg",content)
    def test_fixture_json_kept(self):
        code=(ROOT/FILES["future"]).read_text(encoding="utf-8")
        self.assertIn('Jsonb(row["fixture"])',code)
        self.assertIn('row["source_names"]',code)
    def test_live_provider_cache_and_market_stats(self):
        code=(ROOT/FILES["live"]).read_text(encoding="utf-8")
        for tab in ("live_stats_merged","live_stats_sources","live_provider_probe_cache"):
            self.assertIn(tab,code)
        self.assertIn('Jsonb(row["stats_json"])',code)
        self.assertIn('Jsonb(row["raw_json"])',code)

if __name__=="__main__":
    unittest.main()
