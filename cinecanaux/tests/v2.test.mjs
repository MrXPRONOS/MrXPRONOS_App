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
