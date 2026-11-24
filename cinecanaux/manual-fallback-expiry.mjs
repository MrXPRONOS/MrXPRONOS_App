// Delete only bot-authored public videos recorded by an immutable D1 receipt.
// Exactly one deletion attempt for each message, never blind retry on timeout.
const CHAT=/^-100\d{6,}$/;
const EXPIRY_SQL=[
 "CREATE TABLE IF NOT EXISTS cine_manual_fallback_expiries (category TEXT NOT NULL,content_key TEXT NOT NULL,target_chat_id TEXT NOT NULL CHECK(target_chat_id GLOB '-100[0-9]*'),target_message_id INTEGER NOT NULL CHECK(target_message_id>0),not_before TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN('pending','deleting','uncertain','deleted')),error_code TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(category,content_key))",
 "CREATE INDEX IF NOT EXISTS idx_cine_manual_fallback_expiries ON cine_manual_fallback_expiries(status,not_before)"
];
export async function ensureExpirySchema(db){
 for(const sql of EXPIRY_SQL)await db.query(sql);
}
export async function schedulePublicExpiry(db,category,key){
 await ensureExpirySchema(db);
 // Always take original Telegram receipt time, not current retry time.
 await db.query(
  "INSERT OR IGNORE INTO cine_manual_fallback_expiries"+
  "(category,content_key,target_chat_id,target_message_id,not_before) "+
  "SELECT category,content_key,target_chat_id,target_message_id,"+
  "datetime(updated_at,'+12 hours') FROM cine_manual_fallback_receipts "+
  "WHERE category=? AND content_key=? AND stage='public_video' AND status='complete' "+
  "AND target_message_id>0",
  [category,key]);
 const record=(await db.query(
  "SELECT status,target_message_id FROM cine_manual_fallback_expiries "+
  "WHERE category=? AND content_key=?",[category,key])).results||[];
 if(record.length!==1)throw Error('public_video_expiry_not_registered');
 return record[0];
}
export async function sweepPublicExpiry(db,botForCategory,{limit=15}={}){
 await ensureExpirySchema(db);
 // Recovery after DB failure between complete public video copy and expiry
 // creation is based on the original completed Telegram receipt timestamp.
 await db.query(
  "INSERT OR IGNORE INTO cine_manual_fallback_expiries"+
  "(category,content_key,target_chat_id,target_message_id,not_before) "+
  "SELECT category,content_key,target_chat_id,target_message_id,"+
  "datetime(updated_at,'+12 hours') FROM cine_manual_fallback_receipts "+
  "WHERE stage='public_video' AND status='complete' AND target_message_id>0"
 );
 const count=Math.max(1,Math.min(20,Number(limit)||15));
 const rows=(await db.query(
  "SELECT category,content_key,target_chat_id,target_message_id "+
  "FROM cine_manual_fallback_expiries "+
  "WHERE status='pending' AND not_before<=CURRENT_TIMESTAMP "+
  "ORDER BY not_before LIMIT ?",[count])).results||[];
 let deleted=0,uncertain=0,skipped=0;
 for(const r of rows){
  if(!CHAT.test(String(r.target_chat_id))||
     !Number.isSafeInteger(Number(r.target_message_id))||
     Number(r.target_message_id)<=0){
   skipped++;continue;
  }
  const bot=botForCategory(r.category);
  if(!bot) {skipped++;continue;}
  // Only a verified public destination with an actual completed send
  // receipt can be deleted. Telegram bots cannot list arbitrary history.
  try{
   const proof=(await db.query(
    "SELECT 1 AS ok FROM cine_manual_fallback_receipts WHERE category=? "+
    "AND content_key=? AND stage='public_video' AND status='complete' "+
    "AND target_chat_id=? AND target_message_id=?",
    [r.category,r.content_key,r.target_chat_id,r.target_message_id])).results||[];
   if(proof.length!==1){skipped++;continue;}
   const verified=await bot.verifyChannel(r.target_chat_id,{publicOnly:true});
   if(String(verified.id)!==String(r.target_chat_id)){
    skipped++;continue;
   }
  }catch{skipped++;continue;}
  const claim=await db.query(
   "UPDATE cine_manual_fallback_expiries SET status='deleting',"+
   "updated_at=CURRENT_TIMESTAMP WHERE category=? AND content_key=? "+
   "AND status='pending'",[r.category,r.content_key]);
  if(Number(claim.meta?.changes||0)!==1){skipped++;continue;}
  try{
   const reply=await bot.api('deleteMessage',{
    chat_id:r.target_chat_id,message_id:Number(r.target_message_id)});
   if(reply!==true)throw Error('telegram_delete_result_uncertain');
   await db.query(
    "UPDATE cine_manual_fallback_expiries SET status='deleted',"+
    "error_code='',updated_at=CURRENT_TIMESTAMP "+
    "WHERE category=? AND content_key=? AND status='deleting'",
    [r.category,r.content_key]);
   deleted++;
  }catch{
   // D1/Telegram failures after an attempted delete are NOT retries.
   await db.query(
    "UPDATE cine_manual_fallback_expiries SET status='uncertain',"+
    "error_code='ambiguous_delete_result',updated_at=CURRENT_TIMESTAMP "+
    "WHERE category=? AND content_key=? AND status='deleting'",
    [r.category,r.content_key]).catch(()=>{});
   uncertain++;
  }
 }
 return {seen:rows.length,deleted,uncertain,skipped};
}
