-- Security follow-up. Existing public VIP verification remains callable.
BEGIN;
REVOKE ALL ON FUNCTION public.is_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated, service_role;

-- Event/row triggers execute via the database and do not need public RPC access.
REVOKE ALL ON FUNCTION public.assistant_queue_bad_feedback() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.rls_auto_enable() FROM PUBLIC, anon, authenticated;

-- Pin lookup paths so pg_temp cannot shadow user tables.
ALTER FUNCTION public.set_updated_at()
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.cleanup_assistant_cache()
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.match_faq_official(vector,double precision)
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.match_faq(vector,double precision,integer)
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.match_faq(vector,double precision)
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.insert_vip_code(text,text,text,timestamp without time zone)
  SET search_path TO pg_catalog, public, extensions, pg_temp;
ALTER FUNCTION public.protect_telegram_sent_selection_snapshot()
  SET search_path TO pg_catalog, public, extensions, pg_temp;
COMMIT;
