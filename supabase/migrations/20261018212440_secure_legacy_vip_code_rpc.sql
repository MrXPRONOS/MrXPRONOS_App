-- Phase 1F: remove public access to legacy VIP-code creation RPCs.
-- Keep service_role and current admin_reset_vip/admin_revoke_vip workflow functional.
BEGIN;
REVOKE ALL ON FUNCTION public.create_vip_code(text,text,integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.insert_vip_code(text,text,text,timestamp without time zone) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_vip_code(text,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.insert_vip_code(text,text,text,timestamp without time zone) TO service_role;
COMMIT;
