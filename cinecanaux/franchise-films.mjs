import {guardTelegramMethod,noteTelegramFloodWait} from './telegram-global-quota.mjs';
// Fast & Furious VF: public-channel saga indexed by Telegram Bot API only.
// Owner forwards create permanent receipts in their private CineRadar chat.
// The subscriber receives only actually indexed films, each removed after 24h.
// No user-account session, Telethon, bulk Telegram-history access or binary media.
import {deletionDecision} from './cinex-expiry.mjs';

const SLUG='fast-and-furious';
const HANDLE='fastandfuriousvffr';
const START=/^\/start(?:@[a-z0-9_]+)?\s+ffs_([a-zA-Z0-9_-]{24})\s*$/i;
const NUMBER=/^\/ff(?:@[a-z0-9_]+)?\s+(10|[1-9])\s*$/i;
const STATUS=/^\/ffstatus(?:@[a-z0-9_]+)?\s*$/i;
const HELP=/^\/ff(?:@[a-z0-9_]+)?\s*$/i;
const CHAT=/^-100[0-9]{6,}$/;
const isId=x=>Number.isSafeInteger(Number(x))&&Number(x)>0;
const isVideo=x=>Boolean(x?.video)||String(x?.document?.mime_type||'').startsWith('video/');
const isPoster=x=>Array.isArray(x?.photo)&&x.photo.length>0;
const TG='https://api.telegram.org/bot';

async function telegram(env,method,payload){
 const quota=await guardTelegramMethod(env,method,payload);
 if(quota&&!quota.allowed)return {ok:false,code:429,retry:quota.retryAfter,quotaDeferred:true};
 const reply=await fetch(TG+env.TELEGRAM_TOKEN+'/'+method,{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(payload),signal:AbortSignal.timeout(13000),
 });
 let body;try{body=await reply.json()}catch{throw Error('telegram_response_unknown')}
 if(Number(body?.error_code||reply.status)===429)await noteTelegramFloodWait(env,Number(body?.parameters?.retry_after||30));
 return {ok:reply.ok&&body?.ok===true,result:body?.result,
  code:Number(body?.error_code||reply.status),description:String(body?.description||'').slice(0,100),
  retry:Number(body?.parameters?.retry_after||0)};
}
async function notify(env,chat,message){
 try{await telegram(env,'sendMessage',{chat_id:chat,text:String(message).slice(0,1500)})}catch{}
}
async function owner(env,userId){
 if(!isId(userId))return false;
 const row=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(Number(userId)).first();
 return row?.role==='owner';
}
async function catalogue(env){
 return await env.DB.prepare("SELECT slug,source_chat_id,public_username,title,poster_source_message_id,token,status,rights_attested FROM cine_franchise_catalog WHERE slug=?").bind(SLUG).first();
}
function safeCaption(msg){
 return String(msg?.caption||msg?.text||msg?.video?.file_name||msg?.document?.file_name||'').slice(0,1600);
}

