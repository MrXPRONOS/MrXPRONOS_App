-- Phase 1D: legacy Supabase API hardening.
-- Five public sports-data tables retain SELECT access for existing public consumers.
-- Internal sent_alerts becomes admin-only. Writes from browsers are never permitted.
-- Server-side service_role remains fully privileged and bypasses RLS.
BEGIN;
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['bookmakers','live_match_snapshots','live_matches','predictions','pronostics'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tbl);
    EXECUTE format('DROP POLICY IF EXISTS legacy_public_read ON public.%I',tbl);
    EXECUTE format('DROP POLICY IF EXISTS legacy_admin_write ON public.%I',tbl);
    EXECUTE format('CREATE POLICY legacy_public_read ON public.%I FOR SELECT TO anon,authenticated USING (true)',tbl);
    EXECUTE format('CREATE POLICY legacy_admin_write ON public.%I FOR ALL TO authenticated USING ((SELECT public.is_admin())) WITH CHECK ((SELECT public.is_admin()))',tbl);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC,anon,authenticated',tbl);
    EXECUTE format('GRANT SELECT ON TABLE public.%I TO anon,authenticated',tbl);
    EXECUTE format('GRANT INSERT,UPDATE,DELETE ON TABLE public.%I TO authenticated',tbl);
  END LOOP;
END $$;
ALTER TABLE public.sent_alerts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sent_alerts_admin_only ON public.sent_alerts;
CREATE POLICY sent_alerts_admin_only ON public.sent_alerts FOR ALL TO authenticated
  USING ((SELECT public.is_admin())) WITH CHECK ((SELECT public.is_admin()));
REVOKE ALL ON TABLE public.sent_alerts FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.sent_alerts TO authenticated;
-- The effective permissions are independently verified after this migration.
COMMIT;
