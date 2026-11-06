import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class FavoriteAlertsAcceptance(unittest.TestCase):
    def read(self,path):
        return (ROOT/path).read_text(encoding="utf-8")

    def test_ui_consent_and_optout(self):
        home=self.read("aujourdhui.html")
        front=self.read("assets/js/daily-favorite-alerts.mjs")
        daily=self.read("assets/js/daily-hub.mjs")
        for item in ['id="daily-favorite-alert-enable"','id="daily-favorite-alert-disable"',
            'id="daily-favorite-alert-hour"',"maximum une notification"]:
            self.assertIn(item.lower(),home.lower())
        self.assertIn('activate.addEventListener("click"',front)
        self.assertIn('stop.addEventListener("click"',front)
        self.assertIn('Notification.requestPermission()',front)
        self.assertIn('request("save",subscription',front)
        self.assertIn('new Event("mx-favorites-updated")',daily)
        self.assertIn('"./daily-favorite-alerts.mjs"',daily)
        self.assertIn('export async function disable',front)

    def test_edge_function_requires_subscription_proof_and_server_secret(self):
        edge=self.read("supabase/functions/daily-favorite-alerts/index.ts")
        for token in ('confirmOwnership','keys?.auth','keys?.p256dh',
            'Deno.env.get("CRON_SECRET")','"Bearer " + secret',
            'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")',
            '.eq("endpoint", preference.endpoint).eq("enabled", true)',
            '.or("last_sent_local_day.is.null,last_sent_local_day.lt." + localDay)',
            'enabled: false','MAX_MESSAGES_PER_RUN'):
            if token=='enabled: false':continue # opt-out erases the row instead
            self.assertIn(token,edge)
        self.assertIn('.delete().eq("endpoint", endpoint)',edge)
        self.assertIn('import { cleanFavorites, localClock, selectRelevant }',edge)

    def test_sql_private_schema_table_and_cron_scheduler(self):
        sql=self.read("supabase/migrations/20261106212424_daily_favorite_alerts_v1.sql")
        workflow=self.read(".github/workflows/daily-favorite-alerts.yml")
        self.assertIn("enable row level security",sql)
        self.assertIn("revoke all on public.daily_favorite_alerts_v1",sql)
        self.assertIn("references public.push_subscriptions(endpoint) on delete cascade",sql)
        self.assertIn("timezone_name",sql)
        self.assertIn("CRON_SECRET",workflow)
        self.assertIn("schedule:",workflow)
        self.assertIn('"action":"dispatch"',workflow)
        deploy=self.read(".github/workflows/deploy-supabase-functions.yml")
        self.assertIn("daily-favorite-alerts",deploy)

    def test_privacy_and_artifact_integrity(self):
        privacy=self.read("confidentialite.html")
        build=self.read("scripts/build_public_site.py")
        sw=self.read("service-worker.js")
        self.assertIn("alertes personnalisées",privacy.lower())
        self.assertIn("préférences",privacy.lower())
        self.assertIn('"daily-favorite-alerts.mjs"',build)
        self.assertIn("./assets/js/daily-favorite-alerts.mjs",sw)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY",self.read("assets/js/daily-favorite-alerts.mjs"))

if __name__=="__main__":unittest.main()
