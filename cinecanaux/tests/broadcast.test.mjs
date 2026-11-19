import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateBroadcastText,trackBroadcastSubscriber,broadcastAdminAPI,deliverBroadcastBatch} from '../broadcast.mjs';
import {APP_HTML} from '../app-page.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';
import {botUpdate,initializeProfile} from '../radar-lean.mjs';

const SRC=readFileSync(new URL('../broadcast.mjs',import.meta.url),'utf8');
const ROUTES=readFileSync(new URL('../admin-v2.mjs',import.meta.url),'utf8');
const WORKER=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
const WRANGLER=readFileSync(new URL('../wrangler.jsonc',import.meta.url),'utf8');

function dbFixture(){
 const writes=[],users=new Map([[123,{active:1,blocked:0}],[456,{active:1,blocked:0}]]);
 const job={id:7,status:'draft',owner_id:900,text_html:'<b>Nouveau</b> cinéma 🍿',button_text:'Voir',button_url:'https://t.me/CineRadarFr_Bot',photo_id:''};
 let receipts=[];
 const DB={prepare(sql){
  let args=[];
  const stmt={
   bind(...items){args=items;return stmt;},
   async run(){
    writes.push({sql,args});
    if(sql.startsWith('INSERT INTO cine_broadcast_subscribers')){
     const [id,active]=args;users.set(id,{active:sql.includes('VALUES(?,1,0)')?1:0,blocked:0});
    }
    if(sql.startsWith('UPDATE cine_broadcast_receipts SET state='))return {meta:{changes:1}};
    if(sql.startsWith('INSERT INTO cine_broadcast_jobs'))return {meta:{last_row_id:7,changes:1}};
    if(sql.startsWith('UPDATE cine_broadcast_jobs SET status=')&&sql.includes("status='preparing'")){job.status='preparing';return {meta:{changes:1}};}
    if(sql.includes("SET status='preparing'")){if(job.status==='draft'){job.status='preparing';return {meta:{changes:1}};}return {meta:{changes:0}};}
    if(sql.startsWith('INSERT OR IGNORE INTO cine_broadcast_receipts')){receipts=[...users].filter(([,v])=>v.active).map(([id])=>({job_id:7,chat_id:id}));return {meta:{changes:receipts.length}};}
    if(sql.startsWith('UPDATE cine_broadcast_jobs SET status=?,recipients=?')){job.status=args[0];job.recipients=args[1];return {meta:{changes:1}};}
    return {meta:{changes:1}};
   },
   async first(){
    if(sql.includes('SELECT * FROM cine_broadcast_jobs'))return {...job};
    if(sql.includes('SELECT COUNT(*) n FROM cine_broadcast_receipts'))return {n:receipts.length};
    if(sql.includes('FROM cine_broadcast_subscribers')&&sql.includes('COUNT(*)'))return {total:users.size,active:[...users.values()].filter(v=>v.active).length};
    return null;
   },
   async all(){return {results:[]};}
  };
  return stmt;
 }};
 return {DB,writes,users,job,receipts:()=>receipts};
}

test('broadcast HTML is balanced, escaped and disallows external HTML',()=>{
 assert.equal(validateBroadcastText('🎬 <b>Salut</b> & <i>cinéma</i>',false),'🎬 <b>Salut</b> &amp; <i>cinéma</i>');
 assert.match(validateBroadcastText('<blockquote>Info</blockquote>',true),/blockquote/);
 for(const bad of ['<script>alert(1)</script>','<a href="https://evil.test">click</a>','<b><i>x</b></i>','<b>sans fermeture','']){
  assert.throws(()=>validateBroadcastText(bad,false));
 }
 assert.throws(()=>validateBroadcastText('A'.repeat(1001),true),/1 000/);
});

test('recipient IDs are stored only after /start and removed from future queues on /stop',async()=>{
 const f=dbFixture(),env={DB:f.DB};
 await trackBroadcastSubscriber(env,{message:{chat:{id:333,type:'private'},from:{id:333},text:'/start'}});
 assert.equal(f.users.get(333)?.active,1);
 await trackBroadcastSubscriber(env,{message:{chat:{id:333,type:'private'},from:{id:333},text:'/stop'}});
 assert.equal(f.users.get(333)?.active,0);
 assert.ok(f.writes.some(x=>x.sql.includes("state='skipped'")));
 const before=f.writes.length;
 await trackBroadcastSubscriber(env,{message:{chat:{id:-100,type:'channel'},from:{id:444},text:'/start'}});
 assert.equal(f.writes.length,before,'Do not register groups and channels as recipients');
});

