"""Contract for publishing only authenticated client-side admin UI assets."""
from __future__ import annotations
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_builder", ROOT / "scripts" / "build_public_site.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
ADMIN_HTML = {"admin.html", "admin-supervision.html", "admin-dashboard.html", "admin-vip.html"}
ENTRY_JS = {"admin-real.js", "admin-shell.js", "admin-phase2.mjs", "admin-supervision.js"}
ADMIN_CSS = {"admin-premium.css", "admin-shell.css", "admin-phase1.css", "admin-phase2.css", "admin-home-reference.css", "admin-cms-editor.css"}
IMPORTS = re.compile(r"(?:\bfrom\s*|\bimport\s*|\bimport\s*\(\s*)['\"](\.[^'\"]+)['\"]")

class AdminPagesPublicationContract(unittest.TestCase):
    def test_pages_and_styles_in_allowlist(self):
        self.assertTrue(ADMIN_HTML <= BUILDER.PUBLIC_HTML)
        self.assertTrue(ADMIN_CSS <= BUILDER.PUBLIC_CSS)
        for name in ADMIN_HTML:
            source = ROOT / name
            self.assertTrue(source.is_file(), name)
            self.assertIn('name="robots" content="noindex,nofollow"', source.read_text(encoding="utf-8"))

    def test_js_import_graph_is_complete(self):
        queue = list(ENTRY_JS)
        scanned = set()
        while queue:
            name = queue.pop()
            if name in scanned:
                continue
            scanned.add(name)
            self.assertIn(name, BUILDER.PUBLIC_JS, name)
            file = ROOT / "assets" / "js" / name
            self.assertTrue(file.is_file(), name)
            text = file.read_text(encoding="utf-8")
            for child in IMPORTS.findall(text):
                relative = (file.parent / child.split("?")[0].split("#")[0]).resolve()
                self.assertTrue(relative.is_relative_to((ROOT / "assets" / "js").resolve()), child)
                queue.append(relative.name.split("?")[0].split("#")[0])
        self.assertIn("admin-phase2.mjs", scanned)
        self.assertIn("admin-public-markdown.mjs", scanned)
        self.assertIn("cms-block-editor.mjs", scanned)

    def test_premium_dashboard_artwork_and_no_stale_worker_cache(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-home-reference.css").read_text(encoding="utf-8")
        worker = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("assets/css/admin-home-reference.css", page)
        self.assertIn('id="admin-overview-summary"', page)
        self.assertIn('data-admin-ui="dashboard-premium-v3"', page)
        self.assertIn("admin-home-20261111-v3", page)
        self.assertIn("cache: 'no-store'", worker)
        self.assertIn("adminReferenceArt", worker)
        for name in ("admin-home-ball-reference.webp", "admin-home-lights-reference.webp"):
            asset = ROOT / "assets/images" / name
            self.assertTrue(asset.is_file(), name)
            self.assertGreater(asset.stat().st_size, 1000, name)
            self.assertIn(name, css)
        self.assertIn("fetch(request, { cache: 'no-store' })", worker)
        self.assertIn("adminPage || adminAsset", worker)

    def test_pronostics_v4_theme_and_read_only_controls(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        enhancer = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        self.assertIn("admin-phase2.css?v=20261111-pronos-v4", page)
        self.assertIn("ADMIN PRONOSTICS V4", css)
        self.assertIn("body.admin-shell #tab-pronostics .mx2-match-card", css)
        self.assertIn("body.admin-shell #tab-pronostics .admin-filter-row", css)
        self.assertIn("body.admin-shell #tab-pronostics .admin-pronostics-table-scroll", css)
        self.assertIn("body.admin-shell #tab-pronostics .mx2-segment-button.is-active", css)
        self.assertIn("body.admin-shell #tab-pronostics .mx2-team-logo", css)
        self.assertIn("renderPronosticsReadOnly", controller)
        for control in ("pDay", "pCat", "pSearch", "pRefresh", "pList"):
            self.assertIn('id="' + control + '"', controller)
        self.assertIn('["cards","Fiches"]', enhancer)
        self.assertIn('["table","Tableau"]', enhancer)

    def test_push_v4_styles_preserve_confirmed_send_flow(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        preview = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        self.assertIn("admin-phase2.css?v=20261111-push-v4", page)
        self.assertIn("ADMIN PUSH V4", css)
        for selector in (
            "#tab-push .mx2-push-layout",
            "#tab-push .mx2-push-preview",
            "#tab-push .mx2-push-compose",
            "#tab-push #push_send",
            "#tab-push #push_test",
            "#tab-push #push_schedule",
            "#tab-push .admin-pronostics-table-scroll",
        ):
            self.assertIn(selector, css)
        for control in (
            "push_audience", "push_user_wrap", "push_user_id",
            "push_schedule_at", "push_title", "push_body",
            "push_url", "push_tag", "push_new", "push_preview",
            "push_test", "push_schedule", "push_send",
            "push_history", "subs_list",
        ):
            self.assertIn('id="' + control + '"', controller)
        self.assertIn('option value="">Choisir les destinataires', controller)
        self.assertIn('if(!await adminConfirm(action', controller)
        self.assertIn('const update=()=>', preview)
        self.assertIn('deviceTitle.textContent', preview)

    def test_admin_pages_have_role_gate_and_no_embedded_secrets(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        supervisor = (ROOT / "assets/js/admin-supervision.js").read_text(encoding="utf-8")
        self.assertIn('id="loginCard"', page)
        self.assertIn('id="app"', page)
        self.assertIn('sb.rpc("is_admin")', controller)
        self.assertIn('sb.rpc("is_admin")', supervisor)
        for name in ENTRY_JS:
            script = (ROOT / "assets/js" / name).read_text(encoding="utf-8")
            self.assertNotRegex(script, r"(?:SUPABASE_SERVICE_ROLE_KEY|PRIVATE_KEY)\s*=\s*['\"][A-Za-z0-9]")

if __name__ == "__main__":
    unittest.main()
