// CinéX séries individuelles — Bot API et D1 uniquement.
// Messages entrants: le bot Ciné Radar doit déjà être admin dans les canaux privés.
// getChat NE permet PAS de récupérer l'ensemble des anciens messages épinglés.
import {deletionDecision} from './cinex-expiry.mjs';

const CHAT=/^-100[0-9]{6,}$/;
const TOKEN=/^[a-zA-Z0-9_-]{24}$/;
const hasOwnerCopy=x=>Number.isSafeInteger(Number(x?.owner_chat_id))&&Number(x.owner_chat_id)>0&&Number.isSafeInteger(Number(x?.owner_message_id))&&Number(x.owner_message_id)>0;
const START=/^\/start(?:@[a-zA-Z0-9_]+)?\s+sr_([a-zA-Z0-9_-]{24})\s*$/i;
const TG='https://api.telegram.org/bot';

export function parseSeason(text){
 const s=String(text||'').slice(0,2500);
 const m=/(?:^|[\s#|[(])(?:saison|season|s)[\s.:-]*0?([1-9][0-9]?)(?=$|[\s#|)\]:._-])/i.exec(s);
 return m&&Number(m[1])<=50?Number(m[1]):null;
}
export function parseEpisode(text){
 const s=String(text||'').slice(0,2500);
 const compact=/(?:^|[^a-z0-9])s0?([1-9][0-9]?)\s*e0?([1-9][0-9]?)(?=$|[^0-9])/i.exec(s);
 if(compact)return {season:Number(compact[1]),episode:Number(compact[2])};
 const season=parseSeason(s);
 const ep=/(?:épisode|episode|ep\.?)[\s#.:_-]*0?([1-9][0-9]?)(?=$|[^0-9])/i.exec(s);
 return season&&ep?{season,episode:Number(ep[1])}:null;
}
export function parseExpectedEpisodes(text){
 const s=String(text||'').slice(0,2500);
 const m=/(?:^|[^\d])([1-9][0-9]?)\s*(?:épisodes?|episodes?|eps\b)/i.exec(s) ||
  /(?:nombre\s+d['’]\s*épisodes?|épisodes?\s*(?:au\s*total)?)[\s:=-]*([1-9][0-9]?)/i.exec(s);
 return m?Number(m[1]):null;
}
export function validSeriesPlan(seasons,media){
 if(!Array.isArray(seasons)||!seasons.length||!Array.isArray(media))return false;
 const sequence=[...seasons].sort((a,b)=>Number(a.season)-Number(b.season));
 if(sequence.length>50||Number(sequence[0].season)!==1)return false;
 let total=0;
 for(let i=0;i<sequence.length;i++){
  const row=sequence[i],sn=Number(row.season),count=Number(row.expected_episodes);
  if(sn!==i+1||!Number.isInteger(count)||count<1||count>100)return false;
  const found=media.filter(x=>Number(x.season)===sn);
  if(found.length!==count)return false;
  for(let ep=1;ep<=count;ep++){
   if(Number(found[ep-1].episode)!==ep||
    !Number.isSafeInteger(Number(found[ep-1].source_message_id))||
    Number(found[ep-1].source_message_id)<1)return false;
  }
  total+=count;
 }
 return total===media.length&&total<=300;
}
export function seriesButtons(token,rescue,folder){
 if(!TOKEN.test(token)||!/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})\/?$/.test(rescue)||
 !/^https:\/\/t\.me\/addlist\/[A-Za-z0-9_-]{8,}$/.test(folder))throw Error('series_buttons_config_invalid');
 return {inline_keyboard:[
  [{text:'📥 Télécharger toutes les saisons',url:'https://t.me/CineRadarFr_Bot?start=sr_'+token,style:'success'}],
  [{text:'🛟 Rejoindre le canal de secours',url:rescue,style:'danger'}],
  [{text:'📂 Rejoindre le dossier',url:folder,style:'primary'}]
 ]};
}
async function telegram(env,method,payload){
 const response=await fetch(TG+env.TELEGRAM_TOKEN+'/'+method,{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify(payload),signal:AbortSignal.timeout(12000)
 });
 let data;try{data=await response.json();}catch{throw Error('telegram_response_unknown')}
 if(!response.ok||!data?.ok)return {ok:false,code:Number(data?.error_code||response.status),retry_after:Number(data?.parameters?.retry_after||0)};
 return data;
}
async function notify(env,chat,message){
 try{await telegram(env,'sendMessage',{chat_id:chat,text:message.slice(0,600)})}catch{}
}
const isPoster=x=>Array.isArray(x?.photo)&&x.photo.length>0;
const isEpisode=x=>!!x?.video||x?.document?.mime_type?.startsWith('video/');

// Do not infer an episode index or an expected episode total from a message ID.
export async function ingestIndividualSeriesUpdate(env,update){
 const message=update?.channel_post||update?.edited_channel_post;
 if(message?.chat?.type!=='channel'||!CHAT.test(String(message.chat.id)))return false;
 const chatId=String(message.chat.id);
 const allowed=await env.DB.prepare("SELECT chat_id FROM cine_series_channels WHERE chat_id=? AND enabled=1").bind(chatId).first();
 if(!allowed)return false;
 const pin=message.pinned_message;
 if(isPoster(pin)){
  const season=parseSeason(pin.caption||pin.text||'');
  if(season){
   await env.DB.prepare(
    "INSERT INTO cine_series_posters(chat_id,season,source_message_id,caption) VALUES(?,?,?,?) ON CONFLICT(chat_id,season) DO UPDATE SET source_message_id=excluded.source_message_id,caption=excluded.caption,observed_at=CURRENT_TIMESTAMP"
   ).bind(chatId,season,Number(pin.message_id),String(pin.caption||pin.text||'').slice(0,1800)).run();
   await env.DB.prepare("UPDATE cine_series_channels SET expected_seasons=MAX(COALESCE(expected_seasons,0),?) WHERE chat_id=?").bind(season,chatId).run();
   const expected=parseExpectedEpisodes(pin.caption||pin.text||'');
   if(expected)await env.DB.prepare(
    "INSERT INTO cine_series_seasons(chat_id,season,expected_episodes) VALUES(?,?,?) ON CONFLICT(chat_id,season) DO UPDATE SET expected_episodes=excluded.expected_episodes,observed_at=CURRENT_TIMESTAMP"
   ).bind(chatId,season,expected).run();
   return true;
  }
 }
 const text=String(message.caption||message.text||message.document?.file_name||message.video?.file_name||'');
 if(isEpisode(message)){
  const parsed=parseEpisode(text);
  if(parsed&&parsed.episode<=100){
   await env.DB.prepare(
    "INSERT INTO cine_series_episodes(chat_id,season,episode,source_message_id) VALUES(?,?,?,?) ON CONFLICT(chat_id,season,episode) DO UPDATE SET source_message_id=excluded.source_message_id,observed_at=CURRENT_TIMESTAMP"
   ).bind(chatId,parsed.season,parsed.episode,Number(message.message_id)).run();
   return true;
  }
 }
 if(update?.edited_channel_post&&isPoster(message)){
  const known=await env.DB.prepare("SELECT season FROM cine_series_posters WHERE chat_id=? AND source_message_id=?").bind(chatId,Number(message.message_id)).first();
  if(known){
   await env.DB.prepare("UPDATE cine_series_posters SET caption=?,observed_at=CURRENT_TIMESTAMP WHERE chat_id=? AND source_message_id=?").bind(text.slice(0,1800),chatId,Number(message.message_id)).run();
   const expected=parseExpectedEpisodes(text);
   if(expected)await env.DB.prepare(
    "INSERT INTO cine_series_seasons(chat_id,season,expected_episodes) VALUES(?,?,?) ON CONFLICT(chat_id,season) DO UPDATE SET expected_episodes=excluded.expected_episodes,observed_at=CURRENT_TIMESTAMP"
   ).bind(chatId,Number(known.season),expected).run();
   return true;
  }
 }
 return false;
}

// Backfill of old posters via owner forwarding them to the existing bot.
export async function ingestSeriesOwnerForward(env,message){
 const origin=message?.forward_origin;
 if(message?.chat?.type!=='private'||origin?.type!=='channel'||!origin.chat?.id||!origin.message_id||(!isPoster(message)&&!isEpisode(message)))return {handled:false};
 const owner=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(message.from?.id||0).first();
 if(owner?.role!=='owner')return {handled:false};
 const chatId=String(origin.chat.id);
 const allowed=await env.DB.prepare("SELECT chat_id FROM cine_series_channels WHERE chat_id=? AND enabled=1").bind(chatId).first();
 if(!allowed)return {handled:false};
 const caption=String(message.caption||message.text||message.document?.file_name||message.video?.file_name||'');
 if(isEpisode(message)){
  const item=parseEpisode(caption);
  if(!item||item.episode>100)return {handled:true,stored:false,reason:'Indique la saison ET l’épisode dans la légende, par exemple S01E02.'};
  await env.DB.prepare(
   "INSERT INTO cine_series_episodes(chat_id,season,episode,source_message_id) VALUES(?,?,?,?) ON CONFLICT(chat_id,season,episode) DO UPDATE SET source_message_id=excluded.source_message_id,observed_at=CURRENT_TIMESTAMP"
  ).bind(chatId,item.season,item.episode,Number(origin.message_id)).run();
  return {handled:true,stored:true,season:item.season,episode:item.episode};
 }
 const season=parseSeason(caption);
 if(!season)return {handled:true,stored:false,reason:'Ajoute « Saison 1 », « Saison 2 »… à la description de l’affiche avant de la transférer.'};
 await env.DB.prepare(
  "INSERT INTO cine_series_posters(chat_id,season,source_message_id,caption) VALUES(?,?,?,?) ON CONFLICT(chat_id,season) DO UPDATE SET source_message_id=excluded.source_message_id,caption=excluded.caption,observed_at=CURRENT_TIMESTAMP"
 ).bind(chatId,season,Number(origin.message_id),caption.slice(0,1800)).run();
 await env.DB.prepare("UPDATE cine_series_channels SET expected_seasons=MAX(COALESCE(expected_seasons,0),?) WHERE chat_id=?").bind(season,chatId).run();
 const expected=parseExpectedEpisodes(caption);
 if(expected)await env.DB.prepare(
  "INSERT INTO cine_series_seasons(chat_id,season,expected_episodes) VALUES(?,?,?) ON CONFLICT(chat_id,season) DO UPDATE SET expected_episodes=excluded.expected_episodes"
 ).bind(chatId,season,expected).run();
 return {handled:true,stored:true,season};
}

export async function handleSeriesStart(env,update){
 const message=update?.message,match=START.exec(String(message?.text||'').trim());
 if(!match)return {handled:false};
 const chat=message?.chat?.id,token=match[1];
 if(message?.chat?.type!=='private'||chat!==message?.from?.id||!Number.isSafeInteger(chat)||chat<=0)return {handled:true,accepted:false};
 try{
  const gate=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
  if(gate?.value!=='1'){await notify(env,chat,'📺 Les téléchargements CinéX sont temporairement désactivés.');return {handled:true,accepted:false}}
  const source=await env.DB.prepare(
   "SELECT p.chat_id,c.title,c.expected_seasons,c.radar_access FROM cine_series_publications p JOIN cine_series_channels c ON c.chat_id=p.chat_id WHERE p.token=? AND p.state='published' AND c.enabled=1 AND c.rights_attested=1"
  ).bind(token).first();
  if(!source||!CHAT.test(String(source.chat_id))){await notify(env,chat,'Série indisponible pour le moment.');return {handled:true,accepted:false}}
  const seasons=(await env.DB.prepare("SELECT season,expected_episodes FROM cine_series_seasons WHERE chat_id=? ORDER BY season").bind(source.chat_id).all()).results||[];
  const media=(await env.DB.prepare(
   "SELECT e.season,e.episode,e.source_message_id,CASE WHEN a.user_id IS NOT NULL THEN v.owner_chat_id END AS owner_chat_id,CASE WHEN a.user_id IS NOT NULL THEN v.owner_message_id END AS owner_message_id "+
   "FROM cine_series_episodes e LEFT JOIN cine_owner_vault v ON v.source_chat_id=e.chat_id "+
   "AND v.source_message_id=e.source_message_id AND v.status='stored' "+
   "LEFT JOIN admin_users a ON a.role='owner' AND a.user_id=v.owner_chat_id "+
   "WHERE e.chat_id=? ORDER BY e.season,e.episode"
  ).bind(source.chat_id).all()).results||[];
  const posters=(await env.DB.prepare("SELECT season FROM cine_series_posters WHERE chat_id=? ORDER BY season").bind(source.chat_id).all()).results||[];
  if(!Number.isInteger(Number(source.expected_seasons))||Number(source.expected_seasons)<1||posters.length!==Number(source.expected_seasons)||seasons.length!==Number(source.expected_seasons)||!validSeriesPlan(seasons,media)||posters.length!==seasons.length||
   posters.some((x,i)=>Number(x.season)!==i+1)){
   await notify(env,chat,'⏳ Toutes les saisons ne sont pas encore vérifiées. Le téléchargement est indisponible pour éviter les épisodes manquants.');
   return {handled:true,accepted:false};
  }
  if(source.radar_access!=='verified'&&media.some(x=>!hasOwnerCopy(x))){
   await notify(env,chat,'⏳ L’accès aux vidéos sources n’est pas encore vérifié et toutes les copies propriétaires ne sont pas disponibles.');
   return {handled:true,accepted:false};
  }
  const old=await env.DB.prepare("SELECT id FROM cine_series_jobs WHERE telegram_update_id=?").bind(update.update_id).first();
  if(old)return {handled:true,accepted:true,duplicate:true};
  const recent=await env.DB.prepare("SELECT COUNT(*) AS n FROM cine_series_jobs WHERE telegram_chat_id=? AND created_at>=datetime('now','-1 hour')").bind(chat).first();
  if(Number(recent?.n||0)>=2){await notify(env,chat,'Trop de demandes récentes. Réessaie plus tard.');return {handled:true,accepted:false}}
  await env.DB.prepare("INSERT OR IGNORE INTO cine_series_jobs(token,telegram_chat_id,telegram_update_id,planned_items) VALUES(?,?,?,?)").bind(token,chat,update.update_id,media.length).run();
  const job=await env.DB.prepare("SELECT id FROM cine_series_jobs WHERE telegram_update_id=? AND telegram_chat_id=?").bind(update.update_id,chat).first();
  if(!job?.id)throw Error('series_job_missing');
  await env.DB.batch(media.map((item,i)=>env.DB.prepare(
   "INSERT OR IGNORE INTO cine_series_job_items(job_id,ordinal,source_chat_id,source_message_id) VALUES(?,?,?,?)"
  ).bind(job.id,i+1,hasOwnerCopy(item)?String(item.owner_chat_id):source.chat_id,
   hasOwnerCopy(item)?Number(item.owner_message_id):item.source_message_id)));
  await notify(env,chat,'📥 '+String(source.title||'Ta série').slice(0,80)+': '+seasons.length+' saison(s), '+media.length+' épisodes. Livraison automatique en plusieurs lots. Chaque copie du bot sera supprimée après 24 heures.');
  return {handled:true,accepted:true};
 }catch(e){console.warn('series_start_error',String(e?.name||'Error'));await notify(env,chat,'Service temporairement indisponible.');return {handled:true,accepted:false}}
}

export async function processSeriesQueue(env,{limit=5}={}){
 if(!env?.TELEGRAM_TOKEN||!env?.DB)return {processed:0,disabled:true};
 const gate=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
 if(gate?.value!=='1')return {processed:0,disabled:true};
 await env.DB.prepare("UPDATE cine_series_jobs SET status='needs_review' WHERE status='sending' AND lock_until<CURRENT_TIMESTAMP").run();
 await env.DB.prepare("UPDATE cine_series_job_items SET state='needs_review' WHERE state='sending' AND job_id IN (SELECT id FROM cine_series_jobs WHERE status='needs_review')").run();
 const batch=(await env.DB.prepare(
  "SELECT j.id,j.telegram_chat_id,p.chat_id AS source_chat_id FROM cine_series_jobs j JOIN cine_series_publications p ON p.token=j.token JOIN cine_series_channels c ON c.chat_id=p.chat_id WHERE j.status='queued' AND j.not_before<=CURRENT_TIMESTAMP AND p.state='published' AND c.enabled=1 AND c.rights_attested=1 AND (c.radar_access='verified' OR NOT EXISTS("+
  "SELECT 1 FROM cine_series_job_items x WHERE x.job_id=j.id AND x.source_chat_id=p.chat_id"+
  ")) ORDER BY j.created_at,j.id LIMIT 2"
 ).all()).results||[];
 let processed=0,errors=0;
 for(const job of batch){
  const items=(await env.DB.prepare("SELECT ordinal,source_chat_id,source_message_id FROM cine_series_job_items WHERE job_id=? AND state='queued' ORDER BY ordinal LIMIT ?").bind(job.id,Math.max(1,Math.min(8,Number(limit)||5))).all()).results||[];
  if(!items.length){await env.DB.prepare("UPDATE cine_series_jobs SET status='complete' WHERE id=? AND status='queued'").bind(job.id).run();continue}
  for(const item of items){
   let verifiedSource=item.source_chat_id===job.source_chat_id&&CHAT.test(String(item.source_chat_id));
   if(!verifiedSource&&Number.isSafeInteger(Number(item.source_chat_id))&&Number(item.source_chat_id)>0){
    const receipt=await env.DB.prepare(
     "SELECT 1 AS ok FROM cine_owner_vault v JOIN cine_series_episodes e ON "+
     "e.chat_id=v.source_chat_id AND e.source_message_id=v.source_message_id "+
     "JOIN admin_users a ON a.role='owner' AND a.user_id=v.owner_chat_id "+
     "WHERE e.chat_id=? AND v.owner_chat_id=? AND v.owner_message_id=? AND v.status='stored'"
    ).bind(job.source_chat_id,Number(item.source_chat_id),Number(item.source_message_id)).first();
    verifiedSource=Boolean(receipt?.ok);
   }
   if(!verifiedSource){errors++;await env.DB.prepare("UPDATE cine_series_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();break}
   const still=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first();
   if(still?.value!=='1')return {processed,errors,disabled:true};
   const claimed=await env.DB.prepare("UPDATE cine_series_jobs SET status='sending',lock_until=datetime('now','+4 minutes') WHERE id=? AND status='queued'").bind(job.id).run();
   if(Number(claimed.meta?.changes)!==1)break;
   await env.DB.prepare("UPDATE cine_series_job_items SET state='sending' WHERE job_id=? AND ordinal=? AND state='queued'").bind(job.id,item.ordinal).run();
   let answer;
   try{answer=await telegram(env,'copyMessage',{chat_id:job.telegram_chat_id,from_chat_id:item.source_chat_id,message_id:item.source_message_id,protect_content:false});}
   catch{await env.DB.prepare("UPDATE cine_series_job_items SET state='needs_review' WHERE job_id=? AND ordinal=?").bind(job.id,item.ordinal).run();await env.DB.prepare("UPDATE cine_series_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();errors++;break}
   if(!answer.ok){
    if(answer.code===429&&answer.retry_after>0){
     await env.DB.prepare("UPDATE cine_series_job_items SET state='queued' WHERE job_id=? AND ordinal=?").bind(job.id,item.ordinal).run();
     await env.DB.prepare("UPDATE cine_series_jobs SET status='queued',not_before=datetime('now',?),lock_until=NULL WHERE id=?").bind('+'+Math.max(5,Math.min(3600,answer.retry_after))+' seconds',job.id).run();
    }else{
     await env.DB.prepare("UPDATE cine_series_job_items SET state='needs_review' WHERE job_id=? AND ordinal=?").bind(job.id,item.ordinal).run();
     await env.DB.prepare("UPDATE cine_series_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();
    }
    errors++;break;
   }
   const delivered=Number(answer.result?.message_id);
   if(!Number.isSafeInteger(delivered)||delivered<1){
    await env.DB.prepare("UPDATE cine_series_jobs SET status='needs_review' WHERE id=?").bind(job.id).run();errors++;break;
   }
   await env.DB.batch([
    env.DB.prepare("UPDATE cine_series_job_items SET state='sent',delivered_message_id=?,sent_at=CURRENT_TIMESTAMP,delete_after=datetime('now','+24 hours'),delete_retry_at=datetime('now','+24 hours') WHERE job_id=? AND ordinal=? AND state='sending'").bind(delivered,job.id,item.ordinal),
    env.DB.prepare("UPDATE cine_series_jobs SET status='queued',lock_until=NULL,delivered_items=delivered_items+1 WHERE id=?").bind(job.id)
   ]);
   processed++;
   if(items.length>1)await new Promise(resolve=>setTimeout(resolve,1100));
  }
 }
 return {processed,errors};
}

export async function cleanupSeriesCopies(env,{limit=12,now=Date.now()}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {deleted:0,disabled:true};
 const result={deleted:0,already_gone:0,retry:0,manual_review:0};
 await env.DB.prepare("UPDATE cine_series_job_items SET delete_state='retry',delete_lock_until=NULL WHERE delete_state='deleting' AND delete_lock_until<CURRENT_TIMESTAMP").run();
 const rows=(await env.DB.prepare(
  "SELECT i.job_id,i.ordinal,i.delivered_message_id,i.sent_at,i.delete_attempts,j.telegram_chat_id FROM cine_series_job_items i JOIN cine_series_jobs j ON j.id=i.job_id WHERE i.state='sent' AND i.delivered_message_id IS NOT NULL AND i.delete_after<=CURRENT_TIMESTAMP AND COALESCE(i.delete_retry_at,i.delete_after)<=CURRENT_TIMESTAMP AND i.delete_state IN ('pending','retry') ORDER BY i.delete_after LIMIT ?"
 ).bind(Math.max(1,Math.min(24,Number(limit)||12))).all()).results||[];
 for(const row of rows){
  const claimed=await env.DB.prepare("UPDATE cine_series_job_items SET delete_state='deleting',delete_lock_until=datetime('now','+2 minutes'),delete_attempts=delete_attempts+1 WHERE job_id=? AND ordinal=? AND delete_state IN ('pending','retry')").bind(row.job_id,row.ordinal).run();
  if(Number(claimed.meta?.changes)!==1)continue;
  const attempt=Number(row.delete_attempts||0)+1;
  let decision;
  try{
   const answer=await telegram(env,'deleteMessage',{chat_id:row.telegram_chat_id,message_id:row.delivered_message_id});
   decision=deletionDecision(answer.ok?{ok:true,result:answer.result}:{ok:false,error_code:answer.code},{sentAt:row.sent_at,now,attempt});
  }catch{decision=deletionDecision({networkError:true},{sentAt:row.sent_at,now,attempt})}
  if(decision.state==='deleted'||decision.state==='already_gone'){
   await env.DB.prepare("UPDATE cine_series_job_items SET delete_state=?,delete_lock_until=NULL,delete_retry_at=NULL,delete_last_error=NULL WHERE job_id=? AND ordinal=?").bind(decision.state,row.job_id,row.ordinal).run();
   result[decision.state==='deleted'?'deleted':'already_gone']++;
  }else if(decision.state==='retry'){
   await env.DB.prepare("UPDATE cine_series_job_items SET delete_state='retry',delete_retry_at=datetime('now',?),delete_lock_until=NULL,delete_last_error=? WHERE job_id=? AND ordinal=?").bind('+'+Math.max(60,Math.min(3600,decision.retrySeconds||90))+' seconds',decision.reason||'retry',row.job_id,row.ordinal).run();
   result.retry++;
  }else{
   await env.DB.prepare("UPDATE cine_series_job_items SET delete_state='manual_review',delete_lock_until=NULL,delete_last_error=? WHERE job_id=? AND ordinal=?").bind(decision.reason||'unresolved',row.job_id,row.ordinal).run();
   result.manual_review++;
  }
 }
 return result;
}
