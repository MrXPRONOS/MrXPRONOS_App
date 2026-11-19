import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const code = await readFile(new URL('../worker.js',import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
const url = 'https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook';
const publicId = 222;
const adminId = 111;

function harness(){
 const calls = [], settings = new Map([['welcome','🎮 Bienvenue sur Mr XPRONOS Play. Tapote et gagne des XP.']]);
 const pending = new Map();
 const rows = {players:3,sync_receipts:1,wheel_claims:2,daily_claims:1};
 const env={
  BOT_TOKEN:'fake-token',
  WEBHOOK_SECRET:'unit-test-secret',
  DB:{
   prepare(sql) {
    const lower=sql.toLowerCase();
    return {
     bind(...values){
      return {
       async first(){
        if(lower.includes('from bot_admins'))return String(values[0])===String(adminId)?{telegram_id:String(adminId)}:null;
        if(lower.includes('from bot_settings'))return {value:settings.get(values[0])};
        if(lower.includes('from bot_admin_pending'))return pending.get(String(values[0]))||null;
        if(lower.includes('from players'))return {n:rows.players,xp:180};
        if(lower.includes('from sync_receipts'))return {n:rows.sync_receipts};
        if(lower.includes('from wheel_claims'))return {n:rows.wheel_claims};
        if(lower.includes('from daily_claims'))return {n:rows.daily_claims};
        return null;
       },
       async run(){
        if(lower.includes('insert into bot_admin_pending'))pending.set(String(values[0]),{edit_key:values[1],expires_ms:values[2]});
        if(lower.includes('delete from bot_admin_pending'))pending.delete(String(values[0]));
        if(lower.includes('insert into bot_settings'))settings.set(values[0],values[1]);
        return {success:true};
       }
      };
     },
     async all(){if(lower.includes('from bot_admins'))return {results:[{telegram_id:String(adminId)}]};return {results:[]}},
     async first(){
      if(lower.includes('from players'))return {n:rows.players,xp:180};
      if(lower.includes('from sync_receipts'))return {n:rows.sync_receipts};
      if(lower.includes('from wheel_claims'))return {n:rows.wheel_claims};
      if(lower.includes('from daily_claims'))return {n:rows.daily_claims};
      return null;
     }
    };
   }
  }
 };
 const oldFetch=globalThis.fetch;
 globalThis.fetch=async(input,init)=>{
  const method=String(input).split('/').at(-1);
  calls.push({method,args:JSON.parse(init.body)});
  let result=method==='sendMessage'?{message_id:123}:true;
  if(method==='getMyCommands')result=init.body.includes('"type":"chat"')?[{command:'start'},{command:'admin'}]:[{command:'start'}];
  if(method==='getWebhookInfo')result={url:'https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook',allowed_updates:['message','callback_query']};
  if(method==='getChatMenuButton')result={type:'commands'};
  return Response.json({ok:true,result});
 };
 return {
  env,calls,settings,pending,
  restore(){globalThis.fetch=oldFetch},
  async webhook(update,secret='unit-test-secret',ctx){
   return worker.fetch(new Request(url,{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':secret,'content-type':'application/json'},body:JSON.stringify(update)}),env,ctx);
  }
 };
}

function message(userId,text){
 return {message:{from:{id:userId},chat:{id:userId,type:'private'},text}};
}
function callback(userId,data){
 return {callback_query:{id:'cb-'+userId,from:{id:userId},data,message:{message_id:12,chat:{id:userId,type:'private'}}}};
}

test('rejects forged webhook secrets',async()=>{
 const h=harness();
 try{const res=await h.webhook(message(publicId,'/start'),'wrong');assert.equal(res.status,403);assert.equal(h.calls.length,0)}finally{h.restore()}
});

test('public Start shows only one Mini App button',async()=>{
 const h=harness();
 try{
  const res=await h.webhook(message(publicId,'/start'));assert.equal(res.status,200);
  const send=h.calls.filter(x=>x.method==='sendMessage');
  assert.equal(send.length,1);
  assert.equal(send[0].args.reply_markup.inline_keyboard.length,1);
  assert.equal(send[0].args.reply_markup.inline_keyboard[0][0].web_app.url,'https://mrxpronos-play.cinecanaux-xpronos.workers.dev');
  assert.ok(!JSON.stringify(send).includes('Administration'));
 }finally{h.restore()}
});

test('public cannot access admin commands, even by typing /admin',async()=>{
 const h=harness();
 try{await h.webhook(message(publicId,'/admin'));assert.equal(h.calls.length,0)}finally{h.restore()}
});

test('admin sees a private panel after /admin and a private button after /start',async()=>{
 const h=harness();
 try{
  await h.webhook(message(adminId,'/start'));
  let send=h.calls.find(x=>x.method==='sendMessage');
  assert.equal(send.args.reply_markup.inline_keyboard.length,2);
  h.calls.length=0;
  await h.webhook(message(adminId,'/admin'));
  send=h.calls.find(x=>x.method==='sendMessage');
  assert.ok(send.args.text.includes('Administration'));
  assert.ok(send.args.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==='mrxp:admin:stats'));
 }finally{h.restore()}
});

test('public cannot operate a forged admin callback',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(publicId,'mrxp:admin:stats'));
  assert.equal(h.calls.length,1);
  assert.equal(h.calls[0].method,'answerCallbackQuery');
  assert.equal(h.calls[0].args.show_alert,true);
 }finally{h.restore()}
});

test('admin can edit welcome, and new public users see new welcome',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:edit_welcome'));
  assert.equal(h.pending.get(String(adminId)).edit_key,'welcome');
  await h.webhook(message(adminId,'🎮 Nouveau message : ouvre le jeu et récupère des XP.'));
  assert.equal(h.settings.get('welcome'),'🎮 Nouveau message : ouvre le jeu et récupère des XP.');
  assert.equal(h.pending.has(String(adminId)),false);
  h.calls.length=0;
  await h.webhook(message(publicId,'/start'));
  assert.equal(h.calls[0].args.text,'🎮 Nouveau message : ouvre le jeu et récupère des XP.');
 }finally{h.restore()}
});

test('approved admin /start safely synchronizes Telegram command scopes and webhook callbacks',async()=>{
 const h=harness();const tasks=[];const context={waitUntil(p){tasks.push(p)}};
 try{
  const res=await h.webhook(message(adminId,'/start'),'unit-test-secret',context);
  assert.equal(res.status,200);
  assert.equal(tasks.length,1);
  await Promise.all(tasks);
  const commands=h.calls.filter(x=>x.method==='setMyCommands');
  assert.equal(commands.length,4);
  const privateCmd=commands.find(x=>x.args.scope?.type==='all_private_chats');
  assert.deepEqual(privateCmd.args.commands.map(x=>x.command),['start']);
  const adminCmd=commands.find(x=>x.args.scope?.type==='chat');
  assert.deepEqual(adminCmd.args.commands.map(x=>x.command),['start','admin']);
  const webhook=h.calls.find(x=>x.method==='setWebhook');
  assert.ok(webhook.args.allowed_updates.includes('callback_query'));
  assert.ok(h.calls.some(x=>x.method==='setMyDescription'));
 }finally{h.restore()}
});
