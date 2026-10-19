-- Fix privileged public RPC object resolution; anonymous telemetry remains callable.
-- pg_temp MUST be last so client-created temporary tables cannot shadow public tables.
BEGIN;
ALTER FUNCTION public.increment_counter(text)
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.insert_analytics(text,text,text)
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.record_event(text,text,text)
  SET search_path TO pg_catalog, public, pg_temp;
COMMIT;
