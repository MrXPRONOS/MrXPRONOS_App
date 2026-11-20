import test from 'node:test';
import assert from 'node:assert/strict';
import {recordBotStartFunnel,recordSignedAppLaunch,launchFunnelStats} from '../launch-funnel.mjs';
import {botUpdate} from '../radar-lean.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';
import {APP_HTML} from '../app-page.mjs';
import {adminAPI} from '../admin-v2.mjs';
import {readFileSync} from 'node:fs';

const enc=new TextEncoder();
async function hmac(key,message){
 const cryptoKey=await crypto.subtle.importKey('raw',typeof key==='string'?enc.encode(key):key,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return new Uint8Array(await crypto.subtle.sign('HMAC',cryptoKey,enc.encode(message)));
}
async function signedInitData(id=123,secret='fake:token'){
 const auth_date=Math.floor(Date.now()/1000);
 const user=JSON.stringify({id,first_name:'Cine User',username:'cine_user'});
 const text='auth_date='+auth_date+'\nuser='+user;
 const signingKey=await hmac('WebAppData',secret);
 const hash=Array.from(await hmac(signingKey,text)).map(v=>v.toString(16).padStart(2,'0')).join('');
 return new URLSearchParams({auth_date:String(auth_date),user,hash}).toString();
}
function fixture(){
 const users=new Map(),writes=[],ownerId=900;
 const DB={prepare(sql){let args=[];const p={
  bind(...v){args=v;return p},
  async run(){
   if(sql.startsWith('CREATE TABLE'))return {meta:{changes:0}};
   writes.push({sql,args});
   if(sql.includes('INSERT INTO cine_bot_launch_funnel')){
    const key=args[0];let row=users.get(key);
    if(!row)row={first_start_at:null,first_launch_at:null,starts:0,launches:0};
    if(sql.includes('first_start_at')){row.first_start_at='now';row.starts++;}
    if(sql.includes('first_launch_at')){row.first_launch_at='now';row.launches++;}
    users.set(key,row);
   }
   return {meta:{changes:1}};
  },
  async first(){
   if(sql.includes('SELECT role FROM admin_users'))return args[0]===ownerId?{role:'owner'}:null;
   if(sql.includes('FROM cine_bot_launch_funnel')){
    const rows=[...users.values()],start=rows.filter(x=>x.first_start_at).length;
    const both=rows.filter(x=>x.first_start_at&&x.first_launch_at).length;
    return {
     started:start,started_and_launched:both,started_without_launch:start-both,
     total_launch_users:rows.filter(x=>x.first_launch_at).length,
     start_commands:rows.reduce((n,x)=>n+x.starts,0),
     app_opens:rows.reduce((n,x)=>n+x.launches,0)
    };
   }
   return null;
  }
 };return p;}};
 return {DB,users,writes,ownerId};
}
test('signed Telegram ID connects /start and Mini App launch without raw identifiers',async()=>{
 const f=fixture(),env={DB:f.DB,TELEGRAM_WEBHOOK_SECRET:'fake:webhook',TELEGRAM_TOKEN:'fake:token'};
 const start=id=>({message:{chat:{id,type:'private'},from:{id},text:'/start'}});
 assert.equal(await recordBotStartFunnel(env,start(123)),true);
 assert.equal(await recordBotStartFunnel(env,start(456)),true);
 assert.equal(await recordBotStartFunnel(env,start(123)),true);
 assert.equal(await recordBotStartFunnel(env,{message:{chat:{id:123,type:'private'},from:{id:123},text:'/aide'}}),false);
 const before=await launchFunnelStats(env);
 assert.equal(before.started_users,2);
 assert.equal(before.started_without_launch,2);
 assert.equal(before.start_commands,3);
 const launch=await recordSignedAppLaunch(env,new Request('https://cine.test/api/analytics/launch',{
  method:'POST',headers:{'X-Telegram-Init-Data':await signedInitData(123,'fake:token')}
 }));
 assert.equal(launch.status,200);
 const after=await launchFunnelStats(env);
 assert.equal(after.started_users,2);
 assert.equal(after.launched_after_start,1);
 assert.equal(after.started_without_launch,1);
 assert.equal(after.total_telegram_launch_users,1);
 assert.equal(after.signed_app_opens,1);
 const identityArgs=f.writes.filter(x=>x.sql.includes('INSERT INTO cine_bot_launch_funnel')).map(x=>x.args[0]);
 assert.ok(identityArgs.every(x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)),'Only salted hashes are stored');
 assert.ok(identityArgs.every(x=>x!==String(123)&&x!==String(456)));
});
test('unsigned or forged Mini App identity cannot increment the launch funnel',async()=>{
 const f=fixture(),env={DB:f.DB,TELEGRAM_WEBHOOK_SECRET:'fake:webhook',TELEGRAM_TOKEN:'fake:token'};
 const noAuth=await recordSignedAppLaunch(env,new Request('https://cine.test/api/analytics/launch',{method:'POST'}));
 assert.equal(noAuth.status,403);
 const invalid=await signedInitData(123,'wrong:token');
 const tampered=await recordSignedAppLaunch(env,new Request('https://cine.test/api/analytics/launch',{
  method:'POST',headers:{'X-Telegram-Init-Data':invalid}
 }));
 assert.equal(tampered.status,403);
 const badOrigin=await recordSignedAppLaunch(env,new Request('https://cine.test/api/analytics/launch',{
  method:'POST',headers:{origin:'https://other.test','X-Telegram-Init-Data':await signedInitData(123,'fake:token')}
 }));
 assert.equal(badOrigin.status,403);
 assert.equal(f.users.size,0);
});
test('owner receives the blue Administration button, an ordinary visitor never does',async()=>{
 const f=fixture(),env={DB:f.DB,TELEGRAM_TOKEN:'fake:token'},messages=[];
 const old=globalThis.fetch;
 globalThis.fetch=async(url,opts={})=>{
  const method=String(url).split('/').at(-1);
  const body=JSON.parse(String(opts.body||'{}'));
  messages.push({method,body});
  return Response.json({ok:true,result:{message_id:1}});
 };
 try{
  await botUpdate(env,{message:{chat:{id:111,type:'private'},from:{id:111,username:'film_fan'},text:'/start'}});
  const visitor=messages.filter(x=>x.method==='sendPhoto').at(-1).body;
  assert.equal(visitor.reply_markup.inline_keyboard.length,1);
  assert.ok(!JSON.stringify(visitor.reply_markup).includes('/admin'));
  await botUpdate(env,{message:{chat:{id:900,type:'private'},from:{id:900},text:'/start'}});
  const owner=messages.filter(x=>x.method==='sendPhoto').at(-1).body;
  assert.equal(owner.reply_markup.inline_keyboard.length,2);
  assert.equal(owner.reply_markup.inline_keyboard[0][0].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app');
  assert.equal(owner.reply_markup.inline_keyboard[1][0].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/admin');
  assert.equal(owner.reply_markup.inline_keyboard[1][0].style,'primary');
  await botUpdate(env,{message:{chat:{id:901,type:'private'},from:{id:901,username:'mr_xpronos'},text:'/start'}});
  assert.equal(messages.filter(x=>x.method==='sendPhoto').at(-1).body.reply_markup.inline_keyboard.length,2);
 }finally{globalThis.fetch=old}
});
test('only signed owner can read the conversion summary through protected admin route',async()=>{
 const f=fixture(),env={DB:f.DB,TELEGRAM_TOKEN:'fake:token',TELEGRAM_WEBHOOK_SECRET:'fake:webhook'};
 const guest=await adminAPI(env,new Request('https://cine.test/api/admin/launch-funnel'),undefined);
 assert.equal(guest.status,403);
 const signed=await signedInitData(900,'fake:token');
 const access=await adminAPI(env,new Request('https://cine.test/api/admin/launch-funnel',{headers:{'X-Telegram-Init-Data':signed}}),undefined);
 assert.equal(access.status,200);
 const data=await access.json();
 assert.equal(data.started_users,0);
});
test('Mini App sends signed launch once at entry; dashboard displays all three conversion cohorts',()=>{
 const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
 assert.ok(worker.includes('recordBotStartFunnel(env,update)'));
 assert.ok(worker.includes('if(u.pathname==="/api/analytics/launch")return recordSignedAppLaunch(env,request)'));
 assert.ok(APP_HTML.includes('if(signed)fetch("/api/analytics/launch"'));
 assert.ok(APP_HTML.includes('"X-Telegram-Init-Data":signed'));
 assert.ok(APP_HTML.includes('if(!metricsAllowed())return'));
 for(const token of ['id="cine-launch-funnel"','id="cine-launch-funnel-metrics"','"started_users"','"launched_after_start"','"started_without_launch"','id="cine-launch-funnel-refresh"']){
  assert.ok(ADMIN_HTML.includes(token),token);
 }
});
