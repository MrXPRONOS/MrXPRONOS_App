import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {runCopyExpirySweep,cleanupHealthOverview} from '../cinex-cleanup-coordinator.mjs';
import {ADMIN_OPS_JS} from '../admin-ops-ui.mjs';

function fixture({due=true,recipient=321}={}){
 const db=new DatabaseSync(':memory:');
 db.exec(`
 CREATE TABLE cine_delivery_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER);
 CREATE TABLE cine_delivery_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_lock_until TEXT,delete_attempts INTEGER DEFAULT 0,delete_last_error TEXT,deleted_at TEXT);
 CREATE TABLE cine_delivery_cleanup_runs(claimed INTEGER,deleted INTEGER,already_gone INTEGER,retries INTEGER,failed INTEGER,manual_review INTEGER,run_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE cine_series_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER);
 CREATE TABLE cine_series_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_lock_until TEXT,delete_attempts INTEGER DEFAULT 0,delete_last_error TEXT);
 CREATE TABLE cine_classic_deliveries(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_lock_until TEXT,delete_attempts INTEGER DEFAULT 0,delete_last_error TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE cine_franchise_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER);
 CREATE TABLE cine_franchise_job_items(job_id INTEGER,part INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_lock_until TEXT,delete_attempts INTEGER DEFAULT 0,delete_last_error TEXT);
 `);
 const since=due?"datetime('now','-25 hours')":"datetime('now','-23 hours')";
 const ttl=due?"datetime('now','-1 hour')":"datetime('now','+1 hour')";
 db.exec(`
 INSERT INTO cine_delivery_jobs VALUES(1,${recipient});
 INSERT INTO cine_delivery_job_items(job_id,ordinal,state,delivered_message_id,sent_at,delete_after,delete_retry_at) VALUES(1,1,'sent',100,${since},${ttl},${ttl});
 INSERT INTO cine_series_jobs VALUES(2,${recipient});
 INSERT INTO cine_series_job_items(job_id,ordinal,state,delivered_message_id,sent_at,delete_after,delete_retry_at) VALUES(2,1,'sent',101,${since},${ttl},${ttl});
 INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status,delivered_message_id,sent_at,delete_after,delete_retry_at) VALUES(3,${recipient},'sent',102,${since},${ttl},${ttl});
 INSERT INTO cine_franchise_jobs VALUES(4,${recipient});
 INSERT INTO cine_franchise_job_items(job_id,part,state,delivered_message_id,sent_at,delete_after,delete_retry_at) VALUES(4,1,'sent',103,${since},${ttl},${ttl});
 `);
 const DB={prepare(sql){let args=[];return{
  bind(...x){args=x;return this},
  async first(){return db.prepare(sql).get(...args)||null},
  async all(){return {results:db.prepare(sql).all(...args)}},
  async run(){const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes||0)}}},
 }}};
 return {db,env:{DB,TELEGRAM_TOKEN:'test:bot-token'}};
}

test('T03: four private family copies are actually deleted through Bot API and never twice',async()=>{
 const {db,env}=fixture(),old=globalThis.fetch;
 const calls=[];
 globalThis.fetch=async(url,opts)=>{calls.push({method:String(url).split('/').at(-1),body:JSON.parse(opts.body)});
  return Response.json({ok:true,result:true});};
 try{
  const first=await runCopyExpirySweep(env);
  assert.equal(first.checked,4);
  assert.equal(first.failed,0);
  assert.equal(first.deleted,4);
  assert.equal(first.overdue,0);
  assert.deepEqual(calls.map(x=>x.body.message_id).sort((a,b)=>a-b),[100,101,102,103]);
  assert.ok(calls.every(x=>x.method==='deleteMessage'&&x.body.chat_id===321));
  assert.equal(db.prepare("SELECT delete_state FROM cine_delivery_job_items").get().delete_state,'deleted');
  assert.equal(db.prepare("SELECT delete_state FROM cine_series_job_items").get().delete_state,'deleted');
  assert.equal(db.prepare("SELECT status FROM cine_classic_deliveries").get().status,'deleted');
  assert.equal(db.prepare("SELECT delete_state FROM cine_franchise_job_items").get().delete_state,'deleted');
  const again=await runCopyExpirySweep(env);
  assert.equal(again.deleted,0);
  assert.equal(calls.length,4);
  assert.equal((await cleanupHealthOverview(env)).active,true);
  const health=db.prepare("SELECT COUNT(*) AS n FROM cine_cleanup_health WHERE status='ok'").get();
  assert.equal(health.n,4);
 }finally{globalThis.fetch=old;db.close()}
});

