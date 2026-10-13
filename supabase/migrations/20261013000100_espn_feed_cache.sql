-- Server-only ESPN cache; service-role access only.
create table if not exists public.espn_feed_cache (
 cache_key text primary key,
 payload jsonb not null,
 fetched_at timestamptz not null default now(),
 expires_at timestamptz not null,
 last_http_status integer,
 fail_count integer not null default 0,
 last_error text
);
create index if not exists espn_feed_cache_expiry_idx on public.espn_feed_cache(expires_at);
alter table public.espn_feed_cache enable row level security;
revoke all on public.espn_feed_cache from anon, authenticated;
