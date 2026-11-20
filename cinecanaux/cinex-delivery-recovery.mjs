// T02 — Owner-only, non-sending recovery of quarantined delivery jobs.
// Telegram's Bot API cannot prove that a timed-out copyMessage was NOT sent.
// Therefore no API in this module performs a send, retries an uncertain copy,
// or converts an ambiguous delivery into a queued item.
import {recordAdminAudit} from './admin-ops.mjs';

const FAMILIES=Object.freeze({
 libraries:{jobs:'cine_delivery_jobs',items:'cine_delivery_job_items',item:'ordinal'},
 series:{jobs:'cine_series_jobs',items:'cine_series_job_items',item:'ordinal'},
 franchise:{jobs:'cine_franchise_jobs',items:'cine_franchise_job_items',item:'part'},
});
const VALID_FAMILIES=Object.keys(FAMILIES);

function positive(value){
 const n=Number(value);
 return Number.isSafeInteger(n)&&n>0?n:null;
}
function evidenceDate(value,now=Date.now()){
 if(typeof value!=='string'||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/.test(value))return null;
 const millis=Date.parse(value);
 if(!Number.isFinite(millis)||millis>now+60000||millis<now-46*3600000)return null;
 // SQLite UTC timestamps; TTL is computed from the actual time claimed by owner.
 return value.slice(0,19).replace('T',' ');
}

const conditions=(item,job)=>{
 const queued=`EXISTS(SELECT 1 FROM ${item} q WHERE q.job_id=${job}.id AND q.state='queued')`;
 const uncertain=`EXISTS(SELECT 1 FROM ${item} u WHERE u.job_id=${job}.id AND u.state IN ('sending','needs_review'))`;
 const invalid=`EXISTS(SELECT 1 FROM ${item} bad WHERE bad.job_id=${job}.id AND ((bad.state='queued' AND (bad.delivered_message_id IS NOT NULL OR bad.sent_at IS NOT NULL)) OR (bad.state='sent' AND (bad.delivered_message_id IS NULL OR bad.sent_at IS NULL))))`;
 return {queued,uncertain,invalid};
};

// Only numeric job references and state counts leave the owner API.
// Never return subscriber IDs, private channel IDs, tokens or message references.
export async function listDeliveryRecovery(env,{limit=15}={}){
 const size=Math.min(30,Math.max(1,Number(limit)||15));
 const families=[];
 for(const family of VALID_FAMILIES){
  const {jobs,items}=FAMILIES[family];
  const sql=`SELECT j.id,j.created_at,
  (SELECT COUNT(*) FROM ${items} i WHERE i.job_id=j.id AND i.state='queued') queued,
  (SELECT COUNT(*) FROM ${items} i WHERE i.job_id=j.id AND i.state='sent') sent,
  (SELECT COUNT(*) FROM ${items} i WHERE i.job_id=j.id AND i.state='needs_review') uncertain,
  (SELECT COUNT(*) FROM ${items} i WHERE i.job_id=j.id AND i.state='sending') in_flight,
  (SELECT COUNT(*) FROM ${items} i WHERE i.job_id=j.id AND i.state='queued' AND (i.delivered_message_id IS NOT NULL OR i.sent_at IS NOT NULL)) inconsistent
  FROM ${jobs} j WHERE j.status='needs_review' ORDER BY j.id DESC LIMIT ?`;
  const rows=(await env.DB.prepare(sql).bind(size).all()).results||[];
  families.push(...rows.map(row=>{
   const queued=Number(row.queued||0),sent=Number(row.sent||0);
   const uncertain=Number(row.uncertain||0),inFlight=Number(row.in_flight||0);
   return {family,job_id:Number(row.id),created_at:row.created_at,
    queued,sent,uncertain,in_flight:inFlight,
    resume_safe:uncertain===0&&inFlight===0&&Number(row.inconsistent||0)===0,
    diagnosis:uncertain||inFlight?'delivery_result_uncertain':'sources_or_queue_need_recheck'};
  }));
 }
 const classics=(await env.DB.prepare(
  "SELECT id,created_at,delivered_message_id IS NOT NULL AS has_receipt FROM cine_classic_deliveries WHERE status='needs_review' ORDER BY id DESC LIMIT ?"
 ).bind(size).all()).results||[];
 for(const row of classics)families.push({
  family:'classics',job_id:Number(row.id),created_at:row.created_at,
  queued:0,sent:0,uncertain:row.has_receipt?0:1,in_flight:0,
  resume_safe:false,diagnosis:row.has_receipt?'receipt_needs_manual_check':'delivery_result_uncertain'
 });
 const owner=(await env.DB.prepare(
  "SELECT COUNT(*) n FROM cine_owner_vault WHERE status='needs_review'"
 ).first())?.n||0;
 return {cases:families.slice(0,90),owner_archive_review:Number(owner),
  archive_recovery:'owner_forward_verified_original_to_bot',checked_at:new Date().toISOString()};
}

