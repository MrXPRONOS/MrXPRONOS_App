-- Quotas LIVE partages par toutes les Edge Functions (service_role seulement).
-- Operation idempotente : deja creee dans le projet Supabase via migration.
create table if not exists public.live_odds_provider_quota(
 provider text not null,
 window_kind text not null check (window_kind in ('day','minute')),
 period_start timestamptz not null,
 used integer not null default 0 check (used>=0),
 updated_at timestamptz not null default now(),
 primary key(provider,window_kind,period_start)
);
alter table public.live_odds_provider_quota enable row level security;
revoke all on public.live_odds_provider_quota from public,anon,authenticated;
grant select,insert,update,delete on public.live_odds_provider_quota to service_role;

create or replace function public.odds_take_request_slot(
  p_provider text,p_day_limit integer,p_minute_limit integer
) returns boolean
language plpgsql security definer set search_path=''
as $$
declare
 v_day timestamptz := date_trunc('day',now() at time zone 'UTC') at time zone 'UTC';
 v_minute timestamptz := date_trunc('minute',now());
 v_day_used integer;
 v_minute_used integer;
begin
 if p_provider not in ('moviodds','pinnwire') or
    p_day_limit not between 1 and 10000 or p_minute_limit not between 1 and 100
 then return false; end if;
 perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtext('mrx_odds_' || p_provider));
 select used into v_day_used from public.live_odds_provider_quota
  where provider=p_provider and window_kind='day' and period_start=v_day;
 select used into v_minute_used from public.live_odds_provider_quota
  where provider=p_provider and window_kind='minute' and period_start=v_minute;
 if coalesce(v_day_used,0)>=p_day_limit or coalesce(v_minute_used,0)>=p_minute_limit
 then return false; end if;
 insert into public.live_odds_provider_quota(provider,window_kind,period_start,used,updated_at)
 values(p_provider,'day',v_day,1,now())
 on conflict(provider,window_kind,period_start) do update
 set used=public.live_odds_provider_quota.used+1,updated_at=now();
 insert into public.live_odds_provider_quota(provider,window_kind,period_start,used,updated_at)
 values(p_provider,'minute',v_minute,1,now())
 on conflict(provider,window_kind,period_start) do update
 set used=public.live_odds_provider_quota.used+1,updated_at=now();
 return true;
end;
$$;
revoke all on function public.odds_take_request_slot(text,integer,integer) from public,anon,authenticated;
grant execute on function public.odds_take_request_slot(text,integer,integer) to service_role;
