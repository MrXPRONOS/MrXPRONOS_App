-- Phase 3: alertes favorites après consentement explicite uniquement.
-- Les abonnés push existants ne sont jamais inscrits automatiquement.
create table if not exists public.daily_favorite_alerts_v1 (
  endpoint text primary key references public.push_subscriptions(endpoint) on delete cascade,
  favorites jsonb not null default '{"teams":[],"leagues":[]}'::jsonb,
  hour_local smallint not null default 9 check (hour_local between 7 and 21),
  timezone_offset_minutes smallint not null default 0
    check (timezone_offset_minutes between -840 and 720),
  timezone_name text not null default 'UTC'
    check (length(timezone_name) between 2 and 64 and
      timezone_name ~ '^[A-Za-z][A-Za-z0-9_+./-]{1,63}$'),
  enabled boolean not null default false,
  last_sent_local_day date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint daily_favorite_alerts_structure check (
    jsonb_typeof(favorites) = 'object' and
    jsonb_typeof(favorites->'teams') = 'array' and
    jsonb_typeof(favorites->'leagues') = 'array' and
    jsonb_array_length(favorites->'teams') <= 20 and
    jsonb_array_length(favorites->'leagues') <= 20
  )
);
create index if not exists daily_favorite_alerts_enabled_idx
  on public.daily_favorite_alerts_v1(hour_local,enabled)
  where enabled=true;
alter table public.daily_favorite_alerts_v1 enable row level security;
revoke all on table public.daily_favorite_alerts_v1 from public, anon, authenticated;
-- Seul service_role cote serveur est autorise a gerer les preferences.
