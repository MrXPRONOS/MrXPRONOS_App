import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {
 parseFranchiseFilmNumber,ingestFranchiseOwnerForward,ingestFranchiseChannelPost,
 handleFranchiseOwnerCommand,handleFranchiseDownloadStart,processFranchiseQueue,cleanupFranchiseCopies,
} from '../franchise-films.mjs';
import {captureOwnerForwardInVault} from '../owner-chat-vault.mjs';

const HANDLE='fastandfuriousvffr', CHANNEL='-1004567890123',OWNER=1234567,USER=456789;
const TOKEN='ffFurious2026CineRadarXX';

function fixture(){
 const db=new DatabaseSync(':memory:');
 for(const file of ['019_cinex_individual_series.sql','020_cinex_owner_chat_vault.sql','021_cinex_franchise_films.sql']){
  db.exec(readFileSync(new URL('../migrations/'+file,import.meta.url),'utf8'));
 }
 db.exec("CREATE TABLE admin_users(user_id INTEGER PRIMARY KEY,role TEXT NOT NULL)");
 db.exec("CREATE TABLE bot_settings(setting_key TEXT PRIMARY KEY,value TEXT NOT NULL)");
 db.exec("CREATE TABLE cine_classic_links(source_chat_id TEXT,source_message_id INTEGER,status TEXT)");
 db.exec("CREATE TABLE cine_delivery_libraries(private_chat_id TEXT,rights_attested INTEGER,bot_access TEXT)");
 db.prepare("INSERT INTO admin_users VALUES(?,'owner')").run(OWNER);
 db.exec("INSERT INTO bot_settings VALUES('cine_delivery_enabled','1')");
 db.prepare("UPDATE cine_franchise_catalog SET token=? WHERE slug='fast-and-furious'").run(TOKEN);
 db.exec("UPDATE cine_series_config SET setting_value='true' WHERE setting_key='owner_chat_vault_enabled'");
 const DB={
  prepare(sql){
   let args=[];
   return {
    bind(...x){args=x;return this},
    async first(){return db.prepare(sql).get(...args)||null},
    async all(){return {results:db.prepare(sql).all(...args)}},
    async run(){let v=db.prepare(sql).run(...args);return {meta:{changes:Number(v.changes)}}},
   };
  },
  async batch(stmts){for(const q of stmts)await q.run()},
 };
 return {db,env:{DB,TELEGRAM_TOKEN:'fake:bot-token'}};
}
function forwarded({messageId=13,originId=101,kind='video',caption='Fast and Furious 1 VF'}={}){
 return {
  chat:{type:'private',id:OWNER},from:{id:OWNER},message_id:messageId,
  forward_origin:{type:'channel',chat:{id:Number(CHANNEL),username:HANDLE},message_id:originId},
  caption,
  ...(kind==='photo'?{photo:[{file_id:'cover'}]}:{video:{file_id:'video'}}),
 };
}
const userStart=(id=1)=>({update_id:id,message:{
 chat:{type:'private',id:USER},from:{id:USER},text:'/start ffs_'+TOKEN,
}});
test('parse only a verifiable Fast and Furious film number',()=>{
 for(const [caption,part] of [
  ['Fast and Furious 1 VF',1],['FF09 1080p',9],['Film 10 - Fast X',10],
  ['2 Fast 2 Furious',2],['Fast and Furious Tokyo Drift 2006',3],
  ['Fast Five VF',5],['Furious 7 VF',7],['The Fate of the Furious',8],
  ['F9 The Fast Saga 2021',9],['Fast X VF',10],
  ['clip générique sans numéro',null],
  ['Fast and Furious 1 à 10 VF',null],
  ['Fast and Furious 1-9 VF',null],
  ['Fast and Furious 1 – 10 VF',null],
  ['Fast and Furious 1 + Fast and Furious 2',null],
  ['FF 1 to 9 compilation',null],
 ]){
  assert.equal(parseFranchiseFilmNumber(caption),part,caption);
 }
});
test('owner forwards exactly one poster and numbered films, and vault keeps private references',async()=>{
 const {db,env}=fixture();
 try{
  const photo=forwarded({kind:'photo',caption:'Affiche Fast and Furious 1 à 10',originId:100,messageId:10});
  assert.equal((await ingestFranchiseOwnerForward(env,photo)).stored,true);
  assert.equal((await captureOwnerForwardInVault(env,photo)).captured,true);
  assert.equal(db.prepare("SELECT source_chat_id,poster_source_message_id FROM cine_franchise_catalog").get().source_chat_id,CHANNEL);
  assert.equal(db.prepare("SELECT owner_message_id,status FROM cine_owner_vault WHERE source_message_id=100").get().owner_message_id,10);
  const ff1=forwarded();
  assert.equal((await ingestFranchiseOwnerForward(env,ff1)).stored,true);
  assert.equal((await captureOwnerForwardInVault(env,ff1)).captured,true);
  const ff3=forwarded({messageId:14,originId:103,caption:'Tokyo Drift VF'});
  assert.equal((await ingestFranchiseOwnerForward(env,ff3)).part,3);
  await captureOwnerForwardInVault(env,ff3);
  assert.deepEqual(db.prepare("SELECT part FROM cine_franchise_films ORDER BY part").all().map(x=>x.part),[1,3]);
  const duplicate=forwarded({messageId:15,originId:104,caption:'Fast and Furious 1 - remplacement'});
  assert.equal((await ingestFranchiseOwnerForward(env,duplicate)).stored,false);
  // Unrelated and unverified owners never register media.
  const stranger={...forwarded({messageId:16,originId:106}),chat:{type:'private',id:99},from:{id:99}};
  assert.equal((await ingestFranchiseOwnerForward(env,stranger)).handled,false);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_films").get().n,2);
 }finally{db.close()}
});
test('ambiguously numbered saga compilation is kept pending instead of being indexed as film 1',async()=>{
 const {db,env}=fixture();
 try{
  const video=forwarded({messageId:55,originId:455,caption:'Fast and Furious 1 à 10 VF'});
  const result=await ingestFranchiseOwnerForward(env,video);
  assert.equal(result.pending,true);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cine_franchise_films').get().n,0);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM cine_franchise_pending').get().n,1);
 }finally{db.close()}
});
test('unknown video name goes to pending; owner reply /ff 2 assigns the correct part',async()=>{
 const {db,env}=fixture();const old=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({ok:true,result:{message_id:999}});
 try{
  const unknown=forwarded({messageId:21,originId:202,caption:'Vidéo complète VF haute qualité'});
  const captured=await ingestFranchiseOwnerForward(env,unknown);
  assert.equal(captured.pending,true);
  assert.equal((await captureOwnerForwardInVault(env,unknown)).captured,true);
  const reply={update_id:100,message:{chat:{id:OWNER,type:'private'},from:{id:OWNER},text:'/ff 2',reply_to_message:{message_id:21}}};
  assert.equal((await handleFranchiseOwnerCommand(env,reply)).stored,true);
  assert.equal(db.prepare("SELECT part,source_message_id FROM cine_franchise_films").get().part,2);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_pending").get().n,0);
 }finally{globalThis.fetch=old;db.close()}
});
test('channel photo pin update and numbered channel videos work without Telegram user session',async()=>{
 const {db,env}=fixture();
 try{
  const pinned={channel_post:{chat:{type:'channel',id:Number(CHANNEL),username:HANDLE},
     message_id:202,pinned_message:{message_id:100,photo:[{file_id:'pic'}],caption:'Fast and Furious'}}};
  assert.equal((await ingestFranchiseChannelPost(env,pinned)).stored,true);
  const video={channel_post:{chat:{type:'channel',id:Number(CHANNEL),username:HANDLE},
    message_id:9,video:{file_id:'v'},caption:'Fast and Furious 6 VF'}};
  assert.equal((await ingestFranchiseChannelPost(env,video)).stored,true);
  assert.equal(db.prepare("SELECT part FROM cine_franchise_films").get().part,6);
 }finally{db.close()}
});
test("CineRadar saga link queues only stored films, delivers owner's copies and deletes ONLY subscriber receipts after 24h",async()=>{
 const {db,env}=fixture(),old=globalThis.fetch,calls=[];let next=900;
 globalThis.fetch=async(url,opts)=>{
  const method=String(url).split('/').at(-1),body=JSON.parse(opts.body);
  calls.push({method,body});
  return Response.json({ok:true,result:method==='deleteMessage'?true:{message_id:next++}});
 };
 try{
  for(const [part,msg,origin] of [[1,11,101],[3,13,103]]){
   const data=forwarded({messageId:msg,originId:origin,caption:part===1?'Fast & Furious 1':'Tokyo Drift'});
   assert.equal((await ingestFranchiseOwnerForward(env,data)).stored,true);
   assert.equal((await captureOwnerForwardInVault(env,data)).captured,true);
  }
  db.exec("UPDATE cine_franchise_catalog SET status='published'");
  const accepted=await handleFranchiseDownloadStart(env,userStart(90));
  assert.equal(accepted.accepted,true);
  assert.equal(accepted.planned,2);
  assert.equal((await handleFranchiseDownloadStart(env,userStart(90))).duplicate,true);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_jobs").get().n,1);
  db.exec('DELETE FROM cine_telegram_send_quota'); // Simulated later Cron tick.
  const output=await processFranchiseQueue(env);
  assert.equal(output.processed,2);
  assert.equal((await processFranchiseQueue(env)).processed,0);
  assert.equal(db.prepare("SELECT status,delivered_items FROM cine_franchise_jobs").get().status,'complete');
  assert.equal(db.prepare("SELECT delivered_items FROM cine_franchise_jobs").get().delivered_items,2);
  const sends=calls.filter(x=>x.method==='copyMessage');
  assert.deepEqual(sends.map(x=>[x.body.chat_id,x.body.from_chat_id,x.body.message_id]),[
   [USER,String(OWNER),11],[USER,String(OWNER),13],
  ]);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_job_items WHERE delete_after IS NOT NULL").get().n,2);
  db.exec("UPDATE cine_franchise_job_items SET sent_at=datetime('now','-25 hours'),delete_after=datetime('now','-1 hour'),delete_retry_at=datetime('now','-1 hour')");
  const result=await cleanupFranchiseCopies(env);
  assert.equal(result.deleted,2);
  assert.deepEqual(calls.filter(x=>x.method==='deleteMessage').map(x=>x.body.chat_id),[USER,USER]);
  // Source entries and vault copies always remain.
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_films").get().n,2);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_owner_vault WHERE status='stored'").get().n,2);
 }finally{globalThis.fetch=old;db.close()}
});
test('unregistered saga never queues subscriber deliveries',async()=>{
 const {db,env}=fixture(),old=globalThis.fetch;
 globalThis.fetch=async()=>Response.json({ok:true,result:{message_id:1}});
 try{
  const r=await handleFranchiseDownloadStart(env,userStart(91));
  assert.equal(r.accepted,false);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM cine_franchise_jobs").get().n,0);
 }finally{globalThis.fetch=old;db.close()}
});


