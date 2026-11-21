// CinéX private Telegram media stock: IDs and timestamps only, no video bytes.
// Destination channel is created by the OWNER session once, not by the bot.
// The only copy operations are Bot API copyMessage on rights-attested sources.
// Copy ambiguities become needs_review, never blindly retried.
import {reserveTelegramSend,noteTelegramFloodWait} from './telegram-global-quota.mjs';

const SOURCE=/^-100[0-9]{6,}$/;
const validId=x=>Number.isSafeInteger(Number(x))&&Number(x)>0;

const CREATE_CONFIG=`CREATE TABLE IF NOT EXISTS cine_private_stock_config (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 stock_chat_id TEXT NOT NULL CHECK(stock_chat_id GLOB '-100[0-9]*'),
 owner_id INTEGER NOT NULL CHECK(owner_id>0),
 radar_bot_id INTEGER NOT NULL CHECK(radar_bot_id>0),
 publisher_bot_id INTEGER CHECK(publisher_bot_id IS NULL OR publisher_bot_id>0),
 ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN(0,1)),
 verified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)`;
const CREATE_ITEMS=`CREATE TABLE IF NOT EXISTS cine_private_stock_items (
 source_chat_id TEXT NOT NULL CHECK(source_chat_id GLOB '-100[0-9]*'),
 source_message_id INTEGER NOT NULL CHECK(source_message_id>0),
 media_kind TEXT NOT NULL DEFAULT 'video' CHECK(media_kind IN('video','document')),
 source_family TEXT NOT NULL CHECK(source_family IN('classic','franchise','library','series')),
 state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN('queued','sending','stored','needs_review','disabled')),
 stock_message_id INTEGER CHECK(stock_message_id IS NULL OR stock_message_id>0),
 attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 10),
 not_before TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 lock_until TEXT,
 error_code TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(source_chat_id,source_message_id),
 UNIQUE(stock_message_id),
 CHECK((state != 'stored') OR stock_message_id IS NOT NULL)
)`;
const INDEX="CREATE INDEX IF NOT EXISTS idx_cinex_stock_queue ON cine_private_stock_items(state,not_before,created_at)";
const initializers=new WeakMap();
export async function ensurePrivateStockTables(env){
 if(!env?.DB?.prepare)throw Error('stock_d1_unavailable');
 let pending=initializers.get(env.DB);
 if(!pending){
  pending=(async()=>{
   await env.DB.prepare(CREATE_CONFIG).run();
   await env.DB.prepare(CREATE_ITEMS).run();
   await env.DB.prepare(INDEX).run();
  })();
  initializers.set(env.DB,pending);
 }
 try{await pending}catch(e){initializers.delete(env.DB);throw e}
}

async function privateStock(env){
 await ensurePrivateStockTables(env);
 const row=await env.DB.prepare("SELECT stock_chat_id,owner_id,radar_bot_id FROM cine_private_stock_config WHERE singleton=1 AND ready=1").first();
 if(!row||!SOURCE.test(String(row.stock_chat_id))||!validId(row.owner_id)||!validId(row.radar_bot_id))return null;
 return row;
}
const SOURCES=[
 // Existing approved classics. The owner has explicitly published those links.
 ["classic","SELECT l.source_chat_id,l.source_message_id,'video' media_kind FROM cine_classic_links l WHERE l.status='published'"],
 // Single franchise + explicitly attested distribution rights, no pending films.
 ["franchise","SELECT f.source_chat_id,f.source_message_id,'video' media_kind FROM cine_franchise_films f JOIN cine_franchise_catalog c ON c.slug=f.slug WHERE c.rights_attested=1 AND c.status='published'"],
 // Only fully verified film catalogue entries; no series and no review-pending uploads.
 ["library","SELECT b.private_chat_id source_chat_id,m.source_message_id,m.media_kind FROM cine_delivery_media m JOIN cine_delivery_libraries b ON b.category=m.category JOIN cine_delivery_titles t ON t.title_key=m.title_key AND t.category=m.category WHERE t.content_kind='film' AND t.approval='approved' AND t.rights_attested=1 AND b.rights_attested=1 AND b.bot_access='verified' AND m.availability='approved'"],
];

