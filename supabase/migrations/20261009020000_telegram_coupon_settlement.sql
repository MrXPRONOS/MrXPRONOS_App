-- BSD V2 Telegram: immutable published selections and safe settlement state.
-- Apply this migration in Supabase before the new path becomes operational.
alter table public.telegram_sent
    add column if not exists selection_snapshot jsonb,
    add column if not exists delivery_status text not null default 'legacy',
    add column if not exists telegram_message_id bigint,
    add column if not exists published_at timestamptz,
    add column if not exists settlement_status text not null default 'pending',
    add column if not exists settlement_claimed_at timestamptz,
    add column if not exists validated_at timestamptz,
    add column if not exists validation_message_id bigint,
    add column if not exists validation_details text;

create index if not exists telegram_sent_bsd_settle_queue_idx
    on public.telegram_sent (kind, validation_sent, ref_date)
    where validation_sent = false;

create or replace function public.protect_telegram_sent_selection_snapshot()
returns trigger language plpgsql as $$
begin
    if old.selection_snapshot is not null
       and new.selection_snapshot is distinct from old.selection_snapshot then
        raise exception 'Telegram published selection snapshot cannot be changed';
    end if;
    return new;
end;
$$;

drop trigger if exists protect_telegram_sent_selection_snapshot
    on public.telegram_sent;
create trigger protect_telegram_sent_selection_snapshot
before update on public.telegram_sent
for each row execute function public.protect_telegram_sent_selection_snapshot();

comment on column public.telegram_sent.selection_snapshot is
    'Immutable original published Telegram pick or two-leg combination. Must be set when the message is first reserved.';
comment on column public.telegram_sent.delivery_status is
    'reserved -> sent; uncertain failures require manual review and never automatic re-post.';
comment on column public.telegram_sent.settlement_status is
    'pending -> sending -> won/lost/void; ambiguous win delivery -> manual_review.';
