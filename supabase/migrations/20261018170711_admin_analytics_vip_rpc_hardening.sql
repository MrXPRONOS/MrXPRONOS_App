-- Phase 1B: narrow sensitive data API permissions without changing public INSERT analytics tracking.
BEGIN;
DROP POLICY IF EXISTS "Allow anonymous selects" ON public.analytics;
REVOKE SELECT, UPDATE, DELETE ON TABLE public.analytics FROM anon;
-- Authenticated non-admin sessions remain denied by analytics_select_admin RLS.
REVOKE ALL ON FUNCTION public.admin_reset_vip(text,text,integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_reset_vip(text,text,integer) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_revoke_vip(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_revoke_vip(text) TO authenticated;
COMMIT;
