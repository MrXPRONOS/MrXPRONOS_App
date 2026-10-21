-- XPRONOS 4+ : tables isolées ; rerunnable, aucun changement aux tables historiques.
create table if not exists public.xpronos_bot_users (
 id bigint primary key, name text not null default 'Membre',
 referred_by bigint references public.xpronos_bot_users(id),
 adult_confirmed boolean not null default false,
 required_verified boolean not null default false,
 referral_rewarded boolean not null default false,
 xp integer not null default 0 check(xp >= 0),
 bonus_last_at timestamptz,
 bonus_day date,
 bonus_day_total integer not null default 0,
 created_at timestamptz not null default now()
);
create table if not exists public.xpronos_bot_tasks (
 id bigint generated always as identity primary key,
 chat_id text not null unique,
 url text not null,
 xp integer not null check(xp > 0),
 active boolean not null default true
);
create table if not exists public.xpronos_bot_task_claims (
 user_id bigint not null references public.xpronos_bot_users(id),
 task_id bigint not null references public.xpronos_bot_tasks(id),
 claimed_at timestamptz not null default now(),
 primary key(user_id,task_id)
);
create table if not exists public.xpronos_bot_coupons (
 id bigint generated always as identity primary key,
 tier text not null check(tier in ('SIMPLE','PRO','VIP')),
 title text not null,
 selections jsonb not null check(jsonb_typeof(selections)='array'),
 total_odds numeric(20,4) not null check(total_odds >= 4),
 xp_cost integer not null check(xp_cost >= 0),
 expires_at timestamptz not null,
 stock integer not null default -1 check(stock >= -1),
 active boolean not null default true,
 created_at timestamptz not null default now()
);
create table if not exists public.xpronos_bot_redemptions (
 user_id bigint not null references public.xpronos_bot_users(id),
 coupon_id bigint not null references public.xpronos_bot_coupons(id),
 snapshot jsonb not null,
 xp_spent integer not null check(xp_spent >= 0),
 claimed_at timestamptz not null default now(),
 primary key(user_id,coupon_id)
);
create table if not exists public.xpronos_bot_ledger (
 id bigint generated always as identity primary key,
 user_id bigint not null references public.xpronos_bot_users(id),
 delta integer not null,
 reason text not null,
 created_at timestamptz not null default now()
);
create index if not exists xpronos_bot_coupons_live_idx on public.xpronos_bot_coupons(active,expires_at);
create index if not exists xpronos_bot_referrals_idx on public.xpronos_bot_users(referred_by);

-- Les tables sont privées : aucun accès à anon/authenticated et RLS sans politiques publiques.
alter table public.xpronos_bot_users enable row level security;
alter table public.xpronos_bot_tasks enable row level security;
alter table public.xpronos_bot_task_claims enable row level security;
alter table public.xpronos_bot_coupons enable row level security;
alter table public.xpronos_bot_redemptions enable row level security;
alter table public.xpronos_bot_ledger enable row level security;
revoke all on public.xpronos_bot_users,public.xpronos_bot_tasks,public.xpronos_bot_task_claims,public.xpronos_bot_coupons,public.xpronos_bot_redemptions,public.xpronos_bot_ledger from anon,authenticated;

-- Mutations atomiques, invoker/service_role SEULEMENT ; aucun SECURITY DEFINER public.
create or replace function public.xpronos_bot_register(p_uid bigint,p_name text,p_ref bigint)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare v_id bigint; v_created boolean := false;
begin
 if p_uid <= 0 then return jsonb_build_object('status','invalid'); end if;
 insert into public.xpronos_bot_users(id,name,referred_by)
 values(p_uid,left(coalesce(nullif(p_name,''),'Membre'),100),
   case when p_ref <> p_uid and exists(select 1 from public.xpronos_bot_users where id=p_ref) then p_ref else null end)
 on conflict(id) do nothing returning id into v_id;
 v_created := v_id is not null;
 if not v_created then update public.xpronos_bot_users set name=left(coalesce(nullif(p_name,''),'Membre'),100) where id=p_uid; end if;
 return jsonb_build_object('status','ok','created',v_created);
end $$;

create or replace function public.xpronos_bot_verify(p_uid bigint,p_reward integer,p_enabled boolean)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare u record;
begin
 if p_reward < 0 or p_reward > 100000 then return jsonb_build_object('status','invalid'); end if;
 select * into u from public.xpronos_bot_users where id=p_uid for update;
 if not found then return jsonb_build_object('status','missing'); end if;
 if not u.adult_confirmed then return jsonb_build_object('status','age'); end if;
 update public.xpronos_bot_users set required_verified=true where id=p_uid;
 if p_enabled and p_reward > 0 and u.referred_by is not null and not u.referral_rewarded then
   update public.xpronos_bot_users set xp=xp+p_reward where id=u.referred_by;
   insert into public.xpronos_bot_ledger(user_id,delta,reason) values(u.referred_by,p_reward,'referral:'||p_uid);
   update public.xpronos_bot_users set referral_rewarded=true where id=p_uid;
   return jsonb_build_object('status','credited');
 end if;
 return jsonb_build_object('status','verified');
end $$;

