-- Phase 4 / MR XPRONOS — analyse d'audience, cohortes et canaux.
-- Mesures à compter de l'activation. Ne pas fabriquer d'historique V2.
-- Aucun IP, URL de provenance, nom de personne ni identifiant public brut stocké.
create table if not exists public.analytics_acquisition_events_v1 (
  event_id uuid primary key,
  visitor_id text not null,
  channel text not null check (channel in (
    'direct','google','organic_search','facebook','instagram','whatsapp',
    'telegram','youtube','tiktok','pinterest','linkedin','referral','other','unknown')),
  campaign text,
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists analytics_acquisition_events_v1_date_idx
  on public.analytics_acquisition_events_v1(created_at desc,channel);

create table if not exists public.analytics_acquisition_v1 (
  visitor_id text primary key,
  first_channel text not null,
  first_campaign text,
  first_seen_at timestamptz not null default clock_timestamp(),
  last_channel text not null,
  last_campaign text,
  last_seen_at timestamptz not null default clock_timestamp(),
  touches integer not null default 1 check (touches between 1 and 100000)
);
create index if not exists analytics_acquisition_v1_first_idx
  on public.analytics_acquisition_v1(first_channel,first_seen_at desc);
create index if not exists analytics_acquisition_v1_last_idx
  on public.analytics_acquisition_v1(last_channel,last_seen_at desc);

alter table public.analytics_acquisition_events_v1 enable row level security;
alter table public.analytics_acquisition_v1 enable row level security;
revoke all on table public.analytics_acquisition_events_v1,public.analytics_acquisition_v1
  from public,anon,authenticated;
-- Aucune lecture directe du journal ni des identifiants (même pour les administrateurs).
-- Seule la fonction agrégée, avec contrôle is_admin(), expose des statistiques.

create or replace function public.track_acquisition_v1(
  p_event_id uuid,
  p_user_id text,
  p_channel text,
  p_campaign text default null
) returns boolean
language plpgsql security definer
set search_path to 'pg_catalog','public','mx_telemetry_private','pg_temp'
as $body$
declare
  v_salt text;
  v_user text;
  v_event uuid;
  v_channel text;
  v_campaign text;
begin
  if p_event_id is null
     or p_user_id is null or length(p_user_id) > 128
     or p_user_id !~ '^(MX|PL)-[A-Za-z0-9._-]{6,120}$'
     or p_channel is null
     or p_channel not in (
       'direct','google','organic_search','facebook','instagram','whatsapp',
       'telegram','youtube','tiktok','pinterest','linkedin','referral','other','unknown'
     )
     or (p_campaign is not null and
         (length(p_campaign) > 48 or p_campaign !~ '^[a-z0-9][a-z0-9_.-]{0,47}$'))
  then return false; end if;

  if not mx_telemetry_private.take_slot('analytics',1200) then return false; end if;
  select secret into v_salt
    from mx_telemetry_private.telemetry_secret where name='visitor_identity';
  if v_salt is null then return false; end if;
  v_user := 'visitor:'||md5(v_salt||':'||p_user_id);
  v_channel := p_channel;
  v_campaign := nullif(p_campaign,'');

  insert into public.analytics_acquisition_events_v1(event_id,visitor_id,channel,campaign)
  values (p_event_id,v_user,v_channel,v_campaign)
  on conflict(event_id) do nothing
  returning event_id into v_event;
  if v_event is null then return true; end if;

  insert into public.analytics_acquisition_v1
    (visitor_id,first_channel,first_campaign,last_channel,last_campaign)
  values (v_user,v_channel,v_campaign,v_channel,v_campaign)
  on conflict(visitor_id) do update
    set last_channel=excluded.last_channel,
        last_campaign=excluded.last_campaign,
        last_seen_at=clock_timestamp(),
        touches=least(100000,public.analytics_acquisition_v1.touches+1);
  return true;
end;
$body$;
revoke all on function public.track_acquisition_v1(uuid,text,text,text) from public,anon,authenticated;
grant execute on function public.track_acquisition_v1(uuid,text,text,text) to anon,authenticated;


-- Exclusivement des agrégats : pas de retour d'identifiants, de jetons ni de provenance brute.
-- Rétention J+1, J+7, J+30 = retour EXACT au jour d'échéance, cohorte mûre uniquement.
-- Le premier jour observé vient exclusivement de analytics_visitor_days_v2.
create or replace function public.admin_audience_dashboard_v1(p_days integer default 30)
returns jsonb language plpgsql security definer
set search_path to 'pg_catalog','public','pg_temp'
as $body$
declare
  v_start date;
  v_today date;
  v_window_start timestamptz;
  v_summary jsonb;
  v_daily jsonb;
  v_cohorts jsonb;
  v_sources jsonb;
  v_campaigns jsonb;
  v_install jsonb;
  v_quality jsonb;
  v_pages jsonb;
begin
  if not public.is_admin() then
    raise exception 'Administrateur requis' using errcode='42501';
  end if;
  if p_days is null or p_days not between 1 and 90 then
    raise exception 'Période invalide' using errcode='22023';
  end if;

  v_today := (now() at time zone 'UTC')::date;
  v_start := v_today - (p_days-1);
  v_window_start := (v_start::timestamp at time zone 'UTC');

  select jsonb_build_object(
    'visitors_period',(select count(distinct visitor_id) from public.analytics_visitor_days_v2 where visit_day>=v_start),
    'dau',(select count(distinct visitor_id) from public.analytics_visitor_days_v2 where visit_day=v_today),
    'wau',(select count(distinct visitor_id) from public.analytics_visitor_days_v2 where visit_day>=v_today-6),
    'mau',(select count(distinct visitor_id) from public.analytics_visitor_days_v2 where visit_day>=v_today-29),
    'sessions',(select count(*) from public.analytics_sessions_v2 where started_at>=v_window_start),
    'page_views',(select coalesce(sum(page_views),0) from public.analytics_sessions_v2 where started_at>=v_window_start),
    'engaged_sessions',(select count(*) from public.analytics_sessions_v2 where started_at>=v_window_start and engaged),
    'standalone_sessions',(select count(*) from public.analytics_sessions_v2 where started_at>=v_window_start and display_mode='standalone'),
    'returning_visitor_ids',(select count(*) from (
      select visitor_id from public.analytics_visitor_days_v2
      where visit_day>=v_start group by visitor_id having count(*)>=2
    ) r),
    'sessions_mobile',(select count(*) from public.analytics_sessions_v2
      where started_at>=v_window_start and device in ('mobile','tablet')),
    'sessions_desktop',(select count(*) from public.analytics_sessions_v2
      where started_at>=v_window_start and device='desktop')
  ) into v_summary;

  with dates as (
    select generate_series(v_start,v_today,interval '1 day')::date as day
  ), visits as (
    select visit_day as day,count(*) as visitors
    from public.analytics_visitor_days_v2 where visit_day>=v_start
    group by visit_day
  ), session_stats as (
    select (started_at at time zone 'UTC')::date as day,
      count(*) as sessions,
      coalesce(sum(page_views),0) as pages,
      count(*) filter(where engaged) as engaged,
      count(*) filter(where display_mode='standalone') as standalone
    from public.analytics_sessions_v2 where started_at>=v_window_start
    group by 1
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'day',d.day::text,'visitors',coalesce(v.visitors,0),
    'sessions',coalesce(s.sessions,0),'page_views',coalesce(s.pages,0),
    'engaged_sessions',coalesce(s.engaged,0),
    'standalone_sessions',coalesce(s.standalone,0)) order by d.day),'[]'::jsonb)
  into v_daily from dates d left join visits v on v.day=d.day
    left join session_stats s on s.day=d.day;

  with first_day as (
    select visitor_id,min(visit_day) as day
    from public.analytics_visitor_days_v2 group by visitor_id
  ), matured as (
    select f.visitor_id,f.day,
      exists(select 1 from public.analytics_visitor_days_v2 r
        where r.visitor_id=f.visitor_id and r.visit_day=f.day+1) as returned_1,
      exists(select 1 from public.analytics_visitor_days_v2 r
        where r.visitor_id=f.visitor_id and r.visit_day=f.day+7) as returned_7,
      exists(select 1 from public.analytics_visitor_days_v2 r
        where r.visitor_id=f.visitor_id and r.visit_day=f.day+30) as returned_30
    from first_day f where f.day>=v_start and f.day<=v_today
  )
  select jsonb_build_object(
    'j1',jsonb_build_object(
      'eligible',count(*) filter(where day<=v_today-1),
      'returned',count(*) filter(where day<=v_today-1 and returned_1)),
    'j7',jsonb_build_object(
      'eligible',count(*) filter(where day<=v_today-7),
      'returned',count(*) filter(where day<=v_today-7 and returned_7)),
    'j30',jsonb_build_object(
      'eligible',count(*) filter(where day<=v_today-30),
      'returned',count(*) filter(where day<=v_today-30 and returned_30))
  ) into v_cohorts from matured;

  -- Sources au premier contact, parmi les navigateurs actifs mesurés durant la fenêtre.
  -- Ne pas considérer ces valeurs déclaratives comme une preuve des canaux réels.
  with visitors as (
    select distinct visitor_id from public.analytics_visitor_days_v2
    where visit_day>=v_start
    union
    select distinct visitor_id from public.pwa_install_events_v2
    where occurred_on>=v_start
  ), base as (
    select v.visitor_id,coalesce(a.first_channel,'unattributed') as channel,
      coalesce(a.first_campaign,'') as campaign
    from visitors v left join public.analytics_acquisition_v1 a using(visitor_id)
  ), aggregate as (
    select channel,count(*) as visitors from base group by channel
  ), funnel as (
    select base.channel,
      count(distinct base.visitor_id) filter(where p.stage='cta_click') as cta_clicks,
      count(distinct base.visitor_id) filter(where p.stage='appinstalled') as appinstalled,
      count(distinct base.visitor_id) filter(where p.stage='standalone_open') as standalone_open
    from base left join public.pwa_install_events_v2 p
      on p.visitor_id=base.visitor_id and p.occurred_on>=v_start
    group by base.channel
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'channel',a.channel,'visitors',a.visitors,
    'cta_clicks',coalesce(f.cta_clicks,0),
    'appinstalled',coalesce(f.appinstalled,0),
    'standalone_open',coalesce(f.standalone_open,0)
  ) order by a.visitors desc,a.channel),'[]'::jsonb)
  into v_sources from aggregate a join funnel f on f.channel=a.channel;

  with active as (
    select distinct visitor_id from public.analytics_visitor_days_v2
    where visit_day>=v_start
  )
  select coalesce(jsonb_agg(jsonb_build_object('campaign',campaign,'channel',channel,
    'visitors',visitors) order by visitors desc,campaign),'[]'::jsonb)
  into v_campaigns from (
    select a.first_campaign as campaign,a.first_channel as channel,count(*) as visitors
    from public.analytics_acquisition_v1 a join active v using(visitor_id)
    where a.first_campaign is not null
    group by a.first_campaign,a.first_channel order by count(*) desc limit 15
  ) t;

  select coalesce(jsonb_object_agg(stage,n),'{}'::jsonb)
  into v_install from (
    select stage,count(distinct visitor_id) n
    from public.pwa_install_events_v2 where occurred_on>=v_start
    group by stage
  ) t;

  select coalesce(jsonb_agg(jsonb_build_object('page',page,'views',views)
    order by views desc,page),'[]'::jsonb)
  into v_pages from (
    select page,count(*) as views
    from public.analytics_session_events_v2
    where kind='page_view' and created_at>=v_window_start
    group by page order by count(*) desc limit 12
  ) t;

  select jsonb_build_object(
    'legacy_raw_visits',(select count(*) from public.analytics where event_type='visit'
       and created_at>=v_window_start),
    'legacy_historic_ci_window_visits',(select count(*) from public.analytics
       where event_type='visit' and created_at>='2026-10-18 13:10:00+00'::timestamptz
       and created_at<'2026-10-18 13:30:00+00'::timestamptz and created_at>=v_window_start),
    'legacy_high_rate_minutes',(select count(*) from (
       select date_trunc('minute',created_at) as minute from public.analytics
       where event_type='visit' and created_at>=v_window_start
       group by 1 having count(*)>=30
    ) s),
    'days_without_telemetry',(select count(*) from generate_series(v_start,v_today,interval '1 day') d(day)
       where not exists(select 1 from public.analytics_visitor_days_v2 t where t.visit_day=d.day::date)),
    'acquisition_visitor_ids',(select count(*) from public.analytics_acquisition_v1
       where first_seen_at>=v_window_start),
    'session_events',(select count(*) from public.analytics_session_events_v2
       where created_at>=v_window_start),
    'installation_events',(select count(*) from public.pwa_install_events_v2
       where created_at>=v_window_start)
  ) into v_quality;

  return jsonb_build_object(
    'generated_at',now(),
    'start_day',v_start::text,'end_day',v_today::text,
    'period_days',p_days,'summary',v_summary,'daily',v_daily,
    'cohorts',v_cohorts,'acquisition',v_sources,'campaigns',v_campaigns,
    'install_funnel',v_install,'pages',v_pages,'quality',v_quality,
    'definitions','J+1/J+7/J+30: exact-day first-observed cohorts with matured follow-up; DAU/WAU/MAU: pseudonymous browser identifiers UTC; acquisition: first observed declared source, no IP or raw referrer; install events are not verified installs.'
  );
end;
$body$;
revoke all on function public.admin_audience_dashboard_v1(integer) from public,anon,authenticated;
grant execute on function public.admin_audience_dashboard_v1(integer) to authenticated;
