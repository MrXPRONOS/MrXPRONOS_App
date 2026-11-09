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
ADMIN_CSS = {"admin-premium.css", "admin-shell.css", "admin-phase1.css", "admin-phase2.css", "admin-cms-editor.css"}
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
                relative = (file.parent / child).resolve()
                self.assertTrue(relative.is_relative_to((ROOT / "assets" / "js").resolve()), child)
                queue.append(relative.name)
        self.assertIn("admin-phase2.mjs", scanned)
        self.assertIn("admin-public-markdown.mjs", scanned)
        self.assertIn("cms-block-editor.mjs", scanned)

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
