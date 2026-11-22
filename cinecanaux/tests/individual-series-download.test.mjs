import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {
 availableSeriesPlan,handleSeriesStart,processSeriesQueue,cleanupSeriesCopies,
} from '../individual-series.mjs';
import {processExpiryNotices} from '../expiry-notice-outbox.mjs';

const TOKEN='abcdefghijklmnopqrstuvwx';
const CHANNEL='-1001234567890';
function fixture(){
 const db=new DatabaseSync(':memory:');
 db.exec(readFileSync(new URL('../migrations/019_cinex_individual_series.sql',import.meta.url),'utf8'));
 db.exec(readFileSync(new URL('../migrations/020_cinex_owner_chat_vault.sql',import.meta.url),'utf8'));
 db.exec("CREATE TABLE admin_users(user_id INTEGER PRIMARY KEY,role TEXT NOT NULL)");
 db.exec("CREATE TABLE bot_settings(setting_key TEXT PRIMARY KEY,value TEXT NOT NULL)");
 db.prepare("INSERT INTO bot_settings(setting_key,value) VALUES(?,?)").run('cine_delivery_enabled','1');
 // The title explicitly mentions season 3 only, no claim about S1/S2 completeness.
 db.prepare("INSERT INTO cine_series_channels(chat_id,title,expected_seasons,publisher_access,radar_access,rights_attested) VALUES(?,?,3,'verified','verified',1)")
   .run(CHANNEL,'Vigil – Saison 3 (en cours)');
 db.prepare("INSERT INTO cine_series_posters(chat_id,season,source_message_id,caption) VALUES(?,?,?,?)")
   .run(CHANNEL,3,5,'Vigil S03 en cours');
 db.prepare("INSERT INTO cine_series_episodes(chat_id,season,episode,source_message_id) VALUES(?,?,?,?)")
   .run(CHANNEL,3,1,101);
 db.prepare("INSERT INTO cine_series_episodes(chat_id,season,episode,source_message_id) VALUES(?,?,?,?)")
   .run(CHANNEL,3,2,102);
 db.prepare("INSERT INTO cine_series_publications(token,chat_id,public_post_id,rescue_post_id,state) VALUES(?,?,?,?,?)")
   .run(TOKEN,CHANNEL,100,200,'published');
 const wrap=sql=>{
  let params=[];
  return {
   bind(...p){params=p;return this},
   async first(){return db.prepare(sql).get(...params)||null},
   async all(){return {results:db.prepare(sql).all(...params)}},
   async run(){const x=db.prepare(sql).run(...params);return {meta:{changes:Number(x.changes)}}},
  };
 };
 const DB={prepare:wrap,async batch(statements){
  for(const item of statements)await item.run();
 }};
 return {db,env:{DB,TELEGRAM_TOKEN:'123:fake-worker-bot'}};
}
const userRequest=(chat=321,update_id=77)=>({
 update_id,message:{chat:{type:'private',id:chat},from:{id:chat},
 text:'/start sr_'+TOKEN},
});
test('download available episode plan accepts a lone current season, never promises all historical seasons',()=>{
 assert.deepEqual(availableSeriesPlan([
  {season:3,episode:1,source_message_id:13},
  {season:3,episode:2,source_message_id:14},
 ]),{ready:true,count:2,seasons:[{season:3,episodes:2}],reason:null});
 assert.equal(availableSeriesPlan([{season:3,episode:2,source_message_id:14}]).ready,false);
 assert.equal(availableSeriesPlan([
  {season:1,episode:1,source_message_id:13},
  {season:1,episode:3,source_message_id:14},
 ]).reason,'episode_gap_or_duplicate');
 assert.equal(availableSeriesPlan([]).ready,false);
});

