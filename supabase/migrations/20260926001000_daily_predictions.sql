-- Pronostics du jour MrXPRONOS
-- Snapshot quotidien: la cote, la mise et le gain potentiel ne changent jamais après insertion.

create extension if not exists pgcrypto;

create table if not exists public.daily_predictions (
  id uuid primary key default gen_random_uuid(),
  prediction_date date not null,
  source_match_id text not null,
  bsd_event_id bigint,
  home_team text not null,
  away_team text not null,
  league_name text,
  kickoff timestamptz,
  home_logo text,
  away_logo text,
  market_type text not null,
  market_label text not null,
  outcome text not null,
  line numeric,
  odds_snapshot numeric not null check (odds_snapshot > 1),
  odds_source text not null default 'consensus',
  odds_captured_at timestamptz not null default now(),
  stake numeric not null default 500000 check (stake >= 0),
  potential_gain numeric not null default 0 check (potential_gain >= 0),
  confidence numeric,
  xpronos_score numeric,
  source_category text,
  source_badge text,
  status text not null default 'accepted'
    check (status in ('accepted','won','lost','push','void')),
  final_home_score integer,
  final_away_score integer,
  validated boolean not null default false,
  validated_at timestamptz,
  created_at timestamptz not null default now(),
  unique (prediction_date, source_match_id, market_type, outcome)
);

create index if not exists daily_predictions_date_idx
  on public.daily_predictions(prediction_date desc, kickoff asc);

create index if not exists daily_predictions_pending_idx
  on public.daily_predictions(validated, kickoff)
  where validated = false;

alter table public.daily_predictions enable row level security;

comment on table public.daily_predictions is
  'Snapshots des pronostics du jour MrXPRONOS. Les cotes sont figees a la publication de 00:10 UTC.';
