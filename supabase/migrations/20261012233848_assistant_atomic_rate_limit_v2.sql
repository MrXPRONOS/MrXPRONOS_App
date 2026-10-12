create or replace function public.assistant_take_rate_slot(p_key text, p_limit integer default 20, p_window_seconds integer default 900)
returns boolean language plpgsql security definer set search_path=public
as $$
declare v_count integer;
begin
  if p_key is null or length(p_key) < 10 or p_limit < 1 or p_window_seconds < 1 then return false; end if;
  insert into public.assistant_rate_limits(user_id,window_start,window_count,last_message_at,updated_at)
  values(p_key,now(),1,now(),now())
  on conflict (user_id) do update
    set window_start=case when public.assistant_rate_limits.window_start <= now() - make_interval(secs=>p_window_seconds)
                              then now() else public.assistant_rate_limits.window_start end,
        window_count=case when public.assistant_rate_limits.window_start <= now() - make_interval(secs=>p_window_seconds)
                              then 1 else public.assistant_rate_limits.window_count+1 end,
        last_message_at=now(),updated_at=now()
  returning window_count into v_count;
  return v_count <= p_limit;
end; $$;
revoke all on function public.assistant_take_rate_slot(text,integer,integer) from public,anon,authenticated;
grant execute on function public.assistant_take_rate_slot(text,integer,integer) to service_role;
