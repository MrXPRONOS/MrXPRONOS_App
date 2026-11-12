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
ADMIN_CSS = {"admin-premium.css", "admin-shell.css", "admin-phase1.css", "admin-phase2.css", "admin-home-reference.css", "admin-cms-editor.css", "admin-incidents-v4.css", "admin-health-v4.css"}
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
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
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
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
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

    def test_vip_v4_design_keeps_access_and_revoke_contract(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        enhancer = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertIn("ADMIN VIP V4", css)
        for selector in (
            "#tab-vip .mx2-vip-summary",
            "#tab-vip .mx2-vip-toolbar",
            "#tab-vip .mx2-vip-table",
            "#tab-vip #v_reset",
            "#tab-vip .mx2-vip-table [data-revoke]",
        ):
            self.assertIn(selector, css)
        self.assertIn('id="tab-vip"', page)
        for name in ("v_user", "v_ip", "v_days", "v_reset"):
            self.assertIn('id="' + name + '"', controller)
        self.assertIn('sb.rpc("admin_reset_vip"', controller)
        self.assertIn('sb.rpc("admin_revoke_vip"', controller)
        self.assertIn('if (!await adminConfirm("Créer ou réinitialiser cet accès VIP', controller)
        self.assertIn('if (!await adminConfirm("Désactiver l\'accès VIP', controller)
        self.assertIn('const stateOf=tr=>', enhancer)
        self.assertIn('["active","Actifs"]', enhancer)
        self.assertIn('["expired","Expirés"]', enhancer)
        self.assertIn('["disabled","Désactivés"]', enhancer)

    def test_articles_v4_visuals_and_cms_controls_are_retained(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        enhancer = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        blocks = (ROOT / "assets/js/cms-block-editor.mjs").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertIn("ADMIN ARTICLES V4", css)
        for selector in (
            "#tab-articles .admin-cms-editor-toggle",
            "#tab-articles .mx2-editor-preview",
            "#tab-articles .mx-cms-list-filters",
            "#tab-articles .mx2-content-card",
            "#tab-articles .mx-block-toolbar",
            "#tab-articles #a_save",
        ):
            self.assertIn(selector, css)
        for control in (
            "a_slug", "a_title", "a_image", "a_meta", "a_category",
            "a_tags", "a_content", "a_status", "a_active", "a_save",
        ):
            self.assertIn('id="' + control + '"', controller)
        for method in ("mountCmsBlockEditor", "mountCmsRevisionPanel",
                       "mountCmsListFilters", "mountCmsServerSearch",
                       "confirmCmsQuality"):
            self.assertIn(method, controller)
        self.assertIn('sb.from("cms_articles").upsert(payload)', controller)
        self.assertIn('const preview=elt("aside","mx2-editor-preview")', enhancer)
        self.assertIn('renderSafeCmsMarkdown', enhancer)
        self.assertIn('Aperçu de l\'article (non publié)', blocks)

    def test_conseils_v4_visuals_and_cms_controls_are_retained(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        enhancer = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        blocks = (ROOT / "assets/js/cms-block-editor.mjs").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertIn("ADMIN CONSEILS V4", css)
        for selector in (
            "#tab-conseils .admin-cms-editor-toggle",
            "#tab-conseils .mx2-editor-preview",
            "#tab-conseils .mx-cms-list-filters",
            "#tab-conseils .mx2-content-card",
            "#tab-conseils .mx-block-toolbar",
            "#tab-conseils #c_save",
        ):
            self.assertIn(selector, css)
        for control in (
            "c_slug", "c_title", "c_image", "c_category", "c_level",
            "c_tags", "c_content", "c_status", "c_active", "c_save",
        ):
            self.assertIn('id="' + control + '"', controller)
        for method in ("mountCmsBlockEditor", "mountCmsRevisionPanel",
                       "mountCmsListFilters", "mountCmsServerSearch",
                       "confirmCmsQuality"):
            self.assertIn(method, controller)
        self.assertIn('sb.from("cms_conseils").upsert(payload)', controller)
        self.assertIn('const preview=elt("aside","mx2-editor-preview")', enhancer)
        self.assertIn('renderSafeCmsMarkdown', enhancer)
        self.assertIn('Aperçu de l\'article (non publié)', blocks)

    def test_bonus_bookmakers_v4_design_and_cms_controls_are_retained(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertIn("ADMIN BONUS BOOKMAKERS V4", css)
        for selector in (
            "#tab-bonus > .card",
            "#tab-bonus .mx-cms-list-filters",
            "#tab-bonus :is([data-bonus-id],[data-book-id])",
            "#tab-bonus > .card :is(#b_save,#bk_save)",
        ):
            self.assertIn(selector, css)
        for control in (
            "b_bookmaker", "b_title", "b_description", "b_image", "b_link",
            "b_footer", "b_status", "b_start", "b_end", "b_active", "b_save",
            "bk_name", "bk_logo", "bk_url", "bk_description", "bk_status",
            "bk_active", "bk_save",
        ):
            self.assertIn('id="' + control + '"', controller)
        for method in (
            "mountCmsMediaFieldPicker", "mountCmsListFilters", "mountCmsServerSearch",
            "attachDuplicateButtons", "confirmCmsQuality",
        ):
            self.assertIn(method, controller)
        self.assertIn('sb.from("cms_bonus").upsert(payload)', controller)
        self.assertIn('sb.from("cms_bookmakers").upsert(payload)', controller)
        self.assertIn('loadCmsRows("cms_bonus")', controller)
        self.assertIn('loadCmsRows("cms_bookmakers")', controller)


    def test_media_v4_visual_contract_and_private_publish_workflow(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        library = (ROOT / "assets/js/cms-media-library.mjs").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertRegex(page, r'admin-real\.js\?v=[^"]+')
        self.assertIn("ADMIN MEDIATHEQUE V4", css)
        for selector in (
            "#tab-media > .card",
            "#tab-media .mx-cms-library",
            "#tab-media .mx-media-filters",
            "#tab-media .mx-media-grid",
            "#tab-media .mx-media-item-wrap",
        ):
            self.assertIn(selector, css)
        self.assertIn('id="tab-media"', page)
        self.assertIn('mountCmsMediaPicker(sb,intro,media=>', controller)
        self.assertIn('les fichiers restent privés', controller)
        self.assertIn('const PRIVATE_BUCKET="cms-drafts"', library)
        self.assertIn("await bucket.upload(path,transformed.file,opts)", library)
        self.assertIn('publishCmsMedia(sb,m.id)', library)
        self.assertIn('if(!confirm("Rendre ce média public', library)
        self.assertIn('wrapper.dataset.mediaState=m.is_private?"private":"published"', library)
        self.assertIn('status.setAttribute("role","status")', library)
        self.assertIn('isSafeCmsUrl(m.thumbUrl||m.url,"image")', library)
        self.assertIn('file.type="file";file.accept=', library)

    def test_informations_v4_visuals_and_cms_controls_are_retained(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        enhancer = (ROOT / "assets/js/admin-phase2.mjs").read_text(encoding="utf-8")
        self.assertRegex(page, r'admin-phase2\.css\?v=[^"]+')
        self.assertIn("admin-phase2.mjs?v=20261111-infos-v4", page)
        self.assertIn("ADMIN INFOS V4", css)
        for selector in (
            "#tab-infos .admin-cms-editor-toggle",
            "#tab-infos .mx2-editor-preview",
            "#tab-infos .mx-cms-list-filters",
            "#tab-infos .mx2-content-card",
            "#tab-infos .mx-block-toolbar",
            "#tab-infos #i_save",
        ):
            self.assertIn(selector, css)
        for control in (
            "i_title", "i_category", "i_image", "i_content",
            "i_status", "i_active", "i_save",
        ):
            self.assertIn('id="' + control + '"', controller)
        for method in (
            "mountCmsBlockEditor", "mountCmsRevisionPanel",
            "mountCmsListFilters", "mountCmsServerSearch",
            "mountCmsMediaFieldPicker", "confirmCmsQuality",
        ):
            self.assertIn(method, controller)
        self.assertIn('sb.from("cms_infos").upsert(payload)', controller)
        self.assertIn('else if(name==="infos")enhanceCms(root,"i");', enhancer)
        self.assertIn('const preview=elt("aside","mx2-editor-preview")', enhancer)
        self.assertIn('renderSafeCmsMarkdown', enhancer)


    def test_users_v4_visuals_and_role_permissions(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-phase2.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        users = (ROOT / "assets/js/admin-users.mjs").read_text(encoding="utf-8")
        self.assertIn("admin-phase2.css?v=20261111-users-v4", page)
        self.assertRegex(page, r'admin-real\.js\?v=[^"]+')
        self.assertIn("ADMIN UTILISATEURS V4", css)
        for selector in (
            "#tab-users .users-v4-summary", "#tab-users .users-v4-toolbar",
            "#tab-users #role-table", "#tab-users #role-save",
        ):
            self.assertIn(selector, css)
        for control in (
            "role-user-id", "role-kind", "role-active", "role-save", "role-table",
            "users-v4-search", "users-v4-role", "users-v4-state",
            "users-v4-total", "users-v4-active", "users-v4-disabled", "users-v4-counter",
        ):
            self.assertIn('id="' + control + '"', users)
        self.assertIn('import { mountAdminUsers } from "./admin-users.mjs?v=20261111-users-v4";', controller)
        self.assertIn('users:"users"', controller)
        self.assertIn('if(uid===self&&(!active||role!=="owner"))', users)
        self.assertIn('if(!await adminConfirm("Confirmer le rôle ', users)
        self.assertIn('sb.from("admin_users").upsert({', users)
        self.assertIn('sb.from("audit_log").insert({', users)
        self.assertIn('.limit(250)', users)
        self.assertIn('tr.dataset.userRole=row.access_role||"viewer"', users)
        self.assertIn('row.hidden=!visible;', users)


    def test_incidents_v4_visuals_filters_and_status_contract(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-incidents-v4.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        incidents = (ROOT / "assets/js/admin-incidents.mjs").read_text(encoding="utf-8")
        self.assertIn("admin-incidents-v4.css?v=20261112-incidents-v4", page)
        self.assertIn("admin-real.js?v=20261112-incidents-v4", page)
        self.assertIn("ADMIN INCIDENTS V4", css)
        for selector in (
            "#tab-incidents .incidents-v4-summary",
            "#tab-incidents .incidents-v4-toolbar",
            "#tab-incidents #incident-table",
            "#tab-incidents #incident-create",
        ):
            self.assertIn(selector, css)
        for field in (
            "incident-source", "incident-severity", "incident-filter", "incident-summary",
            "incident-create", "incident-refresh", "incident-more", "incident-table",
            "incidents-v4-open", "incidents-v4-ack", "incidents-v4-resolved",
            "incidents-v4-escalated", "incidents-v4-search",
            "incidents-v4-severity", "incidents-v4-count",
        ):
            self.assertIn('id="' + field + '"', incidents)
        self.assertIn('import { mountIncidentCenter } from "./admin-incidents.mjs?v=20261112-incidents-v4";', controller)
        self.assertIn('sb.from("admin_incidents").insert({', incidents)
        self.assertIn('sb.from("admin_incidents").update({', incidents)
        self.assertIn('sb.from("audit_log").insert({', incidents)
        self.assertIn('.range(offset,offset+99)', incidents)
        self.assertIn('tr.dataset.incidentState=row.status||"open"', incidents)
        self.assertIn('const visible=rows.filter(', incidents)
        self.assertIn('maybeSingle()', incidents)
        self.assertIn('role="status" aria-live="polite"', incidents)


    def test_health_v4_monitoring_styles_and_sources_are_preserved(self):
        page = (ROOT / "admin.html").read_text(encoding="utf-8")
        css = (ROOT / "assets/css/admin-health-v4.css").read_text(encoding="utf-8")
        controller = (ROOT / "assets/js/admin-real.js").read_text(encoding="utf-8")
        dashboard = (ROOT / "assets/js/admin-phase3.mjs").read_text(encoding="utf-8")
        cron = (ROOT / "assets/js/admin-cron-register.mjs").read_text(encoding="utf-8")
        self.assertIn("admin-health-v4.css?v=20261112-health-v4", page)
        self.assertIn("ADMIN HEALTH V4", css)
        for selector in (
            "#tab-health .mx3-stats", "#tab-health .mx3-automation-list",
            "#tab-health .mx3-health-filters", "#tab-health .mx2-responsive-table",
        ):
            self.assertIn(selector, css)
        self.assertIn('id="tab-health"', page)
        self.assertIn('sb.from("cron_runs").select("name,last_run_at,last_ok,meta")', controller)
        self.assertIn('enhanceHealthDashboard(root,{cron:cronEntries,runs});', controller)
        self.assertIn('mountCronJobRegister(sb,externalCronRoot,{', controller)
        self.assertIn('https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/runs', controller)
        self.assertIn('const cronState=item=>', dashboard)
        self.assertIn('const ghState=item=>', dashboard)
        self.assertIn('new Map()', dashboard)
        self.assertIn('readCronJobs(sb,config)', cron)
        self.assertIn('detectCronDuplicateConfigs(jobs)', cron)
        self.assertIn('cron-job.org indisponible : ', cron)

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
