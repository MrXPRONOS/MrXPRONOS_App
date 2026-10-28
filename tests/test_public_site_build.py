"""Tests for public-only GitHub Pages packaging."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

SPEC = importlib.util.spec_from_file_location(
    "build_public_site", Path(__file__).resolve().parents[1] / "scripts" / "build_public_site.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PublicBuildTest(TestCase):
    def test_no_workflow_publishes_repository_root(self):
        workflows = (Path(__file__).resolve().parents[1] / ".github/workflows").glob("*.yml")
        import re
        unsafe = []
        for path in workflows:
            raw = path.read_text(encoding="utf-8")
            if re.search(r"(?m)^\s*publish_dir:\s*\./\s*$", raw):
                unsafe.append(path.name)
        self.assertEqual([], unsafe, "Unsafe full-repository GitHub Pages publishing found")

    def test_match_article_public_copy_removes_engine_naming(self):
        sample = (
            "FC A vs FC B : fiche match BSD V2\n"
            "## Signal calculé par le moteur BSD V2\n"
            "**Source des données :** BSD V2, identifiant 123.\n"
            "**Statut :** rencontre selon le dernier flux BSD disponible.\n"
        )
        cleaned = module.clean_match_article_text(sample)
        self.assertNotIn("BSD", cleaned)
        self.assertNotIn("moteur", cleaned)
        self.assertNotIn("identifiant 123", cleaned)
        self.assertIn("analyse du match", cleaned)

    def test_strict_public_feed_projects_only_product_fields(self):
        raw = {
            "source": "bsd",
            "policy_version": "bsd-v2-policy-internal",
            "model_version": "bsd-v2-isolated",
            "diagnostics": {"private": True},
            "performance_tracker": {"training_score": 99},
            "retired_predictions": [{"internal": True}],
            "generated_at": "2026-10-28T17:00:00Z",
            "matches": [
                {
                    "id": "bsd:alpha", "home_team": "Alpha", "away_team": "Beta",
                    "category": "pro", "final_score": 88,
                    "badge": "BSD V2", "signal_tier": "PREMIUM",
                    "policy_version": "bsd-v2", "publication_audit": {"debug": True},
                    "recommendation_eligible": True, "is_finished": False,
                    "prediction": {
                        "label": "Over 2.5", "confidence": 81, "odds": 1.7,
                        "selection_key": "OVER_25", "estimated_odds": False,
                        "calibration_samples": 2000, "policy_version": "bsd-v2",
                        "fair_odds": 1.2, "odds_source": "provider-private",
                    },
                },
                {
                    "id": "bsd:beta", "home_team": "Gamma", "away_team": "Delta",
                    "category": "vip", "final_score": 93,
                    "prediction": {"label": "1X", "confidence": 83, "odds": 1.4},
                },
            ],
        }
        public = module.public_copy(raw)
        self.assertEqual(len(public["matches"]), 2)
        self.assertEqual(public["matches"][1]["display_rank"], 1)
        self.assertEqual(public["matches"][0]["display_rank"], 2)
        self.assertEqual(public, module.public_copy(raw))
        self.assertTrue(public["matches"][0]["id"].startswith("match-"))
        self.assertNotIn("bsd", public["matches"][0]["id"])
        serialized = json.dumps(public).lower()
        for forbidden in ("bsd", "policy_version", "publication_audit",
                          "signal_tier", "calibration_samples", "fair_odds",
                          "performance_tracker", "retired_predictions",
                          "final_score", "xpronos_score", "odds_source", "diagnostics"):
            self.assertNotIn(forbidden, serialized, forbidden)
        self.assertEqual(public["matches"][0]["prediction"]["confidence"], 81)
        self.assertEqual(public["matches"][0]["prediction"]["odds"], 1.7)
        self.assertFalse(public["matches"][0]["prediction"]["estimated_odds"])
        self.assertTrue(public["matches"][0]["recommendation_eligible"])

    def test_unlisted_future_model_fields_cannot_leak(self):
        data = {"generated_at": "2026-10-28", "matches": [
            {"id": "event-one", "category": "vip",
             "internal_new_secret": "token", "future_model_hash": "private",
             "prediction": {"type": "1X", "confidence": 88,
                            "future_provider_token": "private-secret"}}
        ]}
        public = module.public_copy(data)
        self.assertNotIn("internal_new_secret", public["matches"][0])
        self.assertNotIn("future_model_hash", public["matches"][0])
        self.assertNotIn("future_provider_token", public["matches"][0]["prediction"])

    def test_private_files_not_exported_and_predictions_kept(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "assets/js").mkdir(parents=True)
            (root / "assets/data/private").mkdir(parents=True)
            (root / "bsd").mkdir(parents=True)
            (root / "scripts").mkdir(parents=True)
            for name in ("index.html", "pronos.html", "historique.html", "live.html"):
                (root / name).write_text("<html><body>Public</body></html>")
            (root / "assets/js/main.js").write_text("console.log('public')", encoding="utf-8")
            (root / "assets/data/private/secret.json").write_text('{"secret":true}')
            (root / "bsd/quality_report.json").write_text('{"private":true}')
            (root / "model_meta.json").write_text('{"trained_at":1}')
            (root / "footnews.json").write_text("[]", encoding="utf-8")
            data = {
                "source": "bsd", "model_version": "bsd-v2-isolated",
                "diagnostics": {"provider": "internal"},
                "model_odds_observations": [{"debug": True}],
                "generated_at": "2026-10-28T00:00:00Z",
                "matches": [{"id": "1", "category": "pro",
                             "source": "bsd", "recommendation_eligible": True,
                             "multisource_verification": {"debug": True},
                             "prediction": {"type": "Over 2.5", "confidence": 82,
                                            "odds": 1.61, "odds_source": "pinnwire"}}],
            }
            (root / "data.json").write_text(json.dumps(data), encoding="utf-8")
            old = root / "_previous_pages" / "assets/images/footnews"
            old.mkdir(parents=True)
            (old / "legacy.webp").write_bytes(b"webp")
            original_root = module.ROOT
            try:
                module.ROOT = root
                module.stage_site(root / "_public_site", root / "_previous_pages")
            finally:
                module.ROOT = original_root
            result = root / "_public_site"
            self.assertTrue((result / "index.html").exists())
            self.assertTrue((result / "live.html").exists())
            self.assertTrue((result / "assets/images/footnews/legacy.webp").exists())
            self.assertFalse((result / "bsd").exists())
            self.assertFalse((result / "model_meta.json").exists())
            self.assertFalse((result / "assets/data/private").exists())
            public = json.loads((result / "data.json").read_text(encoding="utf-8"))
            self.assertNotIn("source", public)
            self.assertNotIn("diagnostics", public)
            self.assertNotIn("model_odds_observations", public)
            self.assertEqual(public["matches"][0]["prediction"]["confidence"], 82)
            self.assertEqual(public["matches"][0]["prediction"]["odds"], 1.61)
            self.assertNotIn("odds_source", public["matches"][0]["prediction"])
            self.assertTrue(public["matches"][0]["recommendation_eligible"])
