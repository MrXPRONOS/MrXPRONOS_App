-- Clean cache implementation using PostgreSQL, not a web-accessible endpoint.
-- Run only after controlled snapshot and scheduling with a protected service.
CREATE SCHEMA IF NOT EXISTS mrx_internal;
CREATE OR REPLACE FUNCTION mrx_internal.clean_cache()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE faq_deleted integer := 0; conversations_deleted integer := 0;
BEGIN
  DELETE FROM public.faq WHERE created_at < now() - interval '30 days';
  GET DIAGNOSTICS faq_deleted = ROW_COUNT;
  DELETE FROM public.conversations WHERE created_at < now() - interval '7 days';
  GET DIAGNOSTICS conversations_deleted = ROW_COUNT;
  RETURN jsonb_build_object('success',true,'deleted_faq',faq_deleted,'deleted_conversations',conversations_deleted);
END $$;
REVOKE ALL ON SCHEMA mrx_internal FROM PUBLIC;
REVOKE ALL ON FUNCTION mrx_internal.clean_cache() FROM PUBLIC;
REVOKE ALL ON FUNCTION mrx_internal.clean_cache() FROM anonymous, authenticated;
