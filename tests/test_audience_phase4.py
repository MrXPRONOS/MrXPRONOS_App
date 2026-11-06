"""Phase 4: safety and integration contracts for analytics-only admin panel."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Phase4Contracts(unittest.TestCase):
    def load(self,path):
        return (ROOT/path).read_text(encoding="utf-8")
    def test_admin_dashboard_has_four_tabs_and_server_gate(self):
        html=self.load("statistiques-audience.html")
        js=self.load("assets/js/audience-dashboard.mjs")
        for name in ("audience","retention","installation","acquisition"):
            self.assertIn('id="tab-'+name+'"',html)
            self.assertIn('id="panel-'+name+'"',html)
            self.assertIn('role="tabpanel"',html)
        for name in ("kpi-dau","kpi-wau","kpi-mau","ret-j1","ret-j7","ret-j30",
                     "source-rows","campaign-rows","daily-rows","data-note","quality-gaps"):
            self.assertIn('id="'+name+'"',html)
        self.assertIn('id="dashboard" hidden',html)
        self.assertIn('sb.rpc("is_admin")',js)
        self.assertIn('sb.rpc("admin_audience_dashboard_v1"',js)
        self.assertIn('sb.rpc("admin_pwa_install_funnel_v2"',js)
        self.assertNotIn("service_role",js.lower())
        self.assertIn("csvCell",js)
        self.assertIn('"—"',js)

    def test_sources_do_not_send_urls_referrers_or_secrets(self):
        attribution=self.load("assets/js/acquisition-attribution.mjs")
        self.assertIn("classifyLanding",attribution)
        self.assertIn("document.referrer",attribution)
        self.assertIn('p_channel:item.channel',attribution)
        self.assertIn('p_campaign:item.campaign',attribution)
        self.assertNotIn('p_referrer:',attribution)
        self.assertNotIn('p_url:',attribution)
        self.assertNotIn('SUPABASE_SERVICE_ROLE_KEY',attribution)
        self.assertIn('mx_acquisition_tab_v1',attribution)
        self.assertIn('event_id',attribution)
        self.assertIn('acquisition-attribution.mjs',self.load("assets/js/pwa.js"))

    def test_migration_limits_all_public_data_reads(self):
        sql=self.load("supabase/migrations/20261106223900_audience_analytics_phase4.sql").lower()
        self.assertIn("enable row level security",sql)
        self.assertIn("revoke all on table public.analytics_acquisition_events_v1",sql)
        self.assertIn("grant execute on function public.track_acquisition_v1",sql)
        self.assertIn("grant execute on function public.admin_audience_dashboard_v1",sql)
        self.assertIn("if not public.is_admin() then",sql)
        self.assertIn("on conflict(event_id) do nothing",sql)
        self.assertIn("visit_day=f.day+30",sql)
        self.assertIn("day<=v_today-30",sql)
        self.assertIn("unattributed",sql)
        self.assertNotIn("create policy",sql)

    def test_public_only_package_and_privacy(self):
        package=self.load("scripts/build_public_site.py")
        for name in ("statistiques-audience.html","acquisition-attribution.mjs",
                     "audience-dashboard.mjs","audience-analytics.css"):
            self.assertIn('"'+name+'"',package)
        self.assertIn('"admin-supervision.html"',package)
        self.assertIn('"assets/js/admin-supervision.js"',package)
        sw=self.load("service-worker.js")
        self.assertIn("v118-audience-analytics",sw)
        self.assertIn("./assets/js/acquisition-attribution.mjs",sw)
        self.assertNotIn("'./statistiques-audience.html'",sw)
        privacy=self.load("confidentialite.html")
        self.assertIn("canaux d’acquisition",privacy)
        self.assertIn("J+1",privacy)
        self.assertIn("les adresses IP",privacy)

if __name__=="__main__":unittest.main()
