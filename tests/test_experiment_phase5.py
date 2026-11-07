from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class Phase5Experiments(unittest.TestCase):
    def read(self,p):return (ROOT/p).read_text(encoding="utf-8")
    def test_private_sql_and_stable_server_bucketing(self):
        sql=self.read("supabase/migrations/20261107020805_experiments_phase5.sql")
        for phrase in (
            "experiment_flags_v1","experiment_participants_v1","experiment_admin_actions_v1",
            "enable row level security","from public,anon,authenticated",
            "if not public.is_admin() then",
            "create or replace function public.experiment_variant_v1",
            "create or replace function public.track_experiment_v1",
            "create or replace function public.admin_experiment_report_v1",
            "create or replace function public.admin_set_experiment_v1",
            "get_byte(decode(md5(v_salt", "p_kind not in ('exposure','conversion')",
            "on conflict do nothing", "interval '7 days'", "converted_at is null",
            "matured_exposed", "matured_converted", "auth.uid()"):
            self.assertIn(phrase,sql)
        self.assertIn("enabled boolean not null default false",sql)
        self.assertNotIn("grant select on public.experiment",sql.lower())
    def test_dashboard_integrated_and_safe(self):
        dashboard=self.read("statistiques-audience.html")
        js=self.read("assets/js/audience-dashboard.mjs")
        for key in ("tab-experiments","panel-experiments","experiment-cards",
                    "experiment-results","experiment-trend-kind","experiment-daily"):
            self.assertIn('id="'+key+'"',dashboard)
        for rpc in ("admin_experiment_report_v1","admin_set_experiment_v1"):
            self.assertIn(rpc,js)
        self.assertIn("wilson(",js)
        self.assertIn("confirm(",js)
        self.assertIn("matured_exposed",js)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY",js)
        self.assertIn("window.__mxDashboardAb",self.read("scripts/audience_phase4_browser_smoke.py"))
    def test_build_privacy_and_existing_features(self):
        build=self.read("scripts/build_public_site.py")
        sw=self.read("service-worker.js")
        self.assertIn('"experiment-ux.mjs"',build)
        self.assertIn("'./assets/js/experiment-ux.mjs'",sw)
        self.assertNotIn("'./statistiques-audience.html'",sw)
        privacy=self.read("confidentialite.html")
        self.assertIn("Expériences d'ergonomie",privacy)
        self.assertIn("identifiant de navigateur pseudonymisé",privacy)
        self.assertIn("facultative",privacy)
        self.assertIn("mx-experiment-favorite-added",self.read("assets/js/daily-hub.mjs"))
if __name__=="__main__":unittest.main()
