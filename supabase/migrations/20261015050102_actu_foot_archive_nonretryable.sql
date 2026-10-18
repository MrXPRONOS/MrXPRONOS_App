-- Archive les anciennes entrées outbox qui ne peuvent plus être rejouées.
-- "archived" est terminal: le claim atomique ne réclame que status='failed'.

alter table public.actu_foot_publications
  drop constraint if exists actu_foot_publications_status_check;

alter table public.actu_foot_publications
  add constraint actu_foot_publications_status_check
  check (status = any (array[
    'claimed'::text,
    'sent'::text,
    'failed'::text,
    'uncertain'::text,
    'archived'::text
  ]));

update public.actu_foot_publications
   set status='archived',
       updated_at=now(),
       locked_at=null,
       next_retry_at=null,
       last_error=coalesce(last_error,'') ||
         case when coalesce(last_error,'')='' then '' else ' | ' end ||
         'archived_nonretryable'
 where
   (
     status='failed'
     and (
       attempts >= max_attempts
       or (expires_at is not null and expires_at <= now())
     )
   )
   or
   (
     status='uncertain'
     and updated_at < now() - interval '6 hours'
     and telegram_message_id is null
     and media_message_id is null
     and poll_message_id is null
     and next_retry_at is null
   );

create or replace function public.actu_foot_retryable_publications(p_limit integer default 20)
returns setof public.actu_foot_publications
language plpgsql
security definer
set search_path=public
as $$
begin
  update public.actu_foot_publications
     set status='uncertain',
         last_error=coalesce(last_error,'') ||
           case when coalesce(last_error,'')='' then '' else ' | ' end ||
           'stale_claim_quarantined',
         updated_at=now(),
         locked_at=null,
         next_retry_at=null
   where status='claimed'
     and locked_at is not null
     and locked_at < now() - interval '4 minutes';

  update public.actu_foot_publications
     set status='archived',
         updated_at=now(),
         locked_at=null,
         next_retry_at=null,
         last_error=coalesce(last_error,'') ||
           case when coalesce(last_error,'')='' then '' else ' | ' end ||
           'archived_nonretryable'
   where
     (
       status='failed'
       and (
         attempts >= max_attempts
         or (expires_at is not null and expires_at <= now())
       )
     )
     or
     (
       status='uncertain'
       and updated_at < now() - interval '6 hours'
       and telegram_message_id is null
       and media_message_id is null
       and poll_message_id is null
       and next_retry_at is null
     );

  return query
  select p.*
  from public.actu_foot_publications p
  where p.status='failed'
    and p.attempts < p.max_attempts
    and (p.next_retry_at is null or p.next_retry_at <= now())
    and (p.expires_at is null or p.expires_at > now())
  order by
    case p.category
      when 'goal' then 0
      when 'carton_rouge' then 0
      when 'resultat' then 0
      when 'tirs_au_but' then 0
      when 'tir_au_but_marque' then 0
      when 'tir_au_but_manque' then 0
      else 1
    end,
    p.updated_at asc
  limit greatest(1,least(coalesce(p_limit,20),50));
end;
$$;
