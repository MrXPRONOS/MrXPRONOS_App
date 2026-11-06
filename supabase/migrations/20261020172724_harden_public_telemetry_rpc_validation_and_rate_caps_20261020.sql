-- Harden anonymous event RPCs without changing their interface.
create or replace function public.insert_analytics(p_event_type text,p_user_id text,p_page text)
returns void language plpgsql security definer set search_path=pg_catalog,public,pg_temp
as $$
begin
  if p_event_type is null or length(p_event_type)>64 or p_event_type !~ '^[a-z][a-z0-9_]*$'
     or length(coalesce(p_user_id,''))>128 or length(coalesce(p_page,''))>255 then
    return;
  end if;
  if not mx_telemetry_private.take_slot('analytics',500) then
    return;
  end if;
  insert into public.analytics(event_type,user_id,page)
  values(p_event_type,nullif(p_user_id,''),nullif(p_page,''));
end;
$$;

create or replace function public.record_event(p_type text,p_user_id text,p_page text)
returns void language plpgsql security definer set search_path=pg_catalog,public,pg_temp
as $$
begin
  if p_type is null or length(p_type)>64 or p_type !~ '^[a-z][a-z0-9_]*$'
     or length(coalesce(p_user_id,''))>128 or length(coalesce(p_page,''))>255 then
    return;
  end if;
  if not mx_telemetry_private.take_slot('events',300) then
    return;
  end if;
  insert into public.events(type,user_id,page,"timestamp")
  values(p_type,nullif(p_user_id,''),nullif(p_page,''),now());
end;
$$;
revoke execute on function public.insert_analytics(text,text,text) from public;
revoke execute on function public.record_event(text,text,text) from public;
grant execute on function public.insert_analytics(text,text,text) to anon,authenticated,service_role;
grant execute on function public.record_event(text,text,text) to anon,authenticated,service_role;
