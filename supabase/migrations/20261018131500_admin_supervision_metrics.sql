-- Mr XPRONOS: admin observability V1. Additive only; no changes to prediction logic.
-- Existing tables with RLS disabled are deliberately not modified here.
CREATE TABLE IF NOT EXISTS public.admin_web_vitals (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  metric text NOT NULL CHECK (metric IN ('LCP','INP','CLS')),
  value double precision NOT NULL CHECK (value >= 0 AND value <= 60000),
  page text NOT NULL CHECK (length(page) BETWEEN 1 AND 140 AND page ~ '^/[A-Za-z0-9/_\.-]+$'),
  device text NOT NULL CHECK (device IN ('mobile','desktop','tablet')),
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.admin_web_vitals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_web_vitals_public_insert ON public.admin_web_vitals;
CREATE POLICY admin_web_vitals_public_insert ON public.admin_web_vitals FOR INSERT TO anon,authenticated WITH CHECK (true);
DROP POLICY IF EXISTS admin_web_vitals_admin_read ON public.admin_web_vitals;
CREATE POLICY admin_web_vitals_admin_read ON public.admin_web_vitals FOR SELECT TO authenticated USING ((SELECT public.is_admin()));
CREATE INDEX IF NOT EXISTS admin_web_vitals_recent_idx ON public.admin_web_vitals(created_at DESC,metric);
REVOKE ALL ON TABLE public.admin_web_vitals FROM anon,authenticated;
GRANT INSERT ON public.admin_web_vitals TO anon,authenticated;
GRANT SELECT ON public.admin_web_vitals TO authenticated;
-- Explicit sequence privilege for insert in clients where needed.
GRANT USAGE ON SEQUENCE public.admin_web_vitals_id_seq TO anon,authenticated;

CREATE OR REPLACE FUNCTION public.admin_monitor_snapshot(p_days integer DEFAULT 1)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  v_since timestamptz;
  v_events jsonb;
  v_daily jsonb;
  v_live jsonb;
  v_live_market jsonb;
  v_live_tier jsonb;
  v_prematch jsonb;
  v_crons jsonb;
  v_telegram jsonb;
  v_health jsonb;
  v_webvitals jsonb;
  v_sources jsonb;
  v_push jsonb;
BEGIN
  IF NOT public.is_admin() THEN
    RAISE EXCEPTION 'Acces administrateur requis' USING ERRCODE='42501';
  END IF;
  IF p_days NOT BETWEEN 1 AND 90 THEN
    RAISE EXCEPTION 'Periode invalide' USING ERRCODE='22023';
  END IF;
  v_since := CASE WHEN p_days=1 THEN date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
             ELSE now() - make_interval(days=>p_days) END;

  SELECT jsonb_build_object(
   'visits', count(*) FILTER (WHERE event_type='visit'),
   'page_views', count(*) FILTER (WHERE event_type='page_view'),
   'unique_visitors', count(DISTINCT user_id) FILTER (WHERE event_type='visit' AND user_id IS NOT NULL),
   'click_pronostic', count(*) FILTER (WHERE event_type='click_pronostic'),
   'share_generic', count(*) FILTER (WHERE event_type='share'),
   'share_whatsapp', count(*) FILTER (WHERE event_type='share_whatsapp'),
   'share_telegram', count(*) FILTER (WHERE event_type='share_telegram'),
   'vip_conversion_event', count(*) FILTER (WHERE event_type='vip_conversion'),
   'editorial_views', count(*) FILTER (WHERE event_type='editorial_view'),
   'editorial_clicks', count(*) FILTER (WHERE event_type='editorial_promo_copy' OR event_type='editorial_ab_click'))
  INTO v_events FROM public.analytics WHERE created_at>=v_since;

  SELECT coalesce(jsonb_agg(jsonb_build_object('day',day,'visits',visits,'page_views',page_views,'clicks',clicks) ORDER BY day),'[]'::jsonb)
    INTO v_daily FROM (
      SELECT (created_at AT TIME ZONE 'UTC')::date day,
       count(*) FILTER (WHERE event_type='visit') visits,
       count(*) FILTER (WHERE event_type='page_view') page_views,
       count(*) FILTER (WHERE event_type='click_pronostic') clicks
      FROM public.analytics WHERE created_at>=v_since GROUP BY 1
    ) s;

  SELECT jsonb_build_object(
    'total',count(*),
    'validated',count(*) FILTER(WHERE validated IS TRUE),
    'wins',count(*) FILTER(WHERE validated IS TRUE AND outcome='success'),
    'losses',count(*) FILTER(WHERE validated IS TRUE AND outcome='failure'),
    'pending',count(*) FILTER(WHERE validated IS NOT TRUE),
    'telegram_sent',count(*) FILTER(WHERE telegram_sent IS TRUE),
    'last_signal',max(created_at))
    INTO v_live FROM public.live_predictions WHERE created_at>=v_since;

  SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'total',total,'wins',wins,'losses',losses) ORDER BY total DESC),'[]'::jsonb)
    INTO v_live_market FROM (
      SELECT coalesce(nullif(prediction_type,''),'autre') name,count(*) total,
       count(*) FILTER(WHERE validated AND outcome='success') wins,
       count(*) FILTER(WHERE validated AND outcome='failure') losses
      FROM public.live_predictions WHERE created_at>=v_since
      GROUP BY 1 ORDER BY total DESC LIMIT 12
    ) t;

  SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'total',total,'wins',wins,'losses',losses) ORDER BY total DESC),'[]'::jsonb)
    INTO v_live_tier FROM (
      SELECT coalesce(nullif(signal_tier,''),'non classe') name,count(*) total,
       count(*) FILTER(WHERE validated AND outcome='success') wins,
       count(*) FILTER(WHERE validated AND outcome='failure') losses
      FROM public.live_predictions WHERE created_at>=v_since GROUP BY 1 ORDER BY total DESC LIMIT 10
    ) t;

  SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'total',total,'wins',wins,'losses',losses) ORDER BY name),'[]'::jsonb)
    INTO v_prematch FROM (
      SELECT coalesce(nullif(lower(category),''),'autre') name,count(*) total,
       count(*) FILTER(WHERE is_finished IS TRUE AND verified_double IS TRUE) wins,
       count(*) FILTER(WHERE is_finished IS TRUE AND verified_double IS FALSE) losses
      FROM public.pronostics WHERE created_at>=v_since GROUP BY 1
    ) t;

  SELECT coalesce(jsonb_agg(jsonb_build_object('name',name,'last_run',last_run,'ok',ok,'origin',origin) ORDER BY last_run DESC NULLS LAST),'[]'::jsonb)
    INTO v_crons FROM (
      SELECT name,last_run_at last_run,last_ok ok,'cron_runs' origin FROM public.cron_runs
      UNION ALL
      SELECT name,last_run,ok,'cron_runs_scrape' FROM public.cron_runs_scrape
      ORDER BY last_run DESC NULLS LAST LIMIT 35
    ) t;

  SELECT jsonb_build_object('total',count(*),'published',count(*) FILTER(WHERE delivery_status IN ('published','sent','success')),
     'failed',count(*) FILTER(WHERE delivery_status IN ('failed','error')),
     'latest_sent',max(sent_at))
    INTO v_telegram FROM public.telegram_sent WHERE sent_at>=v_since;

  SELECT jsonb_build_object(
    'live_scrape_last', (SELECT max(updated_at) FROM public.matches_live_scrape),
    'live_merged_last', (SELECT max(updated_at) FROM public.live_stats_merged),
    'latest_live_prediction', (SELECT max(created_at) FROM public.live_predictions),
    'last_actu_foot_run', (SELECT max(created_at) FROM public.actu_foot_run_metrics),
    'actu_foot_errors', (SELECT coalesce(sum(errors),0) FROM public.actu_foot_run_metrics WHERE created_at>=v_since),
    'blocked_signals', (SELECT count(*) FROM public.live_signal_blocks_scrape WHERE created_at>=v_since))
   INTO v_health;

  SELECT coalesce(jsonb_agg(jsonb_build_object('metric',metric,'device',device,'sample_count',samples,'p75',p75) ORDER BY metric,device),'[]'::jsonb)
    INTO v_webvitals FROM (
      SELECT metric,device,count(*) samples,
        round((percentile_cont(0.75) WITHIN GROUP (ORDER BY value))::numeric,3) p75
      FROM public.admin_web_vitals WHERE created_at>=v_since
      GROUP BY metric,device
    ) t;

  SELECT coalesce(jsonb_agg(jsonb_build_object('source',source,'views',views,'interactions',interactions) ORDER BY views DESC),'[]'::jsonb)
    INTO v_sources FROM (
      SELECT split_part(page,'|',3) source,
        count(*) FILTER (WHERE event_type='editorial_view') views,
        count(*) FILTER (WHERE event_type IN ('editorial_promo_copy','editorial_ab_click')) interactions
      FROM public.analytics WHERE created_at>=v_since
       AND page LIKE 'article|%|%|%' OR created_at>=v_since AND page LIKE 'conseil|%|%|%'
      GROUP BY 1 LIMIT 12
    ) t;

  SELECT jsonb_build_object(
    'subscriptions',count(*),
    'unique_users',count(DISTINCT user_id))
   INTO v_push FROM public.push_subscriptions;

  RETURN jsonb_build_object(
    'generated_at',now(),'period_start',v_since,'period_days',p_days,
    'analytics',v_events,'daily',v_daily,'live',v_live,'live_markets',v_live_market,
    'live_tiers',v_live_tier,'prematch',v_prematch,'crons',v_crons,
    'telegram',v_telegram,'health',v_health,'web_vitals',v_webvitals,
    'attribution',v_sources,'push',v_push);
END
$fn$;
REVOKE ALL ON FUNCTION public.admin_monitor_snapshot(integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.admin_monitor_snapshot(integer) TO authenticated;
COMMENT ON FUNCTION public.admin_monitor_snapshot(integer) IS 'Admin only; server-side aggregated metrics, no identifying rows.';