test('CineRadar deep-link queues only indexed S3 episodes, delivers once and expires only 12h private copies',async()=>{
 const {db,env}=fixture();
 const oldFetch=globalThis.fetch;
 const calls=[];
 let nextMessage=900;
 globalThis.fetch=async (url,opt)=>{
  const method=String(url).split('/').at(-1);
  const body=JSON.parse(opt.body);
  calls.push({method,body});
  if(method==='copyMessage')return Response.json({ok:true,result:{message_id:nextMessage++}});
  if(method==='deleteMessage')return Response.json({ok:true,result:true});
  return Response.json({ok:true,result:{message_id:999}});
 };
 try{
  const accepted=await handleSeriesStart(env,userRequest());
  assert.deepEqual(accepted,{handled:true,accepted:true});
  assert.equal((await handleSeriesStart(env,userRequest())).duplicate,true);
  const queued=db.prepare('SELECT planned_items,status FROM cine_series_jobs').get();
  assert.equal(queued.planned_items,2);
  assert.equal(queued.status,'queued');
  assert.deepEqual(db.prepare('SELECT ordinal,source_chat_id,source_message_id FROM cine_series_job_items ORDER BY ordinal').all().map(x=>({ordinal:x.ordinal,source_chat_id:x.source_chat_id,source_message_id:x.source_message_id})),[
   {ordinal:1,source_chat_id:CHANNEL,source_message_id:101},
   {ordinal:2,source_chat_id:CHANNEL,source_message_id:102},
  ]);
  // No introductory warning: the videos must come first.
  assert.equal(calls.length,0);
  // No pre-video Telegram notice: quota storage is lazily created at the first copy.
  assert.equal((await processSeriesQueue(env)).processed,2);
  assert.equal((await processSeriesQueue(env)).processed,0);
  assert.equal(db.prepare('SELECT status,delivered_items FROM cine_series_jobs').get().status,'complete');
  assert.equal(db.prepare('SELECT delivered_items FROM cine_series_jobs').get().delivered_items,2);
  const copies=calls.filter(x=>x.method==='copyMessage');
  assert.deepEqual(copies.map(x=>({dest:x.body.chat_id,source:x.body.from_chat_id,id:x.body.message_id})),[
   {dest:321,source:CHANNEL,id:101},{dest:321,source:CHANNEL,id:102},
  ]);
  for(const copy of copies)assert.equal(Object.hasOwn(copy.body,'caption'),false);
  assert.deepEqual(calls.map(x=>x.method),['copyMessage','copyMessage','sendMessage']);
  const notice=calls.at(-1).body;
  assert.match(notice.text,/Ces 2 vidéos seront supprimées automatiquement de ce chat 12 heures après chaque envoi/);
  assert.match(notice.text,/Première suppression prévue/);
  assert.match(notice.text,/Dernière suppression prévue/);
  assert.equal((await processExpiryNotices(env)).sent,0);
  const receipts=db.prepare("SELECT delivered_message_id,sent_at,delete_after FROM cine_series_job_items ORDER BY ordinal").all();
  assert.equal(receipts.length,2);
  for(const receipt of receipts){
   assert.ok(receipt.sent_at);
   assert.ok(receipt.delete_after);
   assert.ok(Math.abs(Date.parse(receipt.delete_after.replace(' ','T')+'Z')-Date.parse(receipt.sent_at.replace(' ','T')+'Z')-12*3600_000)<1000);
  }
  // Emulate expiry after 13h without waiting or sending any external Telegram call.
  db.exec("UPDATE cine_series_job_items SET sent_at=datetime('now','-13 hours'), delete_after=datetime('now','-1 hour'), delete_retry_at=datetime('now','-1 hour')");
  const expired=await cleanupSeriesCopies(env);
  assert.equal(expired.deleted,2);
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM cine_series_job_items WHERE delete_state='deleted'").get().n,2);
  assert.deepEqual(calls.filter(x=>x.method==='deleteMessage').map(x=>({chat:x.body.chat_id,id:x.body.message_id})),[
   {chat:321,id:900},{chat:321,id:901},
  ]);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cine_series_episodes').get().n,2);
 }finally{globalThis.fetch=oldFetch;db.close()}
});

test('atomic series insert blocks concurrent tap race after stale prechecks',async()=>{
 const {db,env}=fixture(),oldFetch=globalThis.fetch;
 const prepare=env.DB.prepare.bind(env.DB);
 env.DB.prepare=sql=>{
  const stmt=prepare(sql);
  if(sql.startsWith('SELECT id FROM cine_series_jobs WHERE telegram_chat_id='))stmt.first=async()=>null;
  return stmt;
 };
 globalThis.fetch=async()=>Response.json({ok:true,result:{message_id:31}});
 try{
  assert.equal((await handleSeriesStart(env,userRequest(321,300))).accepted,true);
  assert.equal((await handleSeriesStart(env,userRequest(321,301))).duplicate,true);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM cine_series_jobs').get().n,1);
  assert.equal(db.prepare('SELECT COUNT(*) n FROM cine_series_job_items').get().n,2);
 }finally{globalThis.fetch=oldFetch;db.close()}
});
test('unpublished and unapproved series cannot create download jobs',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;const calls=[];
 globalThis.fetch=async (url,opt)=>{calls.push(String(url).split('/').at(-1));return Response.json({ok:true,result:true})};
 try{
  db.exec("UPDATE cine_series_channels SET rights_attested=0");
  assert.equal((await handleSeriesStart(env,userRequest())).accepted,false);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cine_series_jobs').get().n,0);
  db.exec("UPDATE cine_series_channels SET rights_attested=1");
  db.exec("UPDATE cine_series_publications SET state='disabled'");
  assert.equal((await handleSeriesStart(env,userRequest(321,78))).accepted,false);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cine_series_jobs').get().n,0);
  assert.ok(!calls.includes('copyMessage'));
 }finally{globalThis.fetch=old;db.close()}
});
