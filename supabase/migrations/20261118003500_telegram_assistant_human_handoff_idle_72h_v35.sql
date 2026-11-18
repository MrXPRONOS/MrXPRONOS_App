alter table public.mx_telegram_assistant_chats
  add column if not exists human_handoff boolean not null default false,
  add column if not exists human_handoff_started_at timestamptz,
  add column if not exists human_last_activity_at timestamptz,
  add column if not exists human_handoff_reason text not null default '';

create index if not exists mx_ta_chats_handoff_activity_idx
  on public.mx_telegram_assistant_chats(human_handoff, human_last_activity_at);

comment on column public.mx_telegram_assistant_chats.human_handoff
  is 'True while the human owner has taken over the conversation; bot stays silent until 72h inactivity.';
comment on column public.mx_telegram_assistant_chats.human_last_activity_at
  is 'Last observed user or human-owner activity used for the 72h sliding inactivity window.';
