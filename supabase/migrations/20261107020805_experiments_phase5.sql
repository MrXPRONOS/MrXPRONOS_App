-- Phase 5: controlled product-experience experiments, no wagering-pressure content.
-- Disabled until deployment and smoke checks; activate explicitly via admin RPC.
create table if not exists public.experiment_flags_v1 (
  experiment_id text primary key
    check (experiment_id in ('install_value_v1','favorites_guidance_v1')),
  label text not null,
  goal text not null check (goal in ('install_cta_click','favorite_added')),
  enabled boolean not null default false,
  updated_at timestamptz not null default clock_timestamp()
);
insert into public.experiment_flags_v1 (experiment_id,label,goal,enabled)
values
('install_value_v1','Texte du panneau d’installation','install_cta_click',false),
('favorites_guidance_v1','Présentation des favoris dans Aujourd’hui','favorite_added',false)
on conflict (experiment_id) do nothing;

create table if not exists public.experiment_participants_v1 (
  experiment_id text not null references public.experiment_flags_v1(experiment_id),
  visitor_id text not null,
  variant text not null check (variant in ('a','b')),
  exposure_event_id uuid not null unique,
  first_exposed_at timestamptz not null default clock_timestamp(),
  conversion_event_id uuid unique,
  converted_at timestamptz,
  primary key (experiment_id,visitor_id),
  constraint conversion_after_exposure check (converted_at is null or converted_at>=first_exposed_at)
);
create index if not exists experiment_participants_v1_period_idx
  on public.experiment_participants_v1(experiment_id,first_exposed_at,variant);

create table if not exists public.experiment_admin_actions_v1 (
  action_id bigint generated always as identity primary key,
  experiment_id text not null references public.experiment_flags_v1(experiment_id),
  actor_id uuid not null,
  previous_enabled boolean not null,
  enabled boolean not null,
  changed_at timestamptz not null default clock_timestamp()
);
alter table public.experiment_flags_v1 enable row level security;
alter table public.experiment_participants_v1 enable row level security;
alter table public.experiment_admin_actions_v1 enable row level security;
revoke all on table public.experiment_flags_v1,public.experiment_participants_v1,
  public.experiment_admin_actions_v1 from public,anon,authenticated;