export async function queueKnownStockSources(env,{limit=20}={}){
 if(!await privateStock(env))return {queued:0,disabled:true};
 const max=Math.min(25,Math.max(1,Number(limit)||20));
 let queued=0;
 for(const [family,sql] of SOURCES){
  if(queued>=max)break;
  const result=await env.DB.prepare(
   "INSERT OR IGNORE INTO cine_private_stock_items(source_chat_id,source_message_id,media_kind,source_family) "+
   "SELECT source_chat_id,source_message_id,media_kind,? FROM ("+sql+") "+
   "WHERE source_chat_id GLOB '-100[0-9]*' AND source_message_id>0 LIMIT ?"
  ).bind(family,max-queued).run();
  queued+=Number(result.meta?.changes||0);
 }
 return {queued};
}

async function sourceApproved(env,row){
 const id=Number(row.source_message_id),chat=String(row.source_chat_id);
 if(!validId(id)||!SOURCE.test(chat))return false;
 let sql,parameters;
 switch(row.source_family){
 case 'classic':
  sql="SELECT 1 ok FROM cine_classic_links WHERE source_chat_id=? AND source_message_id=? AND status='published'";
  parameters=[chat,id];break;
 case 'franchise':
  sql="SELECT 1 ok FROM cine_franchise_films f JOIN cine_franchise_catalog c ON c.slug=f.slug WHERE f.source_chat_id=? AND f.source_message_id=? AND c.rights_attested=1 AND c.status='published'";
  parameters=[chat,id];break;
 case 'library':
  sql="SELECT 1 ok FROM cine_delivery_media m JOIN cine_delivery_libraries b ON b.category=m.category JOIN cine_delivery_titles t ON t.title_key=m.title_key AND t.category=m.category WHERE b.private_chat_id=? AND m.source_message_id=? AND t.content_kind='film' AND t.approval='approved' AND t.rights_attested=1 AND b.rights_attested=1 AND b.bot_access='verified' AND m.availability='approved'";
  parameters=[chat,id];break;
 default:return false;
 }
 return Boolean((await env.DB.prepare(sql).bind(...parameters).first())?.ok);
}

export async function sourceFromPrivateStock(env,chat,message){
 // Only confirmed Telegram channel copies may replace the source reference.
 if(!SOURCE.test(String(chat))||!validId(message))return {chatId:chat,messageId:message,fromStock:false};
 try{
  const config=await privateStock(env);
  if(!config)return {chatId:chat,messageId:message,fromStock:false};
  const row=await env.DB.prepare(
   "SELECT stock_message_id FROM cine_private_stock_items WHERE source_chat_id=? AND source_message_id=? AND state='stored' AND stock_message_id>0"
  ).bind(String(chat),Number(message)).first();
  if(!validId(row?.stock_message_id))return {chatId:chat,messageId:message,fromStock:false};
  return {chatId:config.stock_chat_id,messageId:Number(row.stock_message_id),fromStock:true};
 }catch{return {chatId:chat,messageId:message,fromStock:false}}
}

