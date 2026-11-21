import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {
 ensurePrivateStockTables,queueKnownStockSources,processPrivateStockQueue,
 sourceFromPrivateStock,privateStockOverview,
} from '../private-stock.mjs';
import {ADMIN_OPS_JS} from '../admin-ops-ui.mjs';

const source='-1001234567890',stock='-1009876543210';
function fixture(){
 const db=new DatabaseSync(':memory:');
 db.exec(`
 CREATE TABLE cine_classic_links(source_chat_id TEXT,source_message_id INTEGER,status TEXT);
 CREATE TABLE cine_franchise_catalog(slug TEXT,rights_attested INTEGER,status TEXT);
 CREATE TABLE cine_franchise_films(slug TEXT,source_chat_id TEXT,source_message_id INTEGER);
 CREATE TABLE cine_delivery_libraries(category TEXT,private_chat_id TEXT,rights_attested INTEGER,bot_access TEXT);
 CREATE TABLE cine_delivery_titles(category TEXT,title_key TEXT,content_kind TEXT,approval TEXT,rights_attested INTEGER);
 CREATE TABLE cine_delivery_media(category TEXT,title_key TEXT,source_message_id INTEGER,media_kind TEXT,availability TEXT);
 `);
 const DB={prepare(sql){let args=[];return{
  bind(...values){args=values;return this},
  async run(){let r=db.prepare(sql).run(...args);return {meta:{changes:r.changes||0}}},
  async first(){return db.prepare(sql).get(...args)||null},
  async all(){return {results:db.prepare(sql).all(...args)}},
 }}};
 return {db,env:{DB,TELEGRAM_TOKEN:'test:stock-bot'}};
}
async function prepare(env,db){
 await ensurePrivateStockTables(env);
 db.prepare("INSERT INTO cine_private_stock_config(singleton,stock_chat_id,owner_id,radar_bot_id,ready) VALUES(1,?,?,?,1)").run(stock,123,987);
 db.prepare("INSERT INTO cine_classic_links(source_chat_id,source_message_id,status) VALUES(?,11,'published')").run(source);
}
test('Private channel stock remains inactive without owner/bot verified config',async()=>{
 const {env,db}=fixture();
 try{
  assert.deepEqual(await privateStockOverview(env),{ready:false,stored:0,queued:0,review:0});
  assert.equal((await queueKnownStockSources(env)).disabled,true);
  assert.equal((await processPrivateStockQueue(env)).disabled,true);
 }finally{db.close()}
});
test('Only pre-approved movie source references are queued; no bytes',async()=>{
 const {env,db}=fixture();
 try{
  await prepare(env,db);
  db.prepare("INSERT INTO cine_classic_links VALUES(?,12,'pending')").run(source);
  db.prepare("INSERT INTO cine_franchise_catalog VALUES('ff',1,'published')").run();
  db.prepare("INSERT INTO cine_franchise_films VALUES('ff',?,21)").run(source);
  db.prepare("INSERT INTO cine_delivery_libraries VALUES('action',?,1,'verified')").run(source);
  db.prepare("INSERT INTO cine_delivery_titles VALUES('action','t','film','approved',1)").run();
  db.prepare("INSERT INTO cine_delivery_media VALUES('action','t',31,'video','approved')").run();
  db.prepare("INSERT INTO cine_delivery_media VALUES('action','t',32,'video','pending_review')").run();
  const first=await queueKnownStockSources(env);
  assert.equal(first.queued,3);
  assert.equal((await queueKnownStockSources(env)).queued,0);
  const rows=db.prepare('SELECT source_message_id FROM cine_private_stock_items ORDER BY source_message_id').all();
  assert.deepEqual(rows.map(x=>x.source_message_id),[11,21,31]);
  assert.equal(db.prepare("SELECT stock_chat_id FROM cine_private_stock_config").get().stock_chat_id,stock);
 }finally{db.close()}
});
test('Telegram copyMessage is issued once, never uploaded, and future delivery uses confirmed stock reference',async()=>{
 const {env,db}=fixture(),orig=globalThis.fetch;
 const requests=[];
 try{
  await prepare(env,db);
  await queueKnownStockSources(env);
  globalThis.fetch=async(url,args)=>{
   requests.push({name:String(url).split('/').at(-1),data:JSON.parse(args.body)});
   return Response.json({ok:true,result:{message_id:500}});
  };
  const result=await processPrivateStockQueue(env);
  assert.equal(result.stored,1);
  assert.deepEqual(requests.map(x=>x.name),['copyMessage']);
  assert.equal(requests[0].data.from_chat_id,source);
  assert.equal(requests[0].data.chat_id,stock);
  assert.equal(requests[0].data.message_id,11);
  assert.equal((await privateStockOverview(env)).stored,1);
  const chosen=await sourceFromPrivateStock(env,source,11);
  assert.deepEqual(chosen,{chatId:stock,messageId:500,fromStock:true});
  await processPrivateStockQueue(env);
  assert.equal(requests.length,1,'must never duplicate a proven stored media');
  assert.deepEqual(await sourceFromPrivateStock(env,source,999),{chatId:source,messageId:999,fromStock:false});
 }finally{globalThis.fetch=orig;db.close()}
});
test('Ambiguous Telegram response quarantines copied media, never blindly retries',async()=>{
 const {env,db}=fixture(),orig=globalThis.fetch;let hits=0;
 try{
  await prepare(env,db);
  await queueKnownStockSources(env);
  globalThis.fetch=async()=>{hits++;throw Error('response lost')};
  const result=await processPrivateStockQueue(env);
  assert.equal(result.review,1);
  assert.equal(db.prepare('SELECT state FROM cine_private_stock_items').get().state,'needs_review');
  await processPrivateStockQueue(env);
  assert.equal(hits,1);
  assert.equal((await sourceFromPrivateStock(env,source,11)).fromStock,false);
 }finally{globalThis.fetch=orig;db.close()}
});
test('Removed source rights stop a scheduled copy before sending',async()=>{
 const {env,db}=fixture(),orig=globalThis.fetch;let hits=0;
 try{
  await prepare(env,db);
  await queueKnownStockSources(env);
  db.prepare("UPDATE cine_classic_links SET status='disabled'").run();
  globalThis.fetch=async()=>{hits++;throw Error('must not be sent')};
  const result=await processPrivateStockQueue(env);
  assert.equal(result.review,1);
  assert.equal(hits,0);
  assert.equal(db.prepare('SELECT state FROM cine_private_stock_items').get().state,'disabled');
 }finally{globalThis.fetch=orig;db.close()}
});
test('No subscriber IDs, media bytes, or public private-channel invitations in owner dashboard',async()=>{
 assert.doesNotThrow(()=>new Function(ADMIN_OPS_JS));
 const file=readFileSync(new URL('../private-stock.mjs',import.meta.url),'utf8');
 assert.ok(!/getFile|downloadFile|sendVideo|sendDocument|upload\(/.test(file));
 assert.match(file,/stock_message_id/);
 assert.match(file,/rights_attested/);
 assert.match(file,/copyMessage/);
});
