-- Phase 2 — parcours d'installation PWA, métadonnées pseudonymisées.
-- Les événements sont déclarés par le navigateur ; aucun événement ne
-- constitue à lui seul la preuve d'une installation effective.
create table if not exists public.pwa_install_events_v2 (
  event_id uuid primary key,
  visitor_id text not null,
  stage text not null check (stage in
    ('cta_visible','cta_click','prompt_ready','prompt_shown','prompt_accepted',
     'prompt_dismissed','guide_open','guide_closed','appinstalled',
     'standalone_open','welcome_visible')),
  platform text not null check (platform in ('ios','android','desktop')),
  surface text not null check (surface in ('header','home','guide','system')),
  context text not null check (context in ('browser','in_app','standalone')),
  created_at timestamptz not null default clock_timestamp(),
  occurred_on date not null default ((now() at time zone 'UTC')::date),
  unique(visitor_id,stage,surface,occurred_on)
);
create index if not exists pwa_install_event_day_stage_idx
  on public.pwa_install_events_v2(occurred_on desc,stage,platform);
create index if not exists pwa_install_event_visitor_idx
  on public.pwa_install_events_v2(visitor_id,created_at desc);

alter table public.pwa_install_events_v2 enable row level security;
revoke all on table public.pwa_install_events_v2 from public,anon,authenticated;
grant select on public.pwa_install_events_v2 to authenticated;
create policy "Only admins read PWA installation events"
  on public.pwa_install_events_v2 for select to authenticated
  using (public.is_admin());

create or replace function public.track_pwa_install_event_v2(
  p_event_id uuid, p_user_id text, p_stage text, p_platform text,
  p_surface text, p_context text
) returns boolean language plpgsql security definer
set search_path to 'pg_catalog','public','mx_telemetry_private','pg_temp'
as $body$
declare
  v_salt text;
  v_user text;
begin
  if p_event_id is null
     or p_user_id is null or length(p_user_id) > 128
     or p_user_id !~ '^(MX|PL)-[A-Za-z0-9._-]{6,120}$'
     or p_stage not in
       ('cta_visible','cta_click','prompt_ready','prompt_shown','prompt_accepted',
        'prompt_dismissed','guide_open','guide_closed','appinstalled',
        'standalone_open','welcome_visible')
     or p_platform not in ('ios','android','desktop')
     or p_surface not in ('header','home','guide','system')
     or p_context not in ('browser','in_app','standalone')
     or (p_stage in ('standalone_open','welcome_visible') and p_context<>'standalone')
  then return false; end if;

  if not mx_telemetry_private.take_slot('analytics',1200) then return false; end if;
  select secret into v_salt
    from mx_telemetry_private.telemetry_secret where name='visitor_identity';
  if v_salt is null then return false; end if;
  v_user := 'visitor:'||md5(v_salt||':'||p_user_id);

  insert into public.pwa_install_events_v2 (
    event_id,visitor_id,stage,platform,surface,context)
  values (
    p_event_id,v_user,p_stage,p_platform,p_surface,p_context)
  on conflict do nothing;
  return true;
