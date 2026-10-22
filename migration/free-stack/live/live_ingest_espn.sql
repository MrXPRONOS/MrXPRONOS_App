
CREATE OR REPLACE FUNCTION public.live_ingest_espn(p_key text, p_events jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, mx_internal AS $fn$
DECLARE
  expected text;
  e jsonb;
  id_value text;
  date_value timestamptz;
  live_count integer := 0;
  scheduled_count integer := 0;
BEGIN
  SELECT secret_hash INTO expected FROM mx_internal.live_ingest_auth WHERE slot=1;
  IF expected IS NULL OR p_key IS NULL
    OR length(p_key)<32 OR encode(sha256(convert_to(p_key,'UTF8')),'hex')<>expected THEN
    RAISE EXCEPTION 'forbidden' USING ERRCODE='42501';
  END IF;
  IF p_events IS NULL OR jsonb_typeof(p_events)<>'array'
    OR jsonb_array_length(p_events)>250 THEN
    RAISE EXCEPTION 'invalid events' USING ERRCODE='22023';
  END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(p_events) LOOP
    id_value := e->>'id';
    IF id_value !~ '^espn:[0-9]+$'
      OR length(coalesce(e->>'home_team',''))<2
      OR length(coalesce(e->>'away_team',''))<2 THEN CONTINUE; END IF;
    IF e->>'is_live'='true' THEN
      INSERT INTO public.matches_live(
        id,home_team,away_team,home_score,away_score,current_minute,
        league_name,status,raw_data,updated_at)
      VALUES(
        id_value,left(e->>'home_team',200),left(e->>'away_team',200),
        coalesce((e->>'home_score')::integer,0),coalesce((e->>'away_score')::integer,0),
        coalesce((e->>'current_minute')::integer,0),left(coalesce(e->>'league_name','Football'),200),
        left(coalesce(e->>'status','in'),40),e,now())
      ON CONFLICT (id) DO UPDATE SET
        home_team=excluded.home_team,away_team=excluded.away_team,
        home_score=excluded.home_score,away_score=excluded.away_score,
        current_minute=excluded.current_minute,league_name=excluded.league_name,
        status=excluded.status,raw_data=excluded.raw_data,updated_at=excluded.updated_at;
      live_count:=live_count+1;
    ELSIF e->>'is_finished' <> 'true' AND e ? 'event_date' THEN
      BEGIN date_value:=(e->>'event_date')::timestamptz;
      EXCEPTION WHEN OTHERS THEN CONTINUE; END;
      IF date_value BETWEEN now()-interval '10 minutes' AND now()+interval '48 hours' THEN
        INSERT INTO public.live_scheduled_fixtures(
          fixture_id,event_date,home_team,away_team,source_names,fixture,updated_at)
        VALUES(id_value,date_value,left(e->>'home_team',200),left(e->>'away_team',200),
          ARRAY['espn']::text[],e,now())
        ON CONFLICT (fixture_id) DO UPDATE SET
          event_date=excluded.event_date,home_team=excluded.home_team,
          away_team=excluded.away_team,source_names=excluded.source_names,
          fixture=excluded.fixture,updated_at=excluded.updated_at;
        scheduled_count:=scheduled_count+1;
      END IF;
    END IF;
  END LOOP;
  INSERT INTO public.cron_runs(name,last_run_at,last_ok,meta)
    VALUES('live_refresh',now(),true,
      jsonb_build_object('engine','espn_scoreboard_only','live_matches',live_count,
                         'scheduled_matches',scheduled_count))
    ON CONFLICT(name) DO UPDATE SET last_run_at=excluded.last_run_at,
      last_ok=excluded.last_ok,meta=excluded.meta;
  RETURN jsonb_build_object('success',true,'engine','espn_scoreboard_only',
        'live_matches',live_count,'scheduled_matches',scheduled_count,
        'generated_signals',0,'telegram_sent',0);
END
$fn$;
REVOKE ALL ON FUNCTION public.live_ingest_espn(text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.live_ingest_espn(text,jsonb) TO anonymous;
