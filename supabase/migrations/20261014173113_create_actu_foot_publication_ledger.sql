create table if not exists public.actu_foot_publications (
  event_key text primary key,
  category text not null,
  status text not null check (status in ('claimed','sent','failed','uncertain')),
  payload_hash text,
  claimed_at timestamptz not null default now(),
  sent_at timestamptz,
  telegram_message_id bigint,
  updated_at timestamptz not null default now()
);

alter table public.actu_foot_publications enable row level security;
revoke all on table public.actu_foot_publications from anon, authenticated;
grant select, insert, update, delete on table public.actu_foot_publications to service_role;

create index if not exists actu_foot_publications_status_updated_idx
  on public.actu_foot_publications(status, updated_at desc);
