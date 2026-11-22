import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {listDeliveryRecovery,resumeProvenQueued,attestExistingCopy} from '../cinex-delivery-recovery.mjs';
import {ADMIN_RECOVERY_JS,ADMIN_RECOVERY_HTML} from '../admin-recovery-ui.mjs';

function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 // Minimal D1-compatible schema for all four independent delivery families.
 sqlite.exec(`
 CREATE TABLE cine_delivery_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,delivered_items INTEGER DEFAULT 0,lock_until TEXT,not_before TEXT);
 CREATE TABLE cine_delivery_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_attempts INTEGER DEFAULT 0);
 CREATE TABLE cine_series_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,delivered_items INTEGER DEFAULT 0,lock_until TEXT,not_before TEXT);
 CREATE TABLE cine_series_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_attempts INTEGER DEFAULT 0);
 CREATE TABLE cine_franchise_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,delivered_items INTEGER DEFAULT 0,lock_until TEXT,not_before TEXT);
 CREATE TABLE cine_franchise_job_items(job_id INTEGER,part INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',delete_attempts INTEGER DEFAULT 0);
 CREATE TABLE cine_classic_deliveries(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,delete_retry_at TEXT,delete_state TEXT DEFAULT 'pending',lock_until TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE cine_owner_vault(status TEXT);
 `);
 const DB={prepare(sql){
  let args=[];
  return {bind(...v){args=v;return this},
   async first(){return sqlite.prepare(sql).get(...args)||null},
   async all(){return {results:sqlite.prepare(sql).all(...args)}},
   async run(){const r=sqlite.prepare(sql).run(...args);return {meta:{changes:r.changes||0}}},
  };
 }};
 return {sqlite,env:{DB}};
}
const now=Date.parse('2026-11-20T20:00:00Z');
const sent_at='2026-11-20T19:30:00Z';

test('T02: read-only overview strips Telegram chats, tokens and media references',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_delivery_jobs(id,telegram_chat_id,status) VALUES(1,123456,'needs_review')");
  sqlite.exec("INSERT INTO cine_delivery_job_items(job_id,ordinal,state) VALUES(1,1,'needs_review'),(1,2,'queued')");
  sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status) VALUES(2,987654,'needs_review')");
  sqlite.exec("INSERT INTO cine_owner_vault(status) VALUES('needs_review')");
  const report=await listDeliveryRecovery(env);
  assert.equal(report.cases.length,2);
  assert.equal(report.cases[0].diagnosis,'delivery_result_uncertain');
  assert.equal(report.cases[0].resume_safe,false);
  assert.equal(report.owner_archive_review,1);
  assert.ok(!JSON.stringify(report).includes('123456'));
  assert.ok(!JSON.stringify(report).includes('987654'));
 }finally{sqlite.close()}
});

test('T02: safe recovery requeues only proven queued copies and can close all-sent jobs',async()=>{
 const {sqlite,env}=fixture(),old=globalThis.fetch;
 globalThis.fetch=async()=>{throw Error('Telegram must not be touched by recovery')};
 try{
  sqlite.exec("INSERT INTO cine_series_jobs(id,telegram_chat_id,status,delivered_items) VALUES(12,100,'needs_review',1)");
  sqlite.exec("INSERT INTO cine_series_job_items(job_id,ordinal,state,delivered_message_id,sent_at) VALUES(12,1,'sent',900,'2026-11-20 19:00:00'),(12,2,'queued',NULL,NULL)");
  const result=await resumeProvenQueued(env,{family:'series',job_id:12},888);
  assert.equal(result.ok,true);
  assert.equal(result.copy_sent,false);
  assert.equal(sqlite.prepare('SELECT status,delivered_items FROM cine_series_jobs WHERE id=12').get().status,'queued');
  assert.equal((await resumeProvenQueued(env,{family:'series',job_id:12},888)).status,409);
  sqlite.exec("INSERT INTO cine_franchise_jobs(id,telegram_chat_id,status) VALUES(15,101,'needs_review')");
  sqlite.exec("INSERT INTO cine_franchise_job_items(job_id,part,state,delivered_message_id,sent_at) VALUES(15,1,'sent',901,'2026-11-20 19:00:00')");
  assert.equal((await resumeProvenQueued(env,{family:'franchise',job_id:15},888)).job_status,'complete');
  assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM cine_admin_audit').get().n,2);
 }finally{globalThis.fetch=old;sqlite.close()}
});

