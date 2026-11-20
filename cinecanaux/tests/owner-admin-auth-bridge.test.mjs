import test from 'node:test';
import assert from 'node:assert/strict';
import {APP_HTML} from '../app-page.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';
import {adminAPI} from '../admin-v2.mjs';
import {botUpdate} from '../radar-lean.mjs';

const ROOT='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';
const enc=new TextEncoder();
async function hmac(key,message){
 const k=await crypto.subtle.importKey('raw',typeof key==='string'?enc.encode(key):key,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(message)));
}
async function signed(id,token='bot:test'){
 const auth_date=Math.floor(Date.now()/1000);
 const user=JSON.stringify({id,username:'mr_xpronos',first_name:'Owner'});
 const data='auth_date='+auth_date+'\nuser='+user;
 const secret=await hmac('WebAppData',token);
 const hash=Array.from(await hmac(secret,data),n=>n.toString(16).padStart(2,'0')).join('');
 return new URLSearchParams({user,auth_date:String(auth_date),hash}).toString();
}

test('Telegram SDK initializes before inline Mini App authentication code',()=>{
 const sdk='<script src="https://telegram.org/js/telegram-web-app.js?64"></script>';
 assert.ok(APP_HTML.includes(sdk));
 assert.ok(!APP_HTML.includes('<script defer src="https://telegram.org/js/telegram-web-app.js?64"></script>'));
 assert.ok(APP_HTML.indexOf(sdk)<APP_HTML.indexOf('const telegram=()=>window.Telegram?.WebApp||null'));
});

test('owner launch uses signed /app context and automatically shows administration',async()=>{
 const calls=[],old=globalThis.fetch;
 const env={TELEGRAM_TOKEN:'bot:test',DB:{prepare(sql){let args=[];const p={bind(...v){args=v;return p},async first(){return sql.includes('SELECT role FROM admin_users')&&args[0]===900?{role:'owner'}:null}};return p;}}};
 globalThis.fetch=async(url,options={})=>{
  const method=String(url).split('/').at(-1);
  calls.push({method,data:JSON.parse(options.body)});
  return Response.json({ok:true,result:{message_id:1}});
 };
 try{
  await botUpdate(env,{message:{chat:{id:900,type:'private'},from:{id:900,username:'mr_xpronos'},text:'/start'}});
  const admin=calls.find(x=>x.method==='sendPhoto')?.data.reply_markup.inline_keyboard[1]?.[0];
  assert.equal(admin?.web_app?.url,ROOT+'/app?admin=1');
  assert.equal(admin?.style,'primary');
  assert.ok(APP_HTML.includes('const wantsAdmin=new URLSearchParams(location.search).get("admin")==="1"'));
  assert.ok(APP_HTML.includes('if(wantsAdmin)openOwnerAdmin()'));
 }finally{globalThis.fetch=old;}
});

test('iframe requests signed auth from the parent instead of racing stale sessionStorage',()=>{
 for(const fragment of [
  'const framed=window.parent!==window',
  'let init=framed?"":window.Telegram?.WebApp?.initData',
  'window.parent.postMessage({type:"cine-radar-admin-ready"},location.origin)',
  'if(event.origin!==location.origin||event.source!==window.parent',
  'const activeToken=init',
  'if(init&&init!==activeToken)bootstrapAdmin()'
 ])assert.ok(ADMIN_HTML.includes(fragment),fragment);
 for(const fragment of [
  'event.origin!==location.origin||event.source!==frame?.contentWindow',
  'event.data?.type!=="cine-radar-admin-ready"',
  'frame.contentWindow.postMessage({type:"cine-radar-owner-auth",initData:signed},location.origin)',
  'frame.src="/admin"',
  'ownerAdmin.onclick=openOwnerAdmin'
 ])assert.ok(APP_HTML.includes(fragment),fragment);
});

test('API remains private to signed enrolled owner, without any anonymous bypass',async()=>{
 const env={TELEGRAM_TOKEN:'bot:test',TELEGRAM_WEBHOOK_SECRET:'secret',DB:{prepare(sql){
  let args=[];const p={bind(...v){args=v;return p},async first(){
   if(sql.includes('SELECT role FROM admin_users'))return args[0]===900?{role:'owner'}:null;
   return null;
  }};return p;
 }}};
 const make=async id=>new Request(ROOT+'/api/admin/access',{headers:{'X-Telegram-Init-Data':await signed(id)}});
 assert.equal((await adminAPI(env,new Request(ROOT+'/api/admin/access'))).status,403);
 const ok=await adminAPI(env,await make(900));
 assert.equal(ok.status,200);
 assert.equal((await ok.json()).role,'owner');
 // The username by itself never authenticates a forged Telegram signature.
 const fake=new URLSearchParams(await signed(123,'wrong:token'));
 assert.equal((await adminAPI(env,new Request(ROOT+'/api/admin/access',{headers:{'X-Telegram-Init-Data':fake.toString()}}))).status,403);
});
