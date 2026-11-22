import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {queueExpiryNotice,processExpiryNotices,expiryNoticeText} from '../expiry-notice-outbox.mjs';

function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 sqlite.exec(`
  CREATE TABLE bot_settings(setting_key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE cine_classic_deliveries(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER NOT NULL,status TEXT NOT NULL,
   delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE cine_delivery_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,planned_items INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE cine_delivery_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT);
  CREATE TABLE cine_series_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,planned_items INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE cine_series_job_items(job_id INTEGER,ordinal INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT);
  CREATE TABLE cine_franchise_jobs(id INTEGER PRIMARY KEY,telegram_chat_id INTEGER,status TEXT,planned_items INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE cine_franchise_job_items(job_id INTEGER,part INTEGER,state TEXT,delivered_message_id INTEGER,sent_at TEXT,delete_after TEXT);
 `);
 const DB={prepare(sql){let args=[];return{
  bind(...values){args=values;return this},
  async run(){const x=sqlite.prepare(sql).run(...args);return {meta:{changes:x.changes}}},
  async first(){return sqlite.prepare(sql).get(...args)||null},
  async all(){return {results:sqlite.prepare(sql).all(...args)}}
 }}};
 return {sqlite,env:{DB,TELEGRAM_TOKEN:'123456789:test_secret'}};
}
test('one saved classic copy creates only one post-video notice even on repeated Cron',async()=>{
 const {sqlite,env}=fixture(),old=globalThis.fetch,calls=[];
 sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status,delivered_message_id,sent_at,delete_after) VALUES(3,789,'sent',100,'2026-11-22 07:00:00','2026-11-22 19:00:00')");
 globalThis.fetch=async(url,options)=>{calls.push({method:String(url).split('/').at(-1),body:JSON.parse(options.body)});return Response.json({ok:true,result:{message_id:102}})};
 try{
  assert.equal(await queueExpiryNotice(env,'classics',3),true);
  assert.equal(await queueExpiryNotice(env,'classics',3),false);
  assert.equal((await processExpiryNotices(env,{family:'classics',jobId:3})).sent,1);
  assert.equal((await processExpiryNotices(env,{family:'classics',jobId:3})).sent,0);
  assert.equal(calls.length,1);
  assert.equal(calls[0].method,'sendMessage');
  assert.equal(calls[0].body.chat_id,789);
  assert.match(calls[0].body.text,/Suppression prévue : 22\/11\/2026 à 19:00/);
  assert.equal(sqlite.prepare("SELECT state,telegram_message_id FROM cine_expiry_notice_outbox WHERE family='classics' AND job_id=3").get().state,'sent');
 }finally{globalThis.fetch=old;sqlite.close()}
});
test('a partially delivered season never announces expiration before all episodes',async()=>{
 const {sqlite,env}=fixture();
 try{
  sqlite.exec("INSERT INTO cine_series_jobs(id,telegram_chat_id,status,planned_items) VALUES(8,789,'complete',2)");
  sqlite.exec("INSERT INTO cine_series_job_items VALUES(8,1,'sent',100,'2026-11-22 07:00:00','2026-11-22 19:00:00')");
  sqlite.exec("INSERT INTO cine_series_job_items VALUES(8,2,'queued',NULL,NULL,NULL)");
  assert.equal(await queueExpiryNotice(env,'series',8),false);
  assert.equal(sqlite.prepare("SELECT COUNT(*) AS n FROM cine_expiry_notice_outbox").get().n,0);
 }finally{sqlite.close()}
});
test('a definite Telegram rate limit defers the notice instead of blindly resending',async()=>{
 const {sqlite,env}=fixture(),old=globalThis.fetch,calls=[];
 sqlite.exec("INSERT INTO cine_classic_deliveries(id,telegram_chat_id,status,delivered_message_id,sent_at,delete_after) VALUES(5,789,'sent',100,'2026-11-22 07:00:00','2026-11-22 19:00:00')");
 globalThis.fetch=async(url,opts)=>{calls.push(String(url).split('/').at(-1));return Response.json({ok:false,error_code:429,parameters:{retry_after:10}},{status:429})};
 try{
  assert.equal(await queueExpiryNotice(env,'classics',5),true);
  const first=await processExpiryNotices(env,{family:'classics',jobId:5});
  assert.equal(first.deferred,1);
  assert.equal(sqlite.prepare("SELECT state FROM cine_expiry_notice_outbox WHERE job_id=5").get().state,'queued');
  assert.equal((await processExpiryNotices(env,{family:'classics',jobId:5})).sent,0);
  assert.deepEqual(calls,['sendMessage']);
 }finally{globalThis.fetch=old;sqlite.close()}
});
