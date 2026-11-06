-- Treat browser IDs as untrusted telemetry hints, never as authenticated identity.
create table if not exists mx_telemetry_private.telemetry_secret (
 name text primary key, secret text not null
);
insert into mx_telemetry_private.telemetry_secret(name,secret)
values ('visitor_identity',md5(gen_random_uuid()::text||clock_timestamp()::text||random()::text))
on conflict (name) do nothing;
revoke all on table mx_telemetry_private.telemetry_secret from PUBLIC,anon,authenticated;
alter table public.analytics add column if not exists identity_verified boolean not null default false;
alter table public.events add column if not exists identity_verified boolean not null default false;

create or replace function public.insert_analytics(p_event_type text,p_user_id text,p_page text)
returns void language plpgsql security definer
set search_path=pg_catalog,public,mx_telemetry_private,pg_temp as $$
declare v_id text; v_salt text; v_authenticated uuid;
begin
  if p_event_type is null or p_event_type not in (
    'visit','page_view','share','share_telegram','share_whatsapp',
    'click_pronostic','view_upcoming','view_history','bonus_nav_click',
    'bookmaker_click','prediction_view','video_view',
    'editorial_view','editorial_promo_copy','editorial_ab_exposure',
    'editorial_ab_click','editorial_share','share_link') then return; end if;
  if length(coalesce(p_user_id,''))>128 or length(coalesce(p_page,''))>255
     or p_page ~ '[[:cntrl:]]' then return; end if;
  if not mx_telemetry_private.take_slot('analytics',300) then return; end if;
  v_authenticated:=auth.uid();
  if v_authenticated is not null then
     v_id='auth:'||v_authenticated::text;
  elsif p_user_id ~ '^(MX|PL)-[a-zA-Z0-9._-]{6,120}$' then
     select secret into v_salt from mx_telemetry_private.telemetry_secret
       where name='visitor_identity';
     v_id='visitor:'||md5(v_salt||':'||p_user_id);
  else
     v_id=null;
  end if;
  insert into public.analytics(event_type,user_id,page,identity_verified)
  values(p_event_type,v_id,nullif(p_page,''),v_authenticated is not null);
end; $$;

create or replace function public.record_event(p_type text,p_user_id text,p_page text)
returns void language plpgsql security definer
set search_path=pg_catalog,public,mx_telemetry_private,pg_temp as $$
declare v_id text; v_salt text; v_authenticated uuid;
begin
  if p_type not in ('visit','page_view','share','click_pronostic',
    'share_whatsapp','share_telegram','view_upcoming','view_history',
    'bonus_nav_click','bookmaker_click') then return; end if;
  if length(coalesce(p_user_id,''))>128 or length(coalesce(p_page,''))>255
     or p_page ~ '[[:cntrl:]]' then return; end if;
  if not mx_telemetry_private.take_slot('events',120) then return; end if;
  v_authenticated:=auth.uid();
  if v_authenticated is not null then
     v_id='auth:'||v_authenticated::text;
  elsif p_user_id ~ '^(MX|PL)-[a-zA-Z0-9._-]{6,120}$' then
     select secret into v_salt from mx_telemetry_private.telemetry_secret
       where name='visitor_identity';
     v_id='visitor:'||md5(v_salt||':'||p_user_id);
  else
     v_id=null;
  end if;
  insert into public.events(type,user_id,page,"timestamp",identity_verified)
  values(p_type,v_id,nullif(p_page,''),clock_timestamp(),v_authenticated is not null);
end; $$;
revoke execute on function public.insert_analytics(text,text,text) from PUBLIC;
revoke execute on function public.record_event(text,text,text) from PUBLIC;
grant execute on function public.insert_analytics(text,text,text) to anon,authenticated,service_role;
grant execute on function public.record_event(text,text,text) to anon,authenticated,service_role;
