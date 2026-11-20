import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import {adminAPI} from '../admin-v2.mjs';
import {ownerRemovePin,syncLatestPinned,ownerPinnedList} from '../pinned-showcase.mjs';
import {APP_HTML} from '../app-page.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';

const enc=new TextEncoder();
async function telegramInitData(username='mr_xpronos',id=4201,token='test_telegram_token'){
 const auth_date=Math.floor(Date.now()/1000);
 const user=JSON.stringify({id,first_name:'Cine Radar',username});
 const value='auth_date='+auth_date+'\nuser='+user;
 const hmac=async(key,message)=>{
  const k=await crypto.subtle.importKey('raw',typeof key==='string'?enc.encode(key):key,{name:'HMAC',hash:'SHA-256'},false,['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(message)));
 };
 const secret=await hmac('WebAppData',token);
 const hash=Array.from(await hmac(secret,value)).map(n=>n.toString(16).padStart(2,'0')).join('');
 return new URLSearchParams({auth_date:String(auth_date),user,hash}).toString();
}
function ownerDatabase(){
 const changes=[];
 const DB={prepare(sql){let args=[];
  const query={bind(...v){args=v;return query},
   async first(){if(sql.includes('SELECT role FROM admin_users'))return null;return null},
   async run(){changes.push({sql,args});return {meta:{changes:1}}}
  };return query;
 },async batch(items){for(const i of items)await i.run();}};
 return {DB,changes};
}
test('only signed @mr_xpronos can recover owner rights; arbitrary usernames cannot',async()=>{
 const f=ownerDatabase(),env={DB:f.DB,TELEGRAM_TOKEN:'test_telegram_token',TELEGRAM_WEBHOOK_SECRET:'test_secret'};
 const make=async username=>new Request('https://cineradar.test/api/admin/access',{headers:{'X-Telegram-Init-Data':await telegramInitData(username)}});
 const foreign=await adminAPI(env,await make('not_mr_xpronos'));
 assert.equal(foreign.status,403);
 assert.equal(f.changes.length,0);
 const legitimate=await adminAPI(env,await make('mr_xpronos'));
 assert.equal(legitimate.status,200);
 assert.equal((await legitimate.json()).role,'owner');
 assert.ok(f.changes.some(x=>x.sql.startsWith("DELETE FROM admin_users WHERE role='owner'")));
 assert.ok(f.changes.some(x=>x.sql.startsWith('INSERT INTO admin_users')));
 const tampered=await telegramInitData('mr_xpronos');
 const fake=new URLSearchParams(tampered);fake.set('user',JSON.stringify({id:999,username:'mr_xpronos'}));
 const invalid=await adminAPI(env,new Request('https://cineradar.test/api/admin/access',{headers:{'X-Telegram-Init-Data':fake.toString()}}));
 assert.equal(invalid.status,403);
});

test('Mini App embeds admin in same Telegram WebView and passes signed credentials only to same origin',()=>{
 for(const fragment of ['cine-owner-admin-overlay','frame.src="/admin"','frame.contentWindow?.postMessage({type:"cine-radar-owner-auth",initData:signed},location.origin)','ownerAdmin.hidden=false'])
  assert.ok(APP_HTML.includes(fragment),fragment);
 for(const fragment of ['window.addEventListener("message"','event.origin!==location.origin','event.source!==window.parent','bootstrapAdmin();'])
  assert.ok(ADMIN_HTML.includes(fragment),fragment);
});

test('the latest pin disappears when Telegram confirms the channel has no pinned message',async()=>{
 const username=['CineXFilms_vf','seriesvf_cinex','CineXAnimeFR'];
 const chat_ids=[-1003921647496,-1004406527554,-1004347937458],writes=[];
 const env={TELEGRAM_TOKEN:'fake_bot',DB:{prepare(sql){let args=[];const stmt={
  bind(...v){args=v;return stmt},
  async first(){if(sql.includes('FROM cine_pins_poll'))return null;if(sql.includes('FROM radar_primary_channels'))return {chat_id:String(chat_ids[['films','series','animes'].indexOf(args[0])])};return null},
  async run(){writes.push({sql,args});return {meta:{changes:1}}}
 };return stmt;}}};
 const old=globalThis.fetch;
 globalThis.fetch=async(url,options)=>{
  const name=JSON.parse(options.body).chat_id.slice(1),i=username.indexOf(name);
  return Response.json({ok:true,result:{id:chat_ids[i],username:name,type:'channel'}});
 };
 try{
  const result=await syncLatestPinned(env,{force:true});
  assert.equal(result.errors.length,0);
  const deactivations=writes.filter(w=>w.sql.includes('UPDATE cine_pinned_posts SET active=0'));
  assert.equal(deactivations.length,3);
  assert.deepEqual(deactivations.map(w=>w.args[0]).sort(),['animes','films','series']);
 }finally{globalThis.fetch=old;}
});

test('owner can hide a stale pinned card without unpinning in Telegram',async()=>{
 const writes=[],env={DB:{prepare(sql){let args=[];const stmt={
  bind(...v){args=v;return stmt},
  async first(){return {message_id:77,chat_id:'-1003921647496'}},
  async run(){writes.push({sql,args});return {meta:{changes:1}}},
  async all(){return {results:[]}}
 };return stmt;}}};
 const result=await ownerRemovePin(env,'films',77);
 assert.deepEqual(result,{ok:true,telegram_unpinned:false});
 assert.ok(writes.some(x=>x.sql.includes('SET active=0')&&x.args[0]==='films'&&x.args[1]===77));
 assert.equal((await ownerPinnedList(env)).items.length,0);
});

test('pin moderation in Mini App uses explicit owner-only route with confirmation',()=>{
 assert.ok(ADMIN_HTML.includes('id="owner-pinned"'));
 assert.ok(ADMIN_HTML.includes('Désépingler sur Telegram'));
 assert.ok(ADMIN_HTML.includes("Retirer de l\'affiche"));
 assert.ok(ADMIN_HTML.includes('"/api/admin/pins/"'));
});


test('owner operations preserve the former Telegram trend summary and missing-title alert behavior',()=>{
 const source=readFileSync(new URL('../admin-v2.mjs',import.meta.url),'utf8');
 assert.ok(source.includes('radarOwnerDigest(env)'), 'owner-only API must return the historic trend digest');
 assert.ok(source.includes('notifyOwnerMissingRadarTitles(env)'), 'manual refresh must still send private, deduplicated missing-title notifications');
 assert.ok(source.includes('notifications:{sent:notices.sent,listed:notices.listed,errors:notices.errors.length}'));
 assert.ok(source.includes('if(!admin)return json({error:\'Accès réservé\'},403)'), 'admin routes must stay signed and owner restricted');
 assert.ok(ADMIN_HTML.includes('id="radar-ops-digest"'));
 assert.ok(ADMIN_HTML.includes('String(data.digest||"Aucune tendance indexée.")'));
 assert.ok(ADMIN_HTML.includes('notification(s) privée(s) envoyée(s)'));
});
