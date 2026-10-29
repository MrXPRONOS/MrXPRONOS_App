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
    def test_reject_invalid_public_matches_and_all_selections(self):
        valid = {
            "id": "alpha", "category": "pro",
            "recommendation_eligible": True,
            "prediction": {"confidence": 85, "odds": 1.5},
            "predictions": [{"confidence": 79, "odds": 1.4}],
        }
        scenarios = (
            {"category": "simple"},
            {"category": "other"},
            {"recommendation_eligible": False},
            {"prediction": {"confidence": 78.9}},
            {"prediction": {"confidence": 101}},
            {"prediction": {"confidence": float("nan")}},
            {"predictions": [{"confidence": 78.5}]},
            {"predictions": [{"confidence": 81, "recommendation_eligible": False}]},
        )
        for patch in scenarios:
            with self.subTest(patch=str(patch)):
                match = {**valid, **patch}
                with self.assertRaises(ValueError):
                    module.public_copy({"generated_at": "2026-10-29", "matches": [match]})
        self.assertEqual(
            module.public_copy({"matches": [valid]})["matches"][0]["category"], "pro"
        )

    def test_public_editorial_image_aliases_keep_legacy_links(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("index.html", "pronos.html", "live.html"):
                (root / name).write_text("<html>Public</html>", encoding="utf-8")
            original = root / "assets/images/editorial/match-bsd-match-123-tag-og.webp"
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(b"image data")
            (root / "assets/js").mkdir(parents=True)
            (root / "assets/js/main.js").write_text("console.log(1)")
            (root / "footnews.json").write_text("[]")
            (root / "data.json").write_text(json.dumps({"matches": [{
                "id": "alpha", "category": "pro",
                "prediction": {"confidence": 82, "odds": 1.6}
            }]}))
            (root / "articles.json").write_text(json.dumps([{
                "slug": "bsd-match-123", "type": "match", "source": "bsd",
                "title": "Alpha vs Beta : fiche match BSD V2",
                "image_url": str(original.relative_to(root)),
                "og_image": str(original.relative_to(root)),
            }]))
            html = root / "articles/bsd-match-123/index.html"
            html.parent.mkdir(parents=True)
            html.write_text('<meta property="og:image" content="' +
                            str(original.relative_to(root)) +
                            '"><a href="article.html?slug=bsd-match-123">BSD V2</a>')
            former = module.ROOT
            try:
                module.ROOT = root
                module.stage_site(root / "_public_site", None)
            finally:
                module.ROOT = former
            output = root / "_public_site"
            alias = output / "assets/images/editorial/match-123-tag-og.webp"
            self.assertEqual(alias.read_bytes(), b"image data")
            self.assertTrue((output / original.relative_to(root)).is_file())
            published = json.loads((output / "articles.json").read_text())
            self.assertEqual(published[0]["image_url"], str(alias.relative_to(output)))
            self.assertEqual(published[0]["og_image"], str(alias.relative_to(output)))
            meta = (output / "articles/match-123/index.html").read_text()
            self.assertIn("match-123-tag-og.webp", meta)
            self.assertNotIn("match-bsd-match-", meta)

    def test_paused_live_and_assistant_are_hidden_without_removing_sources(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("index.html", "pronos.html"):
                (root / name).write_text(
                    '<html><head></head><body><script defer src="assets/js/assistant.js?v=old"></script></body></html>',
                    encoding="utf-8",
                )
            live = root / "live.html"
            live.write_text("<html><head></head><body>LIVE engine intact</body></html>", encoding="utf-8")
            old_live_source = live.read_text(encoding="utf-8")
            js = root / "assets/js"
            js.mkdir(parents=True)
            (js / "main.js").write_text("console.log('site');", encoding="utf-8")
            (js / "assistant.js").write_text("console.log('widget is preserved');", encoding="utf-8")
            (root / "footnews.json").write_text("[]", encoding="utf-8")
            (root / "data.json").write_text(json.dumps({"matches": [
                {"id": "id-1", "category": "vip", "prediction": {"confidence": 79, "odds": 1.5}}
            ]}), encoding="utf-8")
            (root / "sitemap.xml").write_text(
                '<urlset><url><loc>https://example.com/prono-live/</loc></url>'
                '<url><loc>https://example.com/pronos.html</loc></url></urlset>',
                encoding="utf-8",
            )
            old_root = module.ROOT
            try:
                module.ROOT = root
                module.stage_site(root / "_public_site", None)
            finally:
                module.ROOT = old_root
            output = root / "_public_site"
            self.assertNotIn("assistant.js", (output / "index.html").read_text())
            self.assertNotIn("assistant.js", (output / "pronos.html").read_text())
            self.assertFalse((output / "assets/js/assistant.js").exists())
            self.assertFalse((output / "live.html").exists())
            self.assertEqual(live.read_text(encoding="utf-8"), old_live_source)
            sitemap = (output / "sitemap.xml").read_text()
            self.assertNotIn("prono-live/", sitemap)
            self.assertIn("pronos.html", sitemap)

    def test_public_artifact_excludes_admin_telemetry_and_generator_prompts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("index.html", "pronos.html", "admin.html",
                         "admin-supervision.html", "telegram-analytics.html",
                         "live.html", "threads-callback.html"):
                (root / name).write_text(
                    '<html><script src="assets/js/web-vitals-monitor.js?v=old"></script></html>',
                    encoding="utf-8",
                )
            js = root / "assets/js"
            css = root / "assets/css"
            js.mkdir(parents=True)
            css.mkdir(parents=True)
            for name in ("main.js", "cms-url-guard.mjs", "assistant.js",
                         "actu-foot-neon.js", "admin-real.js", "web-vitals-monitor.js"):
                (js / name).write_text("console.log('source unchanged')", encoding="utf-8")
            for name in ("style.css", "admin-premium.css", "live-premium.css"):
                (css / name).write_text("body { color: white }", encoding="utf-8")
            (root / "footnews.json").write_text(json.dumps([{
                "title": "Football", "summary": "Une actualité", "source": "Journal sportif",
                "source_url": "https://example.org/football",
                "espn_verification": {"url": "https://www.espn.com/"},
                "quality_sources": [{"provider": "internal", "token": "hidden"}],
                "source_feed": "internal", "editorial_score": 99, "telegram_summary": "draft",
                "provider": {"private": "secret"}, "raw_data": {"secret": True},
            }]), encoding="utf-8")
            (root / "evergreen_topics.json").write_text(
                json.dumps({"topics": [{"angle": "INTERNAL GENERATOR PROMPT"}]}),
                encoding="utf-8",
            )
            (root / "historical_scores.json").write_text("[]", encoding="utf-8")
            (root / "articles.json").write_text(json.dumps([{
                "slug": "public-article", "title": "Article public", "content": "Contenu",
                "internal_notes": "private", "source_feed": "internal",
                "editorial_score": 42, "author": "Mr XPRONOS",
            }, {
                "slug": "draft", "title": "Brouillon caché", "active": False,
                "internal_notes": "private",
            }]), encoding="utf-8")
            (root / "data.json").write_text(json.dumps({"matches": [{
                "id": "match-1", "category": "pro",
                "prediction": {"type": "1X", "confidence": 82},
            }]}), encoding="utf-8")
            old_root = module.ROOT
            try:
                module.ROOT = root
                module.stage_site(root / "_public_site", None)
            finally:
                module.ROOT = old_root
            output = root / "_public_site"
            for name in ("admin.html", "admin-supervision.html", "telegram-analytics.html",
                         "live.html", "threads-callback.html", "evergreen_topics.json",
                         "historical_scores.json"):
                self.assertFalse((output / name).exists(), name)
            for name in ("assistant.js", "actu-foot-neon.js", "admin-real.js",
                         "web-vitals-monitor.js"):
                self.assertFalse((output / "assets/js" / name).exists(), name)
            self.assertTrue((output / "assets/js/cms-url-guard.mjs").exists())
            self.assertTrue((output / "assets/css/style.css").exists())
            self.assertFalse((output / "assets/css/admin-premium.css").exists())
            self.assertFalse((output / "assets/css/live-premium.css").exists())
            self.assertNotIn("web-vitals-monitor.js",
                             (output / "index.html").read_text(encoding="utf-8"))
            self.assertEqual((root / "evergreen_topics.json").read_text(encoding="utf-8"),
                             json.dumps({"topics": [{"angle": "INTERNAL GENERATOR PROMPT"}]}))
            news = json.loads((output / "footnews.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(news["source"], "Journal sportif")
            self.assertEqual(news["source_url"], "https://example.org/football")
            for private_key in ("espn_verification", "quality_sources", "source_feed",
                                "editorial_score", "telegram_summary", "provider",
                                "raw_data"):
                self.assertNotIn(private_key, news)
            articles = json.loads((output / "articles.json").read_text(encoding="utf-8"))
            self.assertEqual(len(articles), 1)
            self.assertEqual(articles[0]["title"], "Article public")
            self.assertNotIn("internal_notes", articles[0])
            self.assertNotIn("source_feed", articles[0])
            self.assertNotIn("editorial_score", articles[0])
            self.assertTrue((root / "admin.html").exists())

    def test_public_navigation_no_longer_promotes_paused_live(self):
        root = Path(__file__).resolve().parents[1]
        index = (root / "index.html").read_text(encoding="utf-8")
        mobile = (root / "assets/js/menu.js").read_text(encoding="utf-8")
        share = (root / "assets/js/home-premium.js").read_text(encoding="utf-8")
        sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
        generator = (root / "generate_sitemap.py").read_text(encoding="utf-8")
        for source in (index, mobile, share):
            self.assertNotIn('href="live.html"', source)
            self.assertNotIn('url: \'live.html\'', source)
            self.assertNotIn("nos sélections LIVE", source)
        self.assertNotIn("prono-live/", sitemap)
        self.assertNotIn('"prono-live/":', generator)
        self.assertIn('href="historique.html"', index)
        self.assertIn("icon-history.webp", mobile)

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
            (root / "articles.json").write_text(json.dumps([{
                "slug": "bsd-match-123", "type": "match", "source": "bsd",
                "title": "Alpha vs Beta : fiche match BSD V2",
                "content": "## Signal calculé par le moteur BSD V2",
                "bsd_event_id": "123", "editorial_reasons": ["internal"]
            }]), encoding="utf-8")
            redirect = root / "articles/bsd-match-123/index.html"
            redirect.parent.mkdir(parents=True)
            redirect.write_text(
                '<html><title>Alpha vs Beta : fiche match BSD V2</title>'
                '<a href="/articles/bsd-match-123/">BSD V2</a>'
                '<meta http-equiv="refresh" content="0;url=article.html?slug=bsd-match-123"></html>',
                encoding="utf-8",
            )
            (root / "sitemap.xml").write_text(
                '<loc>https://example.org/articles/bsd-match-123/</loc>', encoding="utf-8"
            )

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
            self.assertFalse((result / "live.html").exists())
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
            articles = json.loads((result / "articles.json").read_text(encoding="utf-8"))
            self.assertEqual(articles[0]["slug"], "match-123")
            self.assertEqual(articles[0]["title"], "Alpha vs Beta : analyse du match")
            self.assertNotIn("bsd_event_id", articles[0])
            self.assertNotIn("BSD", articles[0]["content"])
            self.assertTrue((result / "articles/match-123/index.html").exists())
            new_redirect = (result / "articles/match-123/index.html").read_text(encoding="utf-8")
            self.assertIn("slug=match-123", new_redirect)
            self.assertNotIn("BSD V2", new_redirect)
            self.assertIn("articles/match-123", (result / "sitemap.xml").read_text(encoding="utf-8"))

