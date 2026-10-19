-- Bounded global telemetry, not a per-IP rate limiter. Keep service_role unthrottled.
BEGIN;
CREATE SCHEMA IF NOT EXISTS mx_telemetry_private;
REVOKE ALL ON SCHEMA mx_telemetry_private FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS mx_telemetry_private.minute_buckets(
 channel text PRIMARY KEY, minute_key bigint NOT NULL, calls integer NOT NULL CHECK(calls>=0)
);
ALTER TABLE mx_telemetry_private.minute_buckets ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE mx_telemetry_private.minute_buckets FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION mx_telemetry_private.take_slot(p_channel text,p_limit integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, mx_telemetry_private, pg_temp
AS $function$
DECLARE v_calls integer;
BEGIN
 IF p_limit < 1 OR p_channel NOT IN
 ('analytics','events','counter:total_visits','counter:total_shares','counter:unique_users') THEN RETURN false; END IF;
 INSERT INTO mx_telemetry_private.minute_buckets AS rb(channel,minute_key,calls)
 VALUES (p_channel,floor(extract(epoch FROM clock_timestamp())/60)::bigint,1)
 ON CONFLICT (channel) DO UPDATE SET
 minute_key=EXCLUDED.minute_key,
 calls=CASE WHEN rb.minute_key=EXCLUDED.minute_key THEN rb.calls+1 ELSE 1 END
 WHERE rb.minute_key<>EXCLUDED.minute_key OR rb.calls<p_limit
 RETURNING calls INTO v_calls;
 RETURN v_calls IS NOT NULL;
END;
$function$;
REVOKE ALL ON FUNCTION mx_telemetry_private.take_slot(text,integer) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION mx_telemetry_private.guard_analytics()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, mx_telemetry_private, pg_temp
AS $function$
BEGIN
 IF current_setting('request.jwt.claim.role',true)='service_role' THEN RETURN NEW; END IF;
 IF NOT mx_telemetry_private.take_slot('analytics',3000) THEN RETURN NULL; END IF;
 RETURN NEW;
END;
$function$;
REVOKE ALL ON FUNCTION mx_telemetry_private.guard_analytics() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS analytics_global_rate_cap ON public.analytics;
CREATE TRIGGER analytics_global_rate_cap BEFORE INSERT ON public.analytics
FOR EACH ROW EXECUTE FUNCTION mx_telemetry_private.guard_analytics();

CREATE OR REPLACE FUNCTION mx_telemetry_private.guard_events()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, mx_telemetry_private, pg_temp
AS $function$
BEGIN
 IF current_setting('request.jwt.claim.role',true)='service_role' THEN RETURN NEW; END IF;
 IF NOT mx_telemetry_private.take_slot('events',1800) THEN RETURN NULL; END IF;
 RETURN NEW;
END;
$function$;
REVOKE ALL ON FUNCTION mx_telemetry_private.guard_events() FROM PUBLIC, anon, authenticated;
DROP TRIGGER IF EXISTS events_global_rate_cap ON public.events;
CREATE TRIGGER events_global_rate_cap BEFORE INSERT ON public.events
FOR EACH ROW EXECUTE FUNCTION mx_telemetry_private.guard_events();

-- Retain public RPC signature and existing counting semantics.
CREATE OR REPLACE FUNCTION public.increment_counter(counter_name text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE quota integer;
BEGIN
 quota:=CASE counter_name
 WHEN 'total_visits' THEN 2400
 WHEN 'total_shares' THEN 1200
 WHEN 'unique_users' THEN 1200
 ELSE 0 END;
 IF quota=0 THEN RETURN; END IF;
 IF NOT mx_telemetry_private.take_slot('counter:'||counter_name,quota) THEN RETURN; END IF;
 IF counter_name='total_visits' THEN
   UPDATE public.counters SET total_visits=total_visits+1 WHERE id=1;
 ELSIF counter_name='total_shares' THEN
   UPDATE public.counters SET total_shares=total_shares+1 WHERE id=1;
 ELSIF counter_name='unique_users' THEN
   UPDATE public.counters SET unique_users=unique_users+1 WHERE id=1;
 END IF;
END;
$function$;
COMMIT;