test('owner draft bot link delivers a private test while non-owner cannot access unpublished saga',async()=>{
 const {db,env}=fixture(),old=globalThis.fetch,calls=[];
 globalThis.fetch=async(url,opt)=>{
  const method=String(url).split('/').at(-1),body=JSON.parse(opt.body);
  calls.push({method,body});return Response.json({ok:true,result:{message_id:1000}});
 };
 try{
  const sample=forwarded({messageId:40,originId:350,caption:'Fast and Furious 4 VF'});
  assert.equal((await ingestFranchiseOwnerForward(env,sample)).stored,true);
  assert.equal((await captureOwnerForwardInVault(env,sample)).captured,true);
  assert.equal((await handleFranchiseDownloadStart(env,userStart(98))).accepted,false);
  const privateStart={
   update_id:99,message:{chat:{type:'private',id:OWNER},from:{id:OWNER},text:'/start ffs_'+TOKEN}
  };
  assert.equal((await handleFranchiseDownloadStart(env,privateStart)).accepted,true);
  db.exec('DELETE FROM cine_telegram_send_quota'); // Simulated later Cron tick.
  assert.equal((await processFranchiseQueue(env)).processed,1);
  assert.deepEqual(calls.filter(x=>x.method==='copyMessage').map(x=>x.body),[
   {chat_id:OWNER,from_chat_id:String(OWNER),message_id:40,protect_content:false}
  ]);
 }finally{globalThis.fetch=old;db.close()}
});
