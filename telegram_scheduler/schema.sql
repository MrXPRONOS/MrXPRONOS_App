-- Smart Scheduler V1, additive infrastructure only. No cron or Telegram calls.
begin;
create table public.tg_scheduler_v1_lock (
 singleton boolean primary key default true check(singleton),
 owner uuid, acquired_at timestamptz,
 blocked_until timestamptz not null default '2026-11-24 18:30:00+00'
);
insert into public.tg_scheduler_v1_lock(singleton) values(true);
create table public.tg_scheduler_v1_registry (
 id bigint generated always as identity primary key,
 peer bigint not null, slot timestamptz not null,
 logical_key text not null check(length(logical_key) between 1 and 256),
 fingerprint text not null check(fingerprint ~ '^[0-9a-f]{64}$'),
 owner uuid not null,
 status text not null default 'pending' check(status in ('pending','accepted','verified','uncertain')),
 scheduled_id bigint,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique(peer,slot,logical_key), unique(peer,slot,fingerprint)
);
alter table public.tg_scheduler_v1_lock enable row level security;
alter table public.tg_scheduler_v1_registry enable row level security;
revoke all on public.tg_scheduler_v1_lock, public.tg_scheduler_v1_registry from public, anon, authenticated;
grant select,update on public.tg_scheduler_v1_lock to service_role;
grant select,insert,update on public.tg_scheduler_v1_registry to service_role;
grant usage,select on sequence public.tg_scheduler_v1_registry_id_seq to service_role;
create function public.tg_scheduler_v1_rpc(p_action text,p_owner uuid,p_data jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare
 l public.tg_scheduler_v1_lock%rowtype;
 r public.tg_scheduler_v1_registry%rowtype;
 t timestamptz := clock_timestamp();
 s timestamptz;
 peer_id bigint;
 msg_id bigint;
 wait_s bigint;
begin
 if p_owner is null then raise exception 'owner required'; end if;
 select * into strict l from public.tg_scheduler_v1_lock where singleton for update;
 t := clock_timestamp();
 if p_action='acquire' then
   if l.owner is not null or l.blocked_until > t then
     return jsonb_build_object('ok',false,'blocked_until',l.blocked_until,'occupied',l.owner is not null);
   end if;
   update public.tg_scheduler_v1_lock set owner=p_owner,acquired_at=t where singleton;
   return jsonb_build_object('ok',true);
 end if;
 if l.owner is distinct from p_owner then raise exception 'not lock owner'; end if;
 if p_action='release' then
   wait_s := greatest(1800,coalesce((p_data->>'wait_seconds')::bigint,0));
   update public.tg_scheduler_v1_lock set owner=null,acquired_at=null,
     blocked_until=greatest(l.blocked_until,t+make_interval(secs=>wait_s::double precision)) where singleton;
   return jsonb_build_object('ok',true);
 elsif p_action='reserve' then
   s := (p_data->>'slot')::timestamptz;
   peer_id := (p_data->>'peer')::bigint;
   if s < t+interval '60 seconds' or s > l.acquired_at+interval '7 days' then raise exception 'slot outside safe horizon'; end if;
   insert into public.tg_scheduler_v1_registry(peer,slot,logical_key,fingerprint,owner)
   values(peer_id,s,p_data->>'key',p_data->>'fingerprint',p_owner)
   on conflict do nothing returning * into r;
   if not found then
     select * into r from public.tg_scheduler_v1_registry
       where peer=peer_id and slot=s and (logical_key=p_data->>'key' or fingerprint=p_data->>'fingerprint')
       order by id limit 1;
     return jsonb_build_object('ok',false,'id',r.id,'status',r.status,'scheduled_id',r.scheduled_id,'fingerprint',r.fingerprint);
   end if;
   return jsonb_build_object('ok',true,'id',r.id);
 elsif p_action in ('accepted','verified','uncertain') then
   msg_id := (p_data->>'scheduled_id')::bigint;
   update public.tg_scheduler_v1_registry set status=p_action,
     scheduled_id=coalesce(msg_id,scheduled_id),updated_at=t
   where id=(p_data->>'id')::bigint and owner=p_owner
     and ((p_action='accepted' and status='pending' and msg_id>0)
       or (p_action='verified' and status='accepted' and scheduled_id=msg_id)
       or (p_action='uncertain' and status in ('pending','accepted')))
   returning * into r;
   if not found then raise exception 'invalid registry transition'; end if;
   return jsonb_build_object('ok',true,'id',r.id);
 else raise exception 'unknown action'; end if;
end;
$$;
revoke all on function public.tg_scheduler_v1_rpc(text,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.tg_scheduler_v1_rpc(text,uuid,jsonb) to service_role;
commit;
