import test from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {Script} from 'node:vm';
import {miniApi} from '../src/miniapp.js';
import {summary} from '../src/features.js';
import {miniPage} from '../src/minipage.js';
import {premiumJS} from '../src/premium-ui.js';
const crypto=globalThis.crypto??webcrypto;
async function signed(){
 const payload=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify({id:34567,first_name:'Test'})});
 const enc=new TextEncoder();
 const a=await crypto.subtle.importKey('raw',enc.encode('WebAppData'),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const intermediate=await crypto.subtle.sign('HMAC',a,enc.encode('123:TEST'));
 const b=await crypto.subtle.importKey('raw',intermediate,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const checked=[...payload].map(([k,v])=>k+'='+v).sort().join('\n');
 const digest=new Uint8Array(await crypto.subtle.sign('HMAC',b,enc.encode(checked)));
 payload.set('hash',Array.from(digest).map(n=>n.toString(16).padStart(2,'0')).join(''));
 return payload.toString();
}
const user={id:34567,name:'Test',adult_confirmed:1,required_verified:1,xp:90,earned_total:145,today_total:6,tasks_total:4,coupons_total:2,referrals_total:1};
function database(queries){
 return {prepare(sql){
  queries.push(sql);
  return {bind(){return {
   async first(){
    if(sql.includes('FROM users')&&(sql.includes('adult_confirmed')||sql.includes('earned_total')))return user;
    if(sql.includes('FROM user_preferences'))return {notify_coupons:0,notify_results:0};
    return null;
   },
   async all(){return {results:[]}}
  }}};
 }};
}
test('Dashboard aggregates six counters using one indexed D1 request',async()=>{
 const statements=[];
 const data=await summary({DB:database(statements)},34567);
 assert.equal(statements.length,1);
 assert.match(statements[0],/earned_total/);
 assert.equal(data.xp,90);
 assert.equal(data.earned,145);
 assert.equal(data.tasks,4);
});
test('Signed /api/history does not calculate expensive summary counters',async()=>{
 const sql=[];
 const req=new Request('https://bot.invalid/api/history',{headers:{'X-Telegram-Init-Data':await signed()}});
 const result=await miniApi(req,{DB:database(sql),CF_BOT_TOKEN:'123:TEST'});
 assert.equal(result.status,200);
 assert.ok(sql.some(q=>q.includes('adult_confirmed')));
 assert.ok(!sql.some(q=>q.includes('earned_total')));
 assert.equal(sql.length,4); // authorization + 3 history queries
});
test('Signed /api/me does load the dashboard and alert settings only once',async()=>{
 const sql=[];
 const req=new Request('https://bot.invalid/api/me',{headers:{'X-Telegram-Init-Data':await signed()}});
 const result=await miniApi(req,{DB:database(sql),CF_BOT_TOKEN:'123:TEST'});
 assert.equal(result.status,200);
 const d=await result.json();
 assert.equal(d.me.xp,90);
 assert.equal(sql.length,3); // authorization + summary + settings
});
test('Instant UI script parses, uses in-memory cache with dedupe and invalidates after writes',async()=>{
 const source=await miniPage().text();
 const scripts=[...source.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)].filter(x=>x[1].trim());
 assert.equal(scripts.length,1);
 assert.doesNotThrow(()=>new Script(scripts[0][1]));
 assert.match(scripts[0][1],/pApiPending/);
 assert.match(scripts[0][1],/pCacheVersion\+\+/);
 assert.match(scripts[0][1],/pViewCache/);
 assert.match(premiumJS,/StaleNavigation/);
 assert.match(premiumJS,/pNavEpoch/);
 assert.match(source,/requestIdleCallback/);
});
