
create table if not exists public.mx_telegram_assistant_chats (
  chat_key text primary key,
  chat_id bigint not null,
  business_connection_id text,
  user_id bigint,
  nickname text,
  paused boolean not null default false,
  last_message_at timestamptz not null default now(),
  last_admin_notice_at timestamptz
);
create table if not exists public.mx_telegram_assistant_messages (
  id bigint generated always as identity primary key,
  chat_key text not null references public.mx_telegram_assistant_chats(chat_key) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'human')),
  content text not null,
  created_at timestamptz not null default now()
);
create index if not exists mx_tg_messages_chat_time_idx on public.mx_telegram_assistant_messages(chat_key, id desc);
create table if not exists public.mx_telegram_assistant_updates (
  update_id bigint primary key,
  handled_at timestamptz not null default now()
);
alter table public.mx_telegram_assistant_chats enable row level security;
alter table public.mx_telegram_assistant_messages enable row level security;
alter table public.mx_telegram_assistant_updates enable row level security;
revoke all on public.mx_telegram_assistant_chats, public.mx_telegram_assistant_messages, public.mx_telegram_assistant_updates from anon, authenticated;
grant select, insert, update, delete on public.mx_telegram_assistant_chats, public.mx_telegram_assistant_messages, public.mx_telegram_assistant_updates to service_role;
grant usage, select on sequence public.mx_telegram_assistant_messages_id_seq to service_role;
