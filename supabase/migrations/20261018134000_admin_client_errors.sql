-- Additive, privacy-preserving JS error statistics; never store exception messages or stacks.
CREATE TABLE IF NOT EXISTS public.admin_client_errors (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 kind text NOT NULL CHECK(kind IN ('script','promise','resource')),
 page text NOT NULL CHECK(length(page) BETWEEN 1 AND 140 AND page ~ '^/[A-Za-z0-9/_\.-]+$'),
 device text NOT NULL CHECK(device IN ('mobile','desktop','tablet')),
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.admin_client_errors ENABLE ROW LEVEL SECURITY;
CREATE POLICY admin_client_errors_public_insert ON public.admin_client_errors FOR INSERT TO anon,authenticated WITH CHECK(true);
CREATE POLICY admin_client_errors_admin_read ON public.admin_client_errors FOR SELECT TO authenticated USING ((SELECT public.is_admin()));
CREATE INDEX IF NOT EXISTS admin_client_errors_created_idx ON public.admin_client_errors(created_at DESC,kind);
REVOKE ALL ON public.admin_client_errors FROM anon,authenticated;
GRANT INSERT ON public.admin_client_errors TO anon,authenticated;
GRANT SELECT ON public.admin_client_errors TO authenticated;
GRANT USAGE ON SEQUENCE public.admin_client_errors_id_seq TO anon,authenticated;
CREATE OR REPLACE FUNCTION public.admin_client_error_summary(p_days integer DEFAULT 7)
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
 SELECT CASE WHEN NOT public.is_admin() THEN
   (SELECT NULL::jsonb FROM pg_catalog.generate_series(1,0) UNION ALL SELECT pg_catalog.to_jsonb(1/0) LIMIT 1)
 ELSE (
 SELECT jsonb_build_object('total',count(*),
 'script',count(*) FILTER(WHERE kind='script'),
 'promise',count(*) FILTER(WHERE kind='promise'),
 'resource',count(*) FILTER(WHERE kind='resource'))
 FROM public.admin_client_errors
 WHERE created_at >= now()-make_interval(days=>least(greatest(p_days,1),90))
 ) END;
$fn$;
REVOKE ALL ON FUNCTION public.admin_client_error_summary(integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.admin_client_error_summary(integer) TO authenticated;
