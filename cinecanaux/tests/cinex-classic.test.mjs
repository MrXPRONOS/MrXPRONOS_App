import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {handleClassicDeliveryStart,processClassicDeliveryQueue,cleanupClassicDeliveries} from '../cinex-classic.mjs';

const TOKEN='ABCDEFGHIJKLMNOPQRSTUVWX';
const now=Date.now();
function fixture(){
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../migrations/018_cinex_classic_delivery.sql',import.meta.url),'utf8'));
 db.exec("CREATE TABLE cine_series_config(setting_key TEXT PRIMARY KEY,setting_value TEXT NOT NULL)");
 db.exec(readFileSync(new URL('../migrations/020_cinex_owner_chat_vault.sql',import.meta.url),'utf8'));
 db.exec("CREATE TABLE admin_users(user_id INTEGER PRIMARY KEY,role TEXT NOT NULL)");
 db.exec("CREATE TABLE bot_settings(setting_key TEXT PRIMARY KEY,value TEXT)");
 db.exec("INSERT INTO bot_settings VALUES('cine_delivery_enabled','1')");
 db.prepare("INSERT INTO cine_classic_links(token,source_chat_id,source_message_id,title,public_handle,status) VALUES(?,?,?,?,?,'published')")
  .run(TOKEN,'-1004392607284',238,'Film autorisé','@CineXFilms_vf');
 const DB={prepare(sql){let args=[];
  return {bind(...p){args=p;return this},async first(){return db.prepare(sql).get(...args)||null},
   async all(){return {results:db.prepare(sql).all(...args)}},
   async run(){let r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}}}};
 }};
 return {db,env:{DB,TELEGRAM_TOKEN:'bot:test'}};
}
const request=(chat=123,update_id=42)=>({update_id,message:{text:'/start d_'+TOKEN,chat:{type:'private',id:chat},from:{id:chat}}});
test('feature flag false blocks classic links before any Telegram call',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;let calls=0;
 globalThis.fetch=async()=>{calls++;return Response.json({ok:true,result:true})};
 try{
  db.exec("UPDATE bot_settings SET value='0'");
  const r=await handleClassicDeliveryStart(env,request());
  assert.equal(r.handled,false);
  assert.equal((await processClassicDeliveryQueue(env)).disabled,true);
  assert.equal(calls,0);
 }finally{globalThis.fetch=old;db.close()}
});
test('classic deep link queues exactly one private copy and is idempotent',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const methods=[];
 globalThis.fetch=async url=>{methods.push(String(url).split('/').at(-1));return Response.json({ok:true,result:{message_id:19}})};
 try{
  const result=await handleClassicDeliveryStart(env,request());
  assert.equal(result.accepted,true);
  assert.equal((await handleClassicDeliveryStart(env,request())).duplicate,true);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM cine_classic_deliveries").get().n,1);
  assert.deepEqual(methods,[]);
 }finally{globalThis.fetch=old;db.close()}
});
test('two separate Telegram taps for the same film never queue duplicate copies',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const methods=[];
 globalThis.fetch=async url=>{methods.push(String(url).split('/').at(-1));return Response.json({ok:true,result:{message_id:99}})};
 try{
  assert.equal((await handleClassicDeliveryStart(env,request(321,110))).accepted,true);
  const repeated=await handleClassicDeliveryStart(env,request(321,111));
  assert.equal(repeated.duplicate,true);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM cine_classic_deliveries").get().n,1);
  assert.deepEqual(methods,[]);
 }finally{globalThis.fetch=old;db.close()}
});
test('atomic insert stops duplicate classic taps even when both SELECT prechecks miss',async()=>{
 const {db,env}=fixture(),oldFetch=globalThis.fetch;
 const prepare=env.DB.prepare.bind(env.DB),calls=[];
 env.DB.prepare=sql=>{
  const stmt=prepare(sql);
  if(sql.startsWith('SELECT id FROM cine_classic_deliveries WHERE telegram_chat_id='))stmt.first=async()=>null;
  return stmt;
 };
 globalThis.fetch=async url=>{calls.push(String(url).split('/').at(-1));return Response.json({ok:true,result:{message_id:55}})};
 try{
  assert.equal((await handleClassicDeliveryStart(env,request(321,120))).accepted,true);
  assert.equal((await handleClassicDeliveryStart(env,request(321,121))).duplicate,true);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM cine_classic_deliveries').get().n,1);
  assert.deepEqual(calls,[]);
 }finally{globalThis.fetch=oldFetch;db.close()}
});
test('queue copies only from a verified negative library id into a positive private chat',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const calls=[];
 globalThis.fetch=async(url,options)=>{calls.push({method:String(url).split('/').at(-1),body:JSON.parse(options.body)});return Response.json({ok:true,result:{message_id:66}})};
 try{
  await handleClassicDeliveryStart(env,request(321,43));
  db.exec('DELETE FROM cine_telegram_send_quota'); // Simulated later Cron tick.
  const report=await processClassicDeliveryQueue(env);
  assert.equal(report.processed,1);
  const record=db.prepare('SELECT status,delivered_message_id,delete_after FROM cine_classic_deliveries').get();
  assert.equal(record.status,'sent');assert.equal(record.delivered_message_id,66);assert.ok(record.delete_after);
  const copy=calls.find(x=>x.method==='copyMessage');
  assert.deepEqual({to:copy.body.chat_id,from:copy.body.from_chat_id,id:copy.body.message_id},
   {to:321,from:'-1004392607284',id:238});
  assert.equal((await processClassicDeliveryQueue(env)).processed,0);
 }finally{globalThis.fetch=old;db.close()}
});
test('24h cleanup deletes only the delivered private copy, never source or public video',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const calls=[];
 globalThis.fetch=async(url,options)=>{calls.push({method:String(url).split('/').at(-1),body:JSON.parse(options.body)});return Response.json({ok:true,result:true})};
 try{
  db.prepare("INSERT INTO cine_classic_deliveries(token,telegram_update_id,telegram_chat_id,status,delivered_message_id,sent_at,delete_after,delete_retry_at) VALUES(?,?,?,'sent',?,?,?,?)")
   .run(TOKEN,101,321,66,new Date(now-25*3600000).toISOString().replace('T',' ').slice(0,19),
   new Date(now-3600000).toISOString().replace('T',' ').slice(0,19),
   new Date(now-3600000).toISOString().replace('T',' ').slice(0,19));
  const result=await cleanupClassicDeliveries(env);
  assert.equal(result.deleted,1);
  assert.deepEqual(calls,[{method:'deleteMessage',body:{chat_id:321,message_id:66}}]);
  assert.equal(db.prepare("SELECT status FROM cine_classic_deliveries").get().status,'deleted');
 }finally{globalThis.fetch=old;db.close()}
});


test('classic film delivers from owner bot-chat mirror when stored',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const calls=[];
 globalThis.fetch=async(url,options)=>{calls.push({method:String(url).split('/').at(-1),body:JSON.parse(options.body)});return Response.json({ok:true,result:{message_id:79}})};
 try{
  db.prepare("INSERT INTO admin_users(user_id,role) VALUES(?,'owner')").run(500);
  db.prepare("INSERT INTO cine_owner_vault(source_chat_id,source_message_id,media_kind,owner_chat_id,owner_message_id,status) VALUES(?,?,?,?,?,'stored')")
    .run('-1004392607284',238,'video',500,902);
  await handleClassicDeliveryStart(env,request(321,404));
  db.exec('DELETE FROM cine_telegram_send_quota'); // Simulated later Cron tick.
  const report=await processClassicDeliveryQueue(env);
  assert.equal(report.processed,1);
  const copy=calls.find(x=>x.method==='copyMessage').body;
  assert.deepEqual({to:copy.chat_id,from:copy.from_chat_id,id:copy.message_id},{to:321,from:500,id:902});
 }finally{globalThis.fetch=old;db.close()}
});
