// CinéX -> existing Ciné Radar bot. No video bytes pass through Cloudflare.
// A deep link only enqueues a delivery after explicit owner approval in D1.
// Telegram /start is authenticated by the existing webhook secret in worker.mjs.
const TOKEN=/^[a-zA-Z0-9_-]{24}$/;
const PAYLOAD=/^\/start(?:@[A-Za-z0-9_]+)?\s+d_([a-zA-Z0-9_-]{24})\s*$/i;
const CHAT=/^-100[0-9]{5,}$/;
const TG='https://api.telegram.org/bot';
const MINI_APP='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app';
export const downloadUrl=token=>TOKEN.test(String(token||''))?'https://t.me/CineRadarFr_Bot?start=d_'+token:null;
export function validSequence(kind,season,items){
 if(!Array.isArray(items)||!items.length||items.length>100)return false;
 if(kind==='film')return season===0&&items.length===1&&items[0].season_number===null&&items[0].episode_number===null;
 if(kind!=='series'||!Number.isInteger(season)||season<1||season>50)return false;
 return items.every((x,i)=>Number(x.season_number)===season&&Number(x.episode_number)===i+1);
}
function keyboard(){
 return {inline_keyboard:[
  [{text:'💾 Enregistrer / Partager',callback_data:'cinex:save_help'}],
  [{text:'🍿 Explorer Ciné Radar',web_app:{url:MINI_APP}}]
 ]};
}
async function telegram(env,method,payload){
 const r=await fetch(TG+env.TELEGRAM_TOKEN+'/'+method,{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(payload),signal:AbortSignal.timeout(12000)
 });
 let data;try{data=await r.json()}catch{throw Error('telegram_response_unknown')}
 if(!r.ok||!data?.ok)return {ok:false,error_code:Number(data?.error_code||r.status),retry_after:Number(data?.parameters?.retry_after||0)};
 return data;
}
async function say(env,chat,text,reply_markup){
 try{return await telegram(env,'sendMessage',{chat_id:chat,text,...(reply_markup?{reply_markup}:{})})}
 catch{return {ok:false}}
}
export async function handleDeliveryStart(env,update){
 const msg=update?.message,txt=String(msg?.text||'').trim(),match=PAYLOAD.exec(txt);
 if(!match)return {handled:false};
 const chat=msg?.chat?.id;
 if(msg?.chat?.type!=='private'||chat!==msg?.from?.id||!Number.isSafeInteger(chat)||chat<=0
    ||!Number.isSafeInteger(update?.update_id)||update.update_id<0)return {handled:true,accepted:false};
 const token=match[1];
 try{
  const feature=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
  if(feature?.value!=='1'){await say(env,chat,'🎬 Le téléchargement CinéX est en préparation. Les vidéothèques restent accessibles depuis les canaux.');return {handled:true,accepted:false};}
  const link=await env.DB.prepare(
   "SELECT l.token,l.season_key,l.category,t.title_key,t.display_title,t.content_kind,b.private_chat_id FROM cine_delivery_links l JOIN cine_delivery_titles t ON t.title_key=l.title_key AND t.category=l.category JOIN cine_delivery_libraries b ON b.category=l.category WHERE l.token=? AND l.enabled=1 AND t.approval='approved' AND t.rights_attested=1 AND b.rights_attested=1 AND b.owner_access='verified' AND b.bot_access='verified'"
  ).bind(token).first();
  if(!link||!CHAT.test(String(link.private_chat_id||''))){await say(env,chat,'Ce téléchargement n’est pas disponible pour le moment.');return {handled:true,accepted:false};}
  const rows=await env.DB.prepare(
   "SELECT source_message_id,season_number,episode_number,availability FROM cine_delivery_media WHERE title_key=? AND category=? AND availability='approved' AND ((?=0 AND season_number IS NULL AND episode_number IS NULL) OR (? > 0 AND season_number=?)) ORDER BY episode_number,source_message_id LIMIT 101"
  ).bind(link.title_key,link.category,link.season_key,link.season_key,link.season_key).all();
  const media=rows.results||[];
  // Reject ANY incomplete season and mismatched records before enqueuing.
  if(!validSequence(link.content_kind,Number(link.season_key),media)){
   await say(env,chat,'La saison ou le film est incomplet. Le téléchargement est momentanément indisponible.');
   return {handled:true,accepted:false};
  }
  // Explicit per-user throttling; repeated Telegram update IDs are idempotent.
  const prior=await env.DB.prepare("SELECT id,status FROM cine_delivery_jobs WHERE telegram_update_id=?").bind(update.update_id).first();
  if(prior)return {handled:true,accepted:true,duplicate:true};
  const recent=await env.DB.prepare("SELECT COUNT(*) AS n FROM cine_delivery_jobs WHERE telegram_chat_id=? AND created_at>=datetime('now','-1 hour')").bind(chat).first();
  if(Number(recent?.n||0)>=4){await say(env,chat,'Trop de demandes récentes. Réessaie plus tard.');return {handled:true,accepted:false};}
  const inserted=await env.DB.prepare("INSERT OR IGNORE INTO cine_delivery_jobs(token,telegram_chat_id,telegram_update_id,planned_items) VALUES(?,?,?,?)").bind(token,chat,update.update_id,media.length).run();
  if(Number(inserted.meta?.changes||0)===0)return {handled:true,accepted:true,duplicate:true};
  const job=await env.DB.prepare("SELECT id FROM cine_delivery_jobs WHERE telegram_update_id=? AND telegram_chat_id=?").bind(update.update_id,chat).first();
  if(!job?.id)throw Error('job_insert_missing');
  await env.DB.batch(media.map((m,i)=>env.DB.prepare(
   "INSERT OR IGNORE INTO cine_delivery_job_items(job_id,ordinal,source_chat_id,source_message_id) VALUES(?,?,?,?)"
  ).bind(job.id,i+1,link.private_chat_id,m.source_message_id)));
  await say(env,chat,media.length>1?
   '📺 '+media.length+' épisodes de « '+String(link.display_title).slice(0,85)+' » vont être envoyés automatiquement, dans l’ordre. Les copies envoyées par le bot expirent après 24 heures. Pense à les transférer dans Messages enregistrés.':
   '🎬 Le film « '+String(link.display_title).slice(0,85)+' » va être envoyé automatiquement. Cette copie expire après 24 heures. Pense à la transférer dans Messages enregistrés.',
   {inline_keyboard:[[{text:'🍿 Explorer Ciné Radar',web_app:{url:MINI_APP}}]]});
  return {handled:true,accepted:true,job_id:job.id};
 }catch(e){
  console.warn('cinex_delivery_request_failed',String(e?.name||'Error'));
  await say(env,chat,'Le service de téléchargement est temporairement indisponible.');
  return {handled:true,accepted:false};
 }
}
export async function handleSaveHelp(env,update){
 const cb=update?.callback_query;
 if(cb?.data!=='cinex:save_help')return false;
 try{
  await telegram(env,'answerCallbackQuery',{callback_query_id:cb.id,
   text:'Pour garder le fichier : sélectionne le message vidéo, puis Transférer → Messages enregistrés.',
   show_alert:true});
 }catch(e){console.warn('cinex_save_help_failed',String(e?.name||'Error'));}
 return true;
}
export async function processDeliveryQueue(env,{limit=4}={}){
 if(!env?.TELEGRAM_TOKEN||!env?.DB)return {processed:0,errors:0};
 const enabled=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
 if(enabled?.value!=='1')return {processed:0,errors:0,disabled:true};
 // Never blindly retry an uncertain Telegram send; require human reconciliation.
 await env.DB.prepare("UPDATE cine_delivery_jobs SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE status='sending' AND lock_until<datetime('now')").run();
 await env.DB.prepare("UPDATE cine_delivery_job_items SET state='needs_review' WHERE state='sending' AND job_id IN (SELECT id FROM cine_delivery_jobs WHERE status='needs_review')").run();
 const candidates=await env.DB.prepare(
  "SELECT j.id,j.telegram_chat_id,j.token,l.category,l.title_key,l.season_key,b.private_chat_id FROM cine_delivery_jobs j JOIN cine_delivery_links l ON l.token=j.token JOIN cine_delivery_titles t ON t.title_key=l.title_key JOIN cine_delivery_libraries b ON b.category=l.category WHERE j.status='queued' AND j.not_before<=CURRENT_TIMESTAMP AND l.enabled=1 AND t.approval='approved' AND t.rights_attested=1 AND b.bot_access='verified' AND b.rights_attested=1 ORDER BY j.created_at,j.id LIMIT ?"
 ).bind(Math.min(4,Math.max(1,Number(limit)||2))).all();
 let processed=0,errors=0;
 for(const job of candidates.results||[]){
  if(!CHAT.test(String(job.private_chat_id||'')))continue;
  const rows=await env.DB.prepare("SELECT ordinal,source_chat_id,source_message_id,state,delivered_message_id FROM cine_delivery_job_items WHERE job_id=? ORDER BY ordinal").bind(job.id).all();
  const items=rows.results||[];
  if(!items.length||items.some(x=>x.source_chat_id!==job.private_chat_id||!Number.isSafeInteger(Number(x.source_message_id))||Number(x.source_message_id)<1)){
   await env.DB.prepare("UPDATE cine_delivery_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();errors++;continue;
  }
  const pendingItems=items.filter(x=>x.state==='queued').slice(0,12);
  if(!pendingItems.length){await env.DB.prepare("UPDATE cine_delivery_jobs SET status='complete' WHERE id=? AND status='queued'").bind(job.id).run();processed++;continue;}
  // Each user requests the entire season once: this job can progress through
  // twelve episodes automatically without any further bot interaction.
  for(const pending of pendingItems){
  // Short lease makes concurrent cron workers mutually exclusive.
  const lock=await env.DB.prepare("UPDATE cine_delivery_jobs SET status='sending',lock_until=datetime('now','+4 minutes'),updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='queued'").bind(job.id).run();
  if(Number(lock.meta?.changes||0)!==1)break;
  await env.DB.prepare("UPDATE cine_delivery_job_items SET state='sending',attempts=attempts+1 WHERE job_id=? AND ordinal=? AND state='queued'").bind(job.id,pending.ordinal).run();
  let response;
  try{
   response=await telegram(env,'copyMessage',{chat_id:job.telegram_chat_id,
    from_chat_id:job.private_chat_id,message_id:pending.source_message_id,
    protect_content:false,reply_markup:keyboard()});
  }catch{
   // Ambiguous response: Telegram may have sent the file. No automatic retry!
   await env.DB.prepare("UPDATE cine_delivery_jobs SET status='needs_review',updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(job.id).run();
   await env.DB.prepare("UPDATE cine_delivery_job_items SET state='needs_review' WHERE job_id=? AND ordinal=?").bind(job.id,pending.ordinal).run();
   errors++;break;
  }
  if(!response.ok){
   if(response.error_code===429&&response.retry_after>0){
    await env.DB.batch([
     env.DB.prepare("UPDATE cine_delivery_jobs SET status='queued',not_before=datetime('now',?),updated_at=CURRENT_TIMESTAMP WHERE id=?").bind('+'+Math.min(3600,Math.max(5,response.retry_after))+' seconds',job.id),
     env.DB.prepare("UPDATE cine_delivery_job_items SET state='queued' WHERE job_id=? AND ordinal=?").bind(job.id,pending.ordinal)
    ]);
   }else{
    await env.DB.prepare("UPDATE cine_delivery_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();
    await env.DB.prepare("UPDATE cine_delivery_job_items SET state='needs_review' WHERE job_id=? AND ordinal=?").bind(job.id,pending.ordinal).run();
   }
   errors++;break;
  }
  const copied=Number(response.result?.message_id||0);
  if(!Number.isSafeInteger(copied)||copied<1){
   await env.DB.prepare("UPDATE cine_delivery_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();errors++;break;
  }
  await env.DB.batch([
   env.DB.prepare("UPDATE cine_delivery_job_items SET state='sent',delivered_message_id=?,sent_at=CURRENT_TIMESTAMP,delete_after=datetime('now','+24 hours'),delete_retry_at=datetime('now','+24 hours'),delete_state='pending',delete_attempts=0 WHERE job_id=? AND ordinal=? AND state='sending'").bind(copied,job.id,pending.ordinal),
   env.DB.prepare("UPDATE cine_delivery_jobs SET delivered_items=delivered_items+1,status='queued',lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(job.id)
  ]);
  const remaining=items.filter(x=>x.state==='queued'&&Number(x.ordinal)>Number(pending.ordinal)).length;
  if(remaining===0){
   await env.DB.prepare("UPDATE cine_delivery_jobs SET status='complete',updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(job.id).run();
  }
  processed++;
  // Telegram recommends roughly one media message per second per private chat.
  if(remaining)await new Promise(resolve=>setTimeout(resolve,1100));
  } // pending items in this one requested season
 } // jobs
 return {processed,errors};
}
// Owner-only toggling and approval are wrapped by admin-v2's signed-initData verification.
export async function adminDeliveryAction(env,path,data){
 if(path==='/api/admin/cinex/state'){
  if(data.action!=='enable'&&data.action!=='disable')return {status:400,body:{error:'Action inconnue'}};
  await env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('cine_delivery_enabled',?) ON CONFLICT(setting_key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP").bind(data.action==='enable'?'1':'0').run();
  return {status:200,body:{ok:true,enabled:data.action==='enable'}};
 }
 if(path!=='/api/admin/cinex/approve')return {status:404,body:{error:'Route inconnue'}};
 if(data.rights_confirmed!==true)return {status:400,body:{error:'Droits de redistribution non confirmés'}};
 const titleKey=String(data.title_key||'');
 const season=Number(data.season??0);
 if(!/^[a-f0-9]{32}$/.test(titleKey)||!Number.isInteger(season)||season<0||season>50)return {status:400,body:{error:'Référence invalide'}};
 const title=await env.DB.prepare(
  "SELECT t.title_key,t.category,t.content_kind,b.bot_access,b.owner_access,b.rights_attested FROM cine_delivery_titles t JOIN cine_delivery_libraries b ON b.category=t.category WHERE t.title_key=?"
 ).bind(titleKey).first();
 if(!title||title.bot_access!=='verified'||title.owner_access!=='verified'||Number(title.rights_attested)!==1)
  return {status:409,body:{error:'Vidéothèque ou bot non vérifié'}};
 if((title.content_kind==='series')!== (season>0))return {status:400,body:{error:'Saison invalide'}};
 const media=await env.DB.prepare(
  "SELECT source_message_id,season_number,episode_number FROM cine_delivery_media WHERE title_key=? AND category=? AND ((?=0 AND season_number IS NULL) OR (season_number=? AND ?>0)) ORDER BY episode_number,source_message_id LIMIT 101"
 ).bind(titleKey,title.category,season,season,season).all();
 const items=media.results||[];
 if(!validSequence(title.content_kind,season,items))return {status:409,body:{error:'Catalogue incomplet ou ambigu (épisodes manquants)'}};
 const previous=await env.DB.prepare("SELECT token FROM cine_delivery_links WHERE category=? AND title_key=? AND season_key=?").bind(title.category,titleKey,season).first();
 const token=previous?.token||Array.from(crypto.getRandomValues(new Uint8Array(24)),x=>'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'[x%64]).join('');
 await env.DB.batch([
  env.DB.prepare("UPDATE cine_delivery_titles SET approval='approved',rights_attested=1 WHERE title_key=?").bind(titleKey),
  ...items.map(x=>env.DB.prepare("UPDATE cine_delivery_media SET availability='approved' WHERE category=? AND source_message_id=? AND title_key=?").bind(title.category,x.source_message_id,titleKey)),
  env.DB.prepare("INSERT INTO cine_delivery_links(token,title_key,category,season_key,enabled) VALUES(?,?,?,?,1) ON CONFLICT(category,title_key,season_key) DO UPDATE SET enabled=1,updated_at=CURRENT_TIMESTAMP").bind(token,titleKey,title.category,season)
 ]);
 return {status:200,body:{ok:true,url:downloadUrl(token),media_count:items.length,category:title.category}};
}
