-- Persist verified ESPN-to-primary IDs for subsequent match refreshes.
create table if not exists public.espn_match_map (
  espn_id text primary key,
  primary_match_id text not null,
  fixture_date date,
  confidence numeric(5,4) not null,
  mapped_at timestamptz not null default now()
);
create index if not exists espn_match_map_primary_idx on public.espn_match_map(primary_match_id);
alter table public.espn_match_map enable row level security;
revoke all on public.espn_match_map from anon, authenticated;
