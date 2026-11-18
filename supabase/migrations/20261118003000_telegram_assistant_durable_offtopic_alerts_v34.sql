create table if not exists public.mx_telegram_assistant_escalations (
  update_id bigint primary key,
  chat_key text not null,
  user_label text not null default '',
  question text not null default '',
  origin text not null default 'text'
    check (origin in ('text','voice','audio')),
  status text not null default 'pending'
    check (status in ('pending','delivered')),
  attempts smallint not null default 0
    check (attempts between 0 and 10),
  telegram_message_id bigint,
  last_error_code text not null default '',
  last_attempt_at timestamptz,
  delivered_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists mx_ta_escalations_pending_idx
  on public.mx_telegram_assistant_escalations(status, last_attempt_at, created_at);

alter table public.mx_telegram_assistant_escalations enable row level security;
revoke all on public.mx_telegram_assistant_escalations from anon, authenticated;
grant select, insert, update, delete on public.mx_telegram_assistant_escalations to service_role;