export function parseFranchiseFilmNumber(caption){
 const raw=String(caption||'').slice(0,450);
 // An owner may forward a compilation or a shared cover with ranges
 // such as "1 à 10", "1-9" or multiple named movies. Never silently
 // attribute that file to one film; it must be assigned by /ff N instead.
 if(/\b(?:10|[1-9])\s*(?:[-–—]|à|au|to|through|jusqu['’]?à)\s*(?:10|[1-9])\b/i.test(raw))
  return null;
 const s=raw.replace(/[_-]/g,' ');
 const distinct=new Set([...s.matchAll(/(?:fast\s*(?:and|&)\s*furious|furious|ff|film|partie|part)\s*[#.: -]?\s*(10|0?[1-9])(?=$|[^0-9])/gi)].map(m=>Number(m[1])));
 if(distinct.size>1)return null;
 const patterns=[
  /(?:^|\s)(?:ff|f&f|film|partie|part)\s*[#.: -]?\s*(10|0?[1-9])(?=$|[^0-9])/i,
  /fast\s*(?:and|&)\s*furious\s*[#.: -]?\s*(10|0?[1-9])(?=$|[^0-9])/i,
  /fast\s*furious\s*[#.: -]?\s*(10|0?[1-9])(?=$|[^0-9])/i,
  /furious\s*(10|0?[1-9])(?=$|[^0-9])/i,
  /(?:^|\s)(?:fast|f)\s*9(?=$|[^0-9])/i,
  /fast\s+x(?=$|[^a-z])/i,
 ];
 for(const [index,re] of patterns.entries()){
  const m=re.exec(s);
  if(!m)continue;
  const n=index===4?9:index===5?10:Number(m[1]);
  if(n>=1&&n<=10)return n;
 }
 if(/\b2\s+fast\s+2\s+furious\b/i.test(s))return 2;
 if(/\btokyo\s+drift\b/i.test(s))return 3;
 if(/\bfast\s+five\b/i.test(s))return 5;
 if(/\bfate\s+of\s+the\s+furious\b/i.test(s))return 8;
 return null;
}

async function verifySource(env,origin){
 const row=await catalogue(env);
 if(!row||!origin?.chat?.id||!CHAT.test(String(origin.chat.id)))return null;
 const chatId=String(origin.chat.id);
 if(row.source_chat_id===chatId)return row;
 const username=String(origin.chat.username||'').replace(/^@/,'').toLowerCase();
 if(row.source_chat_id&&row.source_chat_id!==chatId)return null;
 if(username!==HANDLE){
  // If Telegram omitted the username from the forwarded origin, resolve the
  // actual public-channel identity via CineRadar itself, never by user text.
  let info;try{info=await telegram(env,'getChat',{chat_id:'@'+HANDLE})}catch{return null}
  if(!info.ok||String(info.result?.id)!==chatId||
   String(info.result?.username||'').toLowerCase()!==HANDLE)return null;
 }
 await env.DB.prepare(
  "UPDATE cine_franchise_catalog SET source_chat_id=?,updated_at=CURRENT_TIMESTAMP "+
  "WHERE slug=? AND (source_chat_id IS NULL OR source_chat_id=?)"
 ).bind(chatId,SLUG,chatId).run();
 return {...row,source_chat_id:chatId};
}

async function saveFilm(env,chatId,messageId,part,title){
 if(!CHAT.test(chatId)||!isId(messageId)||!Number.isInteger(part)||part<1||part>10)return {stored:false,reason:'Référence invalide'};
 const previous=await env.DB.prepare(
  "SELECT source_chat_id,source_message_id FROM cine_franchise_films WHERE slug=? AND part=?"
 ).bind(SLUG,part).first();
 if(previous&&(previous.source_chat_id!==chatId||Number(previous.source_message_id)!==Number(messageId)))
  return {stored:false,reason:'Le film '+part+' est déjà enregistré avec une autre vidéo. Aucun remplacement automatique.'};
 const used=await env.DB.prepare(
  "SELECT part FROM cine_franchise_films WHERE source_chat_id=? AND source_message_id=?"
 ).bind(chatId,Number(messageId)).first();
 if(used&&Number(used.part)!==part)return {stored:false,reason:'Cette vidéo est déjà enregistrée comme film '+used.part+'.'};
 await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_franchise_films(slug,part,source_chat_id,source_message_id,title) VALUES(?,?,?,?,?)"
 ).bind(SLUG,part,chatId,Number(messageId),String(title||'Fast and Furious '+part).slice(0,120)).run();
 return {stored:true,part};
}

async function savePoster(env,chatId,messageId,caption){
 const row=await catalogue(env);
 if(row?.poster_source_message_id&&Number(row.poster_source_message_id)!==Number(messageId))
  return {stored:false,reason:'Une affiche principale est déjà enregistrée. Aucune substitution automatique.'};
 await env.DB.prepare(
  "UPDATE cine_franchise_catalog SET poster_source_message_id=?,poster_caption=?,updated_at=CURRENT_TIMESTAMP WHERE slug=? AND source_chat_id=?"
 ).bind(Number(messageId),String(caption||'').slice(0,1500),SLUG,chatId).run();
 return {stored:true,poster:true};
}

export async function ingestFranchiseOwnerForward(env,msg){
 const origin=msg?.forward_origin;
 if(msg?.chat?.type!=='private'||msg.chat.id!==msg?.from?.id||origin?.type!=='channel'||
  !isId(origin.message_id)||(!isPoster(msg)&&!isVideo(msg)))return {handled:false};
 if(!await owner(env,msg.from?.id))return {handled:false};
 const source=await verifySource(env,origin);
 if(!source)return {handled:false};
 const channel=String(origin.chat.id),id=Number(origin.message_id),caption=safeCaption(msg);
 if(isPoster(msg)){
  const poster=await savePoster(env,channel,id,caption);
  return {handled:true,...poster,message:poster.stored?'✅ Affiche principale Fast and Furious enregistrée.':'⚠️ '+poster.reason};
 }
 const part=parseFranchiseFilmNumber(caption);
 if(part!==null){
  const film=await saveFilm(env,channel,id,part,caption);
  return {handled:true,...film,message:film.stored?'✅ Fast and Furious '+part+' enregistré dans Ciné Radar.':'⚠️ '+film.reason};
 }
 // The owner can reply /ff 1 ... /ff 10 to the forwarded video. This also
 // handles non-standard movie titles without inventing their franchise order.
 await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_franchise_pending(owner_message_id,owner_chat_id,slug,source_chat_id,source_message_id,caption) "+
  "VALUES(?,?,?,?,?,?)"
 ).bind(Number(msg.message_id),Number(msg.chat.id),SLUG,channel,id,caption).run();
 return {handled:true,stored:false,pending:true,message:'🎬 Vidéo reçue, mais numéro du film inconnu. Réponds directement à cette vidéo par /ff 1, /ff 2… jusqu’à /ff 10.'};
}

export async function ingestFranchiseChannelPost(env,update){
 const msg=update?.channel_post||update?.edited_channel_post;
 if(msg?.chat?.type!=='channel'||(!isVideo(msg)&&!isPoster(msg)&&!isPoster(msg?.pinned_message)))return {handled:false};
 const row=await catalogue(env);
 const id=String(msg.chat.id);
 if(!row||!CHAT.test(id)||(row.source_chat_id!==id&&String(msg.chat.username||'').toLowerCase()!==HANDLE))
  return {handled:false};
 if(row.source_chat_id&&row.source_chat_id!==id)return {handled:false};
 if(!row.source_chat_id){
  await env.DB.prepare("UPDATE cine_franchise_catalog SET source_chat_id=? WHERE slug=? AND source_chat_id IS NULL").bind(id,SLUG).run();
 }
 const pin=isPoster(msg.pinned_message)?msg.pinned_message:null;
 if(pin&&isId(pin.message_id))return {handled:true,...await savePoster(env,id,pin.message_id,safeCaption(pin))};
 if(isPoster(msg)&&!row.poster_source_message_id)return {handled:true,...await savePoster(env,id,msg.message_id,safeCaption(msg))};
 if(isVideo(msg)){
  const part=parseFranchiseFilmNumber(safeCaption(msg));
  if(part!==null)return {handled:true,...await saveFilm(env,id,msg.message_id,part,safeCaption(msg))};
 }
 return {handled:false};
}

export async function handleFranchiseOwnerCommand(env,update){
 const msg=update?.message,text=String(msg?.text||'').trim();
 if(!STATUS.test(text)&&!HELP.test(text)&&!NUMBER.test(text))return {handled:false};
 if(msg?.chat?.type!=='private'||msg.chat.id!==msg?.from?.id||!await owner(env,msg.from?.id))return {handled:false};
 if(STATUS.test(text)){
  const row=await catalogue(env);
  const media=(await env.DB.prepare("SELECT part FROM cine_franchise_films WHERE slug=? ORDER BY part").bind(SLUG).all()).results||[];
  await notify(env,msg.chat.id,'🎬 Fast and Furious VF\nCanal : https://t.me/'+HANDLE+
   '\nAffiche : '+(row?.poster_source_message_id?'✅':'❌')+
   '\nFilms enregistrés : '+(media.length?media.map(x=>x.part).join(', '):'aucun')+
   '\nLien de test privé : https://t.me/CineRadarFr_Bot?start=ffs_'+String(row?.token||'')+
   '\nPour un titre non reconnu : réponds à la vidéo transférée par /ff N.');
  return {handled:true};
 }
 if(HELP.test(text)){
  await notify(env,msg.chat.id,'Transfère l’affiche et les vidéos depuis https://t.me/'+HANDLE+
   ' vers cette discussion. Les numéros visibles (Fast and Furious 1, 2, etc.) seront indexés. Sinon, réponds à chaque vidéo par /ff 1… /ff 10. Commande /ffstatus pour voir le catalogue.');
  return {handled:true};
 }
 const part=Number(NUMBER.exec(text)[1]);
 const replyId=Number(msg.reply_to_message?.message_id);
 if(!isId(replyId)){await notify(env,msg.chat.id,'Réponds avec /ff '+part+' DIRECTEMENT à la vidéo transférée.');return {handled:true,stored:false}}
 const pending=await env.DB.prepare(
  "SELECT source_chat_id,source_message_id,caption FROM cine_franchise_pending "+
  "WHERE slug=? AND owner_chat_id=? AND owner_message_id=?"
 ).bind(SLUG,msg.chat.id,replyId).first();
 if(!pending){await notify(env,msg.chat.id,'Vidéo non trouvée dans les transferts Fast and Furious en attente.');return {handled:true,stored:false}}
 const answer=await saveFilm(env,pending.source_chat_id,pending.source_message_id,part,pending.caption||'Fast and Furious '+part);
 if(answer.stored)await env.DB.prepare("DELETE FROM cine_franchise_pending WHERE slug=? AND owner_chat_id=? AND owner_message_id=?").bind(SLUG,msg.chat.id,replyId).run();
 await notify(env,msg.chat.id,answer.stored?'✅ Film '+part+' enregistré.':'⚠️ '+answer.reason);
 return {handled:true,...answer};
}

export async function handleFranchiseDownloadStart(env,update){
 const msg=update?.message,match=START.exec(String(msg?.text||'').trim());
 if(!match)return {handled:false};
 const chat=msg?.chat?.id;
 if(msg?.chat?.type!=='private'||chat!==msg.from?.id||!isId(chat)||!isId(update.update_id))return {handled:true,accepted:false};
 const gate=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
 if(gate?.value!=='1'){await notify(env,chat,'Les téléchargements sont temporairement désactivés.');return {handled:true,accepted:false}}
 const isOwner=await owner(env,chat);
 const row=await env.DB.prepare(
  "SELECT slug,title,source_chat_id FROM cine_franchise_catalog WHERE token=? AND rights_attested=1 "+
  "AND (status='published' OR (status='draft' AND ?=1))"
 ).bind(match[1],isOwner?1:0).first();
 if(!row||!CHAT.test(String(row.source_chat_id))){await notify(env,chat,'Saga temporairement indisponible.');return {handled:true,accepted:false}}
 const media=(await env.DB.prepare(
  "SELECT f.part,f.source_chat_id,f.source_message_id,"+
  "CASE WHEN a.user_id IS NOT NULL THEN v.owner_chat_id END AS owner_chat_id,"+
  "CASE WHEN a.user_id IS NOT NULL THEN v.owner_message_id END AS owner_message_id "+
  "FROM cine_franchise_films f LEFT JOIN cine_owner_vault v ON v.source_chat_id=f.source_chat_id "+
  "AND v.source_message_id=f.source_message_id AND v.status='stored' "+
  "LEFT JOIN admin_users a ON a.role='owner' AND a.user_id=v.owner_chat_id "+
  "WHERE f.slug=? ORDER BY f.part"
 ).bind(row.slug).all()).results||[];
 if(!media.length||media.length>10){await notify(env,chat,'Aucun film disponible pour le moment.');return {handled:true,accepted:false}}
 const old=await env.DB.prepare("SELECT id FROM cine_franchise_jobs WHERE telegram_update_id=?").bind(update.update_id).first();
 if(old)return {handled:true,accepted:true,duplicate:true};
 const recent=await env.DB.prepare("SELECT COUNT(*) AS n FROM cine_franchise_jobs WHERE telegram_chat_id=? AND created_at>=datetime('now','-1 hour')").bind(chat).first();
 if(Number(recent?.n||0)>=2){await notify(env,chat,'Trop de demandes récentes. Réessaie plus tard.');return {handled:true,accepted:false}}
 await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_franchise_jobs(slug,telegram_update_id,telegram_chat_id,planned_items) VALUES(?,?,?,?)"
 ).bind(row.slug,update.update_id,chat,media.length).run();
 const job=await env.DB.prepare("SELECT id FROM cine_franchise_jobs WHERE telegram_update_id=? AND telegram_chat_id=?").bind(update.update_id,chat).first();
 if(!job?.id)throw Error('franchise_job_missing');
 await env.DB.batch(media.map(x=>env.DB.prepare(
  "INSERT OR IGNORE INTO cine_franchise_job_items(job_id,part,source_chat_id,source_message_id) VALUES(?,?,?,?)"
 ).bind(job.id,x.part,isId(x.owner_chat_id)&&isId(x.owner_message_id)?String(x.owner_chat_id):x.source_chat_id,
 isId(x.owner_chat_id)&&isId(x.owner_message_id)?Number(x.owner_message_id):x.source_message_id)));
 await notify(env,chat,'📥 Fast and Furious VF : '+media.length+' film(s) actuellement disponibles : '+
  media.map(x=>x.part).join(', ')+'.\nEnvoi progressif en privé. Chaque copie envoyée par le bot sera supprimée après 24 h. Les films absents du catalogue ne sont pas promis.');
 return {handled:true,accepted:true,planned:media.length};
}

export async function processFranchiseQueue(env,{limit=2}={}){
 if(!env?.DB||!env.TELEGRAM_TOKEN)return {processed:0,disabled:true};
 const gate=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
 if(gate?.value!=='1')return {processed:0,disabled:true};
 await env.DB.prepare(
  "UPDATE cine_franchise_jobs SET status='needs_review' WHERE status='sending' AND lock_until<CURRENT_TIMESTAMP"
 ).run();
 await env.DB.prepare(
  "UPDATE cine_franchise_job_items SET state='needs_review' WHERE state='sending' AND job_id IN (SELECT id FROM cine_franchise_jobs WHERE status='needs_review')"
 ).run();
 const rows=(await env.DB.prepare(
  "SELECT j.id,j.slug,j.telegram_chat_id,c.source_chat_id AS original_chat "+
  "FROM cine_franchise_jobs j JOIN cine_franchise_catalog c ON c.slug=j.slug "+
  "WHERE j.status='queued' AND j.not_before<=CURRENT_TIMESTAMP AND c.rights_attested=1 "+
  "AND (c.status='published' OR (c.status='draft' AND EXISTS(SELECT 1 FROM admin_users a WHERE a.user_id=j.telegram_chat_id AND a.role='owner'))) "+
  "ORDER BY j.id LIMIT 2"
 ).all()).results||[];
 let processed=0,errors=0;
 for(const job of rows){
  const items=(await env.DB.prepare(
   "SELECT part,source_chat_id,source_message_id FROM cine_franchise_job_items "+
   "WHERE job_id=? AND state='queued' ORDER BY part LIMIT ?"
  ).bind(job.id,Math.min(3,Math.max(1,Number(limit)||2))).all()).results||[];
  if(!items.length){
   await env.DB.prepare("UPDATE cine_franchise_jobs SET status='complete' WHERE id=? AND status='queued'").bind(job.id).run();
   continue;
  }
  for(const item of items){
   if(!isId(item.source_message_id)||!isId(job.telegram_chat_id)){errors++;break}
   const verified=await env.DB.prepare(
    "SELECT 1 AS ok FROM cine_franchise_films f LEFT JOIN cine_owner_vault v ON "+
    "v.source_chat_id=f.source_chat_id AND v.source_message_id=f.source_message_id AND v.status='stored' "+
    "LEFT JOIN admin_users a ON a.role='owner' AND a.user_id=v.owner_chat_id "+
    "WHERE f.slug=? AND f.part=? AND ( (f.source_chat_id=? AND f.source_message_id=?) OR "+
    "(a.user_id IS NOT NULL AND CAST(v.owner_chat_id AS TEXT)=? AND v.owner_message_id=?))"
   ).bind(job.slug,item.part,item.source_chat_id,item.source_message_id,item.source_chat_id,item.source_message_id).first();
   if(!verified?.ok){
    await env.DB.prepare("UPDATE cine_franchise_job_items SET state='needs_review' WHERE job_id=? AND part=?").bind(job.id,item.part).run();
    await env.DB.prepare("UPDATE cine_franchise_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();
    errors++;break;
   }
   const lock=await env.DB.prepare(
    "UPDATE cine_franchise_jobs SET status='sending',lock_until=datetime('now','+3 minutes') WHERE id=? AND status='queued'"
   ).bind(job.id).run();
   if(Number(lock.meta?.changes||0)!==1)break;
   await env.DB.prepare("UPDATE cine_franchise_job_items SET state='sending' WHERE job_id=? AND part=? AND state='queued'").bind(job.id,item.part).run();
   let answer;
   try{answer=await telegram(env,'copyMessage',{
    chat_id:job.telegram_chat_id,from_chat_id:item.source_chat_id,message_id:item.source_message_id,
    protect_content:false
   })}catch{
    await env.DB.prepare("UPDATE cine_franchise_job_items SET state='needs_review' WHERE job_id=? AND part=?").bind(job.id,item.part).run();
    await env.DB.prepare("UPDATE cine_franchise_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();
    errors++;break;
   }
   const receipt=Number(answer?.result?.message_id);
   if(!answer.ok||!isId(receipt)){
    if(answer.code===429&&answer.retry>0){
     await env.DB.prepare("UPDATE cine_franchise_job_items SET state='queued' WHERE job_id=? AND part=?").bind(job.id,item.part).run();
     await env.DB.prepare(
      "UPDATE cine_franchise_jobs SET status='queued',not_before=datetime('now',?),lock_until=NULL WHERE id=?"
     ).bind('+'+Math.min(3600,Math.max(15,answer.retry))+' seconds',job.id).run();
    }else{
     await env.DB.prepare("UPDATE cine_franchise_job_items SET state='needs_review' WHERE job_id=? AND part=?").bind(job.id,item.part).run();
     await env.DB.prepare("UPDATE cine_franchise_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();
    }
    errors++;break;
   }
   await env.DB.batch([
    env.DB.prepare(
     "UPDATE cine_franchise_job_items SET state='sent',delivered_message_id=?,sent_at=CURRENT_TIMESTAMP,"+
     "delete_after=datetime('now','+24 hours'),delete_retry_at=datetime('now','+24 hours') "+
     "WHERE job_id=? AND part=? AND state='sending'"
    ).bind(receipt,job.id,item.part),
    env.DB.prepare(
     "UPDATE cine_franchise_jobs SET status='queued',lock_until=NULL,delivered_items=delivered_items+1 WHERE id=?"
    ).bind(job.id)
   ]);
   processed++;
   if(items.length>1)await new Promise(resolve=>setTimeout(resolve,1000));
  }
 }
 return {processed,errors};
}

export async function cleanupFranchiseCopies(env,{limit=12,now=Date.now()}={}){
 if(!env?.DB||!env.TELEGRAM_TOKEN)return {deleted:0,disabled:true};
 const result={deleted:0,already_gone:0,retried:0,manual_review:0};
 await env.DB.prepare(
  "UPDATE cine_franchise_job_items SET delete_state='retry',delete_retry_at=CURRENT_TIMESTAMP,delete_lock_until=NULL "+
  "WHERE delete_state='deleting' AND delete_lock_until<CURRENT_TIMESTAMP"
 ).run();
 const rows=(await env.DB.prepare(
  "SELECT i.job_id,i.part,i.delivered_message_id,i.sent_at,i.delete_attempts,j.telegram_chat_id "+
  "FROM cine_franchise_job_items i JOIN cine_franchise_jobs j ON j.id=i.job_id "+
  "WHERE i.state='sent' AND i.delivered_message_id IS NOT NULL AND "+
  "i.delete_after<=CURRENT_TIMESTAMP AND COALESCE(i.delete_retry_at,i.delete_after)<=CURRENT_TIMESTAMP "+
  "AND i.delete_state IN ('pending','retry') ORDER BY i.delete_after,i.job_id,i.part LIMIT ?"
 ).bind(Math.min(24,Math.max(1,Number(limit)||12))).all()).results||[];
 for(const row of rows){
  if(!isId(row.telegram_chat_id)||!isId(row.delivered_message_id)){
   await env.DB.prepare(
    "UPDATE cine_franchise_job_items SET delete_state='manual_review',delete_last_error='invalid_private_receipt' "+
    "WHERE job_id=? AND part=?"
   ).bind(row.job_id,row.part).run();
   result.manual_review++;continue;
  }
  const lock=await env.DB.prepare(
   "UPDATE cine_franchise_job_items SET delete_state='deleting',delete_lock_until=datetime('now','+2 minutes'),delete_attempts=delete_attempts+1 "+
   "WHERE job_id=? AND part=? AND state='sent' AND delete_state IN ('pending','retry') AND delete_after<=CURRENT_TIMESTAMP AND COALESCE(delete_retry_at,delete_after)<=CURRENT_TIMESTAMP"
  ).bind(row.job_id,row.part).run();
  if(Number(lock.meta?.changes||0)!==1)continue;
  const attempt=Number(row.delete_attempts||0)+1;
  const opts={sentAt:row.sent_at,now,attempt};
  let decision=deletionDecision({networkError:true},opts);
  if(!['telegram_48h_window','invalid_sent_at','not_due','retry_limit'].includes(decision.reason)){
   let answer;
   try{answer=await telegram(env,'deleteMessage',{chat_id:row.telegram_chat_id,message_id:row.delivered_message_id})}
   catch{answer={networkError:true}}
   decision=deletionDecision(answer?.ok?{ok:true,result:answer.result}:{
    networkError:answer?.networkError,error_code:answer?.code,
    description:answer?.description,parameters:{retry_after:answer?.retry}
   },opts);
  }
  if(decision.state==='deleted'||decision.state==='already_gone'){
   await env.DB.prepare(
    "UPDATE cine_franchise_job_items SET delete_state=?,delete_lock_until=NULL,delete_retry_at=NULL,delete_last_error=NULL WHERE job_id=? AND part=? AND delete_state='deleting'"
   ).bind(decision.state,row.job_id,row.part).run();
   result[decision.state==='deleted'?'deleted':'already_gone']++;
  }else if(decision.state==='retry'){
   await env.DB.prepare(
    "UPDATE cine_franchise_job_items SET delete_state='retry',delete_retry_at=datetime('now',?),delete_last_error=?,delete_lock_until=NULL WHERE job_id=? AND part=? AND delete_state='deleting'"
   ).bind('+'+Math.min(3600,Math.max(60,decision.retrySeconds||90))+' seconds',decision.reason||'retry',row.job_id,row.part).run();
   result.retried++;
  }else{
   await env.DB.prepare(
    "UPDATE cine_franchise_job_items SET delete_state='manual_review',delete_last_error=?,delete_lock_until=NULL WHERE job_id=? AND part=? AND delete_state='deleting'"
   ).bind(decision.reason||'unresolved',row.job_id,row.part).run();
   result.manual_review++;
  }
 }
 return result;
}
