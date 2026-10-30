"""Public navigation and factual football analysis redesign regressions."""
import importlib.util
import json
import re
import unittest
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "public_site_builder_editorial", ROOT / "scripts/build_public_site.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
from scripts import editorial_bsd_bridge as editorial


class EditorialNavigationTests(unittest.TestCase):
    def test_all_public_routes_share_navigation_and_footer(self):
        pages = (
            "index.html", "pronos.html", "historique.html", "blog.html",
            "conseils.html", "conseil.html", "article.html", "infos.html",
            "bonus.html", "bookmakers.html", "contact.html",
        )
        for path in pages:
            with self.subTest(path=path):
                html = (ROOT / path).read_text(encoding="utf-8")
                self.assertEqual(html.count('class="mx-desktop-nav mx-primary-nav"'), 1)
                self.assertEqual(html.count('class="mx-premium-footer mx-unified-footer"'), 1)
                self.assertEqual(html.count('class="mx-footer-layout"'), 1)
                self.assertEqual(html.count('id="mx-current-year"'), 1)
                for target in ("index.html", "pronos.html", "historique.html",
                               "blog.html", "infos.html", "conseils.html",
                               "bonus.html", "contact.html"):
                    self.assertIn('href="' + target + '"', html)
                self.assertNotIn("© 2025", html)
                self.assertNotIn("Powered by", html)

    def test_mobile_menu_has_three_sections_and_five_quick_actions(self):
        content = (ROOT / "assets/js/menu.js").read_text(encoding="utf-8")
        self.assertIn("['Football', 'Découvrir', 'Informations']", content)
        self.assertIn("burger-menu-group-title", content)
        block = content.split("const bottomItems = [", 1)[1].split("];", 1)[0]
        self.assertEqual(block.count("name:"), 5)
        self.assertIn("name: 'Analyses'", content)

    def test_blog_follows_content_and_readability_rules(self):
        html = (ROOT / "blog.html").read_text(encoding="utf-8")
        script = (ROOT / "assets/js/main.js").read_text(encoding="utf-8")
        self.assertIn('id="blog-featured"', html)
        self.assertIn('id="blog-sort"', html)
        self.assertIn('id="blog-load-more"', html)
        self.assertEqual(html.count("data-blog-filter="), 4)
        self.assertNotIn('data-blog-filter="Transferts"', html)
        self.assertIn('blogViewState.visible += 9', script)
        self.assertIn('button.hidden = category !== "Tous"', script)
        self.assertIn("renderBlogFeatured()", script)
        self.assertIn("mx-reader-breadcrumb", script)
        self.assertIn("mx-related-grid", script)

    def test_factual_analysis_has_eight_sections_without_fake_statistics(self):
        match = {
            "id": "bsd:example-20261030",
            "source": "bsd",
            "event_date": "2026-10-31T18:00:00+00:00",
            "home_team": "Togo", "away_team": "Ghana",
            "league": "Compétition témoin",
            "status": "scheduled", "category": "pro",
            "recommendation_eligible": True,
            "prediction": {
                "selection_key": "1X", "type": "Double chance 1X",
                "confidence": 82,
            },
        }
        article = editorial.factual_article(match, datetime(2026, 10, 30, tzinfo=timezone.utc))
        for i in range(1, 9):
            self.assertRegex(article["content"], r"(?m)^## " + str(i) + r"\.")
        self.assertIn("82 %", article["content"])
        self.assertNotIn("Tirs cadrés : 9", article["content"])
        self.assertIn("moins de trois résultats vérifiés", article["content"])

        match["prediction"]["confidence"] = 78
        article = editorial.factual_article(match, datetime(2026, 10, 30, tzinfo=timezone.utc))
        self.assertNotIn("Sélection Pro/VIP publiée", article["content"])
        match["status"] = "finished"
        match["home_score"] = 2
        match["away_score"] = 1
        article = editorial.factual_article(match, datetime(2026, 10, 30, tzinfo=timezone.utc))
        self.assertIn("2 – 1", article["content"])
        self.assertNotIn("Sélection Pro/VIP publiée", article["content"])

    def test_private_history_enriches_form_and_h2h_without_future_leakage(self):
        current = {
            "id": "bsd:200", "source": "bsd",
            "event_date": "2026-10-30T18:00:00+00:00",
            "home_team": "Togo", "away_team": "Ghana",
            "home_team_id": 12, "away_team_id": 13,
            "league": "Coupe test", "status": "scheduled",
        }
        results = [
            {"id": "one", "status": "finished", "event_date": "2026-10-20T15:00:00Z",
             "home_team_id": 12, "away_team_id": 13, "home_score": 2, "away_score": 1},
            {"id": "two", "status": "finished", "event_date": "2026-10-11T15:00:00Z",
             "home_team_id": 13, "away_team_id": 12, "home_score": 1, "away_score": 1},
            {"id": "three", "status": "finished", "event_date": "2026-09-25T15:00:00Z",
             "home_team_id": 12, "away_team_id": 99, "home_score": 1, "away_score": 0},
            {"id": "four", "status": "finished", "event_date": "2026-09-21T15:00:00Z",
             "home_team_id": 13, "away_team_id": 88, "home_score": 3, "away_score": 0},
            {"id": "future", "status": "finished", "event_date": "2026-11-02T15:00:00Z",
             "home_team_id": 12, "away_team_id": 13, "home_score": 9, "away_score": 9},
            {"id": "unverified", "status": "scheduled", "event_date": "2026-10-21T15:00:00Z",
             "home_team_id": 12, "away_team_id": 13, "home_score": 5, "away_score": 0},
        ]
        generated = editorial.factual_article(
            current, datetime(2026, 10, 30, 17, tzinfo=timezone.utc), history=results)
        content = generated["content"]
        self.assertIn("Togo — 3 derniers matchs vérifiés disponibles", content)
        self.assertIn("2 victoire(s), 1 nul(s), 0 défaite(s)", content)
        self.assertIn("Ghana — 3 derniers matchs vérifiés disponibles", content)
        self.assertIn("Sur 2 confrontations terminées vérifiées", content)
        self.assertNotIn("9 but(s)", content)
        self.assertIn("Ghana — 3 derniers matchs vérifiés disponibles", content)
        self.assertIn("5 but(s) marqué(s)", content)
        self.assertNotIn("Sélection Pro/VIP publiée", content)
        # An absent archive must never lead to invented figures.
        missing = editorial.factual_article(
            current, datetime(2026, 10, 30, 17, tzinfo=timezone.utc), history=[])
        self.assertIn("moins de trois résultats vérifiés", missing["content"])
        self.assertIn("Moins de deux confrontations", missing["content"])

    def test_old_verified_fixture_is_enriched_without_rewriting_identity(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bsd").mkdir()
            previous = {
                "slug": "bsd-match-1234", "type": "match", "source": "bsd",
                "bsd_event_id": "1234", "date": "2026-09-30T12:00:00Z",
                "title": "Togo vs Ghana : analyse du match", "league": "Coupe test",
                "image_url": "assets/images/editorial/original.webp",
                "content": "# Togo – Ghana\\n**Marché identifié :** 1X.",
            }
            fixture = {
                "id": 1234, "status": "finished",
                "event_date": "2026-10-01T18:00:00+00:00",
                "home_team": {"id": 12, "name": "Togo"},
                "away_team": {"id": 13, "name": "Ghana"},
                "home_score": 1, "away_score": 0,
            }
            past = [
                {"id": 1, "status": "finished",
                 "event_date": "2026-09-25T12:00:00+00:00",
                 "home_team_id": "12", "away_team_id": "13",
                 "home_score": "2", "away_score": "0"},
                {"id": 2, "status": "finished",
                 "event_date": "2026-09-12T12:00:00+00:00",
                 "home_team_id": 13, "away_team_id": 12,
                 "home_score": 1, "away_score": 1},
                {"id": 3, "status": "finished",
                 "event_date": "2026-09-01T12:00:00+00:00",
                 "home_team_id": 12, "away_team_id": 99,
                 "home_score": 3, "away_score": 1},
            ]
            (root / "bsd/all_matches_bsd.json").write_text(
                json.dumps([fixture] + past), encoding="utf-8")
            (root / "articles.json").write_text(json.dumps([previous]), encoding="utf-8")
            (root / "data.json").write_text(json.dumps({
                "source": "bsd", "model_version": "bsd-v2-isolated", "matches": []
            }), encoding="utf-8")
            report = editorial.run(root=root, now=datetime(
                2026, 10, 30, 18, tzinfo=timezone.utc))
            self.assertEqual(report["enriched_existing"], 1)
            rows = json.loads((root / "articles.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["slug"], previous["slug"])
            self.assertEqual(rows[0]["date"], previous["date"])
            self.assertEqual(rows[0]["image_url"], previous["image_url"])
            self.assertIn("Sur 2 confrontations terminées vérifiées", rows[0]["content"])
            self.assertIn("2 victoire(s)", rows[0]["content"])
            self.assertNotIn("Sélection Pro/VIP publiée", rows[0]["content"])

    def test_old_articles_get_honest_structure_without_prematch_backdating(self):
        article = {
            "type": "match", "match": "Togo vs Ghana", "league": "Coupe test",
            "content": "# Togo – Ghana\n\n**Date et heure :** 30/10/2026 à 18h00.\n"
                       "**Marché identifié :** 1X.\n**Score final :** Togo 2 – 1 Ghana.",
        }
        text = builder.structure_legacy_match_article(article)
        for i in range(1, 9):
            self.assertIn("## " + str(i) + ".", text)
        self.assertIn("ne prouve pas", text)
        self.assertIn("2 – 1", text)
        self.assertNotIn("Sélection Pro/VIP publiée", text)


if __name__ == "__main__":
    unittest.main()
