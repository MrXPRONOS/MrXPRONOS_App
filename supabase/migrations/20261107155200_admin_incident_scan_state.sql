CREATE TABLE IF NOT EXISTS public.admin_monitor_state (
 id integer PRIMARY KEY DEFAULT 1 CHECK(id=1),
 last_scan_at timestamptz,
 last_result text CHECK(last_result IN ('ok','degraded','error')),
 findings integer NOT NULL DEFAULT 0,
 escalations integer NOT NULL DEFAULT 0,
 sources jsonb NOT NULL DEFAULT '{}'::jsonb,
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.admin_monitor_state (id,last_result) VALUES (1,'ok')
ON CONFLICT (id) DO NOTHING;
ALTER TABLE public.admin_monitor_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.admin_monitor_state FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.admin_monitor_state TO authenticated;
DROP POLICY IF EXISTS admin_monitor_state_read ON public.admin_monitor_state;
CREATE POLICY admin_monitor_state_read ON public.admin_monitor_state
 FOR SELECT TO authenticated USING ((SELECT public.admin_can('read')));