test('T03: no early deletion, even if an incorrect earlier deadline was stored',async()=>{
 const {db,env}=fixture({due:false}),old=globalThis.fetch;let calls=0;
 globalThis.fetch=async()=>{calls++;return Response.json({ok:true,result:true})};
 try{
  const result=await runCopyExpirySweep(env);
  assert.equal(result.deleted,0);
  assert.equal(calls,0);
  assert.equal(result.failed,0);
 }finally{globalThis.fetch=old;db.close()}
});

test('T03: a lost delete response is retried; success is not invented',async()=>{
 const {db,env}=fixture(),old=globalThis.fetch;
 globalThis.fetch=async()=>{throw Error('Synthetic network failure')};
 try{
  const result=await runCopyExpirySweep(env);
  assert.equal(result.deleted,0);
  assert.equal(result.failed,0);
  const states=[
   db.prepare("SELECT delete_state FROM cine_delivery_job_items").get().delete_state,
   db.prepare("SELECT delete_state FROM cine_series_job_items").get().delete_state,
   db.prepare("SELECT delete_state FROM cine_classic_deliveries").get().delete_state,
   db.prepare("SELECT delete_state FROM cine_franchise_job_items").get().delete_state
  ];
  assert.deepEqual(states,['retry','retry','retry','retry']);
 }finally{globalThis.fetch=old;db.close()}
});

test('T03: Telegram already-absent copies are terminal, not double-deleted',async()=>{
 const {db,env}=fixture(),old=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({ok:false,error_code:400,description:'Bad Request: message to delete not found'}, {status:400});
 try{
  const result=await runCopyExpirySweep(env);
  assert.equal(result.deleted,0);
  assert.equal(result.already_gone,4);
  assert.equal(db.prepare("SELECT delete_state FROM cine_series_job_items").get().delete_state,'already_gone');
  assert.equal(db.prepare("SELECT delete_state FROM cine_franchise_job_items").get().delete_state,'already_gone');
 }finally{globalThis.fetch=old;db.close()}
});

test('T03: one failing catalogue does not stop the other three cleanup families',async()=>{
 const {db,env}=fixture({due:false});
 try{
  const runners={
   libraries:async()=>{throw TypeError('sensitive private detail must not be stored')},
   series:async()=>({deleted:1,retry:0}),
   classics:async()=>({deleted:2,retries:1}),
   franchise:async()=>({deleted:3,retried:1}),
  };
  const result=await runCopyExpirySweep(env,{runners});
  assert.equal(result.failed,1);
  assert.equal(result.deleted,6);
  const failing=db.prepare("SELECT status,last_error FROM cine_cleanup_health WHERE family='libraries'").get();
  assert.equal(failing.status,'error');
  assert.equal(failing.last_error,'TypeError');
  assert.equal((await cleanupHealthOverview(env)).active,false);
  assert.ok(!JSON.stringify(result).includes('sensitive private detail'));
 }finally{db.close()}
});

test('T03: historical sent receipts without expiry are backfilled from actual sent_at',async()=>{
 const {db,env}=fixture({due:false});
 try{
  for(const table of ['cine_delivery_job_items','cine_series_job_items','cine_classic_deliveries','cine_franchise_job_items'])db.exec('UPDATE '+table+' SET delete_after=NULL,delete_retry_at=NULL');
  const runners={libraries:async()=>({}),series:async()=>({}),classics:async()=>({}),franchise:async()=>({})};
  const result=await runCopyExpirySweep(env,{runners});
  assert.equal(result.families.reduce((x,y)=>x+y.backfilled,0),4);
  for(const table of ['cine_delivery_job_items','cine_series_job_items','cine_classic_deliveries','cine_franchise_job_items']){
   const row=db.prepare('SELECT sent_at,delete_after FROM '+table).get();
   const delta=Date.parse(row.delete_after.replace(' ','T')+'Z')-Date.parse(row.sent_at.replace(' ','T')+'Z');
   assert.equal(delta,24*3600000);
  }
 }finally{db.close()}
});

test('T03: negative channel recipient is never sent to Telegram for deletion',async()=>{
 const {db,env}=fixture({recipient:-1004455497484}),old=globalThis.fetch;let sends=0;
 globalThis.fetch=async()=>{sends++;throw Error('should not send')};
 try{
  const result=await runCopyExpirySweep(env);
  assert.equal(sends,0);
  assert.equal(result.deleted,0);
  assert.equal(result.families.reduce((sum,x)=>sum+x.manual_review,0),4);
 }finally{globalThis.fetch=old;db.close()}
});

test('T03: owner cleanup dashboard script is syntactically valid',()=>{
 assert.doesNotThrow(()=>new Function(ADMIN_OPS_JS));
 assert.match(ADMIN_OPS_JS,/Suppression des copies privées après 24 h/);
});
