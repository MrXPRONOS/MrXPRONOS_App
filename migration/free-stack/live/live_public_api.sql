-- Restorable Neon LIVE read API. Generated from verified staging function.
-- SECURITY: expose only EXECUTE on the curated RPC, not base tables.
CREATE OR REPLACE FUNCTION public.live_public_api(p_route text, p_id text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE result jsonb := '{}'::jsonb; matches jsonb := '[]'::jsonb; opportunities jsonb := '[]'::jsonb;
BEGIN
 IF p_route IN ('matches','opportunities','today') THEN
   WITH current_matches AS (
     SELECT m.id,m.raw_data,m.updated_at
     FROM public.matches_live m
     WHERE m.updated_at >= clock_timestamp() - interval '240 seconds'
     ORDER BY m.updated_at DESC LIMIT 120
   ),
   formatted AS (
     SELECT x.id,
       COALESCE(x.raw_data,'{}'::jsonb) ||
         jsonb_build_object('updated_at',x.updated_at,
              'freshness_seconds', GREATEST(0,EXTRACT(EPOCH FROM clock_timestamp()-x.updated_at)::int),
              'events','[]'::jsonb,
              'predictions',COALESCE(pr.preds,'[]'::jsonb),
              'all_predictions',COALESCE(pr.preds,'[]'::jsonb)) AS item,
       COALESCE(pr.first_score,0) AS score,
       COALESCE(jsonb_array_length(pr.preds),0) AS pred_count
     FROM current_matches x
     LEFT JOIN LATERAL (
       SELECT jsonb_agg(
          (to_jsonb(p) - 'telegram_pending_chat_ids' - 'telegram_last_error'
             - 'telegram_last_attempt_at' - 'telegram_attempts') ||
          jsonb_build_object(
            'type',p.prediction_type,
            'badge',CASE p.prediction_type WHEN 'total_corners' THEN 'Corners'
               WHEN 'total_shots' THEN 'Tirs'
               WHEN 'total_fouls' THEN 'Fautes' ELSE 'Signal' END,
            'title','Over '||p.threshold::text||
               CASE p.prediction_type WHEN 'total_corners' THEN ' corners'
                 WHEN 'total_shots' THEN ' tirs' WHEN 'total_fouls' THEN ' fautes' ELSE '' END,
            'pronostic',p.threshold, 'current',p.current_value,
            'signal_value',COALESCE(p.signal_value,p.current_value),
            'projected',p.projected_value,
            'reliability',COALESCE(p.reliability_score,ROUND(COALESCE(p.probability,0)*100)::numeric),
            'reasons','[]'::jsonb
          ) ORDER BY p.value_score DESC NULLS LAST, p.created_at DESC
       ) AS preds, MAX(p.value_score) AS first_score
       FROM public.live_predictions p
       WHERE p.match_id::text = x.id::text AND p.validated IS FALSE
     ) pr ON TRUE
   )
   SELECT COALESCE(jsonb_agg(item ORDER BY score DESC),'[]'::jsonb),
          COALESCE(jsonb_agg(item ORDER BY score DESC) FILTER(WHERE pred_count>0),'[]'::jsonb)
     INTO matches,opportunities FROM formatted;
   IF p_route='matches' THEN RETURN jsonb_build_object('matches',matches); END IF;
   IF p_route='opportunities' THEN
       RETURN jsonb_build_object('opportunities',(SELECT COALESCE(jsonb_agg(q.value),'[]'::jsonb)
          FROM (SELECT value FROM jsonb_array_elements(opportunities) WITH ORDINALITY a(value,ord) WHERE ord<=12) q));
   END IF;
   RETURN jsonb_build_object('data',jsonb_build_object(
     'live',jsonb_build_object('count',jsonb_array_length(matches),'matches',matches),
     'scheduled',jsonb_build_object('count',0,'matches','[]'::jsonb),
     'finished',jsonb_build_object('count',0,'matches','[]'::jsonb)),
     'meta',jsonb_build_object('source','neon', 'bsd_calls',0,'upstream_espn_calls',0));
 ELSIF p_route='predictions/history' THEN
   SELECT jsonb_build_object('history',COALESCE(jsonb_agg(
       to_jsonb(p)-'telegram_pending_chat_ids'-'telegram_last_error'
        ORDER BY p.created_at DESC),'[]'::jsonb))
     INTO result FROM (SELECT * FROM public.live_predictions
         WHERE created_at >= clock_timestamp()-interval '48 hours'
         ORDER BY created_at DESC LIMIT 250) p;
   RETURN result;
 ELSIF p_route='predictions/by-id' THEN
   SELECT to_jsonb(p)-'telegram_pending_chat_ids'-'telegram_last_error'
    INTO result FROM public.live_predictions p WHERE p.id::text=p_id LIMIT 1;
   IF result IS NULL THEN RETURN jsonb_build_object('error','not found'); END IF;
   RETURN jsonb_build_object('prediction',result);
 ELSE RETURN jsonb_build_object('error','route not found'); END IF;
END
$function$
;
REVOKE ALL ON FUNCTION public.live_public_api(text,text) FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO anonymous;
GRANT EXECUTE ON FUNCTION public.live_public_api(text,text) TO anonymous;
