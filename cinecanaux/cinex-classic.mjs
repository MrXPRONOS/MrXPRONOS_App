import {sourceFromPrivateStock} from './private-stock.mjs';
import {guardTelegramMethod,noteTelegramFloodWait} from './telegram-global-quota.mjs';
// CinéX classic films: safe private Telegram copies from verified library media.
// Public video/poster messages are never deleted; only the bot's private copies.
import {deletionDecision} from './cinex-expiry.mjs';
const TOKEN=/^[A-Za-z0-9_-]{24}$/;
const START=/^\/start(?:@[A-Za-z0-9_]+)?\s+d_([A-Za-z0-9_-]{24})\s*$/i;
const BASE='https://api.telegram.org/bot';
async function telegram(env,method,payload){
 const quota=await guardTelegramMethod(env,method,payload);
 if(quota&&!quota.allowed)return {ok:false,error_code:429,retry_after:quota.retryAfter,quotaDeferred:true};
 const response=await fetch(BASE+env.TELEGRAM_TOKEN+'/'+method,{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)
 });
 let body;try{body=await response.json()}catch{throw Error('telegram_response_unknown')}
 if(Number(body?.error_code||response.status)===429)await noteTelegramFloodWait(env,Number(body?.parameters?.retry_after||30));
 return {ok:response.ok&&body?.ok===true,result:body?.result,
  error_code:Number(body?.error_code||response.status),
  description:String(body?.description||'').slice(0,140),
  retry_after:Number(body?.parameters?.retry_after||0)};
}
const safeChat=id=>Number.isSafeInteger(Number(id))&&Number(id)>0;
const safeChannel=id=>/^-100[0-9]{5,}$/.test(String(id||''));
const enabled=async env=>(await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first())?.value==='1';

export async function handleClassicDeliveryStart(env,update){
 const msg=update?.message,m=START.exec(String(msg?.text||'').trim());
 if(!m)return {handled:false};
 if(msg?.chat?.type!=='private'||msg?.chat?.id!==msg?.from?.id||!safeChat(msg?.chat?.id)
    ||!Number.isSafeInteger(update?.update_id))return {handled:true,accepted:false};
 const token=m[1];
 if(!await enabled(env))return {handled:false}; // existing handler sends disabled message
 const link=await env.DB.prepare("SELECT token,source_chat_id,source_message_id,title FROM cine_classic_links WHERE token=? AND status='published'").bind(token).first();
 if(!link)return {handled:false}; // normal Action/Series download is handled elsewhere
 if(!safeChannel(link.source_chat_id)||!Number.isSafeInteger(Number(link.source_message_id)))return {handled:true,accepted:false};
 const count=await env.DB.prepare("SELECT COUNT(*) AS n FROM cine_classic_deliveries WHERE telegram_chat_id=? AND created_at>=datetime('now','-1 hour')").bind(msg.chat.id).first();
 if(Number(count?.n||0)>=4){
  await telegram(env,'sendMessage',{chat_id:msg.chat.id,text:'Trop de téléchargements récents. Réessaie plus tard.'}).catch(()=>{});
  return {handled:true,accepted:false};
 }
 const out=await env.DB.prepare("INSERT OR IGNORE INTO cine_classic_deliveries(token,telegram_update_id,telegram_chat_id) VALUES(?,?,?)").bind(token,update.update_id,msg.chat.id).run();
 if(Number(out.meta?.changes||0)!==1)return {handled:true,accepted:true,duplicate:true};
 await telegram(env,'sendMessage',{chat_id:msg.chat.id,text:'🎬 Téléchargement de « '+String(link.title).slice(0,80)+' » en cours. La copie envoyée par le bot sera supprimée après 24 heures. Pour garder le fichier, transfère-le vers Messages enregistrés.'}).catch(()=>{});
 return {handled:true,accepted:true};
}