test('admin creates a draft without messaging anybody, previews only owner, then explicitly confirms',async()=>{
 const f=dbFixture(),env={DB:f.DB,TELEGRAM_TOKEN:'test:token'},fetches=[];
 const oldFetch=globalThis.fetch;
 globalThis.fetch=async(url,opts)=>{
  fetches.push({url:String(url),payload:JSON.parse(opts.body)});
  return Response.json({ok:true,result:{message_id:55}});
 };
 try{
  const draft=await broadcastAdminAPI(env,new Request('https://test.test/api/admin/broadcasts',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({text_html:'<b>Nouveau</b> cinéma 🍿',button_text:'Voir',button_url:'https://t.me/CineRadarFr_Bot'})
  }),900);
  assert.equal(draft.status,201);
  assert.deepEqual(await draft.json(),{ok:true,id:7,status:'draft'});
  assert.equal(fetches.length,0,'Saving a draft must never send a message');
  const preview=await broadcastAdminAPI(env,new Request('https://test.test/api/admin/broadcasts/7/preview',{method:'POST',body:'{}'}),900);
  assert.equal(preview.status,200);
  assert.equal(fetches.length,1);
  assert.equal(fetches[0].payload.chat_id,900,'Preview goes only to owner');
  assert.equal(fetches[0].payload.reply_markup.inline_keyboard[0][0].style,'primary');
  const started=await broadcastAdminAPI(env,new Request('https://test.test/api/admin/broadcasts/7/start',{method:'POST',body:'{}'}),900);
  assert.deepEqual(await started.json(),{ok:true,status:'sending',recipients:2});
  assert.equal(fetches.length,1,'Confirm only queues; cron handles recipient delivery');
  assert.equal(f.receipts().length,2);
  const again=await broadcastAdminAPI(env,new Request('https://test.test/api/admin/broadcasts/7/start',{method:'POST',body:'{}'}),900);
  assert.equal(again.status,409,'Duplicate launch must be rejected');
 }finally{globalThis.fetch=oldFetch;}
});

test('admin rejects invalid button and photo data before creating draft',async()=>{
 const f=dbFixture(),env={DB:f.DB};
 for(const draft of [
  {text_html:'ok',button_text:'Click',button_url:'http://example.org'},
  {text_html:'ok',button_text:'Click'},
  {text_html:'ok',photo_id:'INVALID!'},
  {text_html:'<h1>Unsupported</h1>'}
 ]){
  const r=await broadcastAdminAPI(env,new Request('https://test.test/api/admin/broadcasts',{method:'POST',body:JSON.stringify(draft)}),900);
  assert.equal(r.status,400);
 }
 assert.ok(!f.writes.some(x=>x.sql.startsWith('INSERT INTO cine_broadcast_jobs')));
});

test('all public promo cards use Telegram avatars and text only, not decorative icon badges',()=>{
 const s=APP_HTML.slice(APP_HTML.indexOf('function promoCard(info){'),APP_HTML.indexOf('function promoBlock(){'));
 assert.ok(!s.includes('cineLot4Icon(info.kind)'));
 assert.ok(!s.includes('cine-promo-arrow'));
 assert.ok(s.includes('img.src="/assets/promo-avatar/"'));
 assert.ok(s.includes('a.append(avatar,copy)'));
 assert.ok(APP_HTML.includes('function autoScrollPromos()'));
});
test('broadcast API is exclusively owner-authenticated and uses scheduled opt-in batches',()=>{
 assert.ok(ROUTES.includes("const admin=await verifyAdmin(request,env);if(!admin)return json({error:'Accès réservé'},403)"));
 assert.ok(ROUTES.includes('broadcastAdminAPI(env,request,admin.telegram_id)'));
 assert.ok(WORKER.includes('trackBroadcastSubscriber(env,update)'));
 assert.ok(WORKER.includes('deliverBroadcastBatch(env)'));
 assert.ok(WRANGLER.includes('"* * * * *"'));
 assert.ok(SRC.includes("AND r.attempts<3"));
 assert.ok(SRC.includes('lease_until'));
 assert.ok(SRC.includes("state='skipped'"));
 assert.ok(ADMIN_HTML.includes('id="broadcast-save"'));
 assert.ok(ADMIN_HTML.includes('id="broadcast-preview-send"'));
 assert.ok(ADMIN_HTML.includes('id="broadcast-start"'));
 assert.ok(ADMIN_HTML.includes('id="broadcast-photo"'));
 assert.ok(ADMIN_HTML.includes('id="broadcast-button-url"'));
});