test('T02: uncertain, in-flight, invalid receipts and classic cases never requeue',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_delivery_jobs(id,status) VALUES(1,'needs_review'),(2,'needs_review'),(3,'needs_review')");
  sqlite.exec("INSERT INTO cine_delivery_job_items(job_id,ordinal,state) VALUES(1,1,'needs_review'),(2,1,'sending')");
  sqlite.exec("INSERT INTO cine_delivery_job_items(job_id,ordinal,state,delivered_message_id) VALUES(3,1,'queued',123)");
  for(const id of [1,2,3]){
   const out=await resumeProvenQueued(env,{family:'libraries',job_id:id},888);
   assert.equal(out.status,409);
   assert.equal(sqlite.prepare('SELECT status FROM cine_delivery_jobs WHERE id=?').get(id).status,'needs_review');
  }
  assert.equal((await resumeProvenQueued(env,{family:'classics',job_id:1},888)).status,400);
  assert.equal((await resumeProvenQueued(env,{family:'series',job_id:-1},888)).status,400);
 }finally{sqlite.close()}
});

test('T02: owner attests an existing copy once, preserves 24h deletion and unblocks safe remainder',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_delivery_jobs(id,telegram_chat_id,status) VALUES(21,123,'needs_review')");
  sqlite.exec("INSERT INTO cine_delivery_job_items(job_id,ordinal,state) VALUES(21,1,'needs_review'),(21,2,'queued')");
  const values={family:'libraries',job_id:21,item:1,message_id:999,sent_at,confirmed_existing_copy:true};
  const first=await attestExistingCopy(env,values,987,{now});
  assert.equal(first.ok,true);
  const copy=sqlite.prepare('SELECT * FROM cine_delivery_job_items WHERE job_id=21 AND ordinal=1').get();
  assert.equal(copy.state,'sent');
  assert.equal(copy.delivered_message_id,999);
  assert.equal(copy.sent_at,'2026-11-20 19:30:00');
  assert.equal(copy.delete_after,'2026-11-21 19:30:00');
  assert.equal(sqlite.prepare('SELECT delivered_items,status FROM cine_delivery_jobs WHERE id=21').get().delivered_items,1);
  assert.equal(sqlite.prepare('SELECT status FROM cine_delivery_jobs WHERE id=21').get().status,'queued');
  const again=await attestExistingCopy(env,values,987,{now});
  assert.equal(again.ok,false);
  assert.equal(again.status,409);
  assert.equal(sqlite.prepare('SELECT delivered_items FROM cine_delivery_jobs WHERE id=21').get().delivered_items,1);
  assert.equal(sqlite.prepare('SELECT COUNT(*) n FROM cine_admin_audit').get().n,1);
 }finally{sqlite.close()}
});

test('T02: classic uncertain delivery can only be marked sent with explicit evidence',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status) VALUES(25,333,'needs_review')");
  const data={family:'classics',job_id:25,message_id:1100,sent_at,confirmed_existing_copy:true};
  assert.equal((await attestExistingCopy(env,{...data,confirmed_existing_copy:false},987,{now})).status,400);
  assert.equal((await attestExistingCopy(env,{...data,sent_at:'2026-11-17T00:00:00Z'},987,{now})).status,400);
  assert.equal((await attestExistingCopy(env,data,987,{now})).ok,true);
  assert.equal(sqlite.prepare('SELECT status FROM cine_classic_deliveries WHERE id=25').get().status,'sent');
  assert.equal(sqlite.prepare('SELECT delete_after FROM cine_classic_deliveries WHERE id=25').get().delete_after,'2026-11-21 19:30:00');
  assert.equal((await attestExistingCopy(env,data,987,{now})).status,409);
 }finally{sqlite.close()}
});

