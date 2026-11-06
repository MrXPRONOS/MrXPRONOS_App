-- Phase 1 / Mr XPRONOS: serveurs de sessions et visites dédupliquées.
-- Conservation du journal historique et du filtre CI existant.
create table if not exists public.analytics_sessions_v2 (
  session_id uuid primary key,
  visitor_id text not null,
  started_at timestamptz not null default clock_timestamp(),
  last_seen_at timestamptz not null default clock_timestamp(),
  first_page text not null,
  last_page text not null,
  device text not null check (device in ('mobile','tablet','desktop','unknown')),
  display_mode text not null check (display_mode in ('browser','standalone')),
  page_views integer not null default 0 check (page_views between 0 and 200),
  engaged boolean not null default false,
  identity_verified boolean not null default false
);
create index if not exists analytics_sess_v2_visitor_date_idx on public.analytics_sessions_v2(visitor_id, started_at desc);
create index if not exists analytics_sess_v2_started_idx on public.analytics_sessions_v2(started_at desc);

create table if not exists public.analytics_session_events_v2 (
  event_id uuid primary key,
  session_id uuid not null references public.analytics_sessions_v2(session_id) on delete cascade,
  kind text not null check (kind in ('page_view','engaged')),
  page text not null,
  created_at timestamptz not null default clock_timestamp()
);
create index if not exists analytics_sess_evt_v2_session_idx on public.analytics_session_events_v2(session_id, created_at);
create index if not exists analytics_sess_evt_v2_created_idx on public.analytics_session_events_v2(created_at);

create table if not exists public.analytics_visitor_days_v2 (
  visitor_id text not null,
  visit_day date not null,
  first_seen_at timestamptz not null default clock_timestamp(),
  last_seen_at timestamptz not null default clock_timestamp(),
  primary key(visitor_id,visit_day)
);
create index if not exists analytics_days_v2_date_idx on public.analytics_visitor_days_v2(visit_day);

alter table public.analytics_sessions_v2 enable row level security;
alter table public.analytics_session_events_v2 enable row level security;
alter table public.analytics_visitor_days_v2 enable row level security;
revoke all on table public.analytics_sessions_v2, public.analytics_session_events_v2, public.analytics_visitor_days_v2 from public,anon,authenticated;
grant select on public.analytics_sessions_v2, public.analytics_session_events_v2, public.analytics_visitor_days_v2 to authenticated;
create policy "admin read sessions v2" on public.analytics_sessions_v2 for select to authenticated using (public.is_admin());
create policy "admin read events v2" on public.analytics_session_events_v2 for select to authenticated using (public.is_admin());
create policy "admin read days v2" on public.analytics_visitor_days_v2 for select to authenticated using (public.is_admin());

create or replace function public.track_visitor_session_v2(
  p_session_id uuid, p_event_id uuid, p_user_id text, p_kind text, p_page text,
  p_device text default 'unknown', p_display_mode text default 'browser'
) returns boolean language plpgsql security definer
set search_path to 'pg_catalog','public','mx_telemetry_private','pg_temp'
as $body$
declare
  v_user text;
  v_salt text;
  v_auth uuid;
  v_event_id uuid;
  v_day_id text;
  v_day date;
  v_page_count integer;
begin
  if p_session_id is null or p_event_id is null
     or p_user_id is null or p_user_id !~ '^(MX|PL)-[a-zA-Z0-9._-]{6,120}$'
     or length(p_user_id)>128
     or p_kind not in ('page_view','engaged')
     or p_page is null or length(p_page)>140
     or p_page !~ '^/[a-zA-Z0-9_./-]*$' or position('..' in p_page)>0
     or p_device not in ('mobile','tablet','desktop','unknown')
     or p_display_mode not in ('browser','standalone') then
     return false;
  end if;

  if not mx_telemetry_private.take_slot('analytics',1200) then return false; end if;
  v_auth := auth.uid();
  if v_auth is not null then
    v_user := 'auth:'||v_auth::text;
  else
    select secret into v_salt from mx_telemetry_private.telemetry_secret where name='visitor_identity';
    if v_salt is null then return false; end if;
    v_user := 'visitor:'||md5(v_salt||':'||p_user_id);
  end if;

  insert into public.analytics_sessions_v2
    (session_id,visitor_id,first_page,last_page,device,display_mode,identity_verified)
  values (p_session_id,v_user,p_page,p_page,p_device,p_display_mode,v_auth is not null)
  on conflict(session_id) do update
    set last_seen_at=clock_timestamp(),last_page=excluded.last_page
    where public.analytics_sessions_v2.visitor_id=excluded.visitor_id;
  if not found then return false; end if;

  if p_kind='engaged' and not exists (
    select 1 from public.analytics_session_events_v2
    where session_id=p_session_id and kind='page_view'
  ) then return false; end if;
  if p_kind='page_view' then
    select page_views into v_page_count from public.analytics_sessions_v2 where session_id=p_session_id;
    if v_page_count>=200 then return false; end if;
  end if;

  insert into public.analytics_session_events_v2(event_id,session_id,kind,page)
  values(p_event_id,p_session_id,p_kind,p_page)
  on conflict(event_id) do nothing
  returning event_id into v_event_id;

  if v_event_id is null then return true; end if;
  if p_kind='page_view' then
    update public.analytics_sessions_v2
      set page_views=page_views+1,last_seen_at=clock_timestamp(),last_page=p_page
      where session_id=p_session_id and page_views<200;
    if not found then return false; end if;
  else
    update public.analytics_sessions_v2
      set engaged=true,last_seen_at=clock_timestamp()
      where session_id=p_session_id;
  end if;

  v_day := (clock_timestamp() at time zone 'UTC')::date;
  insert into public.analytics_visitor_days_v2(visitor_id,visit_day)
    values(v_user,v_day) on conflict(visitor_id,visit_day) do nothing
    returning visitor_id into v_day_id;

  if v_day_id is not null then
    -- Continuité des anciennes statistiques : une visite par navigateur et jour UTC.
    insert into public.analytics(event_type,user_id,page,identity_verified)
      values('visit',v_user,p_page,v_auth is not null);
    update public.counters set total_visits=total_visits+1 where id=1;
  else
    update public.analytics_visitor_days_v2 set last_seen_at=clock_timestamp()
    where visitor_id=v_user and visit_day=v_day;
  end if;
  return true;
