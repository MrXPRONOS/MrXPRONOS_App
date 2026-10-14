-- Minute-safe LIVE leases and lightweight fixture snapshot refresh.
-- Does not fabricate absent market statistics or change observed market totals.
create or replace function public.claim_live_refresh(p_owner text)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare updated_count integer;
begin
  if p_owner is null or length(p_owner) < 8 then return false; end if;
  update public.live_refresh_control
  set lease_owner=p_owner, lease_until=now()+interval '90 seconds', updated_at=now()
  where key='live_refresh' and (lease_until is null or lease_until < now());
  get diagnostics updated_count=row_count;
  return updated_count=1;
end $$;

create or replace function public.renew_live_refresh(p_owner text)
returns boolean language plpgsql security definer set search_path = ''
as $$
declare updated_count integer;
begin
  if p_owner is null or length(p_owner)<8 then return false; end if;
  update public.live_refresh_control
  set lease_until=now()+interval '90 seconds'
  where key='live_refresh' and lease_owner=p_owner and lease_until>now();
  get diagnostics updated_count=row_count;
  return updated_count=1;
end $$;

create or replace function public.upsert_live_fixture_status(p_rows jsonb)
returns integer language plpgsql security definer set search_path=''
as $$
declare written integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows)>500 then
    raise exception 'Expected array of at most 500 observed LIVE fixtures';
  end if;
  with normalized as (
    select distinct on (f.id)
      f.id, f.home_team, f.away_team, f.home_score, f.away_score, f.current_minute,
      f.league_name, f.status, f.event_date
    from jsonb_to_recordset(p_rows) as f(
      id text, home_team text, away_team text,
      home_score integer, away_score integer,
      current_minute integer, league_name text,
      status text, event_date text)
    where length(coalesce(f.id,'')) between 3 and 160
      and length(coalesce(f.home_team,''))>0
      and length(coalesce(f.away_team,''))>0
    order by f.id
  )
  insert into public.matches_live as ml(
    id,home_team,away_team,home_score,away_score,current_minute,league_name,status,raw_data,updated_at)
  select
    n.id,n.home_team,n.away_team,n.home_score,n.away_score,n.current_minute,n.league_name,n.status,
    jsonb_build_object(
      'id',n.id,'home_team',n.home_team,'away_team',n.away_team,
      'home_score',n.home_score,'away_score',n.away_score,
      'current_minute',n.current_minute,'league_name',n.league_name,
      'league',jsonb_build_object('name',n.league_name),
      'status',n.status,'is_live',true,'is_finished',false,
      'event_date',n.event_date,
      'live_stats',jsonb_build_object('home',jsonb_build_object(),'away',jsonb_build_object())
    ),now()
  from normalized n
  on conflict(id) do update
    set home_team=excluded.home_team,away_team=excluded.away_team,
        home_score=coalesce(excluded.home_score,ml.home_score),
        away_score=coalesce(excluded.away_score,ml.away_score),
        current_minute=case when excluded.current_minute>0 then excluded.current_minute else ml.current_minute end,
        league_name=coalesce(excluded.league_name,ml.league_name),
        status=excluded.status,
        raw_data=coalesce(ml.raw_data,'{}'::jsonb)
           || jsonb_strip_nulls(excluded.raw_data - 'live_stats' - 'current_minute')
           || case when excluded.current_minute>0 then jsonb_build_object('current_minute',excluded.current_minute) else '{}'::jsonb end,
        updated_at=now();
  get diagnostics written=row_count;
  return written;
end $$;

revoke all on function public.claim_live_refresh(text) from public,anon,authenticated;
revoke all on function public.renew_live_refresh(text) from public,anon,authenticated;
revoke all on function public.upsert_live_fixture_status(jsonb) from public,anon,authenticated;
grant execute on function public.claim_live_refresh(text) to service_role;
grant execute on function public.renew_live_refresh(text) to service_role;
grant execute on function public.upsert_live_fixture_status(jsonb) to service_role;
