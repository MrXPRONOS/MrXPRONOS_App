// T03 — Real 24-hour deletion sweeps with independent error isolation.
// Deletes only bot-created PRIVATE subscriber copies from existing receipt tables.
// Never touches the owner archive, channel originals or Saved Messages.
import {cleanupDeliveredCopies} from './cinex-expiry.mjs';
import {cleanupSeriesCopies} from './individual-series.mjs';
import {cleanupClassicDeliveries} from './cinex-classic.mjs';
import {cleanupFranchiseCopies} from './franchise-films.mjs';

const FAMILIES=Object.freeze({
 libraries:{table:'cine_delivery_job_items',type:"state='sent'",
  runner:(env,{now,limit})=>cleanupDeliveredCopies(env,{now:new Date(now),limit})},
 series:{table:'cine_series_job_items',type:"state='sent'",
  runner:(env,{now,limit})=>cleanupSeriesCopies(env,{now,limit})},
 classics:{table:'cine_classic_deliveries',type:"status='sent'",
  runner:(env,{now,limit})=>cleanupClassicDeliveries(env,{now,limit})},
 franchise:{table:'cine_franchise_job_items',type:"state='sent'",
  runner:(env,{now,limit})=>cleanupFranchiseCopies(env,{now,limit})},
});

const CREATE=`CREATE TABLE IF NOT EXISTS cine_cleanup_health (
 family TEXT PRIMARY KEY CHECK(family IN ('libraries','series','classics','franchise')),
 status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN ('waiting','ok','error')),
 last_attempt_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_success_at TEXT,
 last_error TEXT NOT NULL DEFAULT '',
 last_deleted INTEGER NOT NULL DEFAULT 0,
 last_already_gone INTEGER NOT NULL DEFAULT 0,
 last_retried INTEGER NOT NULL DEFAULT 0,
 last_manual_review INTEGER NOT NULL DEFAULT 0,
 last_overdue INTEGER NOT NULL DEFAULT 0,
 last_backfilled INTEGER NOT NULL DEFAULT 0,
 run_count INTEGER NOT NULL DEFAULT 0
)`;
const HOUR_MS=3600000;

export async function ensureCleanupHealth(env){
 await env.DB.prepare(CREATE).run();
}

async function backfillExpiry(env,config){
 // Backfill only copies with a confirmed Telegram receipt, never unverified
 // 'needs_review' or original channel posts. 24h is counted from sent_at.
 const sql=`UPDATE ${config.table}
 SET delete_after=datetime(sent_at,'+24 hours'),
 delete_retry_at=COALESCE(delete_retry_at,datetime(sent_at,'+24 hours'))
 WHERE ${config.type} AND delivered_message_id IS NOT NULL
 AND sent_at IS NOT NULL AND delete_after IS NULL`;
 const r=await env.DB.prepare(sql).run();
 return Number(r?.meta?.changes||0);
}
async function backlog(env,config){
 const sql=`SELECT COUNT(*) AS due FROM ${config.table}
 WHERE ${config.type} AND delivered_message_id IS NOT NULL
 AND delete_after<=CURRENT_TIMESTAMP AND delete_state IN ('pending','retry','deleting')`;
 const row=await env.DB.prepare(sql).first();
 return Number(row?.due||0);
}
async function storeHealth(env,family,value){
 await env.DB.prepare(
  "INSERT INTO cine_cleanup_health(family,status,last_error,last_deleted,last_already_gone,last_retried,last_manual_review,last_overdue,last_backfilled,run_count,last_success_at) "+
  "VALUES(?,?,?,?,?,?,?,?,?,1,CASE WHEN ?='ok' THEN CURRENT_TIMESTAMP ELSE NULL END) "+
  "ON CONFLICT(family) DO UPDATE SET status=excluded.status,last_error=excluded.last_error,last_deleted=excluded.last_deleted,"+
  "last_already_gone=excluded.last_already_gone,last_retried=excluded.last_retried,last_manual_review=excluded.last_manual_review,"+
  "last_overdue=excluded.last_overdue,last_backfilled=excluded.last_backfilled,last_attempt_at=CURRENT_TIMESTAMP,"+
  "last_success_at=CASE WHEN excluded.status='ok' THEN CURRENT_TIMESTAMP ELSE cine_cleanup_health.last_success_at END,"+
  "run_count=cine_cleanup_health.run_count+1"
 ).bind(family,value.status,value.error,value.deleted,value.already_gone,value.retried,
        value.manual_review,value.overdue,value.backfilled,value.status).run();
}

// Caller may inject pure fake runners in offline tests; production always uses
// the four verified cleanup routines. One family cannot stop the other three.
export async function runCopyExpirySweep(env,{now=Date.now(),limit=12,runners={}}={}){
 if(!env?.DB||!env?.TELEGRAM_TOKEN)return {disabled:true,checked:0};
 await ensureCleanupHealth(env);
 const max=Math.min(24,Math.max(1,Number(limit)||12));
 const tasks=Object.entries(FAMILIES).map(async([family,config])=>{
  let backfilled=0,overdue=0,status='ok',error='',stats={};
  try{
   backfilled=await backfillExpiry(env,config);
   const runner=runners[family]||config.runner;
   stats=await runner(env,{now,limit:max});
   if(stats?.disabled)throw Error('cleanup_handler_disabled');
   overdue=await backlog(env,config);
  }catch(reason){
   status='error';error=String(reason?.name||'Error').slice(0,55);
   console.warn('cinex_cleanup_family_failed',family,error); // no private identifiers
   try{overdue=await backlog(env,config)}catch{}
  }
  const value={status,error,deleted:Number(stats?.deleted||0),
   already_gone:Number(stats?.already_gone||0),
   retried:Number(stats?.retried||stats?.retries||stats?.retry||0),
   manual_review:Number(stats?.manual_review||0),overdue,backfilled};
  try{await storeHealth(env,family,value)}catch{
   console.warn('cinex_cleanup_health_unavailable',family);
  }
  return {family,...value};
 });
 const families=await Promise.all(tasks);
 const failed=families.filter(x=>x.status!=='ok').length;
 return {checked:families.length,failed,
  deleted:families.reduce((n,x)=>n+x.deleted,0),
  already_gone:families.reduce((n,x)=>n+x.already_gone,0),
  overdue:families.reduce((n,x)=>n+x.overdue,0),
  families};
}

export async function cleanupHealthOverview(env,{now=Date.now()}={}){
 try{
  const rows=(await env.DB.prepare(
   "SELECT family,status,last_attempt_at,last_success_at,last_error,last_deleted,last_already_gone,last_retried,last_manual_review,last_overdue,last_backfilled,run_count FROM cine_cleanup_health ORDER BY family"
  ).all()).results||[];
  const ms=s=>Date.parse(String(s||'').replace(' ','T')+'Z');
  return {families:rows.map(x=>({...x,healthy:x.status==='ok'&&
     Number.isFinite(ms(x.last_attempt_at))&&(now-ms(x.last_attempt_at))<10*60000})),
   active:rows.length===4&&rows.every(x=>x.status==='ok'&&Number.isFinite(ms(x.last_attempt_at))&&(now-ms(x.last_attempt_at))<10*60000)};
 }catch{return {families:[],active:false,unavailable:true}}
}
