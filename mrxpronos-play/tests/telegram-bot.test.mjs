import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
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
 const player={user_id:'',username:'',display_name:'',confirmed_xp:0,confirmed_taps:0,last_sync_ms:0,next_sync_ms:0};
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
        if(lower.includes('select * from players'))return {...player};
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
        if(lower.includes('update players set username')){player.username=values[0];player.display_name=values[1];player.user_id=values[3]}
        return {success:true};
       }
      };
     },
     async all(){if(lower.includes('from bot_admins'))return {results:[{telegram_id:String(adminId)}]};if(lower.includes('from bot_settings'))return {results:[...settings].map(([key,value])=>({key,value}))};return {results:[]}},
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
  assert.equal(send[0].args.reply_markup.inline_keyboard[0][0].text,'🎮 Ouvrir l’application');
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

test('admin statistics are accessible only through protected callbacks',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:stats'));
  const send=h.calls.find(x=>x.method==='sendMessage');
  assert.ok(send?.args.text.includes('Joueurs : 3'));
  assert.ok(send?.args.text.includes('XP confirmés : 180'));
  assert.ok(send?.args.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==='mrxp:admin:home'));
 }finally{h.restore()}
});

test('admin can cancel a pending text change without changing settings',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:edit_welcome'));
  assert.equal(h.pending.get(String(adminId)).edit_key,'welcome');
  await h.webhook(message(adminId,'/cancel'));
  assert.equal(h.pending.has(String(adminId)),false);
  assert.equal(h.settings.get('welcome'),'🎮 Bienvenue sur Mr XPRONOS Play. Tapote et gagne des XP.');
 }finally{h.restore()}
});

test('public messages cannot overwrite pending admin settings',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:edit_welcome'));
  await h.webhook(message(publicId,'Nouveau faux message d’administration'));
  assert.equal(h.pending.get(String(adminId)).edit_key,'welcome');
  assert.equal(h.settings.get('welcome'),'🎮 Bienvenue sur Mr XPRONOS Play. Tapote et gagne des XP.');
 }finally{h.restore()}
});

test('admin can update Telegram profile description using protected flow',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:edit_description'));
  await h.webhook(message(adminId,'🎮 Jouer gratuitement et collectionner des XP Points.'));
  assert.equal(h.settings.get('description'),'🎮 Jouer gratuitement et collectionner des XP Points.');
  assert.ok(h.calls.some(x=>x.method==='setMyDescription'));
 }finally{h.restore()}
});

function signedTelegramUser(user){
 const params=new URLSearchParams({auth_date:String(Math.floor(Date.now()/1000)),user:JSON.stringify(user)});
 const text=[...params.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([key,value])=>key+'='+value).join('\n');
 const secret=createHmac('sha256','WebAppData').update('fake-token').digest();
 params.set('hash',createHmac('sha256',secret).update(text).digest('hex'));
 return params.toString();
}

test('authenticated Telegram full name is returned for the exact signed user',async()=>{
 const h=harness();
 try{
  const signed=signedTelegramUser({id:44001,first_name:'Aya',last_name:'Kouma',username:'aya_tg'});
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/bootstrap',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(res.status,200);
  const data=await res.json();
  assert.equal(data.user.display_name,'Aya Kouma');
  assert.equal(data.user.username,'aya_tg');
  assert.deepEqual(data.game_features,{tap:true,wheel:true,daily:true,missions:true});
 }finally{h.restore()}
});

test('Mini App uses server-verified display_name and Telegram photo, not brand identity',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  assert.ok(html.includes('state.username=String(r.user.display_name||"").trim()'));
  assert.ok(html.includes('loadTelegramAvatar()'));
  assert.ok(html.includes('avatarInitials(state.username)'));
  assert.ok(!html.includes("avatar.replaceChildren(img(asset.logo,'Logo MX par défaut'))"));
 }finally{h.restore()}
});

test('only approved admin can toggle Lucky Wheel and bootstrap exposes flag',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(publicId,'mrxp:admin:toggle_wheel'));
  assert.equal(h.settings.has('feature_wheel'),false);
  await h.webhook(callback(adminId,'mrxp:admin:toggle_wheel'));
  assert.equal(h.settings.get('feature_wheel'),'0');
  const calls=h.calls.filter(x=>x.method==='sendMessage');
  assert.ok(calls.some(x=>x.args.text.includes('Lucky Wheel')));
  assert.ok(calls.some(x=>x.args.reply_markup?.inline_keyboard?.flat().some(b=>b.callback_data==='mrxp:admin:toggle_wheel')));
  const signed=signedTelegramUser({id:44002,first_name:'Yao',last_name:'Amé',username:'yao_tg'});
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/game-features',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(res.status,200);
  assert.equal((await res.json()).features.wheel,false);
 }finally{h.restore()}
});

test('unauthenticated visitors cannot read game feature configuration',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/game-features'),h.env);
  assert.equal(res.status,401);
 }finally{h.restore()}
});

test('new actions of paused game module cannot be synced',async()=>{
 const h=harness();
 try{
  h.settings.set('feature_tap','0');
  const signed=signedTelegramUser({id:44003,first_name:'Navi',username:'navi'});
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/sync',{method:'POST',headers:{'x-telegram-init-data':signed,'content-type':'application/json'},body:JSON.stringify({batch_id:'1234567890abcdef-abc',taps:1,daily_days:[],wheel_days:[]})}),h.env);
  assert.equal(res.status,423);
  assert.equal((await res.json()).code,'GAME_PAUSED');
 }finally{h.restore()}
});

test('avatar endpoint reads only authenticated user Telegram picture',async()=>{
 const h=harness();
 const oldFetch=globalThis.fetch;
 try{
  const signed=signedTelegramUser({id:44004,first_name:'Aya',last_name:'Kouma'});
  let profileQuery='';
  globalThis.fetch=async(input,options)=>{
   const url=String(input);
   if(url.includes('getUserProfilePhotos')){profileQuery=url;return Response.json({ok:true,result:{photos:[[{file_id:'small'},{file_id:'avatar_id'}]]}})}
   if(url.includes('/getFile?'))return Response.json({ok:true,result:{file_path:'photos/test_avatar.jpg'}});
   if(url.includes('/file/bot'))return new Response(new Uint8Array([255,216,255,217]),{status:200,headers:{'content-type':'image/jpeg'}});
   return oldFetch(input,options);
  };
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/avatar',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(res.status,200);
  assert.equal(res.headers.get('content-type'),'image/jpeg');
  assert.ok(profileQuery.includes('user_id=44004'));
  assert.equal(res.headers.get('cache-control'),'private, no-store');
 }finally{globalThis.fetch=oldFetch;h.restore()}
});
