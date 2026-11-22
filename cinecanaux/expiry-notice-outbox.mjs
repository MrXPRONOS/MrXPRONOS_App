// Envoi strictement APRÈS les copies Telegram : un seul message d'expiration
// séparé par demande, sans légende ajoutée aux vidéos d'origine.
// Un reçu "sending" ambigu ne doit jamais être renvoyé automatiquement.
import {guardTelegramMethod,noteTelegramFloodWait} from './telegram-global-quota.mjs';

const FAMILIES=Object.freeze({
 classics:{jobs:'cine_classic_deliveries',items:null},
 libraries:{jobs:'cine_delivery_jobs',items:'cine_delivery_job_items',key:'ordinal'},
 series:{jobs:'cine_series_jobs',items:'cine_series_job_items',key:'ordinal'},
 franchise:{jobs:'cine_franchise_jobs',items:'cine_franchise_job_items',key:'part'},
});
const initialized=new WeakSet();
const safeId=x=>Number.isSafeInteger(Number(x))&&Number(x)>0;

async function ensureNoticeStorage(env){
 if(initialized.has(env.DB))return;
 await env.DB.prepare(
  "CREATE TABLE IF NOT EXISTS cine_expiry_notice_outbox ("+
  "family TEXT NOT NULL,job_id INTEGER NOT NULL,chat_id INTEGER NOT NULL,"+
  "first_expiry TEXT NOT NULL,last_expiry TEXT NOT NULL,media_count INTEGER NOT NULL,"+
  "state TEXT NOT NULL DEFAULT 'queued',retry_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"+
  "lock_until TEXT,telegram_message_id INTEGER,sent_at TEXT,error_code INTEGER,"+
  "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"+
  "PRIMARY KEY(family,job_id))"
 ).run();
 // Never send new notices for historic jobs, which already had their
 // expiry explanation inside their original video caption.
 await env.DB.prepare(
  "INSERT OR IGNORE INTO bot_settings(setting_key,value) VALUES('cine_expiry_notice_cutover',CURRENT_TIMESTAMP)"
 ).run();
 initialized.add(env.DB);
}

function asDate(value){
 const text=String(value||'').trim().replace(' ','T');
 const date=/Z$|[+-]\d{2}:\d{2}$/.test(text)?text:text+'Z';
 const millis=Date.parse(date);
 return Number.isFinite(millis)?new Date(millis):null;
}
function stamp(value){
 const date=asDate(value);
 if(!date)return null;
 const iso=date.toISOString();
 return iso.slice(8,10)+'/'+iso.slice(5,7)+'/'+iso.slice(0,4)+' à '+iso.slice(11,16)+' (UTC)';
}
export function expiryNoticeText({mediaCount=1,firstExpiry,lastExpiry}={}){
 const first=stamp(firstExpiry),last=stamp(lastExpiry||firstExpiry);
 if(!first||!last)throw Error('invalid_notice_expiry');
 if(Number(mediaCount)>1){
  return '⏳ Ces '+Number(mediaCount)+' vidéos seront supprimées automatiquement de ce chat 12 heures après chaque envoi.\n'+
   '🕒 Première suppression prévue : '+first+'.\n'+
   '🕒 Dernière suppression prévue : '+last+'.\n'+
   '💾 Pour les conserver, transfère-les dans « Messages enregistrés » avant leur suppression.';
 }
 return '⏳ Cette vidéo sera supprimée automatiquement de ce chat 12 heures après son envoi.\n'+
  '🕒 Suppression prévue : '+first+'.\n'+
  '💾 Pour la conserver, transfère-la dans « Messages enregistrés » avant cette heure.';
}

export async function queueExpiryNotice(env,family,jobId){
 const cfg=FAMILIES[family];
 if(!cfg||!safeId(jobId)||!env?.DB)return false;
 await ensureNoticeStorage(env);
 let sql;
 if(family==='classics'){
  sql="SELECT telegram_chat_id AS chat_id,1 AS planned,1 AS total,1 AS confirmed,"+
   "delete_after AS first_expiry,delete_after AS last_expiry "+
   "FROM cine_classic_deliveries WHERE id=? AND status='sent' "+
   "AND delivered_message_id IS NOT NULL AND sent_at IS NOT NULL AND delete_after IS NOT NULL";
 }else{
  sql="SELECT j.telegram_chat_id AS chat_id,j.planned_items AS planned,COUNT(i."+cfg.key+") AS total,"+
   "SUM(CASE WHEN i.state='sent' AND i.delivered_message_id IS NOT NULL "+
   "AND i.sent_at IS NOT NULL AND i.delete_after IS NOT NULL THEN 1 ELSE 0 END) AS confirmed,"+
   "MIN(i.delete_after) AS first_expiry,MAX(i.delete_after) AS last_expiry "+
   "FROM "+cfg.jobs+" j JOIN "+cfg.items+" i ON i.job_id=j.id "+
   "WHERE j.id=? AND j.status='complete' GROUP BY j.id";
 }
 const info=await env.DB.prepare(sql).bind(Number(jobId)).first();
 if(!info||!safeId(info.chat_id)||!safeId(info.planned)||
   Number(info.total)!==Number(info.planned)||Number(info.confirmed)!==Number(info.planned)||
   !stamp(info.first_expiry)||!stamp(info.last_expiry))return false;
 const result=await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_expiry_notice_outbox"+
  "(family,job_id,chat_id,first_expiry,last_expiry,media_count) VALUES(?,?,?,?,?,?)"
 ).bind(family,Number(jobId),Number(info.chat_id),info.first_expiry,info.last_expiry,Number(info.planned)).run();
 return Number(result.meta?.changes||0)===1;
}

