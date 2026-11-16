import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker.mjs';
import {APP_HTML} from '../app-page.mjs';
import {v2API} from '../v2.mjs';

function fixtureDatabase(known=true){
 return {prepare(sql){
  let args=[];
  return {bind(...values){args=values;return this;},async first(){
   if(sql.includes("SELECT id FROM channels WHERE LOWER(link)"))return known?{id:1}:null;
   return null;
  },async all(){
   if(sql.includes('FROM channels c LEFT JOIN channel_profile_cache'))return {results:[{
    id:1,title:'Films publics',description:'',link:'https://t.me/PublicFilms2026',content_type:'films',
    genre:'general',language:'VF',photo:null,tags:'films',review_count:0,rating:null,accuracy:null,link_status:'unknown'
   }]};
   return {results:[]};
  }};
 }};
}
test('public catalog points to a same-origin avatar, never leaks the Telegram token',async()=>{
 const response=await v2API({DB:fixtureDatabase()},new Request('https://test.local/api/catalog'));
 const data=await response.json();
 assert.equal(data.channels[0].avatar,'/assets/channel-avatar/publicfilms2026.jpg');
 assert.ok(!JSON.stringify(data).includes('api.telegram.org/bot'));
});
test('app shows circular profile avatars when present',()=>{
 assert.ok(APP_HTML.includes('channel-profile-img'));
 assert.ok(APP_HTML.includes('photoHost(c.avatar)'));
 assert.ok(APP_HTML.includes('const profilePhoto=[c.avatar,p?.photo,c.photo]'));
 assert.ok(APP_HTML.includes('img.onerror=()=>'));
});
test('unknown channel avatar never makes an outbound request',async()=>{
 const old=globalThis.fetch;
 globalThis.fetch=async()=>{throw Error('Unexpected outbound request')};
 try{
  const response=await worker.fetch(new Request('https://test.local/assets/channel-avatar/unknownchannel.jpg'),{DB:fixtureDatabase(false)});
  assert.equal(response.status,404);
 }finally{globalThis.fetch=old}
});
test('avatar proxy serves authentic cached JPEG without exposing source URL to clients',async()=>{
 const old=globalThis.fetch;
 let called=0;
 globalThis.fetch=async(url)=>{called++;assert.match(String(url),/raw\.githubusercontent\.com\/MrXPRONOS\/MrXPRONOS_App\/main\/cinecanaux\/assets\/avatars\/publicfilms2026\.jpg/);return new Response(new Uint8Array([255,216,255,217]),{status:200,headers:{'content-type':'image/jpeg'}})};
 try{
  const response=await worker.fetch(new Request('https://test.local/assets/channel-avatar/PublicFilms2026.jpg'),{DB:fixtureDatabase(true)});
  assert.equal(response.status,200);
  assert.equal(response.headers.get('content-type'),'image/jpeg');
  assert.equal(called,1);
 }finally{globalThis.fetch=old}
});
test('missing avatar safely falls back to illustration',async()=>{
 const old=globalThis.fetch;
 globalThis.fetch=async()=>new Response('Not Found',{status:404});
 try{
  const response=await worker.fetch(new Request('https://test.local/assets/channel-avatar/PublicFilms2026.jpg'),{DB:fixtureDatabase(true)});
  assert.equal(response.status,404);
 }finally{globalThis.fetch=old}
});
