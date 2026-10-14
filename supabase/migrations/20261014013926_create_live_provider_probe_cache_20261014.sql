-- Secure server-only memory for API-Football league coverage and empty responses.
-- Avoid burning the limited free quota on repeated unsupported fixtures.
create table if not exists public.live_provider_probe_cache (
  provider text not null,
  probe_key text not null,
  supports_stats boolean,
  next_probe_at timestamptz not null,
  last_checked_at timestamptz not null default now(),
  details jsonb not null default '{}'::jsonb,
  constraint live_provider_probe_cache_pkey primary key (provider, probe_key),
  constraint live_provider_probe_cache_provider_check check (provider in ('api_football'))
);
alter table public.live_provider_probe_cache enable row level security;
revoke all on public.live_provider_probe_cache from public, anon, authenticated;
grant select, insert, update on public.live_provider_probe_cache to service_role;
create index if not exists live_provider_probe_cache_next_idx
  on public.live_provider_probe_cache (provider, next_probe_at);