// Rebuild a missed notification only for jobs created after this feature was
// enabled; do not retroactively spam subscribers for earlier deliveries.
async function recoverCompletedNotices(env){
 const cutover=await env.DB.prepare(
  "SELECT value FROM bot_settings WHERE setting_key='cine_expiry_notice_cutover'"
 ).first();
 if(!cutover?.value)return;
 for(const [family,cfg] of Object.entries(FAMILIES)){
  const state=family==='classics'?'sent':'complete';
  const sql="SELECT j.id FROM "+cfg.jobs+" j WHERE j.status=? AND j.created_at>=? "+
   "AND NOT EXISTS (SELECT 1 FROM cine_expiry_notice_outbox n WHERE n.family=? AND n.job_id=j.id) "+
   "ORDER BY j.id DESC LIMIT 10";
  const rows=(await env.DB.prepare(sql).bind(state,cutover.value,family).all()).results||[];
  for(const row of rows)await queueExpiryNotice(env,family,row.id);
 }
}

async function reschedule(env,row,seconds){
 await env.DB.prepare(
  "UPDATE cine_expiry_notice_outbox SET state='queued',retry_at=datetime('now',?),"+
  "lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE family=? AND job_id=? AND state='sending'"
 ).bind('+'+Math.min(3600,Math.max(5,Number(seconds)||30))+' seconds',row.family,row.job_id).run();
}
async function markUncertain(env,row,code=0){
 await env.DB.prepare(
  "UPDATE cine_expiry_notice_outbox SET state='needs_review',error_code=?,lock_until=NULL,"+
  "updated_at=CURRENT_TIMESTAMP WHERE family=? AND job_id=? AND state='sending'"
 ).bind(Number(code)||0,row.family,row.job_id).run();
}

export async function processExpiryNotices(env,{limit=3,family=null,jobId=null}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {sent:0,disabled:true};
 await ensureNoticeStorage(env);
 // A send whose response is lost may already have reached Telegram.
 await env.DB.prepare(
  "UPDATE cine_expiry_notice_outbox SET state='needs_review',lock_until=NULL,"+
  "updated_at=CURRENT_TIMESTAMP WHERE state='sending' AND lock_until<CURRENT_TIMESTAMP"
 ).run();
 if(!family)await recoverCompletedNotices(env);
 const preferred=family&&FAMILIES[family]&&safeId(jobId);
 const sql="SELECT family,job_id,chat_id,first_expiry,last_expiry,media_count "+
  "FROM cine_expiry_notice_outbox WHERE state='queued' AND retry_at<=CURRENT_TIMESTAMP"+
  (preferred?" AND family=? AND job_id=?":"")+" ORDER BY created_at,job_id LIMIT ?";
 const binds=preferred?[family,Number(jobId),Math.max(1,Math.min(6,limit))]:[Math.max(1,Math.min(6,limit))];
 const rows=(await env.DB.prepare(sql).bind(...binds).all()).results||[];
 let sent=0,deferred=0,review=0;
 for(const row of rows){
  if(!safeId(row.chat_id)){await markUncertain(env,row,400);review++;continue}
  const claimed=await env.DB.prepare(
   "UPDATE cine_expiry_notice_outbox SET state='sending',lock_until=datetime('now','+2 minutes'),"+
   "updated_at=CURRENT_TIMESTAMP WHERE family=? AND job_id=? AND state='queued' AND retry_at<=CURRENT_TIMESTAMP"
  ).bind(row.family,row.job_id).run();
  if(Number(claimed.meta?.changes||0)!==1)continue;
  let message;
  try{message=expiryNoticeText({mediaCount:row.media_count,firstExpiry:row.first_expiry,lastExpiry:row.last_expiry})}
  catch{await markUncertain(env,row,400);review++;continue}
  const payload={chat_id:Number(row.chat_id),text:message};
  // Media was just copied: leave Telegram's per-recipient one-second send slot
  // before the separate text, without delaying the video itself.
  if(preferred)await new Promise(resolve=>setTimeout(resolve,1100));
  try{
   const quota=await guardTelegramMethod(env,'sendMessage',payload);
   if(quota&&!quota.allowed){await reschedule(env,row,quota.retryAfter||30);deferred++;continue}
   const reply=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/sendMessage',{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(payload),signal:AbortSignal.timeout(12000)
   });
   let body;
   try{body=await reply.json()}catch{await markUncertain(env,row,502);review++;continue}
   const code=Number(body?.error_code||reply.status);
   if(code===429){
    const delay=Number(body?.parameters?.retry_after||30);
    await noteTelegramFloodWait(env,delay);
    await reschedule(env,row,delay);deferred++;continue;
   }
   const messageId=Number(body?.result?.message_id||0);
   if(reply.ok&&body?.ok===true&&safeId(messageId)){
    await env.DB.prepare(
     "UPDATE cine_expiry_notice_outbox SET state='sent',telegram_message_id=?,sent_at=CURRENT_TIMESTAMP,"+
     "lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE family=? AND job_id=? AND state='sending'"
    ).bind(messageId,row.family,row.job_id).run();
    sent++;continue;
   }
   await markUncertain(env,row,code);review++;
  }catch{
   // Never retry a possibly-delivered Telegram message.
   await markUncertain(env,row,502);review++;
  }
 }
 return {sent,deferred,review};
}
