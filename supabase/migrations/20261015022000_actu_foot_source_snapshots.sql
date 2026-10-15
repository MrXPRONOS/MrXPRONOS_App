-- Snapshot multi-source très court pour mutualiser les appels des runners Actu Foot.
-- Ne remplace pas live_stats_merged : il évite seulement les appels doublés full/lifecycle.
create table if not exists public.actu_foot_source_snapshots (
  snapshot_key text primary key,
  fixture_day date not null,
  payload jsonb not null default '[]'::jsonb,
  sources text[] not null default '{}'::text[],
  fetched_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists actu_foot_source_snapshots_expiry_idx
  on public.actu_foot_source_snapshots(expires_at);

alter table public.actu_foot_source_snapshots enable row level security;
revoke all on table public.actu_foot_source_snapshots from anon, authenticated;
grant select, insert, update, delete on table public.actu_foot_source_snapshots to service_role;