end;
$body$;
revoke execute on function public.track_pwa_install_event_v2(uuid,text,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.track_pwa_install_event_v2(uuid,text,text,text,text,text)
  to anon,authenticated;

-- KPI administrateur : uniques par étape, plateformes, surfaces et jours UTC.
create or replace function public.admin_pwa_install_funnel_v2(p_days integer default 30)
returns jsonb language plpgsql security definer
set search_path to 'pg_catalog','public','pg_temp'
as $body$
declare
  v_start date;
  v_events jsonb;
  v_platforms jsonb;
  v_surfaces jsonb;
  v_daily jsonb;
begin
  if not public.is_admin() then
    raise exception 'Administrateur requis' using errcode='42501';
  end if;
  if p_days is null or p_days not between 1 and 90 then
    raise exception 'Période invalide';
  end if;
  v_start := (now() at time zone 'UTC')::date - (p_days-1);

  select coalesce(jsonb_object_agg(stage,unique_ids),'{}'::jsonb)
    into v_events
    from (
      select stage,count(distinct visitor_id) as unique_ids
      from public.pwa_install_events_v2
      where occurred_on>=v_start
      group by stage
    ) t;

  select coalesce(jsonb_agg(jsonb_build_object(
     'platform',platform,'visitors',visitors,'cta_visible',cta_visible,
     'cta_click',cta_click,'prompt_ready',prompt_ready,
     'prompt_shown',prompt_shown,'prompt_accepted',prompt_accepted,
     'prompt_dismissed',prompt_dismissed,'guide_open',guide_open,
     'appinstalled',appinstalled,'standalone_open',standalone_open)
     order by platform),'[]'::jsonb)
    into v_platforms from (
      select platform,
       count(distinct visitor_id) visitors,
       count(distinct visitor_id) filter(where stage='cta_visible') cta_visible,
       count(distinct visitor_id) filter(where stage='cta_click') cta_click,
       count(distinct visitor_id) filter(where stage='prompt_ready') prompt_ready,
       count(distinct visitor_id) filter(where stage='prompt_shown') prompt_shown,
       count(distinct visitor_id) filter(where stage='prompt_accepted') prompt_accepted,
       count(distinct visitor_id) filter(where stage='prompt_dismissed') prompt_dismissed,
       count(distinct visitor_id) filter(where stage='guide_open') guide_open,
       count(distinct visitor_id) filter(where stage='appinstalled') appinstalled,
       count(distinct visitor_id) filter(where stage='standalone_open') standalone_open
      from public.pwa_install_events_v2
      where occurred_on>=v_start
      group by platform
    ) t;

  select coalesce(jsonb_agg(jsonb_build_object(
      'surface',surface,
      'cta_visible',cta_visible,'cta_click',cta_click,'guide_open',guide_open)
      order by surface),'[]'::jsonb)
    into v_surfaces from (
      select surface,
       count(distinct visitor_id) filter(where stage='cta_visible') cta_visible,
       count(distinct visitor_id) filter(where stage='cta_click') cta_click,
       count(distinct visitor_id) filter(where stage='guide_open') guide_open
      from public.pwa_install_events_v2
      where occurred_on>=v_start
      group by surface
    ) t;

  select coalesce(jsonb_agg(jsonb_build_object(
       'day',day::text,'visible',visible,'clicks',clicks,
       'prompt_accepted',prompt_accepted,'appinstalled',appinstalled,
       'standalone_open',standalone_open)
       order by day),'[]'::jsonb)
    into v_daily from (
      select dates.day::date as day,
        count(distinct e.visitor_id) filter(where e.stage='cta_visible') visible,
        count(distinct e.visitor_id) filter(where e.stage='cta_click') clicks,
        count(distinct e.visitor_id) filter(where e.stage='prompt_accepted') prompt_accepted,
        count(distinct e.visitor_id) filter(where e.stage='appinstalled') appinstalled,
        count(distinct e.visitor_id) filter(where e.stage='standalone_open') standalone_open
      from generate_series(v_start,(now() at time zone 'UTC')::date,'1 day'::interval) dates(day)
      left join public.pwa_install_events_v2 e on e.occurred_on=dates.day::date
      group by dates.day
    ) t;

  return jsonb_build_object(
    'generated_at',now(),'period_days',p_days,'counting_unit','distinct pseudonymous browser IDs',
    'events',v_events,'platforms',v_platforms,'surfaces',v_surfaces,'daily',v_daily,
    'note','Client-reported events; accepted prompt is not confirmed install; iOS home-screen installs are not reliably observable.'
  );
end;
$body$;
revoke execute on function public.admin_pwa_install_funnel_v2(integer)
  from public,anon,authenticated;
grant execute on function public.admin_pwa_install_funnel_v2(integer)
  to authenticated;