// A formerly blocked job may resume ONLY when every remaining copy is still
// unattempted/explicitly queued and no ambiguous state exists.
// The queue will revalidate source rights before any later Telegram request.
export async function resumeProvenQueued(env,{family,job_id},ownerId){
 const config=FAMILIES[family],id=positive(job_id);
 if(!config||!id)return {ok:false,status:400,code:'invalid_case'};
 const {jobs,items}=config,{queued,uncertain,invalid}=conditions(items,jobs);
 const sql=`UPDATE ${jobs} SET
   status=CASE WHEN ${queued} THEN 'queued' ELSE 'complete' END,
   lock_until=NULL,not_before=CURRENT_TIMESTAMP
   WHERE id=? AND status='needs_review' AND NOT ${uncertain} AND NOT ${invalid}
   AND EXISTS(SELECT 1 FROM ${items} e WHERE e.job_id=${jobs}.id)
   RETURNING status`;
 const result=await env.DB.prepare(sql).bind(id).first();
 if(!result)return {ok:false,status:409,code:'ambiguous_or_changed_job'};
 await recordAdminAudit(env,ownerId,'cinex.recovery_safe',family+':'+id,String(result.status));
 return {ok:true,status:200,job_status:result.status,copy_sent:false};
}

// Owner must provide the actual bot-generated private message ID and send
// timestamp OBSERVED in Telegram, plus explicit attestation. Never resend.
// Duplicate submissions cannot count a second delivery or overwrite a receipt.
export async function attestExistingCopy(env,data,ownerId,{now=Date.now()}={}){
 const family=data?.family,id=positive(data?.job_id),itemNo=positive(data?.item),
  messageId=positive(data?.message_id),sentAt=evidenceDate(data?.sent_at,now);
 if(!id||!messageId||!sentAt||data?.confirmed_existing_copy!==true)
  return {ok:false,status:400,code:'valid_existing_copy_evidence_required'};
 if(family==='classics'){
  const prior=await env.DB.prepare(
   "SELECT status,delivered_message_id FROM cine_classic_deliveries WHERE id=?"
  ).bind(id).first();
  if(prior?.status!=='needs_review'||prior.delivered_message_id!==null)
   return {ok:false,status:409,code:'case_already_resolved_or_changed'};
  const r=await env.DB.prepare(
   "UPDATE cine_classic_deliveries SET status='sent',delivered_message_id=?,sent_at=?,delete_after=datetime(?,'+24 hours'),delete_retry_at=datetime(?,'+24 hours'),delete_state='pending',lock_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='needs_review' AND delivered_message_id IS NULL AND sent_at IS NULL RETURNING id"
  ).bind(messageId,sentAt,sentAt,sentAt,id).first();
  if(!r)return {ok:false,status:409,code:'case_already_resolved_or_changed'};
 }else{
  const config=FAMILIES[family];
  if(!config||!itemNo)return {ok:false,status:400,code:'invalid_case'};
  const {jobs,items,item}=config;
  const open=await env.DB.prepare(`SELECT 1 ok FROM ${jobs} WHERE id=? AND status='needs_review'`).bind(id).first();
  if(!open?.ok)return {ok:false,status:409,code:'case_already_resolved_or_changed'};
  const change=await env.DB.prepare(
   `UPDATE ${items} SET state='sent',delivered_message_id=?,sent_at=?,delete_after=datetime(?,'+24 hours'),delete_retry_at=datetime(?,'+24 hours'),delete_state='pending',delete_attempts=0,delete_retry_at=datetime(?,'+24 hours') WHERE job_id=? AND ${item}=? AND state='needs_review' AND delivered_message_id IS NULL AND sent_at IS NULL RETURNING job_id`
  ).bind(messageId,sentAt,sentAt,sentAt,sentAt,id,itemNo).first();
  if(!change)return {ok:false,status:409,code:'item_already_resolved_or_changed'};
  const {queued,uncertain}=conditions(items,jobs);
  // Refresh progress from actual sent receipts, not from a second increment.
  await env.DB.prepare(
   `UPDATE ${jobs} SET delivered_items=(SELECT COUNT(*) FROM ${items} q WHERE q.job_id=${jobs}.id AND q.state='sent'),status=CASE WHEN ${uncertain} THEN 'needs_review' WHEN ${queued} THEN 'queued' ELSE 'complete' END,lock_until=NULL,not_before=CURRENT_TIMESTAMP WHERE id=? AND status='needs_review'`
  ).bind(id).run();
 }
 await recordAdminAudit(env,ownerId,'cinex.existing_copy_attested',family+':'+id,
  family==='classics'?'single':'item_'+itemNo);
 return {ok:true,status:200,copy_sent:false,receipt_recorded:true};
}
