"""Phase 3 acceptance checks for the daily return journey (static integration)."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DailyHubPhase3Tests(unittest.TestCase):
    def read(self,path):
        return (ROOT/path).read_text(encoding="utf-8")

    def test_public_page_is_exposed_and_connected(self):
        html=self.read("aujourdhui.html")
        for required in (
            'id="daily-fixtures"', 'id="daily-favorites"',
            'id="daily-changes"', 'id="daily-performance"',
            'id="daily-exact-scores"', 'id="daily-news"',
            'id="daily-reminder-download"', 'id="daily-push-enable"',
            'id="daily-push-disable"', 'id="daily-tip-body"',
            'assets/js/daily-hub.mjs', 'assets/js/pwa.js',
            'rel="manifest"', 'href="historique.html"',
            'href="confidentialite.html"'
        ):
            with self.subTest(required=required):
                self.assertIn(required,html)

    def test_home_mobile_menu_and_pwa_shortcut(self):
        home=self.read("index.html")
        menu=self.read("assets/js/menu.js")
        manifest=json.loads(self.read("manifest.json"))
        self.assertIn('href="aujourdhui.html"',home)
        self.assertIn("aujourdhui.html",menu)
        self.assertTrue(any(item.get("url")=="./aujourdhui.html"
            for item in manifest["shortcuts"]))

    def test_public_artifact_allowlist_and_service_worker(self):
        build=self.read("scripts/build_public_site.py")
        for path in ("aujourdhui.html","daily-hub.mjs","daily-utils.mjs",
                     "daily-audience.mjs","daily-hub.css"):
            self.assertIn('"'+path+'"',build)
        sw=self.read("service-worker.js")
        for asset in ("./aujourdhui.html","./assets/js/daily-hub.mjs",
                      "./assets/js/daily-utils.mjs",
                      "./assets/js/daily-audience.mjs",
                      "./assets/css/daily-hub.css"):
            self.assertIn(asset,sw)
        self.assertIn("v116-daily-hub",sw)
        self.assertIn("aujourdhui.html",self.read("sitemap.xml"))
        self.assertIn("admin-supervision.html",build)
        self.assertIn("assets/js/admin-supervision.js",build)

    def test_no_fake_winners_or_forced_notifications(self):
        frontend=self.read("assets/js/daily-hub.mjs")
        utils=self.read("assets/js/daily-utils.mjs")
        self.assertIn("Non validée",frontend)
        self.assertIn("resultState",frontend)
        self.assertIn("verified_double === false",utils)
        self.assertIn('function optInPush()',frontend)
        self.assertIn('function optOutPush()',frontend)
        self.assertIn('addEventListener("click"',frontend)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY",frontend)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY",self.read("assets/js/daily-audience.mjs"))
        self.assertNotIn("Promise.allSettled",frontend)
        self.assertIn("Les envois restent généraux",frontend)
        self.assertIn("RRULE:FREQ=DAILY",utils)

    def test_privacy_explains_local_data_and_no_guarantee(self):
        privacy=self.read("confidentialite.html")
        for snippet in ("Favoris, nouveautés", "stockage local", "calendrier",
                        "ne sont pas personnalisés", "notifications"):
            self.assertIn(snippet,privacy)

if __name__=="__main__":
    unittest.main()
