import test from 'node:test';
import assert from 'node:assert/strict';
import {v2API} from '../src/v2.mjs';
import {APP_HTML} from '../src/app-page.mjs';
import {checkDailyLinks} from '../src/maintenance-v2.mjs';
import {createHmac} from 'node:crypto';
function fakeDB(){
 const writes=[];
 const channels=[
  {id:1,title:'Cinéma en français',description:'Films VF',link:'https://t.me/FilmsParis75',content_type:'films',genre:'action',language:'VF',tags:'films,action',photo:null,review_count:3,rating:4.5,accuracy:90,listing_status:'listed',link_status:'reachable'},
  {id:2,title:'Séries du monde',description:'TV',link:'https://t.me/SeriesParis75',content_type:'series',genre:'general',language:'VF',tags:'series',photo:null,review_count:0,rating:null,accuracy:null,listing_status:'listed',link_status:'unknown'},
  {id:3,title:'Manga Zone',description:'Animés',link:'https://t.me/AnimeParis75',content_type:'animes',genre:'manga',language:'VF',tags:'animes',photo:null,review_count:0,rating:null,accuracy:null,listing_status:'listed',link_status:'unknown'}
 ];
 return {writes,prepare(sql){
  let bind=[];
  return {bind(...a){bind=a;return this;},async all(){
   if(sql.includes('FROM channels c LEFT JOIN channel_profile_cache'))return {results:channels};
   if(sql.includes('FROM channel_reviews WHERE channel_id'))return {results:[]};
   if(sql.includes('JOIN channel_index_meta'))return {results:[]};
   return {results:[]};
  },async first(){
   if(sql.includes('SELECT c.id,c.link FROM channels'))return bind[0]===1?{id:1,link:channels[0].link}:null;
   if(sql.includes('SELECT COUNT(*) AS n'))return {n:0};
   if(sql.includes('SELECT id FROM channel_reviews'))return null;
   if(sql.includes('SELECT COUNT(*) AS total'))return {total:0,rating:null,accuracy:null};
   return null;
  },async run(){writes.push({sql,bind});return {meta:{changes:1}};}};
 },async batch(jobs){for(const q of jobs)await q.run();return [];}};
}
const env={DB:fakeDB(),TELEGRAM_TOKEN:'12345678:TEST_TOKEN',TELEGRAM_WEBHOOK_SECRET:'test_session_salt'};
function url(path){return new Request('https://example.org'+path);}
test('public category keyword film returns film channels not just title matches',async()=>{
 const response=await v2API(env,url('/api/search?q=film'));
 assert.equal(response.status,200);
 const data=await response.json();assert.equal(data.total,1);assert.equal(data.channels[0].type,'films');
});
test('multi-category filter shows films and animes',async()=>{
 const data=await (await v2API(env,url('/api/search?types=films,animes'))).json();
 assert.deepEqual(new Set(data.channels.map(x=>x.type)),new Set(['films','animes']));
});
test('accents and synonyms work',async()=>{
 const data=await (await v2API(env,url('/api/search?q=anim%C3%A9'))).json();
 assert.equal(data.total,1);assert.equal(data.channels[0].id,3);
});
test('feedback requires authenticated Telegram Mini App identity',async()=>{
 const request=new Request('https://example.org/api/channels/1/reviews',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rating:5,matches_description:'yes'})});
 const response=await v2API(env,request);assert.equal(response.status,401);
});
function signedData(){
 const user=JSON.stringify({id:777777,first_name:'Test'});
 const d=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),user});
 const data=Array.from(d.entries()).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>k+'='+v).join('\n');
 const secret=createHmac('sha256','WebAppData').update(env.TELEGRAM_TOKEN).digest();
 d.set('hash',createHmac('sha256',secret).update(data).digest('hex'));return d.toString();
}
test('valid signed Telegram user can save review once per channel with UPSERT',async()=>{
 const request=new Request('https://example.org/api/channels/1/reviews',{method:'POST',headers:{'Content-Type':'application/json','X-Telegram-Init-Data':signedData()},body:JSON.stringify({rating:4,matches_description:'part',comment:'Bon canal'})});
 const response=await v2API(env,request);
 assert.equal(response.status,200,await response.clone().text());
 assert.equal((await response.json()).ok,true);
 assert.ok(env.DB.writes.some(x=>x.sql.includes('INSERT INTO channel_reviews')));
});
test('generated mobile app contains valid executable inline JavaScript',()=>{
 const script=APP_HTML.match(/<script>\s*(\(function\(\)[\s\S]*?)<\/script>/)?.[1];
 assert.ok(script,'inline script should be present');
 assert.doesNotThrow(()=>new Function(script));
 assert.ok(APP_HTML.includes('id="search"'));
 assert.ok(APP_HTML.includes('id="suggest"'));
});
test('no link-check job is forced without scheduled records',async()=>{
 const r=await checkDailyLinks({DB:fakeDB()},10);
 assert.equal(r.checked,0);
});

test('multiple search expressions separated by semicolon match independent categories',async()=>{
 const data=await (await v2API(env,url('/api/search?q=film%3Banim%C3%A9'))).json();
 assert.equal(data.total,2);
 assert.deepEqual(new Set(data.channels.map(x=>x.type)),new Set(['films','animes']));
});
test('anonymous user cannot read private moderation data',async()=>{
 const {adminAPI}=await import('../admin-v2.mjs');
 const response=await adminAPI(env,url('/api/admin/overview'));
 assert.equal(response.status,403);
});
test('private dashboard has executable embedded JavaScript',async()=>{
 const {ADMIN_HTML}=await import('../admin-page.mjs');
 const script=ADMIN_HTML.match(/<script>\s*(\(\(\)=>\{[\s\S]*?)<\/script>/)?.[1];
 assert.ok(script);
 assert.doesNotThrow(()=>new Function(script));
});
test('daily check does not delete a channel after one negative result',async()=>{
 const oldFetch=globalThis.fetch;
 const checkDB={
  commands:[],
  prepare(sql){let args=[];const that=this;
   return {bind(...v){args=v;return this;},async all(){
    if(sql.includes('JOIN channel_index_meta'))return {results:[{id:7,link:'https://t.me/TestCinemaPublic'}]};
    return {results:[]};
   },async first(){
    if(sql.includes('consecutive_failures'))return {consecutive_failures:0,first_failure_at:null,listing_status:'listed'};
    return null;
   },async run(){that.commands.push({sql,args});return {meta:{changes:1}};}}
  },
  async batch(stmts){for(const stmt of stmts)await stmt.run();}
 };
 globalThis.fetch=async()=>new Response('Not found',{status:404});
 try{
  const result=await checkDailyLinks({DB:checkDB},10);
  assert.equal(result.checked,1);
  assert.equal(result.results[0].listing,'listed');
  assert.ok(checkDB.commands.every(x=>!x.sql.includes('DELETE FROM channels')));
 }finally{globalThis.fetch=oldFetch;}
});

test('verified admin can access the dashboard without exposing user identity',async()=>{
 const {adminAPI}=await import('../admin-v2.mjs');
 const db=fakeDB();const prepare=db.prepare.bind(db);
 db.prepare=function(sql){
  if(sql.includes('SELECT role FROM admin_users'))return {bind(){return this;},async first(){return {role:'owner'}}};
  return prepare(sql);
 };
 const request=new Request('https://example.org/api/admin/overview',{headers:{'X-Telegram-Init-Data':signedData()}});
 const response=await adminAPI({...env,DB:db},request);
 assert.equal(response.status,200);
 const result=await response.json();
 assert.equal(result.error,undefined);
});
test('admin action hides a channel without deleting its review history',async()=>{
 const {adminAPI}=await import('../admin-v2.mjs');
 const db=fakeDB(),base=db.prepare.bind(db);
 db.prepare=function(sql){
  if(sql.includes('SELECT role FROM admin_users'))return {bind(){return this;},async first(){return {role:'owner'}}};
  if(sql.includes('SELECT id,link FROM channels'))return {bind(){return this;},async first(){return {id:1,link:'https://t.me/FilmsParis75'}}};
  return base(sql);
 };
 const request=new Request('https://example.org/api/admin/channels/1',{method:'POST',headers:{'X-Telegram-Init-Data':signedData(),'Content-Type':'application/json'},body:JSON.stringify({action:'hide'})});
 const response=await adminAPI({...env,DB:db},request);
 assert.equal(response.status,200,await response.clone().text());
 assert.ok(db.writes.some(x=>x.sql.includes('listing_status')));
 assert.ok(db.writes.every(x=>!x.sql.includes('DELETE FROM channels')));
});

test('link health cannot override an administrator-hidden channel',async()=>{
 const oldFetch=globalThis.fetch;
 const checkDB={
  operations:[],
  prepare(sql){let args=[];const self=this;
   return {bind(...v){args=v;return this;},async all(){
    if(sql.includes('JOIN channel_index_meta'))return {results:[{id:9,link:'https://t.me/TestCinemaPublic'}]};
    return {results:[]};
   },async first(){
    if(sql.includes('consecutive_failures'))return {consecutive_failures:0,listing_status:'hidden',admin_hidden:1,first_failure_at:null};
    return null;
   },async run(){self.operations.push({sql,args});return {meta:{changes:1}};}};
  },
  async batch(jobs){for(const job of jobs)await job.run();}
 };
 globalThis.fetch=async()=>new Response('<meta property="og:title" content="Cinéma Telegram"/>',{status:200,headers:{'content-type':'text/html'}});
 try{
  const result=await checkDailyLinks({DB:checkDB},10);
  assert.equal(result.checked,1);
  assert.equal(result.results[0].outcome,'reachable');
  assert.equal(result.results[0].listing,'hidden');
  assert.ok(checkDB.operations.some(x=>x.sql.includes('listing_status')&&x.args.includes('hidden')));
 }finally{globalThis.fetch=oldFetch;}
});
