-- Legacy online_users is not the active presence system. Current site uses
-- Supabase Realtime Presence; last database update was March 2026.
-- PUBLIC/anon/authenticated previously had DELETE and TRUNCATE despite RLS.
-- Preserve stored rows and service_role, allow authenticated admins read-only.
BEGIN;
REVOKE ALL ON TABLE public.online_users FROM PUBLIC, anon, authenticated;
DROP POLICY IF EXISTS "Allow anonymous upsert online_users" ON public.online_users;
DROP POLICY IF EXISTS online_users_admin_read ON public.online_users;
CREATE POLICY online_users_admin_read ON public.online_users
  FOR SELECT TO authenticated USING ((SELECT public.is_admin()));
GRANT SELECT ON TABLE public.online_users TO authenticated;
COMMIT;