test('T02: same recipient cannot attest a receipt that already belongs to another family',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_series_jobs(id,telegram_chat_id,status) VALUES(81,123,'needs_review')");
  sqlite.exec("INSERT INTO cine_series_job_items(job_id,ordinal,state) VALUES(81,1,'needs_review')");
  sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status,delivered_message_id) VALUES(82,123,'sent',555)");
  const proof={family:'series',job_id:81,item:1,message_id:555,sent_at,confirmed_existing_copy:true};
  const out=await attestExistingCopy(env,proof,987,{now});
  assert.equal(out.status,409);
  assert.equal(out.code,'duplicate_or_invalid_telegram_receipt');
  assert.equal(sqlite.prepare('SELECT state FROM cine_series_job_items WHERE job_id=81').get().state,'needs_review');
  sqlite.exec("UPDATE cine_series_jobs SET telegram_chat_id=124 WHERE id=81");
  assert.equal((await attestExistingCopy(env,proof,987,{now})).ok,true);
 }finally{sqlite.close()}
});

test('T02: classic cannot steal a Telegram message already recorded as a series delivery',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status) VALUES(83,123,'needs_review')");
  sqlite.exec("INSERT INTO cine_series_jobs(id,telegram_chat_id,status) VALUES(84,123,'complete')");
  sqlite.exec("INSERT INTO cine_series_job_items(job_id,ordinal,state,delivered_message_id,sent_at) VALUES(84,1,'sent',777,'2026-11-20 19:00:00')");
  const out=await attestExistingCopy(env,{family:'classics',job_id:83,message_id:777,sent_at,confirmed_existing_copy:true},987,{now});
  assert.equal(out.status,409);
  assert.equal(sqlite.prepare('SELECT status FROM cine_classic_deliveries WHERE id=83').get().status,'needs_review');
 }finally{sqlite.close()}
});

test('T02: source files never add Telegram sends or bypass the admin mutation session',()=>{
 const file=readFileSync(new URL('../cinex-delivery-recovery.mjs',import.meta.url),'utf8');
 const api=readFileSync(new URL('../admin-v2.mjs',import.meta.url),'utf8');
 const ui=readFileSync(new URL('../admin-recovery-ui.mjs',import.meta.url),'utf8');
 assert.ok(!/copyMessage|forwardMessage|sendMessage|sendPhoto|\/bot['"]/i.test(file.replaceAll('copyMessage was NOT sent','')));
 assert.match(api,/freshAdminMutationSession\(request\)/);
 assert.match(api,/path==='\/api\/admin\/cinex\/recovery'/);
 assert.match(ui,/confirmed_existing_copy/);
 assert.doesNotThrow(()=>new Function(ADMIN_RECOVERY_JS),'Embedded owner controls must parse as valid JS');
 assert.match(ADMIN_RECOVERY_HTML,/ad-cinex-recover-refresh/);
});

test('T02: post-cutover receipts reconciled by owner expire 12h after the actual Telegram send',async()=>{
 const {sqlite,env}=fixture();
 const recent='2026-11-22T05:30:00Z',seenAt=Date.parse('2026-11-22T06:00:00Z');
 try{
  sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status) VALUES(310,500,'needs_review')");
  const classic=await attestExistingCopy(env,{
   family:'classics',job_id:310,message_id:711,sent_at:recent,confirmed_existing_copy:true
  },987,{now:seenAt});
  assert.equal(classic.ok,true);
  assert.equal(sqlite.prepare('SELECT delete_after FROM cine_classic_deliveries WHERE id=310').get().delete_after,'2026-11-22 17:30:00');
  sqlite.exec("INSERT INTO cine_delivery_jobs(id,telegram_chat_id,status) VALUES(311,501,'needs_review')");
  sqlite.exec("INSERT INTO cine_delivery_job_items(job_id,ordinal,state) VALUES(311,1,'needs_review')");
  const library=await attestExistingCopy(env,{
   family:'libraries',job_id:311,item:1,message_id:712,sent_at:recent,confirmed_existing_copy:true
  },987,{now:seenAt});
  assert.equal(library.ok,true);
  assert.equal(sqlite.prepare('SELECT delete_after FROM cine_delivery_job_items WHERE job_id=311').get().delete_after,'2026-11-22 17:30:00');
 }finally{sqlite.close()}
});