export async function processPrivateStockQueue(env,{limit=1}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {disabled:true,stored:0};
 const config=await privateStock(env);
 if(!config)return {disabled:true,stored:0};
 await env.DB.prepare(
  "UPDATE cine_private_stock_items SET state='needs_review',error_code='ambiguous_copy_result',lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE state='sending' AND lock_until<CURRENT_TIMESTAMP"
 ).run();
 const max=Math.min(2,Math.max(1,Number(limit)||1));
 const rows=(await env.DB.prepare(
  "SELECT source_chat_id,source_message_id,source_family,attempt_count FROM cine_private_stock_items "+
  "WHERE state='queued' AND not_before<=CURRENT_TIMESTAMP AND attempt_count<10 "+
  "ORDER BY created_at,source_chat_id,source_message_id LIMIT ?"
 ).bind(max).all()).results||[];
 let stored=0,deferred=0,review=0;
 for(const row of rows){
  if(!await sourceApproved(env,row)){
   await env.DB.prepare(
    "UPDATE cine_private_stock_items SET state='disabled',error_code='source_rights_not_confirmed',updated_at=CURRENT_TIMESTAMP WHERE source_chat_id=? AND source_message_id=? AND state='queued'"
   ).bind(row.source_chat_id,row.source_message_id).run();
   review++;continue;
  }
  // The limiter protects the private stock bot together with subscriber jobs.
  const slot=await reserveTelegramSend(env);
  if(!slot.allowed){deferred++;break}
  const claim=await env.DB.prepare(
   "UPDATE cine_private_stock_items SET state='sending',attempt_count=attempt_count+1,lock_until=datetime('now','+3 minutes'),updated_at=CURRENT_TIMESTAMP "+
   "WHERE source_chat_id=? AND source_message_id=? AND state='queued' AND not_before<=CURRENT_TIMESTAMP AND attempt_count<10"
  ).bind(row.source_chat_id,row.source_message_id).run();
  if(Number(claim.meta?.changes||0)!==1)continue;
  let answer;
  try{
   const res=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/copyMessage",{
    method:'POST',headers:{'content-type':'application/json'},signal:AbortSignal.timeout(14000),
    body:JSON.stringify({chat_id:config.stock_chat_id,from_chat_id:row.source_chat_id,
     message_id:row.source_message_id,disable_notification:true})
   });
   answer=await res.json();
   if(!res.ok&&Number(answer?.error_code)!==429){
    // Explicit non-429 failure is final; no repeat without manual review.
    answer={ok:false,error_code:Number(answer?.error_code||res.status),description:'telegram_response'};
   }
  }catch{answer=null}
  if(answer?.ok===true&&validId(answer?.result?.message_id)){
   await env.DB.prepare(
    "UPDATE cine_private_stock_items SET state='stored',stock_message_id=?,lock_until=NULL,error_code=NULL,updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND state='sending'"
   ).bind(Number(answer.result.message_id),row.source_chat_id,row.source_message_id).run();
   stored++;
  }else if(Number(answer?.error_code)===429){
   const seconds=Math.max(10,Math.min(3600,Number(answer?.parameters?.retry_after||60)));
   await noteTelegramFloodWait(env,seconds);
   await env.DB.prepare(
    "UPDATE cine_private_stock_items SET state='queued',not_before=datetime('now',?),lock_until=NULL,error_code='telegram_429',updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND state='sending'"
   ).bind('+'+seconds+' seconds',row.source_chat_id,row.source_message_id).run();
   deferred++;break;
  }else{
   await env.DB.prepare(
    "UPDATE cine_private_stock_items SET state='needs_review',error_code=?,lock_until=NULL,updated_at=CURRENT_TIMESTAMP "+
    "WHERE source_chat_id=? AND source_message_id=? AND state='sending'"
   ).bind(answer?'telegram_copy_rejected':'telegram_result_uncertain',row.source_chat_id,row.source_message_id).run();
   review++;
  }
 }
 return {stored,deferred,review,private:true};
}

export async function privateStockOverview(env){
 try{
  const config=await privateStock(env);
  if(!config)return {ready:false,stored:0,queued:0,review:0};
  const result=await env.DB.prepare(
   "SELECT state,COUNT(*) count FROM cine_private_stock_items GROUP BY state"
  ).all();
  const sums=Object.fromEntries((result.results||[]).map(x=>[x.state,Number(x.count||0)]));
  return {ready:true,stored:sums.stored||0,queued:sums.queued||0,
   review:sums.needs_review||0,disabled:sums.disabled||0,
   // The admin only needs counts, not private channel IDs or subscriber IDs.
  };
 }catch{return {ready:false,unavailable:true}}
}
