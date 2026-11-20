import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {broadcastAdminAPI,ensureBroadcastTables,launchScheduledBroadcasts} from '../broadcast.mjs';
import {ownerOperationsOverview} from '../admin-ops.mjs';
import {adminAPI} from '../admin-v2.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';

const root='https://cinecanaux.test';
function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){
  let values=[];
  return {bind(...params){values=params;return this},
   async first(){return sqlite.prepare(sql).get(...values)||null},
   async all(){return {results:sqlite.prepare(sql).all(...values)}},
   async run(){const result=sqlite.prepare(sql).run(...values);return {meta:{changes:Number(result.changes),last_row_id:Number(result.lastInsertRowid)}}}
  };
 }};
 const env={DB,TELEGRAM_TOKEN:'bot:test',TELEGRAM_WEBHOOK_SECRET:'secret'};
 return {env,sqlite};
}
const signed=async()=>{
 const enc=new TextEncoder();
 const hmac=async(k,v)=>{
  const key=await crypto.subtle.importKey('raw',typeof k==='string'?enc.encode(k):k,{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode(v)));
 };
 const user=JSON.stringify({id:900,username:'mr_xpronos'}),auth_date=String(Math.floor(Date.now()/1000));
 const sec=await hmac('WebAppData','bot:test');
 const hash=Array.from(await hmac(sec,'auth_date='+auth_date+'\nuser='+user),x=>x.toString(16).padStart(2,'0')).join('');
 return new URLSearchParams({user,auth_date,hash}).toString();
};
test('V1.3 scheduled announcements launch exactly once, preserve opt-in audience and allow cancellation',async()=>{
 const {env,sqlite}=fixture();
 try{
  await ensureBroadcastTables(env);
  sqlite.prepare("INSERT INTO cine_broadcast_jobs(id,owner_id,text_html,status) VALUES(1,900,'Bonjour','draft')").run();
  sqlite.prepare("INSERT INTO cine_broadcast_jobs(id,owner_id,text_html,status) VALUES(2,900,'A annuler','draft')").run();
  sqlite.prepare("INSERT INTO cine_broadcast_subscribers(chat_id,active,blocked) VALUES(111,1,0),(222,0,0)").run();
  const schedule=async(id,send_at)=>broadcastAdminAPI(env,new Request(root+'/api/admin/broadcasts/'+id+'/schedule',{
   method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({send_at})
  }),900);
  const future=new Date(Date.now()+5*60*1000).toISOString();
  assert.equal((await schedule(1,future)).status,200);
  assert.equal((await schedule(2,future)).status,200);
  const tooSoon=await schedule(2,new Date(Date.now()+5000).toISOString());
  assert.equal(tooSoon.status,400);
  assert.equal((await launchScheduledBroadcasts(env)).started,0,'Future job must not send now');
  const cancel=await broadcastAdminAPI(env,new Request(root+'/api/admin/broadcasts/2/cancel',{method:'POST',body:'{}'}),900);
  assert.equal(cancel.status,200);
  sqlite.prepare("UPDATE cine_broadcast_schedules SET send_at=datetime('now','-1 minute')").run();
  const result=await launchScheduledBroadcasts(env);
  assert.equal(result.started,1,'Only the due, non-cancelled job starts');
  const receipts=sqlite.prepare("SELECT chat_id FROM cine_broadcast_receipts WHERE job_id=1").all();
  assert.deepEqual(receipts.map(x=>x.chat_id),[111],'Opted-out users must never be added to receipts');
  assert.equal(sqlite.prepare("SELECT status FROM cine_broadcast_jobs WHERE id=1").get().status,'sending');
  assert.equal(sqlite.prepare("SELECT status FROM cine_broadcast_schedules WHERE job_id=1").get().status,'started');
  assert.equal(sqlite.prepare("SELECT status FROM cine_broadcast_schedules WHERE job_id=2").get().status,'cancelled');
  assert.equal((await launchScheduledBroadcasts(env)).started,0,'Repeated cron cannot queue duplicate sends');
  assert.equal(sqlite.prepare("SELECT count(*) n FROM cine_broadcast_receipts").get().n,1);
  assert.equal(sqlite.prepare("SELECT count(*) n FROM cine_admin_audit WHERE action='broadcast.auto_start'").get().n,1);
 }finally{sqlite.close()}
});
test('V1.3 operational journal is owner-only and contains no raw Telegram session',async()=>{
 const {env,sqlite}=fixture();
 try{
  sqlite.prepare("CREATE TABLE admin_users(user_id INTEGER PRIMARY KEY,role TEXT)").run();
  sqlite.prepare("INSERT INTO admin_users VALUES(900,'owner')").run();
  sqlite.prepare("CREATE TABLE radar_ops_status(job_name TEXT,status TEXT,last_attempt_at TEXT,last_success_at TEXT)").run();
  sqlite.prepare("INSERT INTO radar_ops_status VALUES('post_reconciliation','error',CURRENT_TIMESTAMP,NULL)").run();
  sqlite.prepare("CREATE TABLE automated_job_runs(id INTEGER,job_name TEXT,status TEXT,errors INTEGER,started_at TEXT)").run();
  sqlite.prepare("INSERT INTO automated_job_runs VALUES(1,'link_check','partial',2,CURRENT_TIMESTAMP)").run();
  sqlite.prepare("CREATE TABLE bot_webhook_status(id INTEGER PRIMARY KEY,status TEXT,updated_at TEXT)").run();
  sqlite.prepare("INSERT INTO bot_webhook_status VALUES(1,'ok',CURRENT_TIMESTAMP)").run();
  const forbidden=await adminAPI(env,new Request(root+'/api/admin/operations'));
  assert.equal(forbidden.status,403);
  const allowed=await adminAPI(env,new Request(root+'/api/admin/operations',{headers:{'X-Telegram-Init-Data':await signed()}}));
  assert.equal(allowed.status,200);
  const data=await allowed.json();
  assert.ok(Array.isArray(data.alerts)&&data.alerts.length>0);
  assert.ok(Array.isArray(data.actions));
  assert.ok(!JSON.stringify(data).includes('bot:test'));
  assert.ok(ADMIN_HTML.includes('id="ad-ops-panel"'));
  assert.ok(ADMIN_HTML.includes('id="broadcast-schedule-at"'));
  assert.ok(ADMIN_HTML.includes('id="broadcast-schedule"'));
 }finally{sqlite.close()}
});
