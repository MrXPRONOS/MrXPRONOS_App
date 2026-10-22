import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {miniApi} from '../src/miniapp.js';
import {miniPage} from '../src/minipage.js';
const c=globalThis.crypto??webcrypto;
async function signed(){
 const p=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:80599,first_name:'Test'})});
 const enc=new TextEncoder();
 const key1=await c.subtle.importKey('raw',enc.encode('WebAppData'),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const digest1=await c.subtle.sign('HMAC',key1,enc.encode('123:TEST'));
 const key2=await c.subtle.importKey('raw',digest1,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const plain=[...p].map(([k,v])=>k+'='+v).sort().join('\n');
 const hash=new Uint8Array(await c.subtle.sign('HMAC',key2,enc.encode(plain)));
 p.set('hash',Array.from(hash).map(x=>x.toString(16).padStart(2,'0')).join(''));
 return p.toString();
}
function database(gate){
 const calls=[];
 return {calls,DB:{prepare(sql){
  calls.push(sql);
  return {bind(...args){
   return {
    async first(){
     if(sql.includes('SELECT adult_confirmed,required_verified FROM users'))return gate();
     if(sql.includes('FROM user_preferences'))return {notify_coupons:0,notify_results:0};
     return {id:80599,name:'Test',adult_confirmed:1,required_verified:1,xp:90,earned_total:105,today_total:4,tasks_total:3,coupons_total:1,referrals_total:0};
    },
    async all(){return {results:[]}}
   };
  }}
 }}};
}
test('coupons are loaded simultaneously with account eligibility, but only released after access granted',async()=>{
 let release,started;
 const permission=new Promise(resolve=>release=resolve);
 const d=database(()=>permission);
 const original=d.DB.prepare.bind(d.DB);
 let onRead;const read=new Promise(resolve=>onRead=resolve);
 d.DB.prepare=function(sql){
  const stmt=original(sql);
  if(sql.includes('SELECT id,title,tier,total_odds'))return {bind:()=>({
   all:async()=>{onRead();return {results:[]}}
  })};
  return stmt;
 };
 const pending=miniApi(new Request('https://freepronos.invalid/api/coupons?category=ALL',{headers:{'X-Telegram-Init-Data':await signed()}}),{DB:d.DB,CF_BOT_TOKEN:'123:TEST'});
 await Promise.race([read,new Promise((_,reject)=>setTimeout(()=>reject(Error('coupon read was delayed behind account lookup')),350))]);
 release({adult_confirmed:1,required_verified:1});
 const r=await pending;assert.equal(r.status,200);assert.deepEqual(await r.json(),{coupons:[]});
});
test('adult/channel access cannot be bypassed even when prefetch is in flight',async()=>{
 const d=database(async()=>({adult_confirmed:1,required_verified:0}));
 const r=await miniApi(new Request('https://freepronos.invalid/api/results',{headers:{'X-Telegram-Init-Data':await signed()}}),{DB:d.DB,CF_BOT_TOKEN:'123:TEST'});
 assert.equal(r.status,403);
 assert.equal((await r.json()).error,'channel_verification_required');
});
test('dashboard no longer performs a redundant preliminary access D1 read',async()=>{
 const d=database(async()=>({adult_confirmed:1,required_verified:1}));
 const r=await miniApi(new Request('https://freepronos.invalid/api/me',{headers:{'X-Telegram-Init-Data':await signed()}}),{DB:d.DB,CF_BOT_TOKEN:'123:TEST'});
 assert.equal(r.status,200);
 assert.equal(d.calls.length,2);
 assert.ok(!d.calls.some(q=>q.includes('SELECT adult_confirmed,required_verified FROM users')));
});
test('admin API still refuses non-admins with signed Telegram identity',async()=>{
 const d=database(async()=>({adult_confirmed:1,required_verified:1}));
 const r=await miniApi(new Request('https://freepronos.invalid/api/admin/overview',{headers:{'X-Telegram-Init-Data':await signed()}}),{DB:d.DB,CF_BOT_TOKEN:'123:TEST',CF_BOT_ADMIN_IDS:'11'});
 assert.equal(r.status,403);
});
test('Mini App static asset is reused with immutable content between requests',async()=>{
 const a=miniPage(),b=miniPage();
 assert.equal(a.status,200);assert.equal(b.status,200);
 assert.equal(await a.text(),await b.text());
 assert.match(b.headers.get('content-type'),/text\/html/);
});
