-- Atomic ESPN request budgeting across all Edge Function instances.
create table if not exists public.espn_request_budget (
  bucket text primary key,
  window_started_at timestamptz not null default now(),
  call_count integer not null default 0,
  blocked_until timestamptz
);
alter table public.espn_request_budget enable row level security;
revoke all on public.espn_request_budget from anon, authenticated;

create or replace function public.espn_take_request_slot(
  p_bucket text, p_max_calls integer, p_window_seconds integer
) returns boolean
language plpgsql security definer
set search_path = ''
as $$
declare v_row public.espn_request_budget%rowtype;
begin
  if p_bucket not in ('scoreboard', 'summary') then return false; end if;
  if p_max_calls < 1 or p_max_calls > 120 or p_window_seconds < 30 or p_window_seconds > 3600 then return false; end if;

  insert into public.espn_request_budget(bucket) values (p_bucket)
  on conflict (bucket) do nothing;

  select * into v_row from public.espn_request_budget
   where bucket = p_bucket for update;

  if v_row.blocked_until is not null and v_row.blocked_until > now() then
    return false;
  end if;

  if v_row.window_started_at < now() - make_interval(secs => p_window_seconds) then
    update public.espn_request_budget
       set window_started_at = now(), call_count = 1
     where bucket = p_bucket;
    return true;
  end if;

  if v_row.call_count >= p_max_calls then return false; end if;
  update public.espn_request_budget
     set call_count = call_count + 1 where bucket = p_bucket;
  return true;
end;
$$;
revoke all on function public.espn_take_request_slot(text,integer,integer) from public, anon, authenticated;
grant execute on function public.espn_take_request_slot(text,integer,integer) to service_role;

create or replace function public.espn_provider_backoff(
  p_bucket text, p_seconds integer
) returns void
language plpgsql security definer
set search_path = ''
as $$
begin
  if p_bucket not in ('scoreboard', 'summary') then return; end if;
  if p_seconds < 1 then return; end if;
  insert into public.espn_request_budget(bucket, blocked_until)
  values (p_bucket, now() + make_interval(secs => least(p_seconds, 300)))
  on conflict (bucket) do update
    set blocked_until = greatest(
      coalesce(public.espn_request_budget.blocked_until, now()),
      excluded.blocked_until
    );
end;
$$;
revoke all on function public.espn_provider_backoff(text,integer) from public, anon, authenticated;
grant execute on function public.espn_provider_backoff(text,integer) to service_role;
