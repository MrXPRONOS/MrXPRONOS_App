// Durable write-ahead receipts shared by future CineX/Formation bot-only
// publication adapters. NO Telegram calls and NO automatic retry of an
// unknown result. A caller must persist this in a real private D1 database.
import {ensureManualFallbackSchema} from './manual-fallback-inbox.mjs';

const CHAT=/^-100[0-9]{6,}$/;
const STAGES=new Set([
 'central_stock','private_poster','private_video','private_index',
 'public_poster','public_video','formation_file'
]);
const CATEGORIES=new Set([
 'films','comedie','desir','action','series','animes',
 'formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset',
]);
const KEY=/^[a-z0-9][a-zA-Z0-9:._ -]{4,240}$/;
const POSITIVE=x=>Number.isSafeInteger(Number(x))&&Number(x)>0;
export class ManualReceiptBlocked extends Error{
 constructor(reason){super(reason);this.name='ManualReceiptBlocked'}
}
function check(op){
 if(!op||!CATEGORIES.has(op.category)||!STAGES.has(op.stage)||
    !KEY.test(String(op.content_key||''))||
    !CHAT.test(String(op.target_chat_id||''))||
    !CHAT.test(String(op.source_chat_id||''))||
    !POSITIVE(op.source_message_id))
   throw new ManualReceiptBlocked('invalid_publication_intent');
}
const SELECT="SELECT status,source_chat_id,source_message_id,target_chat_id,target_message_id "+
 "FROM cine_manual_fallback_receipts WHERE category=? AND content_key=? AND stage=?";
const WHERE=" WHERE category=? AND content_key=? AND stage=?";
const PARAMS=op=>[op.category,op.content_key,op.stage];

export async function readManualReceipt(env,op){
 check(op);
 await ensureManualFallbackSchema(env);
 return await env.DB.prepare(SELECT).bind(...PARAMS(op)).first();
}

export async function acquireManualReceipt(env,op){
 check(op);
 await ensureManualFallbackSchema(env);
 const args=[...PARAMS(op),String(op.target_chat_id),
  String(op.source_chat_id),Number(op.source_message_id)];
 await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_manual_fallback_receipts "+
  "(category,content_key,stage,status,target_chat_id,source_chat_id,source_message_id) "+
  "VALUES(?,?,?,'reserved',?,?,?)"
 ).bind(...args).run();
 const current=await env.DB.prepare(SELECT).bind(...PARAMS(op)).first();
 if(!current)throw new ManualReceiptBlocked('receipt_unavailable');
 if(String(current.target_chat_id)!==String(op.target_chat_id)||
    String(current.source_chat_id)!==String(op.source_chat_id)||
    Number(current.source_message_id)!==Number(op.source_message_id))
   throw new ManualReceiptBlocked('immutable_receipt_identity_conflict');
 if(current.status==='complete'){
  if(!POSITIVE(current.target_message_id))
   throw new ManualReceiptBlocked('complete_receipt_without_message_id');
  return {status:'complete',message_id:Number(current.target_message_id)};
 }
 if(current.status!=='reserved')
  throw new ManualReceiptBlocked('inflight_or_uncertain_requires_reconciliation');
 const claim=await env.DB.prepare(
  "UPDATE cine_manual_fallback_receipts SET status='inflight',updated_at=CURRENT_TIMESTAMP "+
  WHERE+" AND status='reserved'"
 ).bind(...PARAMS(op)).run();
 if(Number(claim.meta?.changes||0)!==1)
  throw new ManualReceiptBlocked('concurrent_publisher_claim');
 return {status:'inflight'};
}

export async function completeManualReceipt(env,op,messageId){
 check(op);
 if(!POSITIVE(messageId))throw new ManualReceiptBlocked('invalid_telegram_receipt_id');
 const completed=await env.DB.prepare(
  "UPDATE cine_manual_fallback_receipts SET status='complete',"+
  "target_message_id=?,updated_at=CURRENT_TIMESTAMP"+WHERE+
  " AND status='inflight' AND target_chat_id=? AND source_chat_id=? "+
  "AND source_message_id=?"
 ).bind(Number(messageId),...PARAMS(op),String(op.target_chat_id),
  String(op.source_chat_id),Number(op.source_message_id)).run();
 if(Number(completed.meta?.changes||0)!==1)
  throw new ManualReceiptBlocked('could_not_complete_receipt');
 return {status:'complete',message_id:Number(messageId)};
}

export async function uncertainManualReceipt(env,op){
 check(op);
 // We never clear an uncertain receipt automatically.
 await env.DB.prepare(
  "UPDATE cine_manual_fallback_receipts SET status='uncertain',"+
  "updated_at=CURRENT_TIMESTAMP"+WHERE+" AND status='inflight'"
 ).bind(...PARAMS(op)).run();
}

export async function performJournaledCopy(env,op,copyMessage){
 // Intent is locked before making an external Telegram write. A timeout,
 // 429, 403, crash or D1 failure must NOT cause blind replay.
 if(typeof copyMessage!=='function')
  throw new ManualReceiptBlocked('copy_transport_unavailable');
 const state=await acquireManualReceipt(env,op);
 if(state.status==='complete')return {...state,skipped:true};
 try{
  const sent=await copyMessage();
  const id=typeof sent==='object'?sent?.message_id:sent;
  return {...await completeManualReceipt(env,op,id),skipped:false};
 }catch(err){
  try{await uncertainManualReceipt(env,op)}catch{
   // The persisted "inflight" remains a locked unsafe state.
  }
  throw err;
 }
}

export async function summarizeManualReceipts(env){
 await ensureManualFallbackSchema(env);
 const data=(await env.DB.prepare(
  "SELECT category,stage,status,COUNT(*) AS n FROM cine_manual_fallback_receipts "+
  "GROUP BY category,stage,status"
 ).all()).results||[];
 return data.map(x=>({
  category:x.category,stage:x.stage,status:x.status,count:Number(x.n||0)}));
}
