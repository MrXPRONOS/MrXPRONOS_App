-- Cursor and lease for the live refresh coordinator. Service-role only.
create table if not exists public.live_refresh_control (
  key text primary key,
  cursor text,
  updated_at timestamptz not null default now(),
  lease_owner text,
  lease_until timestamptz
);
insert into public.live_refresh_control (key) values ('live_refresh')
on conflict (key) do nothing;
alter table public.live_refresh_control enable row level security;
revoke all on public.live_refresh_control from anon, authenticated;

create or replace function public.claim_live_refresh(p_owner text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare updated_count integer;
begin
  if p_owner is null or length(p_owner) < 8 then return false; end if;
  update public.live_refresh_control
     set lease_owner = p_owner, lease_until = now() + interval '15 minutes', updated_at = now()
   where key = 'live_refresh' and (lease_until is null or lease_until < now());
  get diagnostics updated_count = row_count;
  return updated_count = 1;
end;
$$;
revoke all on function public.claim_live_refresh(text) from public, anon, authenticated;
grant execute on function public.claim_live_refresh(text) to service_role;

create or replace function public.release_live_refresh(p_owner text, p_cursor text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare updated_count integer;
begin
  update public.live_refresh_control
     set cursor = p_cursor, lease_owner = null, lease_until = null, updated_at = now()
   where key = 'live_refresh' and lease_owner = p_owner;
  get diagnostics updated_count = row_count;
  return updated_count = 1;
end;
$$;
revoke all on function public.release_live_refresh(text,text) from public, anon, authenticated;
grant execute on function public.release_live_refresh(text,text) to service_role;
