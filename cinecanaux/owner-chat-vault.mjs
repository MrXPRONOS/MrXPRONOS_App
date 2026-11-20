// CinéX Bot-only private owner chat mirror. No user session, Telethon, bytes or file tokens stored.
// Telegram's copyMessage creates a stable bot-sent message in the owner's private bot chat.
// No automatic deletion of these owner copies; ONLY subscriber delivery receipts expire.
const CHANNEL=/^-100[0-9]{6,}$/;
const isVideo=m=>!!m?.video||m?.document?.mime_type?.startsWith('video/');
const isPoster=m=>Array.isArray(m?.photo)&&m.photo.length>0;
const validMessageId=x=>Number.isSafeInteger(Number(x))&&Number(x)>0;
const TG='https://api.telegram.org/bot';
const enabled=async env=>(await env.DB.prepare(
 "SELECT setting_value FROM cine_series_config WHERE setting_key='owner_chat_vault_enabled'"
).first())?.setting_value==='true';

async function sourceAllowed(env,sourceId,messageId,kind,caption){
 if(!CHANNEL.test(sourceId)||!validMessageId(messageId))return false;
 const source=await env.DB.prepare(
  "SELECT (SELECT rights_attested FROM cine_series_channels WHERE chat_id=? AND enabled=1) AS series_rights,"+
  "(SELECT rights_attested FROM cine_delivery_libraries WHERE private_chat_id=? AND bot_access='verified') AS library_rights,"+
  "(SELECT COUNT(*) FROM cine_classic_links WHERE source_chat_id=? AND source_message_id=? AND status='published') AS classic_link"
 ).bind(sourceId,sourceId,sourceId,Number(messageId)).first();
 const isSeries=Number(source?.series_rights)===1;
 const isLibrary=Number(source?.library_rights)===1;
 const classic=Number(source?.classic_link)>0;
 // Photographs are mirrored only when clearly identified as a series season poster,
 // or when they have been indexed as an actual approved poster.
 if(kind==='poster'){
  if(isSeries){
   const known=await env.DB.prepare("SELECT 1 AS ok FROM cine_series_posters WHERE chat_id=? AND source_message_id=?").bind(sourceId,Number(messageId)).first();
   return Boolean(known?.ok)||/(?:saison|season|S)\s*0?[1-9]\d?\b/i.test(caption);
  }
  // Dedicated approved film/series libraries also contain their own posters.
  return isLibrary;
 }
 return isSeries||isLibrary||classic;
}

async function ownerId(env){
 const row=await env.DB.prepare("SELECT user_id FROM admin_users WHERE role='owner' ORDER BY user_id LIMIT 2").all();
 const users=row.results||[];
 if(users.length!==1||!validMessageId(users[0].user_id))return null;
 return Number(users[0].user_id);
}

export async function enqueueOwnerVaultUpdate(env,update){
 const msg=update?.channel_post;
 if(!msg||msg.chat?.type!=='channel')return {queued:false};
 const sourceId=String(msg.chat.id),id=Number(msg.message_id);
 const kind=isVideo(msg)?'video':isPoster(msg)?'poster':null;
 if(!kind||!await enabled(env))return {queued:false};
 const caption=String(msg.caption||msg.text||'').slice(0,1600);
 if(!await sourceAllowed(env,sourceId,id,kind,caption))return {queued:false,ignored:true};
 const result=await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_owner_vault(source_chat_id,source_message_id,media_kind) VALUES(?,?,?)"
 ).bind(sourceId,id,kind).run();
 return {queued:Number(result.meta?.changes||0)===1};
}

// When owner sends an existing channel post to the bot, that forwarded message
// is already IN their private bot chat; index it directly, no duplicate copy.
export async function captureOwnerForwardInVault(env,msg){
 const origin=msg?.forward_origin;
 if(msg?.chat?.type!=='private'||msg?.chat?.id!==msg?.from?.id||
  origin?.type!=='channel'||!origin.chat?.id||!validMessageId(origin.message_id)||
  !validMessageId(msg.message_id)||(!isVideo(msg)&&!isPoster(msg)))return {captured:false};
 const owner=await ownerId(env);
 if(owner!==msg.chat.id)return {captured:false};
 const sourceId=String(origin.chat.id),kind=isVideo(msg)?'video':'poster';
 if(!await sourceAllowed(env,sourceId,Number(origin.message_id),kind,String(msg.caption||'')))return {captured:false};
 const record=await env.DB.prepare("SELECT status FROM cine_owner_vault WHERE source_chat_id=? AND source_message_id=?").bind(sourceId,Number(origin.message_id)).first();
 // Refuse to overwrite a verified receipt or an ambiguous in-flight copy.
 if(record?.status==='stored'||record?.status==='sending')return {captured:false,already_known:true};
 await env.DB.prepare(
  "INSERT INTO cine_owner_vault(source_chat_id,source_message_id,media_kind,owner_chat_id,owner_message_id,status,copied_at) "+
  "VALUES(?,?,?,?,?,'stored',CURRENT_TIMESTAMP) ON CONFLICT(source_chat_id,source_message_id) "+
  "DO UPDATE SET media_kind=excluded.media_kind,owner_chat_id=excluded.owner_chat_id,owner_message_id=excluded.owner_message_id,"+
  "status='stored',copied_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,error_code=NULL"
 ).bind(sourceId,Number(origin.message_id),kind,owner,Number(msg.message_id)).run();
 return {captured:true};
}

