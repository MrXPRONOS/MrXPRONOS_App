"""Phase 2 PWA install checks: source-level contracts and public artifact rules."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PwaInstallPhase2Tests(unittest.TestCase):
    def test_public_routes_have_manifest_and_install_controls(self):
        for path in (
            "index.html", "pronos.html", "historique.html", "blog.html",
            "conseils.html", "infos.html", "bonus.html", "scores-exacts.html",
            "article.html", "conseil.html", "contact.html",
        ):
            with self.subTest(path=path):
                html = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("assets/js/pwa.js", html)
                self.assertIn('id="install-app"', html)
                self.assertIn('rel="manifest"', html)

    def test_home_onboarding_is_voluntary(self):
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="mx-install-panel"', home)
        self.assertIn('data-mx-install-surface="home"', home)
        self.assertIn("Installation facultative", home)

    def test_prompt_is_directly_user_initiated_and_ios_not_forced(self):
        pwa = (ROOT / "assets/js/pwa.js").read_text(encoding="utf-8")
        main = (ROOT / "assets/js/main.js").read_text(encoding="utf-8")
        self.assertIn('button.addEventListener("click"', pwa)
        self.assertIn("await prompt.prompt()", pwa)
        self.assertIn('window.addEventListener("beforeinstallprompt"', pwa)
        self.assertIn('window.addEventListener("appinstalled"', pwa)
        self.assertNotIn('localStorage.getItem("mx_pwa_installed") === "true"', pwa)
        self.assertNotIn("    showIosGuideIfNeeded();", main)
        self.assertIn("p.inApp", pwa)
        self.assertIn("p.isIOS", pwa)
        self.assertIn('aria-modal="true"', pwa)

    def test_telemetry_is_idempotent_and_private(self):
        pwa = (ROOT / "assets/js/pwa.js").read_text(encoding="utf-8")
        client = (ROOT / "assets/js/pwa-telemetry.mjs").read_text(encoding="utf-8")
        migration = (ROOT / "supabase/migrations/20261106202916_pwa_install_funnel_v2.sql").read_text(encoding="utf-8")
        self.assertIn("mx_pwa_install_events_v2", pwa)
        self.assertIn("mx_pwa_install_events_v2", client)
        self.assertIn("track_pwa_install_event_v2", client)
        self.assertIn("event_id", client)
        self.assertIn("on conflict do nothing", migration.lower())
        self.assertIn("enable row level security", migration.lower())
        self.assertIn("public.is_admin()", migration)
        self.assertIn("grant execute on function public.admin_pwa_install_funnel_v2(integer)", migration)

    def test_public_artifact_whitelist_and_private_admin(self):
        packaging = (ROOT / "scripts/build_public_site.py").read_text(encoding="utf-8")
        self.assertIn('"pwa-telemetry.mjs"', packaging)
        self.assertIn('"confidentialite.html"', packaging)
        self.assertIn('"admin-supervision.html"', packaging)
        self.assertIn('"assets/js/admin-supervision.js"', packaging)
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["id"], "./")
        self.assertEqual(manifest["scope"], "./")
        self.assertTrue(manifest["icons"])
        sw = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("./assets/js/pwa-telemetry.mjs", sw)
        self.assertIn("const VERSION = ", sw)
        self.assertIn("./assets/js/pwa-telemetry.mjs", sw)

    def test_public_metrics_login_is_protected_without_admin_bundle(self):
        html = (ROOT / "statistiques-installation.html").read_text(encoding="utf-8")
        js = (ROOT / "assets/js/installation-analytics.mjs").read_text(encoding="utf-8")
        build = (ROOT / "scripts/build_public_site.py").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', html)
        self.assertIn('id="dashboard" hidden', html)
        self.assertIn('id="login-panel" hidden', html)
        self.assertIn('sb.rpc("is_admin")', js)
        self.assertIn('sb.rpc("admin_pwa_install_funnel_v2"', js)
        self.assertIn('createClient(supabaseUrl, supabaseAnonKey)', js)
        self.assertNotIn("service_role", js)
        self.assertIn('"statistiques-installation.html"', build)
        self.assertIn('"installation-analytics.mjs"', build)

    def test_admin_report_and_privacy_disclosure(self):
        dashboard = (ROOT / "admin-supervision.html").read_text(encoding="utf-8")
        script = (ROOT / "assets/js/admin-supervision.js").read_text(encoding="utf-8")
        privacy = (ROOT / "confidentialite.html").read_text(encoding="utf-8")
        self.assertIn("pwa-install-funnel", dashboard)
        self.assertIn("admin_pwa_install_funnel_v2", script)
        self.assertIn("appinstalled", privacy)
        self.assertIn("pseudonymisé", privacy)


if __name__ == "__main__":
    unittest.main()
