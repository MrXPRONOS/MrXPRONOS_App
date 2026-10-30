"""Public navigation and factual football analysis redesign regressions."""
import importlib.util
import re
import unittest
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
            self.assertRegex(article["content"], r"(?m)^## " + str(i) + r"\\.")
        self.assertIn("82 %", article["content"])
        self.assertNotIn("Tirs cadrés : 9", article["content"])
        self.assertIn("ne sont pas suffisamment documentés", article["content"])

        match["prediction"]["confidence"] = 78
        article = editorial.factual_article(match, datetime(2026, 10, 30, tzinfo=timezone.utc))
        self.assertNotIn("Sélection Pro/VIP publiée", article["content"])
        match["status"] = "finished"
        match["home_score"] = 2
        match["away_score"] = 1
        article = editorial.factual_article(match, datetime(2026, 10, 30, tzinfo=timezone.utc))
        self.assertIn("2 – 1", article["content"])
        self.assertNotIn("Sélection Pro/VIP publiée", article["content"])

    def test_old_articles_get_honest_structure_without_prematch_backdating(self):
        article = {
            "type": "match", "match": "Togo vs Ghana", "league": "Coupe test",
            "content": "# Togo – Ghana\\n\\n**Date et heure :** 30/10/2026 à 18h00.\\n"
                       "**Marché identifié :** 1X.\\n**Score final :** Togo 2 – 1 Ghana.",
        }
        text = builder.structure_legacy_match_article(article)
        for i in range(1, 9):
            self.assertIn("## " + str(i) + ".", text)
        self.assertIn("ne prouve pas", text)
        self.assertIn("2 – 1", text)
        self.assertNotIn("Sélection Pro/VIP publiée", text)


if __name__ == "__main__":
    unittest.main()
