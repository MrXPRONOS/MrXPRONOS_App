import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {syncBotProfilePhoto,botUpdate} from '../radar-lean.mjs';
import {APP_HTML} from '../app-page.mjs';
import {ADMIN_HTML} from '../admin-page.mjs';
const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
const admin=readFileSync(new URL('../admin-v2.mjs',import.meta.url),'utf8');
const bot=readFileSync(new URL('../radar-lean.mjs',import.meta.url),'utf8');
const apiBase='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev';

test('approved avatar is uploaded as a new JPEG through official setMyProfilePhoto API, once',async()=>{
 const logs=[],stored=new Map(),old=globalThis.fetch;
 const DB={prepare(sql){let args=[];const stmt={
  bind(...v){args=v;return stmt},
  async first(){return {value:stored.get(args[0])}},
  async run(){stored.set(args[0],args[1]);return {meta:{changes:1}}}
 };return stmt;}};
 const env={DB,TELEGRAM_TOKEN:'fake-token'};
 const jpg=new Uint8Array(15000);jpg[0]=255;jpg[1]=216;jpg[2]=255;
 globalThis.fetch=async(url,options={})=>{
  if(String(url).startsWith('https://raw.githubusercontent.com/')){
   assert.match(String(url),/cinecanaux\/assets\/bot-profile\.jpg$/);
   return new Response(jpg,{status:200,headers:{'content-type':'image/jpeg'}});
  }
  assert.match(String(url),/\/setMyProfilePhoto$/);
  assert.ok(options.body instanceof FormData,'profile must be a multipart request');
  const spec=JSON.parse(options.body.get('photo'));
  assert.deepEqual(spec,{type:'static',photo:'attach://cine_radar_avatar'});
  const file=options.body.get('cine_radar_avatar');
  assert.equal(file.type,'image/jpeg');
  assert.equal(file.size,jpg.length);
  logs.push(String(url));
  return Response.json({ok:true,result:true});
 };
 try{
  assert.deepEqual(await syncBotProfilePhoto(env),{updated:true});
  assert.deepEqual(await syncBotProfilePhoto(env),{updated:false});
  assert.equal(logs.length,1,'Avatar is never reuploaded every time a user starts the bot');
 }finally{globalThis.fetch=old;}
});

test('visitor receives selected square poster with caption and one Mini App button',async()=>{
 const calls=[],old=globalThis.fetch;
 const env={TELEGRAM_TOKEN:'test',DB:{prepare(){return {async first(){return null}}}}};
 globalThis.fetch=async(url,options={})=>{
  calls.push({method:String(url).split('/').pop(),body:JSON.parse(options.body)});
  return Response.json({ok:true,result:{message_id:123}});
 };
 try{
  await botUpdate(env,{message:{chat:{id:123,type:'private'},from:{id:123},text:'/start'}});
  const item=calls.find(x=>x.method==='sendPhoto');
  assert.ok(item);
  assert.equal(item.body.photo,apiBase+'/assets/bot-start-poster.jpg');
  assert.match(item.body.caption,/BIENVENUE SUR CINÉ RADAR/);
  assert.match(item.body.caption,/<blockquote>/);
  assert.equal(item.body.parse_mode,'HTML');
  assert.equal(item.body.reply_markup.inline_keyboard.length,1);
  assert.equal(item.body.reply_markup.inline_keyboard[0][0].style,'primary');
  assert.equal(item.body.reply_markup.inline_keyboard[0][0].web_app.url,apiBase+'/app');
  assert.ok(!JSON.stringify(item.body).includes('/admin'),'Owner management must not be in bot chat');
 }finally{globalThis.fetch=old;}
});

test('old owner commands do not run in chat; Mini App is always the entry point',async()=>{
 for(const command of ['admin','annonces','tendances','manquants','canaux','autoriser','actualiser'])
  assert.ok(!bot.includes('if(name==="'+command+'"'));
 assert.ok(bot.includes('deleteMyCommands'));
 assert.ok(bot.includes('menu_button:{type:"web_app",text:"🎬 Ciné Radar"'));
 assert.ok(APP_HTML.includes('id="cine-owner-admin-link"'));
 assert.ok(APP_HTML.includes('"/api/admin/access"'));
 assert.ok(APP_HTML.includes('ownerAdmin.hidden=false'));
 assert.ok(APP_HTML.includes('sessionStorage.setItem("cine-radar-owner-auth"'));
 assert.ok(ADMIN_HTML.includes('sessionStorage.getItem("cine-radar-owner-auth"'));
 assert.ok(ADMIN_HTML.includes('href="/app"'));
 assert.ok(ADMIN_HTML.includes('id="bot-brand-sync"'));
 assert.ok(admin.includes("path==='/api/admin/sync-bot-identity'"));
 assert.ok(!bot.includes('{command:"admin"'));
});

test('owner authorization on server guards all administration and its new cinema controls',()=>{
 assert.ok(admin.includes("try{admin=await verifyAdmin(request,env)}")&&admin.includes("if(!admin){"));
 assert.ok(admin.includes("path==='/api/admin/access'"));
 assert.ok(admin.includes("path==='/api/admin/radar-ops'"));
 assert.ok(admin.includes("path==='/api/admin/radar-refresh'"));
 assert.ok(admin.includes("path==='/api/admin/radar-authorize'"));
 for(const id of ['radar-ops-refresh','radar-ops-channels','radar-ops-missing','broadcast-start','analytics-refresh','runChecks'])
  assert.ok(ADMIN_HTML.includes('id="'+id+'"'),id+' control missing');
});

test('Worker serves the exact two newly approved JPEGs without exposing bot token',()=>{
 for(const name of ['bot-profile.jpg','bot-start-poster.jpg']){
  assert.ok(worker.includes('"/assets/'+name+'"'));
  assert.ok(worker.includes('https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/'));
 }
 assert.ok(worker.includes('bytes[0]===0xff&&bytes[1]===0xd8'));
 assert.ok(!worker.includes('env.TELEGRAM_TOKEN+"/assets/'));
});

test('user-approved profile and welcome assets are committed as valid JPEG images',()=>{
 for(const [name,maxSize] of [['bot-profile.jpg',400000],['bot-start-poster.jpg',650000]]){
  const bytes=readFileSync(new URL('../assets/'+name,import.meta.url));
  assert.ok(bytes.length>10000&&bytes.length<maxSize,name+' has suspicious size');
  assert.equal(bytes[0],255);
  assert.equal(bytes[1],216);
  assert.equal(bytes[2],255);
  assert.equal(bytes.at(-2),255);
  assert.equal(bytes.at(-1),217);
 }
});