async function telegramCopy(env,destination,source,id){
 const r=await fetch(TG+env.TELEGRAM_TOKEN+'/copyMessage',{
  method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify({chat_id:destination,from_chat_id:source,message_id:id,disable_notification:true}),
  signal:AbortSignal.timeout(14000)
 });
 let x;
 try{x=await r.json();}catch{return {ok:false,indeterminate:true}}
 return {ok:r.ok&&x?.ok===true,id:x?.result?.message_id,code:Number(x?.error_code||r.status),retry:Number(x?.parameters?.retry_after||0)};
}

export async function processOwnerVaultQueue(env,{limit=2}={}){
 if(!env.DB||!env.TELEGRAM_TOKEN||!await enabled(env))return {processed:0,disabled:true};
 const owner=await ownerId(env);
 if(!owner)return {processed:0,disabled:true,reason:'verified_owner_chat_missing'};
 // A lost response to copyMessage is ambiguous: never resend automatically.
 await env.DB.prepare("UPDATE cine_owner_vault SET status='needs_review',error_code='ambiguous_timeout',lock_until=NULL WHERE status='sending' AND lock_until<CURRENT_TIMESTAMP").run();
 const rows=(await env.DB.prepare(
  "SELECT source_chat_id,source_message_id,media_kind FROM cine_owner_vault WHERE status='queued' "+
  "AND not_before<=CURRENT_TIMESTAMP ORDER BY created_at,source_chat_id,source_message_id LIMIT ?"
 ).bind(Math.min(3,Math.max(1,Number(limit)||2))).all()).results||[];
 let processed=0,errors=0;
 for(const row of rows){
  if(!await enabled(env))break;
  if(!CHANNEL.test(row.source_chat_id)||!validMessageId(row.source_message_id))continue;
  // Stop if the owner identity was changed between queue iterations.
  if(await ownerId(env)!==owner)break;
  const lock=await env.DB.prepare(
   "UPDATE cine_owner_vault SET status='sending',lock_until=datetime('now','+3 minutes'),"+
   "attempt_count=attempt_count+1,updated_at=CURRENT_TIMESTAMP "+
   "WHERE source_chat_id=? AND source_message_id=? AND status='queued'"
  ).bind(row.source_chat_id,row.source_message_id).run();
  if(Number(lock.meta?.changes||0)!==1)continue;
  let copied;
  try{copied=await telegramCopy(env,owner,row.source_chat_id,row.source_message_id)}
  catch{copied={ok:false,indeterminate:true}}
  if(copied.ok&&validMessageId(copied.id)){
   await env.DB.prepare(
    "UPDATE cine_owner_vault SET status='stored',owner_chat_id=?,owner_message_id=?,copied_at=CURRENT_TIMESTAMP,"+
    "lock_until=NULL,error_code=NULL,updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND status='sending'"
   ).bind(owner,Number(copied.id),row.source_chat_id,row.source_message_id).run();
   processed++;
  }else if(copied.code===429&&copied.retry>0){
   await env.DB.prepare(
    "UPDATE cine_owner_vault SET status='queued',not_before=datetime('now',?),"+
    "lock_until=NULL,error_code='telegram_rate_limited',updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND status='sending'"
   ).bind('+'+Math.min(3600,Math.max(10,copied.retry))+' seconds',row.source_chat_id,row.source_message_id).run();errors++;
   break; // respect Telegram's rate limits across the queue
  }else{
   await env.DB.prepare(
    "UPDATE cine_owner_vault SET status='needs_review',lock_until=NULL,error_code=?,updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND status='sending'"
   ).bind(copied.indeterminate?'uncertain_telegram_result':('telegram_'+String(copied.code||'unknown')),row.source_chat_id,row.source_message_id).run();
   errors++;
  }
 }
 return {processed,errors};
}

export async function queueKnownVaultSources(env,{limit=25}={}){
 // Explicit controlled backfill of D1-known references only: no history scraping.
 if(!await enabled(env))return {queued:0,disabled:true};
 const cap=Math.min(25,Math.max(1,Number(limit)||25));
 const result=await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_owner_vault(source_chat_id,source_message_id,media_kind) "+
  "SELECT x.chat_id,x.message_id,x.kind FROM ("+
  "SELECT e.chat_id AS chat_id,e.source_message_id AS message_id,'video' AS kind "+
  "FROM cine_series_episodes e JOIN cine_series_channels c ON c.chat_id=e.chat_id WHERE c.rights_attested=1 AND c.enabled=1 "+
  "UNION ALL SELECT p.chat_id,p.source_message_id,'poster' "+
  "FROM cine_series_posters p JOIN cine_series_channels c ON c.chat_id=p.chat_id WHERE c.rights_attested=1 AND c.enabled=1 "+
  "UNION ALL SELECT l.source_chat_id,l.source_message_id,'video' FROM cine_classic_links l WHERE l.status='published'"+
  ") x WHERE NOT EXISTS(SELECT 1 FROM cine_owner_vault v WHERE v.source_chat_id=x.chat_id AND v.source_message_id=x.message_id) ORDER BY x.chat_id,x.message_id LIMIT ?"
 ).bind(cap).run();
 return {queued:Number(result.meta?.changes||0)};
}