create or replace function public.xpronos_bot_claim_task(p_uid bigint,p_task bigint)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare u record; t record;
begin
 select * into u from public.xpronos_bot_users where id=p_uid for update;
 if not found or not u.adult_confirmed or not u.required_verified then return jsonb_build_object('status','locked'); end if;
 select * into t from public.xpronos_bot_tasks where id=p_task and active=true;
 if not found then return jsonb_build_object('status','missing'); end if;
 if exists(select 1 from public.xpronos_bot_task_claims where user_id=p_uid and task_id=p_task) then return jsonb_build_object('status','already'); end if;
 insert into public.xpronos_bot_task_claims(user_id,task_id) values(p_uid,p_task);
 update public.xpronos_bot_users set xp=xp+t.xp where id=p_uid;
 insert into public.xpronos_bot_ledger(user_id,delta,reason) values(p_uid,t.xp,'task:'||p_task);
 return jsonb_build_object('status','ok','xp',t.xp);
end $$;

create or replace function public.xpronos_bot_bonus(p_uid bigint,p_points integer,p_cooldown_seconds integer,p_daily_cap integer)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare u record; v_today date := (now() at time zone 'UTC')::date; v_total integer;
begin
 if p_points<=0 or p_points>100000 or p_cooldown_seconds<60 or p_daily_cap<p_points or p_daily_cap>100000 then
  return jsonb_build_object('status','invalid'); end if;
 select * into u from public.xpronos_bot_users where id=p_uid for update;
 if not found or not u.adult_confirmed or not u.required_verified then return jsonb_build_object('status','locked'); end if;
 v_total := case when u.bonus_day=v_today then u.bonus_day_total else 0 end;
 if v_total+p_points>p_daily_cap then return jsonb_build_object('status','cap'); end if;
 if u.bonus_last_at is not null and extract(epoch from now()-u.bonus_last_at)<p_cooldown_seconds then
  return jsonb_build_object('status','wait','seconds',ceil(p_cooldown_seconds-extract(epoch from now()-u.bonus_last_at))::integer); end if;
 update public.xpronos_bot_users set xp=xp+p_points,bonus_last_at=now(),bonus_day=v_today,bonus_day_total=v_total+p_points where id=p_uid;
 insert into public.xpronos_bot_ledger(user_id,delta,reason) values(p_uid,p_points,'bonus');
 return jsonb_build_object('status','ok','xp',p_points);
end $$;

create or replace function public.xpronos_bot_redeem(p_uid bigint,p_coupon bigint)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare u record; c record;
begin
 select * into u from public.xpronos_bot_users where id=p_uid for update;
 if not found or not u.adult_confirmed or not u.required_verified then return jsonb_build_object('status','locked'); end if;
 select * into c from public.xpronos_bot_coupons where id=p_coupon for update;
 if not found or not c.active or c.expires_at<=now() or c.stock=0 then return jsonb_build_object('status','unavailable'); end if;
 if exists(select 1 from public.xpronos_bot_redemptions where user_id=p_uid and coupon_id=p_coupon) then
  return jsonb_build_object('status','already'); end if;
 if u.xp<c.xp_cost then return jsonb_build_object('status','xp'); end if;
 update public.xpronos_bot_users set xp=xp-c.xp_cost where id=p_uid;
 if c.stock>0 then update public.xpronos_bot_coupons set stock=stock-1 where id=p_coupon; end if;
 insert into public.xpronos_bot_redemptions(user_id,coupon_id,snapshot,xp_spent)
 values(p_uid,p_coupon,jsonb_build_object('title',c.title,'selections',c.selections,'total_odds',c.total_odds,'tier',c.tier,'expires_at',c.expires_at),c.xp_cost);
 insert into public.xpronos_bot_ledger(user_id,delta,reason) values(p_uid,-c.xp_cost,'coupon:'||p_coupon);
 return jsonb_build_object('status','ok');
end $$;

create or replace function public.xpronos_bot_grant(p_uid bigint,p_xp integer)
returns jsonb language plpgsql security invoker set search_path = '' as $$
begin
 if p_xp<=0 or p_xp>100000 then return jsonb_build_object('status','invalid'); end if;
 update public.xpronos_bot_users set xp=xp+p_xp where id=p_uid;
 if not found then return jsonb_build_object('status','missing'); end if;
 insert into public.xpronos_bot_ledger(user_id,delta,reason) values(p_uid,p_xp,'admin');
 return jsonb_build_object('status','ok');
end $$;

revoke all on function public.xpronos_bot_register(bigint,text,bigint),public.xpronos_bot_verify(bigint,integer,boolean),public.xpronos_bot_claim_task(bigint,bigint),public.xpronos_bot_bonus(bigint,integer,integer,integer),public.xpronos_bot_redeem(bigint,bigint),public.xpronos_bot_grant(bigint,integer) from public,anon,authenticated;
grant execute on function public.xpronos_bot_register(bigint,text,bigint),public.xpronos_bot_verify(bigint,integer,boolean),public.xpronos_bot_claim_task(bigint,bigint),public.xpronos_bot_bonus(bigint,integer,integer,integer),public.xpronos_bot_redeem(bigint,bigint),public.xpronos_bot_grant(bigint,integer) to service_role;
-- Accès backend explicite ; la clé serveur reste confinée à Edge Functions.
grant select,insert,update,delete on public.xpronos_bot_users,public.xpronos_bot_tasks,public.xpronos_bot_task_claims,public.xpronos_bot_coupons,public.xpronos_bot_redemptions,public.xpronos_bot_ledger to service_role;
grant usage,select on sequence public.xpronos_bot_tasks_id_seq, public.xpronos_bot_coupons_id_seq, public.xpronos_bot_ledger_id_seq to service_role;
notify pgrst, 'reload schema';
