create table if not exists public.live_scheduled_fixtures (
 fixture_id text primary key, event_date timestamptz not null, home_team text not null,
 away_team text not null, source_names text[] not null default '{}',
 fixture jsonb not null, updated_at timestamptz not null default now()
);
create index if not exists live_scheduled_fixtures_event_date_idx on public.live_scheduled_fixtures(event_date);
create index if not exists live_scheduled_fixtures_updated_at_idx on public.live_scheduled_fixtures(updated_at);
alter table public.live_scheduled_fixtures enable row level security;
revoke all on public.live_scheduled_fixtures from anon,authenticated;
grant all on public.live_scheduled_fixtures to service_role;
