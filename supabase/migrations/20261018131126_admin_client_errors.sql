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
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $fn$
DECLARE result jsonb;
BEGIN
 IF NOT public.is_admin() THEN RAISE EXCEPTION 'Acces administrateur requis' USING ERRCODE='42501'; END IF;
 IF p_days NOT BETWEEN 1 AND 90 THEN RAISE EXCEPTION 'Periode invalide' USING ERRCODE='22023'; END IF;
 SELECT jsonb_build_object('total',count(*),
  'script',count(*) FILTER(WHERE kind='script'),
  'promise',count(*) FILTER(WHERE kind='promise'),
  'resource',count(*) FILTER(WHERE kind='resource'))
 INTO result FROM public.admin_client_errors WHERE created_at >= now()-make_interval(days=>p_days);
 RETURN result;
END $fn$;
REVOKE ALL ON FUNCTION public.admin_client_error_summary(integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.admin_client_error_summary(integer) TO authenticated;
