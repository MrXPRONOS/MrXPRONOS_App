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
  v_claimed boolean := false;
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
    v_claimed := true;
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
      v_claimed := true;
    else
      update public.actu_foot_publications
         set status='claimed',
             attempts=attempts+1,
             updated_at=now(),
             locked_at=now(),
             next_retry_at=null
       where event_key=p_event_key
         and status='claimed'
         and attempts < max_attempts
         and (locked_at is null or locked_at < now() - interval '4 minutes')
         and (expires_at is null or expires_at > now())
      returning * into v_row;

      if found then
        v_claimed := true;
      else
        select * into v_row from public.actu_foot_publications where event_key=p_event_key;
      end if;
    end if;
  end if;

  return jsonb_build_object(
    'can_send', v_claimed,
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

revoke all on function public.actu_foot_claim_publication(text,text,text,jsonb,timestamptz,integer)
  from public, anon, authenticated;
grant execute on function public.actu_foot_claim_publication(text,text,text,jsonb,timestamptz,integer)
  to service_role;