export async function processClassicDeliveryQueue(env,{limit=3}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN||!await enabled(env))return {processed:0,disabled:true};
 // Expired leases are ambiguous: Telegram may have sent despite a lost response.
 await env.DB.prepare("UPDATE cine_classic_deliveries SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE status='sending' AND lock_until<CURRENT_TIMESTAMP").run();
 const rows=await env.DB.prepare(
  "SELECT d.id,d.telegram_chat_id,l.source_chat_id,l.source_message_id,"+
  "CASE WHEN a.user_id IS NOT NULL THEN v.owner_chat_id END AS owner_chat_id,"+
  "CASE WHEN a.user_id IS NOT NULL THEN v.owner_message_id END AS owner_message_id "+
  "FROM cine_classic_deliveries d JOIN cine_classic_links l ON l.token=d.token "+
  "LEFT JOIN cine_owner_vault v ON v.source_chat_id=l.source_chat_id AND v.source_message_id=l.source_message_id AND v.status='stored' "+
  "LEFT JOIN admin_users a ON a.role='owner' AND a.user_id=v.owner_chat_id "+
  "WHERE d.status='queued' AND l.status='published' ORDER BY d.id LIMIT ?"
 ).bind(Math.min(5,Math.max(1,Number(limit)||3))).all();
 let processed=0,errors=0;
 for(const row of rows.results||[]){
  if(!await enabled(env))break;
  if(!safeChat(row.telegram_chat_id)||!safeChannel(row.source_chat_id)||!Number.isSafeInteger(Number(row.source_message_id)))continue;
  const ownerCopy=safeChat(row.owner_chat_id)&&safeChat(row.owner_message_id);
  const stock=await sourceFromPrivateStock(env,row.source_chat_id,row.source_message_id);
  const sendSource=stock.fromStock?stock.chatId:(ownerCopy?Number(row.owner_chat_id):row.source_chat_id);
  const sendMessageId=stock.fromStock?stock.messageId:(ownerCopy?Number(row.owner_message_id):row.source_message_id);
  const lock=await env.DB.prepare("UPDATE cine_classic_deliveries SET status='sending',lock_until=datetime('now','+3 minutes'),updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='queued'").bind(row.id).run();
  if(Number(lock.meta?.changes||0)!==1)continue;
  let response;
  try{response=await telegram(env,'copyMessage',{
   chat_id:row.telegram_chat_id,from_chat_id:sendSource,message_id:sendMessageId,protect_content:false,
   reply_markup:{inline_keyboard:[[{text:'💾 Comment enregistrer',callback_data:'cinex:save_help'}]]}
  })}catch{
   await env.DB.prepare("UPDATE cine_classic_deliveries SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(row.id).run();errors++;continue;
  }
  const id=Number(response?.result?.message_id||0);
  if(!response.ok||!Number.isSafeInteger(id)||id<=0){
   if(response.error_code===429&&response.retry_after>0){
    await env.DB.prepare("UPDATE cine_classic_deliveries SET status='queued',lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(row.id).run();
   }else{
    await env.DB.prepare("UPDATE cine_classic_deliveries SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(row.id).run();
   }errors++;continue;
  }
  await env.DB.prepare(
   "UPDATE cine_classic_deliveries SET status='sent',delivered_message_id=?,sent_at=CURRENT_TIMESTAMP,delete_after=datetime('now','+24 hours'),delete_retry_at=datetime('now','+24 hours'),updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='sending'"
  ).bind(id,row.id).run();
  processed++;
 }
 return {processed,errors};
}

export async function cleanupClassicDeliveries(env,{limit=12,now=Date.now()}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {deleted:0,disabled:true};
 const stamp=now instanceof Date?now.getTime():Number(now);
 await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state='retry',delete_lock_until=NULL WHERE status='sent' AND delete_state='deleting' AND delete_lock_until<CURRENT_TIMESTAMP").run();
 const rows=await env.DB.prepare(
  "SELECT id,telegram_chat_id,delivered_message_id,sent_at,delete_attempts FROM cine_classic_deliveries WHERE status='sent' AND delivered_message_id IS NOT NULL AND delete_after<=CURRENT_TIMESTAMP AND COALESCE(delete_retry_at,delete_after)<=CURRENT_TIMESTAMP AND delete_state IN ('pending','retry') ORDER BY delete_after,id LIMIT ?"
 ).bind(Math.min(30,Math.max(1,Number(limit)||12))).all();
 const out={deleted:0,already_gone:0,retries:0,manual_review:0};
 for(const row of rows.results||[]){
  if(!safeChat(row.telegram_chat_id)||!Number.isSafeInteger(Number(row.delivered_message_id))||Number(row.delivered_message_id)<=0){
   await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state='manual_review',delete_last_error='invalid_receipt' WHERE id=?").bind(row.id).run();out.manual_review++;continue;
  }
  const lease=await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state='deleting',delete_lock_until=datetime('now','+2 minutes'),delete_attempts=delete_attempts+1 WHERE id=? AND status='sent' AND delete_state IN ('pending','retry') AND delete_after<=CURRENT_TIMESTAMP AND COALESCE(delete_retry_at,delete_after)<=CURRENT_TIMESTAMP").bind(row.id).run();
  if(Number(lease.meta?.changes||0)!==1)continue;
  let decision=deletionDecision({networkError:true},{sentAt:row.sent_at,now:stamp,attempt:Number(row.delete_attempts||0)+1});
  if(decision.reason!=='telegram_48h_window'&&decision.reason!=='invalid_sent_at'&&decision.reason!=='not_due'&&decision.reason!=='retry_limit'){
   let api;
   try{api=await telegram(env,'deleteMessage',{chat_id:row.telegram_chat_id,message_id:row.delivered_message_id})}catch{api={networkError:true}}
   decision=deletionDecision(api?.ok?api:{...api,parameters:{retry_after:api?.retry_after||0}},{sentAt:row.sent_at,now:stamp,attempt:Number(row.delete_attempts||0)+1});
  }
  if(decision.state==='deleted'||decision.state==='already_gone'){
   await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state=?,status='deleted',delete_lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND delete_state='deleting'").bind(decision.state,row.id).run();
   out[decision.state]++;continue;
  }
  if(decision.state==='retry'){
   await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state='retry',delete_retry_at=datetime('now',?),delete_last_error=?,delete_lock_until=NULL WHERE id=? AND delete_state='deleting'").bind('+'+Math.max(60,Math.min(3600,decision.retrySeconds||90))+' seconds',decision.reason,row.id).run();out.retries++;
  }else{
   await env.DB.prepare("UPDATE cine_classic_deliveries SET delete_state='manual_review',delete_last_error=?,delete_lock_until=NULL WHERE id=? AND delete_state='deleting'").bind(decision.reason||'unknown',row.id).run();out.manual_review++;
  }
 }
 return out;
}