-- Fixed experiment list; salt never sent to the browser.
-- Variants are assigned SERVER SIDE and stable for each pseudonymous browser ID.
create or replace function public.experiment_variant_v1(
  p_experiment text, p_user_id text
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','public','mx_telemetry_private','pg_temp'
as $body$
declare
  v_enabled boolean;
  v_salt text;
  v_byte integer;
begin
  if p_experiment is null or p_user_id is null
     or p_user_id !~ '^(MX|PL)-[a-zA-Z0-9._-]{6,120}$'
     or length(p_user_id)>128
     or p_experiment not in ('install_value_v1','favorites_guidance_v1')
  then return jsonb_build_object('enabled',false); end if;

  select enabled into v_enabled from public.experiment_flags_v1
    where experiment_id=p_experiment;
  if not coalesce(v_enabled,false) then
    return jsonb_build_object('enabled',false);
  end if;

  select secret into v_salt from mx_telemetry_private.telemetry_secret
    where name='visitor_identity';
  if v_salt is null then return jsonb_build_object('enabled',false); end if;

  v_byte := get_byte(decode(md5(v_salt||':experiment:'||p_experiment||':'||p_user_id),'hex'),0);
  return jsonb_build_object('enabled',true,'variant',case when v_byte<128 then 'a' else 'b' end);
end;
$body$;
revoke all on function public.experiment_variant_v1(text,text)
  from public,anon,authenticated;
grant execute on function public.experiment_variant_v1(text,text) to anon,authenticated;

-- Events: one exposure and one attributed conversion per browser and test.
-- The goal must follow a real exposure; conversions are limited to seven days.
-- Pausing stops new exposures but preserves pending legitimate conversions.
create or replace function public.track_experiment_v1(
  p_event_id uuid, p_user_id text, p_experiment text,
  p_variant text, p_kind text
) returns boolean
language plpgsql security definer
set search_path to 'pg_catalog','public','mx_telemetry_private','pg_temp'
as $body$
declare
  v_salt text;
  v_user text;
  v_expected text;
  v_enabled boolean;
begin
  if p_event_id is null or p_user_id is null
     or length(p_user_id)>128
     or p_user_id !~ '^(MX|PL)-[a-zA-Z0-9._-]{6,120}$'
     or p_experiment not in ('install_value_v1','favorites_guidance_v1')
     or p_variant not in ('a','b')
     or p_kind not in ('exposure','conversion')
  then return false; end if;

  if not mx_telemetry_private.take_slot('analytics',1200) then return false; end if;

  select secret into v_salt from mx_telemetry_private.telemetry_secret
    where name='visitor_identity';
  if v_salt is null then return false; end if;

  v_expected := case
    when get_byte(decode(md5(v_salt||':experiment:'||p_experiment||':'||p_user_id),'hex'),0)<128
    then 'a' else 'b' end;
  if p_variant<>v_expected then return false; end if;
  v_user := 'visitor:'||md5(v_salt||':'||p_user_id);

  if p_kind='exposure' then
    select enabled into v_enabled from public.experiment_flags_v1
      where experiment_id=p_experiment;
    if not coalesce(v_enabled,false) then
      -- Closed experiment: do not collect new users; queued clicks can be drained.
      return true;
    end if;
    insert into public.experiment_participants_v1
      (experiment_id,visitor_id,variant,exposure_event_id)
    values(p_experiment,v_user,p_variant,p_event_id)
    on conflict do nothing;
    return exists(
      select 1 from public.experiment_participants_v1
      where experiment_id=p_experiment and visitor_id=v_user and variant=p_variant
    );
  end if;

  update public.experiment_participants_v1
    set converted_at=clock_timestamp(),conversion_event_id=p_event_id
    where experiment_id=p_experiment and visitor_id=v_user
      and variant=p_variant and converted_at is null
      and first_exposed_at>=clock_timestamp()-interval '7 days';
  if found then return true; end if;
  return exists(
    select 1 from public.experiment_participants_v1
    where experiment_id=p_experiment and visitor_id=v_user
      and variant=p_variant and converted_at is not null
  );
end;
$body$;
revoke all on function public.track_experiment_v1(uuid,text,text,text,text)
  from public,anon,authenticated;
grant execute on function public.track_experiment_v1(uuid,text,text,text,text)
  to anon,authenticated;

-- Observational report: only mature 7-day cohorts are used for final rates.
create or replace function public.admin_experiment_report_v1(p_days integer default 30)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','public','pg_temp'
as $body$
declare
  v_start timestamptz;
  v_flags jsonb;
  v_series jsonb;
begin
  if not public.is_admin() then
    raise exception 'Administrateur requis' using errcode='42501';
  end if;
  if p_days is null or p_days not between 1 and 90 then
    raise exception 'Période invalide' using errcode='22023';
  end if;
  v_start := case when p_days=1
    then date_trunc('day',now() at time zone 'UTC') at time zone 'UTC'
    else now()-make_interval(days=>p_days) end;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id',f.experiment_id,'label',f.label,'goal',f.goal,'enabled',f.enabled,
    'updated_at',f.updated_at,'variants',v.counts)
    order by f.experiment_id),'[]'::jsonb)
  into v_flags
  from public.experiment_flags_v1 f
  cross join lateral (
    select coalesce(jsonb_agg(jsonb_build_object(
      'variant',a.variant,'exposed',a.exposed,'converted',a.converted,
      'matured_exposed',a.matured_exposed,'matured_converted',a.matured_converted)
      order by a.variant),'[]'::jsonb) counts
    from (
      select variants.variant,
        count(p.visitor_id) exposed,
        count(p.visitor_id) filter(where p.converted_at is not null) converted,
        count(p.visitor_id) filter(
          where p.first_exposed_at<=now()-interval '7 days') matured_exposed,
        count(p.visitor_id) filter(
          where p.first_exposed_at<=now()-interval '7 days'
          and p.converted_at is not null) matured_converted
      from (values ('a'),('b')) variants(variant)
      left join public.experiment_participants_v1 p on
        p.experiment_id=f.experiment_id and p.variant=variants.variant
        and p.first_exposed_at>=v_start
      group by variants.variant
    ) a
  ) v;

  with dates as (
    select generate_series((v_start at time zone 'UTC')::date,
      (now() at time zone 'UTC')::date,interval '1 day')::date as day
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'day',d.day::text,'experiment',f.experiment_id,'variant',v.variant,
    'exposed',coalesce(counts.exposed,0),'converted',coalesce(counts.converted,0))
    order by d.day,f.experiment_id,v.variant),'[]'::jsonb)
  into v_series
  from dates d
  cross join public.experiment_flags_v1 f
  cross join (values ('a'),('b')) v(variant)
  left join lateral (
    select count(*) exposed,count(*) filter(where p.converted_at is not null) converted
    from public.experiment_participants_v1 p where
      p.experiment_id=f.experiment_id and p.variant=v.variant
      and (p.first_exposed_at at time zone 'UTC')::date=d.day
      and p.first_exposed_at>=v_start
  ) counts on true;

  return jsonb_build_object(
    'generated_at',now(),'period_days',p_days,
    'experiments',v_flags,'daily',v_series,
    'maturation_days',7,
    'scope','Two 50/50 server-assigned UX copy experiments; 7-day post-exposure conversions; pseudonymous browsers, no historical backfill; no automatic winner; descriptive uncertainty only.'
  );
end;
$body$;
revoke all on function public.admin_experiment_report_v1(integer)
  from public,anon,authenticated;
grant execute on function public.admin_experiment_report_v1(integer)
  to authenticated;

-- Kill switch controlled by a real active administrator.
create or replace function public.admin_set_experiment_v1(
  p_experiment text,p_enabled boolean
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','public','pg_temp'
as $body$
declare
  v_old boolean;
begin
  if not public.is_admin() then
    raise exception 'Administrateur requis' using errcode='42501';
  end if;
  if p_enabled is null or p_experiment not in
    ('install_value_v1','favorites_guidance_v1')
  then raise exception 'Paramètres invalides' using errcode='22023'; end if;

  select enabled into v_old from public.experiment_flags_v1
    where experiment_id=p_experiment for update;
  if not found then raise exception 'Expérience inconnue' using errcode='22023'; end if;
  if v_old is distinct from p_enabled then
    update public.experiment_flags_v1
      set enabled=p_enabled,updated_at=clock_timestamp()
      where experiment_id=p_experiment;
    insert into public.experiment_admin_actions_v1
      (experiment_id,actor_id,previous_enabled,enabled)
    values (p_experiment,auth.uid(),v_old,p_enabled);
  end if;
  return jsonb_build_object('id',p_experiment,'enabled',p_enabled);
end;
$body$;
revoke all on function public.admin_set_experiment_v1(text,boolean)
  from public,anon,authenticated;
grant execute on function public.admin_set_experiment_v1(text,boolean) to authenticated;
