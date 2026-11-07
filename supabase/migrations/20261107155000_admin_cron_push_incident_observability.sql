-- Read-only service snapshot for cron-job.org. Store no API keys, query strings or headers.
CREATE TABLE IF NOT EXISTS public.admin_cron_snapshot (
 id integer PRIMARY KEY DEFAULT 1 CHECK (id=1),
 fetched_at timestamptz,
 status text NOT NULL DEFAULT 'unconfigured'
   CHECK (status IN ('ok','unconfigured','error')),
 jobs jsonb NOT NULL DEFAULT '[]'::jsonb,
 last_error text,
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.admin_cron_snapshot(id) VALUES (1) ON CONFLICT DO NOTHING;
ALTER TABLE public.admin_cron_snapshot ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.admin_cron_snapshot FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.admin_cron_snapshot TO authenticated;
DROP POLICY IF EXISTS admin_cron_snapshot_read ON public.admin_cron_snapshot;
CREATE POLICY admin_cron_snapshot_read ON public.admin_cron_snapshot
 FOR SELECT TO authenticated USING ((SELECT public.admin_can('read')));
CREATE INDEX IF NOT EXISTS admin_cron_snapshot_status_idx ON public.admin_cron_snapshot(status);

-- Detailed, non-identifying Push delivery observations; never store endpoint URLs.
CREATE TABLE IF NOT EXISTS public.admin_push_delivery_logs (
 campaign_id uuid NOT NULL REFERENCES public.admin_push_campaigns(id) ON DELETE CASCADE,
 endpoint_digest text NOT NULL CHECK (length(endpoint_digest)=64),
 result text NOT NULL CHECK (result IN ('sent','failed','expired','skipped')),
 http_status integer,
 error_message text,
 observed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (campaign_id,endpoint_digest)
);
ALTER TABLE public.admin_push_delivery_logs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.admin_push_delivery_logs FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.admin_push_delivery_logs TO authenticated;
DROP POLICY IF EXISTS admin_push_delivery_logs_admin ON public.admin_push_delivery_logs;
CREATE POLICY admin_push_delivery_logs_admin ON public.admin_push_delivery_logs
 FOR SELECT TO authenticated USING ((SELECT public.admin_can('push')));
CREATE INDEX IF NOT EXISTS admin_push_delivery_campaign_idx ON public.admin_push_delivery_logs(campaign_id,result);

-- Automatic incident detector metadata and escalation tracking; no change to old rows.
ALTER TABLE public.admin_incidents
 ADD COLUMN IF NOT EXISTS detected_at timestamptz,
 ADD COLUMN IF NOT EXISTS last_seen_at timestamptz,
 ADD COLUMN IF NOT EXISTS failure_count integer NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS escalation_level integer NOT NULL DEFAULT 0,
 ADD COLUMN IF NOT EXISTS escalated_at timestamptz,
 ADD COLUMN IF NOT EXISTS recoveries integer NOT NULL DEFAULT 0;
