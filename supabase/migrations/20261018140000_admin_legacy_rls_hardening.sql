-- Harden legacy public tables with explicit read-only access and admin-only private data.
-- Service-role data ingestion remains unchanged. No rows are modified.
BEGIN;
-- Public content tables: clients can read, not mutate.
DO $block$
DECLARE tbl text;
BEGIN
 FOR tbl IN SELECT unnest(ARRAY['bookmakers','pronostics','live_matches','predictions','live_match_snapshots']) LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tbl);
  EXECUTE format('DROP POLICY IF EXISTS admin_public_read ON public.%I',tbl);
  EXECUTE format('CREATE POLICY admin_public_read ON public.%I FOR SELECT TO anon,authenticated USING (true)',tbl);
  EXECUTE format('REVOKE ALL ON public.%I FROM anon,authenticated',tbl);
  EXECUTE format('GRANT SELECT ON public.%I TO anon,authenticated',tbl);
 END LOOP;
END $block$;
-- VIP access, private notifications, internal dispatch records: no anonymous direct reads or writes.
DO $block$
DECLARE tbl text;
BEGIN
 FOR tbl IN SELECT unnest(ARRAY['vip_users','notifications','sent_alerts']) LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tbl);
  EXECUTE format('DROP POLICY IF EXISTS admin_only_restricted ON public.%I',tbl);
  EXECUTE format('CREATE POLICY admin_only_restricted ON public.%I FOR ALL TO authenticated USING ((select public.is_admin())) WITH CHECK ((select public.is_admin()))',tbl);
  EXECUTE format('REVOKE ALL ON public.%I FROM anon,authenticated',tbl);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO authenticated',tbl);
 END LOOP;
END $block$;
-- Clean up two legacy VIP policies which allowed unbounded inserts and broad reads.
DROP POLICY IF EXISTS "Allow insert for all users" ON public.vip_users;
DROP POLICY IF EXISTS "Allow select for authenticated users" ON public.vip_users;
DROP POLICY IF EXISTS "allow read notifications" ON public.notifications;
COMMIT;
