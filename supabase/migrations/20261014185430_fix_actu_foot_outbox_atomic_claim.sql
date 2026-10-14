create or replace function public.actu_foot_claim_publication(
  p_event_key text,
  p_category text,
  p_payload_hash text,
  p_payload jsonb,
  p_expires_at timestamptz,
  p_max_attempts integer default 5
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.actu_foot_publications%rowtype;
  v_acquired boolean := false;
begin
  insert into public.actu_foot_publications(
    event_key, category, status, payload_hash, payload,
    delivery_phase, attempts, max_attempts, claimed_at,
    updated_at, locked_at, expires_at, next_retry_at
  )
  values(
    p_event_key, p_category, 'claimed', p_payload_hash, coalesce(p_payload,'{}'::jsonb),
    'pending', 1, greatest(1,coalesce(p_max_attempts,5)), now(),
    now(), now(), p_expires_at, null
  )
  on conflict(event_key) do nothing
  returning * into v_row;

  if found then
    v_acquired := true;
  else
    update public.actu_foot_publications
       set status='claimed',
           attempts=attempts+1,
           updated_at=now(),
           locked_at=now(),
           next_retry_at=null,
           payload=case when payload='{}'::jsonb then coalesce(p_payload,payload) else payload end,
           payload_hash=coalesce(payload_hash,p_payload_hash),
           expires_at=coalesce(expires_at,p_expires_at)
     where event_key=p_event_key
       and status='failed'
       and attempts < max_attempts
       and (next_retry_at is null or next_retry_at <= now())
       and (expires_at is null or expires_at > now())
    returning * into v_row;

    if found then
      v_acquired := true;
    else
      select * into v_row
      from public.actu_foot_publications
      where event_key=p_event_key;
    end if;
  end if;

  return jsonb_build_object(
    'can_send', v_acquired,
    'status', v_row.status,
    'delivery_phase', v_row.delivery_phase,
    'attempts', v_row.attempts,
    'max_attempts', v_row.max_attempts,
    'media_message_id', v_row.media_message_id,
    'poll_message_id', v_row.poll_message_id,
    'telegram_message_id', v_row.telegram_message_id,
    'payload', v_row.payload,
    'expires_at', v_row.expires_at
  );
end;
$$;

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
