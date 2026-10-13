-- Shared provider orchestration state; service-role only.
create table if not exists public.football_provider_state (
  key text primary key,
  provider text not null,
  last_success_at timestamptz,
  last_attempt_at timestamptz,
  last_count integer not null default 0,
  last_error text,
  meta jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.football_provider_state enable row level security;
revoke all on public.football_provider_state from anon, authenticated;

insert into public.football_provider_state(key, provider, last_success_at)
values ('bsd_live_backfill', 'bsd', null)
on conflict (key) do nothing;
