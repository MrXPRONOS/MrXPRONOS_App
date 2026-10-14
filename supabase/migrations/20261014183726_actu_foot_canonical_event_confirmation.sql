alter table public.actu_foot_live_events
  alter column confirmed set default false;

create or replace function public.actu_foot_store_live_events(p_events jsonb)
returns jsonb
language sql
security definer
set search_path=public
as $$
  with incoming as (
    select item, ordinality
    from jsonb_array_elements(coalesce(p_events, '[]'::jsonb))
      with ordinality as t(item, ordinality)
  ),
  upserted as (
    insert into public.actu_foot_live_events(
      event_key, fixture_key, match_id, kind, priority_class, event_minute,
      score, home_team, away_team, league_name, provider_event_id, sources,
      payload, confirmed, last_seen_at, event_at
    )
    select
      item->>'event_key',
      item->>'fixture_key',
      nullif(item->>'match_id',''),
      item->>'kind',
      coalesce(nullif(item->>'priority_class',''),'P2'),
      nullif(item->>'event_minute','')::integer,
      nullif(item->>'score',''),
      item->>'home_team',
      item->>'away_team',
      nullif(item->>'league_name',''),
      nullif(item->>'provider_event_id',''),
      coalesce(
        array(select jsonb_array_elements_text(coalesce(item->'sources','[]'::jsonb))),
        '{}'::text[]
      ),
      coalesce(item->'payload','{}'::jsonb),
      false,
      coalesce(nullif(item->>'last_seen_at','')::timestamptz, now()),
      nullif(item->>'event_at','')::timestamptz
    from incoming
    where coalesce(item->>'event_key','') <> ''
      and coalesce(item->>'fixture_key','') <> ''
      and coalesce(item->>'kind','') <> ''
      and coalesce(item->>'home_team','') <> ''
      and coalesce(item->>'away_team','') <> ''
    on conflict(event_key) do update set
      fixture_key=excluded.fixture_key,
      match_id=coalesce(excluded.match_id, public.actu_foot_live_events.match_id),
      kind=excluded.kind,
      priority_class=excluded.priority_class,
      event_minute=coalesce(excluded.event_minute, public.actu_foot_live_events.event_minute),
      score=coalesce(excluded.score, public.actu_foot_live_events.score),
      home_team=excluded.home_team,
      away_team=excluded.away_team,
      league_name=coalesce(excluded.league_name, public.actu_foot_live_events.league_name),
      provider_event_id=coalesce(excluded.provider_event_id, public.actu_foot_live_events.provider_event_id),
      sources=case when cardinality(excluded.sources)>0 then excluded.sources else public.actu_foot_live_events.sources end,
      payload=excluded.payload,
      last_seen_at=excluded.last_seen_at,
      event_at=coalesce(excluded.event_at, public.actu_foot_live_events.event_at),
      confirmed=public.actu_foot_live_events.confirmed
    returning event_key, payload
  )
  select coalesce(jsonb_agg(u.payload order by i.ordinality), '[]'::jsonb)
  from incoming i
  join upserted u on u.event_key=i.item->>'event_key';
$$;

revoke all on function public.actu_foot_store_live_events(jsonb) from public, anon, authenticated;
grant execute on function public.actu_foot_store_live_events(jsonb) to service_role;
