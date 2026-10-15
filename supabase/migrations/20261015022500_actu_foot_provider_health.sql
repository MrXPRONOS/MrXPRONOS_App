-- Santé dynamique des fournisseurs Actu Foot. Service-role uniquement.
create table if not exists public.actu_foot_provider_health (
  provider text primary key,
  base_quality integer not null,
  effective_quality integer not null,
  consecutive_failures integer not null default 0,
  success_count bigint not null default 0,
  failure_count bigint not null default 0,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  last_error text,
  updated_at timestamptz not null default now()
);

alter table public.actu_foot_provider_health enable row level security;
revoke all on table public.actu_foot_provider_health from anon, authenticated;
grant select, insert, update, delete on table public.actu_foot_provider_health to service_role;
