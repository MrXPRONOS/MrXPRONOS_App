// One-shot, owner-only production bridge probe for the already authorized
// Cine Radar film relay. Triggered only by an explicit D1 flag and the existing
// minute Cron. Never broadcasts to subscribers and never retries ambiguous sends.
import {delivery44Enabled,remoteCopyMessage} from './delivery44-client.mjs';
import {sourceFromPrivateStock} from './private-stock.mjs';
const FLAG='cine_delivery44_smoke_once';
const JOB='delivery44_bridge_smoke';
async function saveOutcome(env,status,detail){
 await env.DB.prepare(
  "INSERT INTO radar_ops_status(job_name,last_attempt_at,last_success_at,status,detail) "+
  "VALUES(?,CURRENT_TIMESTAMP,CASE WHEN ?='ok' THEN CURRENT_TIMESTAMP ELSE NULL END,?,?) "+
  "ON CONFLICT(job_name) DO UPDATE SET last_attempt_at=CURRENT_TIMESTAMP,"+
  "last_success_at=CASE WHEN excluded.status='ok' THEN CURRENT_TIMESTAMP ELSE radar_ops_status.last_success_at END,"+
  "status=excluded.status,detail=excluded.detail"
 ).bind(JOB,status,status,JSON.stringify(detail).slice(0,650)).run();
}
export async function runDelivery44SmokeOnce(env){
 if (!env?.DB) return {status:'skipped',reason:'db_unavailable'};
 const flag=await env.DB.prepare('SELECT value FROM bot_settings WHERE setting_key=?').bind(FLAG).first();
 if(flag?.value!=='1')return {status:'skipped'};
 const claim=await env.DB.prepare(
  "UPDATE bot_settings SET value='running',updated_at=CURRENT_TIMESTAMP WHERE setting_key=? AND value='1'"
 ).bind(FLAG).run();
 if(Number(claim.meta?.changes||0)!==1)return {status:'skipped',reason:'already_claimed'};
 const started=Date.now();
 let result;
 try{
  if(!delivery44Enabled(env)) throw Error('bridge_not_enabled');
  const owners=(await env.DB.prepare(
   "SELECT user_id FROM admin_users WHERE role='owner' LIMIT 2"
  ).all()).results||[];
  if(owners.length!==1||!Number.isSafeInteger(Number(owners[0].user_id))||Number(owners[0].user_id)<=0)
   throw Error('single_owner_required');
  // A previously delivered authorized source is the safest live test.
  const source=await env.DB.prepare(
   "SELECT l.source_chat_id,l.source_message_id FROM cine_classic_deliveries d "+
   "JOIN cine_classic_links l ON l.token=d.token "+
   "WHERE d.status='sent' AND l.status='published' "+
   "ORDER BY d.id DESC LIMIT 1"
  ).first();
  if(!source||!/^-100[0-9]{5,}$/.test(String(source.source_chat_id))||
     !Number.isSafeInteger(Number(source.source_message_id))||Number(source.source_message_id)<=0)
   throw Error('verified_classic_source_unavailable');
  const stock=await sourceFromPrivateStock(env,source.source_chat_id,source.source_message_id);
  if(!stock||!Number.isSafeInteger(Number(stock.messageId))||Number(stock.messageId)<=0)
   throw Error('private_source_missing');
  const requestId='classic:'+Date.now();
  const reply=await remoteCopyMessage(env,requestId,{
   chat_id:Number(owners[0].user_id),
   from_chat_id:stock.chatId,message_id:stock.messageId,protect_content:false
  });
  const elapsed_ms=Date.now()-started;
  const via44=reply?.ok===true&&reply.via44===true;
  const fallback=reply?.ok===true&&reply.via44===false;
  const status=via44?'ok':fallback?'partial':'error';
  result={status,via44,elapsed_ms,request_id:requestId,
   error_code:reply?.ok?0:Number(reply?.error_code||reply?.code||0),
   uncertain:!!reply?.uncertain};
  await saveOutcome(env,status,result);
 }catch(err){
  result={status:'error',via44:false,elapsed_ms:Date.now()-started,
   error:String(err?.message||err?.name||'unexpected').slice(0,100)};
  await saveOutcome(env,'error',result).catch(()=>{});
 }finally{
  await env.DB.prepare(
   "UPDATE bot_settings SET value='finished',updated_at=CURRENT_TIMESTAMP WHERE setting_key=? AND value='running'"
  ).bind(FLAG).run().catch(()=>{});
 }
 console.log(JSON.stringify({event:'cine_delivery44_owner_smoke',...result}));
 return result;
}
