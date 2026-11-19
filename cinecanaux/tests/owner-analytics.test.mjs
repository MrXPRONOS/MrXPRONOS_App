import test from 'node:test';
import assert from 'node:assert/strict';
import {Script} from 'node:vm';
import {APP_HTML} from '../app-page.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';
import {tryOwnerClaim} from '../owner-claim.mjs';
import {analyticsEvent,recordBotTouch,adminAnalytics} from '../analytics.mjs';

const codeHash=async s=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(x=>x.toString(16).padStart(2,'0')).join('');
const CODE='Vn-5VtGkJ_xRroBaGVhvg7DF-0123';
function mockClaim(){
 const state={roleId:123,writes:[],used:false};
 const db={prepare(sql){
  let vals=[];const query={
   bind(...xs){vals=xs;return query},
   async all(){return sql.includes('FROM admin_users')?{results:[{user_id:state.roleId}]}:{results:[]}},
   async first(){
    if(sql.includes('FROM owner_claim_request'))return {code_sha256:await codeHash(CODE),expires_at:'2099-01-01 00:00:00',used_at:state.used?'now':null};
    return null;
   },
   async run(){
    state.writes.push({sql,vals});
    if(sql.startsWith('UPDATE owner_claim_request')){if(state.used)return {meta:{changes:0}};state.used=true}
    return {meta:{changes:1}};
   }
  };return query;
 },async batch(items){for(const item of items)await item.run()}};
 return {state,DB:db};
}
test('only verified private Telegram username and one-time code can claim owner',async()=>{
 const old=globalThis.fetch,fixture=mockClaim(),calls=[];
 globalThis.fetch=async(url,opts)=>{calls.push(JSON.parse(opts.body));return Response.json({ok:true,result:{message_id:1}})};
 try{
  const bad={message:{chat:{id:900,type:'private'},from:{id:900,username:'other_user'},text:'/lieradmin '+CODE}};
  assert.equal((await tryOwnerClaim({DB:fixture.DB,TELEGRAM_TOKEN:'test'},bad)).activated,false);
  assert.equal(fixture.state.used,false);
  const invalid={message:{chat:{id:900,type:'private'},from:{id:900,username:'mr_xpronos'},text:'/lieradmin '+'x'.repeat(25)}};
  assert.equal((await tryOwnerClaim({DB:fixture.DB,TELEGRAM_TOKEN:'test'},invalid)).activated,false);
  assert.equal(fixture.state.used,false);
  const good={message:{chat:{id:900,type:'private'},from:{id:900,username:'mr_xpronos'},text:'/lieradmin '+CODE}};
  const done=await tryOwnerClaim({DB:fixture.DB,TELEGRAM_TOKEN:'test'},good);
  assert.equal(done.activated,true);
  assert.equal(fixture.state.used,true);
  assert.ok(fixture.state.writes.some(x=>x.sql.startsWith("DELETE FROM admin_users")));
  assert.ok(fixture.state.writes.some(x=>x.sql.startsWith("INSERT INTO admin_users")&&x.vals[0]===900));
  assert.equal((await tryOwnerClaim({DB:fixture.DB,TELEGRAM_TOKEN:'test'},good)).activated,false);
  const messages=calls.filter(x=>typeof x.text==='string');
  assert.ok(messages.some(x=>x.text.includes('activé')));
  assert.ok(messages.filter(x=>!x.text.includes('activé')).every(x=>!x.reply_markup),'Denied owner claims must never show an admin button');
  assert.ok(messages.filter(x=>x.text.includes('activé')).every(x=>x.reply_markup?.inline_keyboard?.length===1),'Only successful owner claim should show admin entry point');
  assert.ok(calls.some(x=>x.scope?.type==='chat'&&x.scope?.chat_id===123),'Old owner command scope should be revoked');
  assert.ok(calls.some(x=>x.chat_id===123&&x.menu_button?.type==='commands'),'Old owner admin menu should be reset');
 }finally{globalThis.fetch=old}
});
test('analytics reject invalid and cross-site event payloads',async()=>{
 const DB={prepare(){throw Error('Invalid input must never reach DB')}},env={DB,TELEGRAM_WEBHOOK_SECRET:'secure-testing-secret'};
 let r=await analyticsEvent(env,new Request('https://demo.test/api/analytics/event',{method:'POST',headers:{origin:'https://evil.test','content-type':'application/json'},body:JSON.stringify({event:'visit',id:crypto.randomUUID()})}));
 assert.equal(r.status,403);
 r=await analyticsEvent(env,new Request('https://demo.test/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'promo_open',target:'unknown'})}));
 assert.equal(r.status,400);
 r=await analyticsEvent(env,new Request('https://demo.test/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'visit',id:'not-a-uuid'})}));
 assert.equal(r.status,400);
});
test('bot /start metrics hash user IDs rather than storing raw Telegram IDs',async()=>{
 const entries=[];
 const DB={prepare(sql){let args=[];return {bind(...params){args=params;return {async run(){entries.push({sql,args});return {meta:{changes:1}}}}}}}};
 await recordBotTouch({DB,TELEGRAM_WEBHOOK_SECRET:'secure-testing-secret'},{message:{chat:{type:'private'},from:{id:345676},text:'/start'}});
 assert.equal(entries.length,2);
 assert.ok(entries.every(x=>!JSON.stringify(x).includes('345676')));
 assert.equal(entries[0].args[1],1);
});
test('Mini App and administration inline JavaScript parse and include requested features',()=>{
 for(const [label,html] of [['app',APP_HTML],['admin',ADMIN_HTML]]){
  const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(x=>x[1]).filter(Boolean);
  assert.ok(scripts.length,label+' missing scripts');
  for(const source of scripts)assert.doesNotThrow(()=>new Script(source),label+' syntax invalid');
 }
 for(const token of ['function autoScrollPromos(){','promoTimer=setInterval','function shareCineRadar(){','communityTools(home);','function analyticsPreference(about){','metric("channel_open"','metric("pin_open"','metric("promo_open"']){
  assert.ok(APP_HTML.includes(token),token);
 }
 for(const token of ['analytics-period','analytics-from','analytics-to','analytics-metrics','analytics-daily','analytics-channels','analytics-pins','analytics-promos','analytics-csv']){
  assert.ok(ADMIN_HTML.includes(token),token);
 }
 assert.ok(ADMIN_HTML.includes('30 derniers jours'));
 assert.ok(ADMIN_HTML.includes('Année passée'));
});
test('unknown administrative period is rejected before queries',async()=>{
 const env={DB:{prepare(){throw Error('Invalid period must not query D1')}}};
 const r=await adminAnalytics(env,new Request('https://test.local/api/admin/analytics?period=invalid'));
 assert.equal(r.status,400);
});

test('every valid UUID v4 is accepted including random fields containing digits 0-3',async()=>{
 const writes=[];
 const env={TELEGRAM_WEBHOOK_SECRET:'testing-secret-for-hash',DB:{prepare(sql){let args=[];const q={bind(...values){args=values;return q},async run(){writes.push({sql,args});return {meta:{changes:1}}}};return q;}}};
 const valid=[
  '00000000-0000-4000-8000-000000000000',
  '11111111-2222-4012-8abc-123456789012',
  'abcdef12-3456-4123-9a01-0123456789ab',
  '01234567-89ab-4abc-bdef-0123456789ab'
 ];
 for(const id of valid){
  const r=await analyticsEvent(env,new Request('https://demo.test/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'visit',id})}));
  assert.equal(r.status,200,'Valid UUIDv4 unexpectedly rejected: '+id);
 }
 const invalid=[
  '00000000-0000-3000-8000-000000000000',
  '00000000-0000-4000-7000-000000000000',
  '00000000-0000-4000-8000-00000000000g'
 ];
 for(const id of invalid){
  const r=await analyticsEvent(env,new Request('https://demo.test/api/analytics/event',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({event:'visit',id})}));
  assert.equal(r.status,400,'Malformed UUID accepted: '+id);
 }
 assert.equal(writes.length,valid.length*2);
 assert.ok(writes.every(x=>!JSON.stringify(x).includes('123456789012')));
});
