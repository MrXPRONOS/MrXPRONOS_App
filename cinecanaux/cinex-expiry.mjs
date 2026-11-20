// CinéX stage 6: delete ONLY the bot's private-chat copies after 24 hours.
// Original channel/library messages, users' Saved Messages and other bots are
// outside this table and never passed to deleteMessage.
const TG='https://api.telegram.org/bot';
const MAX_AGE_HOURS=47; // Telegram standard deletion window is 48h.
const MAX_RETRIES=30; // Keep retrying transient failures while the 48-hour Bot API deletion window remains open.
const RETRY_DELAY_SECONDS=[90,180,300,600,900,1800,2700,3600,3600];
const VALID_STATES=new Set(['pending','retry','deleting']);
const RETRYABLE_CODES=new Set([429,500,502,503,504]);

export function deletionDecision(api,{sentAt,now=Date.now(),attempt=1}={}){
 const stamp=Date.parse(String(sentAt||'').replace(' ','T').replace(/(?:Z|[+-]\d\d:\d\d)$/,'')+'Z');
 if(!Number.isFinite(stamp)||stamp>now+60000)return {state:'manual_review',reason:'invalid_sent_at'};
 const elapsed=now-stamp;
 if(elapsed<24*3600_000)return {state:'retry',retrySeconds:Math.ceil((24*3600_000-elapsed)/1000),reason:'not_due'};
 if(elapsed>=MAX_AGE_HOURS*3600_000)return {state:'manual_review',reason:'telegram_48h_window'};
 if(api?.ok&&api.result===true)return {state:'deleted'};
 const desc=String(api?.description||'').toLowerCase();
 // Do not interpret arbitrary errors as successful deletions.
 if(Number(api?.error_code)===400&&/message to delete not found/.test(desc))return {state:'already_gone'};
 if(Number(api?.error_code)===403)return {state:'manual_review',reason:'bot_access_denied'};
 if(Number(api?.error_code)===400)return {state:'manual_review',reason:'telegram_bad_request'};
 if(attempt>=MAX_RETRIES)return {state:'manual_review',reason:'retry_limit'};
 if(!RETRYABLE_CODES.has(Number(api?.error_code))&&!api?.networkError)return {state:'manual_review',reason:'unrecognized_error'};
 const retryAfter=Number(api?.parameters?.retry_after||0);
 const delay=Math.max(RETRY_DELAY_SECONDS[Math.min(attempt-1,RETRY_DELAY_SECONDS.length-1)],Number.isFinite(retryAfter)?Math.min(retryAfter,3600):0);
 if(elapsed+delay*1000>=MAX_AGE_HOURS*3600_000)return {state:'manual_review',reason:'telegram_window_closing'};
 return {state:'retry',retrySeconds:delay,reason:Number(api?.error_code)===429?'telegram_flood':'telegram_temporary'};
}

async function telegramDelete(env,chatId,messageId){
 try{
  const response=await fetch(TG+env.TELEGRAM_TOKEN+'/deleteMessage',{
   method:'POST',
   headers:{'content-type':'application/json'},
   body:JSON.stringify({chat_id:chatId,message_id:messageId}),
   signal:AbortSignal.timeout(9000),
  });
  let result;
  try{result=await response.json()}catch{return {networkError:true};}
  return {ok:response.ok&&result?.ok===true,
   result:result?.result,error_code:Number(result?.error_code||response.status),
   description:String(result?.description||''),parameters:result?.parameters||null};
 }catch{return {networkError:true}}
}