end;
$body$;
revoke execute on function public.track_visitor_session_v2(uuid,uuid,text,text,text,text,text) from public,anon,authenticated;
grant execute on function public.track_visitor_session_v2(uuid,uuid,text,text,text,text,text) to anon,authenticated;

create or replace function public.admin_visitor_quality_v2(p_days integer default 30)
returns jsonb language plpgsql security definer
set search_path to 'pg_catalog','public','pg_temp'
as $body$
declare
  v_since timestamptz;
  v_sessions jsonb;
  v_days jsonb;
  v_suspect jsonb;
  v_gaps jsonb;
  v_legacy jsonb;
begin
  if not public.is_admin() then raise exception 'Administrateur requis' using errcode='42501'; end if;
  if p_days not between 1 and 90 then raise exception 'Période invalide'; end if;
  v_since := case when p_days=1
    then date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'
    else now()-make_interval(days=>p_days) end;

  select jsonb_build_object(
    'sessions',count(*),
    'visitor_ids',count(distinct visitor_id),
    'page_views',coalesce(sum(page_views),0),
    'engaged_sessions',count(*) filter (where engaged),
    'standalone_sessions',count(*) filter (where display_mode='standalone'))
    into v_sessions from public.analytics_sessions_v2 where started_at>=v_since;

  select jsonb_build_object(
    'unique_visitor_days',count(*),
    'returning_visitor_ids',(select count(*) from (
       select visitor_id from public.analytics_visitor_days_v2
       where visit_day >= (v_since at time zone 'UTC')::date
       group by visitor_id having count(*)>=2) r))
  into v_days from public.analytics_visitor_days_v2
  where visit_day >= (v_since at time zone 'UTC')::date;

  select coalesce(jsonb_agg(jsonb_build_object('minute',minute_key,'visits',n,'ids',ids) order by minute_key),'[]'::jsonb)
    into v_suspect from (
      select date_trunc('minute',created_at) minute_key,count(*) n,count(distinct user_id) ids
      from public.analytics
      where event_type='visit' and created_at>=v_since
      group by 1 having count(*)>=30
      order by n desc limit 30
    ) x;

  select coalesce(jsonb_agg(to_char(day_key,'YYYY-MM-DD') order by day_key),'[]'::jsonb)
    into v_gaps from (
      select g.day_key from generate_series(
        (v_since at time zone 'UTC')::date,
        (now() at time zone 'UTC')::date,'1 day'::interval
      ) g(day_key)
      where not exists (
        select 1 from public.analytics a where a.event_type='visit'
          and (a.created_at at time zone 'UTC')::date=g.day_key
      ) order by g.day_key limit 90
    ) x;

  select jsonb_build_object('raw_visit_events',count(*),
    'historic_ci_window_visits',count(*) filter (where
      created_at >= '2026-10-18 13:10:00+00'::timestamptz
      and created_at < '2026-10-18 13:30:00+00'::timestamptz))
    into v_legacy from public.analytics where event_type='visit' and created_at>=v_since;

  return jsonb_build_object(
    'started_at',v_since,'generated_at',now(),'session_v2',v_sessions,
    'visitor_days_v2',v_days,'legacy',v_legacy,
    'suspect_high_rate_minutes_review_only',v_suspect,
    'days_without_recorded_visits',v_gaps,
    'scope','browser identifiers; events can be lost offline; high-rate minutes require human review'
  );
end;
$body$;
revoke execute on function public.admin_visitor_quality_v2(integer) from public,anon,authenticated;
grant execute on function public.admin_visitor_quality_v2(integer) to authenticated;
