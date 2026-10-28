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
