create table if not exists public.telegram_promo_deliveries (
 campaign text not null,
 delivery_day date not null,
 chat_id text not null,
 status text not null default 'reserved' check (status in ('reserved','sent','uncertain')),
 created_at timestamptz not null default now(),
 sent_at timestamptz,
 primary key (campaign,delivery_day,chat_id)
);
alter table public.telegram_promo_deliveries enable row level security;
revoke all on public.telegram_promo_deliveries from anon,authenticated;
grant select,insert,update on public.telegram_promo_deliveries to service_role;
comment on table public.telegram_promo_deliveries is 'Telegram promotion per-channel once-only reservations; ambiguous failures remain reserved to avoid duplicate sends';
