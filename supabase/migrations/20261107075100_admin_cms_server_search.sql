-- Admin-only paginated CMS search, evaluated server-side without exposing drafts.
CREATE OR REPLACE FUNCTION public.admin_cms_search(
  p_kind text, p_query text DEFAULT '', p_page integer DEFAULT 0, p_size integer DEFAULT 50
) RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=''
AS $$
DECLARE
  v_table text;
  v_term text;
  v_total bigint;
  v_items jsonb;
BEGIN
  IF NOT public.admin_can('read') THEN
    RAISE EXCEPTION 'Accès administrateur requis' USING ERRCODE='42501';
  END IF;
  IF p_kind NOT IN ('articles','conseils','bonus','bookmakers','infos') THEN
    RAISE EXCEPTION 'Module CMS inconnu';
  END IF;
  IF p_page < 0 OR p_page > 100000 OR p_size < 1 OR p_size > 100 THEN
    RAISE EXCEPTION 'Pagination invalide';
  END IF;
  v_table := 'cms_' || p_kind;
  v_term := '%' || left(trim(coalesce(p_query,'')),100) || '%';
  EXECUTE format(
    'SELECT count(*) FROM public.%I t
      WHERE concat_ws('' '', to_jsonb(t)->>''title'', to_jsonb(t)->>''name'',
          to_jsonb(t)->>''slug'', to_jsonb(t)->>''bookmaker'',
          to_jsonb(t)->>''description'', to_jsonb(t)->>''category'') ILIKE $1',
    v_table
  ) INTO v_total USING v_term;
  EXECUTE format(
    'SELECT coalesce(jsonb_agg(to_jsonb(x)),''[]''::jsonb) FROM (
       SELECT * FROM public.%I t
        WHERE concat_ws('' '', to_jsonb(t)->>''title'', to_jsonb(t)->>''name'',
          to_jsonb(t)->>''slug'', to_jsonb(t)->>''bookmaker'',
          to_jsonb(t)->>''description'', to_jsonb(t)->>''category'') ILIKE $1
        ORDER BY updated_at DESC NULLS LAST,id DESC LIMIT $2 OFFSET $3
     ) x',v_table
  ) INTO v_items USING v_term,p_size,p_page*p_size;
  RETURN jsonb_build_object('items',v_items,'total',v_total,'page',p_page,
    'page_size',p_size,'has_more',(p_page+1)*p_size<v_total);
END $$;
REVOKE ALL ON FUNCTION public.admin_cms_search(text,text,integer,integer) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_cms_search(text,text,integer,integer) TO authenticated;