export async function cleanupDeliveredCopies(env,{limit=12,now}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {checked:0,deleted:0,retried:0,manual_review:0,disabled:true};
 const current=now instanceof Date?now.toISOString():null;
 const anchor=current?current.replace('T',' ').slice(0,19):null;
 const batchSize=Math.min(30,Math.max(1,Number(limit)||12));
 const result={checked:0,deleted:0,already_gone:0,retried:0,manual_review:0,failed:0};
 // The expiry cleanup is independent of the distribution kill-switch: even if
 // downloads are turned off, already-delivered copies still must expire.
 // Recover a crashed worker only after its lease expired; previous deletion
 // might already have succeeded, so only a subsequent idempotent Telegram
 // deleteMessage can settle the row.
 await env.DB.prepare(
  "UPDATE cine_delivery_job_items SET delete_state='retry',delete_retry_at=CURRENT_TIMESTAMP,delete_lock_until=NULL WHERE delete_state='deleting' AND delete_lock_until < CURRENT_TIMESTAMP AND sent_at IS NOT NULL AND delivered_message_id IS NOT NULL"
 ).run();
 const due=await env.DB.prepare(
  "SELECT i.job_id,i.ordinal,i.delivered_message_id,i.sent_at,i.delete_attempts,j.telegram_chat_id FROM cine_delivery_job_items i JOIN cine_delivery_jobs j ON j.id=i.job_id WHERE i.state='sent' AND i.delivered_message_id IS NOT NULL AND i.sent_at IS NOT NULL AND i.delete_after IS NOT NULL AND i.delete_after <= COALESCE(?,CURRENT_TIMESTAMP) AND i.delete_state IN ('pending','retry') AND COALESCE(i.delete_retry_at,i.delete_after)<=COALESCE(?,CURRENT_TIMESTAMP) ORDER BY i.delete_after ASC,i.job_id,i.ordinal LIMIT ?"
 ).bind(anchor,anchor,batchSize).all();
 for(const item of due.results||[]){
  // Do not allow cleanup of channel-like negative chat IDs, or a missing
  // delivery receipt. Only the Telegram *private user* recipient can be used.
  const chat=Number(item.telegram_chat_id),id=Number(item.delivered_message_id);
  if(!Number.isSafeInteger(chat)||chat<=0||!Number.isSafeInteger(id)||id<=0) {
   await env.DB.prepare("UPDATE cine_delivery_job_items SET delete_state='manual_review',delete_last_error='invalid_private_receipt' WHERE job_id=? AND ordinal=? AND delete_state IN ('pending','retry')").bind(item.job_id,item.ordinal).run();
   result.manual_review++;continue;
  }
  const lease=await env.DB.prepare(
   "UPDATE cine_delivery_job_items SET delete_state='deleting',delete_lock_until=datetime('now','+2 minutes'),delete_attempts=delete_attempts+1 WHERE job_id=? AND ordinal=? AND delete_state IN ('pending','retry') AND delete_after<=CURRENT_TIMESTAMP AND COALESCE(delete_retry_at,delete_after)<=CURRENT_TIMESTAMP"
  ).bind(item.job_id,item.ordinal).run();
  if(Number(lease.meta?.changes||0)!==1)continue;
  result.checked++;
  const sentAt=String(item.sent_at||''),nowMs=now instanceof Date?now.getTime():Date.now(),attempt=Number(item.delete_attempts||0)+1;
  // A same-age stale test record must not be sent to Telegram outside its 48h window.
  let decision=deletionDecision({networkError:true},{sentAt,now:nowMs,attempt});
  if(decision.reason!=='telegram_48h_window'&&decision.reason!=='invalid_sent_at'&&decision.reason!=='not_due'&&decision.reason!=='retry_limit'){
   const api=await telegramDelete(env,chat,id);
   decision=deletionDecision(api,{sentAt,now:nowMs,attempt});
  }
  if(decision.state==='deleted'||decision.state==='already_gone'){
   await env.DB.prepare(
    "UPDATE cine_delivery_job_items SET delete_state=?,deleted_at=CURRENT_TIMESTAMP,delete_lock_until=NULL,delete_retry_at=NULL,delete_last_error=NULL WHERE job_id=? AND ordinal=? AND delete_state='deleting'"
   ).bind(decision.state,item.job_id,item.ordinal).run();
   result[decision.state]++;continue;
  }
  if(decision.state==='retry'){
   await env.DB.prepare(
    "UPDATE cine_delivery_job_items SET delete_state='retry',delete_retry_at=datetime('now',?),delete_lock_until=NULL,delete_last_error=? WHERE job_id=? AND ordinal=? AND delete_state='deleting'"
   ).bind('+'+Math.max(5,Math.min(7200,decision.retrySeconds||90))+' seconds',decision.reason||'retry',item.job_id,item.ordinal).run();
   result.retried++;
  }else{
   await env.DB.prepare(
    "UPDATE cine_delivery_job_items SET delete_state='manual_review',delete_lock_until=NULL,delete_last_error=? WHERE job_id=? AND ordinal=? AND delete_state='deleting'"
   ).bind(decision.reason||'unknown',item.job_id,item.ordinal).run();
   result.manual_review++;
  }
 }
 // A lightweight, capped record makes failures visible in owner dashboard.
 if(result.checked||result.manual_review){
  await env.DB.prepare("INSERT INTO cine_delivery_cleanup_runs(claimed,deleted,already_gone,retries,failed,manual_review) VALUES(?,?,?,?,?,?)").bind(result.checked,result.deleted,result.already_gone,result.retried,result.failed,result.manual_review).run();
 }
 return result;
}
