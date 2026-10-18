-- Protect private VIP information and per-user notifications.
-- Server-side Edge Functions use service_role and retain their access.
BEGIN;
ALTER TABLE public.vip_users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow insert for all users" ON public.vip_users;
DROP POLICY IF EXISTS "Allow select for authenticated users" ON public.vip_users;
CREATE POLICY vip_users_admin_only ON public.vip_users
 FOR ALL TO authenticated USING ((SELECT public.is_admin())) WITH CHECK ((SELECT public.is_admin()));
REVOKE ALL ON TABLE public.vip_users FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.vip_users TO authenticated;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow read notifications" ON public.notifications;
CREATE POLICY notifications_admin_only ON public.notifications
 FOR ALL TO authenticated USING ((SELECT public.is_admin())) WITH CHECK ((SELECT public.is_admin()));
REVOKE ALL ON TABLE public.notifications FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.notifications TO authenticated;
COMMIT;
