-- Snapshot public en lecture seule des Infos Foot.
-- Ecriture service-role uniquement; le site lit la ligne singleton "latest".
create table if not exists public.actu_foot_news_snapshot (
  id text primary key,
  payload jsonb not null default '[]'::jsonb,
  generated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint actu_foot_news_snapshot_singleton check (id = 'latest')
);

alter table public.actu_foot_news_snapshot enable row level security;

revoke all on table public.actu_foot_news_snapshot from anon, authenticated;
grant select on table public.actu_foot_news_snapshot to anon, authenticated;
grant select, insert, update, delete on table public.actu_foot_news_snapshot to service_role;

drop policy if exists "actu_foot_news_public_read" on public.actu_foot_news_snapshot;
create policy "actu_foot_news_public_read"
  on public.actu_foot_news_snapshot
  for select
  to anon, authenticated
  using (id = 'latest');

insert into public.actu_foot_news_snapshot (id, payload)
values ('latest', '[]'::jsonb)
on conflict (id) do nothing;
