import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac, createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const code = await readFile(new URL('../worker.js',import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
const url = 'https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook';
const publicId = 222;
const adminId = 111;

function harness(){
 const calls = [], settings = new Map([['welcome','🎮 Bienvenue sur Mr XPRONOS Play. Tapote et gagne des XP.']]);
 const pending = new Map(),missionClaims=new Map(),channelMembership=new Map(),v2Progress=new Map();
 const v2Counts={daily:0,wheel:0};
 const membership={botAdmin:true};
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
        if(lower.includes(' as daily_count'))return {daily_count:v2Counts.daily,wheel_count:v2Counts.wheel,mission_count:[...missionClaims.keys()].filter(x=>x.startsWith(String(values[0])+':')&&!/:(join_main|join_foot)$/.test(x)).length};
        if(lower.includes('from player_progress_v2'))return v2Progress.get(String(values[0]))||null;
        if(lower.includes('from mission_claims'))return missionClaims.has(String(values[0])+':'+String(values[1]))?{mission_key:String(values[1])}:null;
        if(lower.includes('select * from players'))return {...player};
        if(lower.includes('from players'))return {n:rows.players,xp:180};
        if(lower.includes('select xp_awarded from sync_receipts'))return null;
        if(lower.includes('from sync_receipts'))return {n:rows.sync_receipts};
        if(lower.includes('from wheel_claims'))return {n:rows.wheel_claims};
        if(lower.includes('from daily_claims'))return {n:rows.daily_claims};
        return null;
       },
       async run(){
        if(lower.includes('insert or ignore into player_progress_v2')&&!v2Progress.has(String(values[0])))v2Progress.set(String(values[0]),{user_id:String(values[0]),legacy_level_floor:values[1],current_level:values[2]});
        if(lower.includes('update player_progress_v2 set current_level')){const row=v2Progress.get(String(values[2]));if(row)row.current_level=Math.max(Number(row.current_level),Number(values[0]));}
        if(lower.includes('insert into bot_admin_pending'))pending.set(String(values[0]),{edit_key:values[1],expires_ms:values[2]});
        if(lower.includes('delete from bot_admin_pending'))pending.delete(String(values[0]));
        if(lower.includes('insert into bot_settings'))settings.set(values[0],values[1]);
        if(lower.includes('update players set username')){player.username=values[0];player.display_name=values[1];player.user_id=values[3]}
        return {success:true};
       },
       get _sql(){return lower},get _values(){return values},
       async all(){if(lower.includes('from mission_claims'))return {results:[...missionClaims.keys()].filter(x=>x.startsWith(String(values[0])+':')).map(x=>({mission_key:x.slice(String(values[0]).length+1)}))};return {results:[]}}
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
   },
   async batch(ops){
    let applied=0;
    for(const op of ops){
     if(op._sql?.includes('insert or ignore into mission_claims')){
      const [id,key,xp]=op._values;const claimId=String(id)+':'+String(key);
      applied=missionClaims.has(claimId)?0:1;
      if(applied)missionClaims.set(claimId,{xp});
     }else if(op._sql?.includes('update players set confirmed_xp')){
      if(applied)player.confirmed_xp+=Number(op._values[0]);
     }
    }
    return [{success:true,meta:{changes:applied}},{success:true,meta:{changes:applied}}];
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
  if(method==='getMe')result={id:99,username:'MrXpronosPlayBot'};
  if(method==='getChat')result={id:-100123,title:'Test '+(JSON.parse(init.body).chat_id||'')};
  if(method==='getChatMember'){const args=JSON.parse(init.body);result=Number(args.user_id)===99?{status:membership.botAdmin?'administrator':'member'}:{status:channelMembership.get(args.chat_id)||'left'}};
  return Response.json({ok:true,result});
 };
 return {
  env,calls,settings,pending,missionClaims,channelMembership,membership,player,v2Progress,v2Counts,
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
 h.env.DEV_MODE='true';
 try{
  const signed=signedTelegramUser({id:44001,first_name:'Aya',last_name:'Kouma',username:'aya_tg'});
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/bootstrap',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(res.status,200,await res.clone().text());
  const data=await res.json();
  assert.equal(data.user.display_name,'Aya Kouma');
  assert.equal(data.user.username,'aya_tg');
  assert.deepEqual(data.game_features,{tap:true,wheel:true,daily:true,missions:true});
 }finally{h.restore()}
});

test('Mini App uses the verified Telegram display name but the official rank portrait',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  assert.ok(html.includes('state.username=String(r.user.display_name||"").trim()'));
  assert.ok(html.includes('renderRankAvatar()'));
  assert.ok(html.includes('rank-01-recrue.webp'));
  assert.ok(html.includes('rank-02-eclaireur.webp'));
  assert.ok(!html.includes('loadTelegramAvatar()'));
  assert.ok(!html.includes('id="photo-refresh"'));
  assert.ok(!html.includes('Photo Telegram en attente'));
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

test('all six server missions are visible to the signed Telegram user',async()=>{
 const h=harness();
 try{
  const signed=signedTelegramUser({id:50001,first_name:'Dayo'});
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/bootstrap',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(res.status,200,await res.clone().text());
  const data=await res.json();
  assert.equal(data.missions.length,6);
  assert.deepEqual(data.missions.filter(m=>m.kind==='channel').map(m=>m.channel),['@mrxpronosfr','@actufoot_mrxp']);
  assert.equal(data.missions.find(m=>m.key==='first_open').xp,25);
 }finally{h.restore()}
});

async function claimMissionForTest(h,userId,key){
 const signed=signedTelegramUser({id:userId,first_name:'Test'});
 return worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/missions/claim',{
  method:'POST',headers:{'content-type':'application/json','x-telegram-init-data':signed},
  body:JSON.stringify({mission_key:key})
 }),h.env);
}

test('welcome reward can be claimed only once even on repeated requests',async()=>{
 const h=harness();
 try{
  let r=await claimMissionForTest(h,50002,'first_open');
  assert.equal(r.status,200,await r.clone().text());
  assert.equal((await r.json()).awarded,25);
  r=await claimMissionForTest(h,50002,'first_open');
  assert.equal((await r.json()).awarded,0);
  assert.equal(h.player.confirmed_xp,25);
  assert.equal(h.missionClaims.size,1);
 }finally{h.restore()}
});

test('50, 200 and 500 tap missions are independent and reward all thresholds once',async()=>{
 const h=harness();
 try{
  let r=await claimMissionForTest(h,50003,'tap_50');
  assert.equal(r.status,409);
  h.player.confirmed_taps=500;
  for(const [key,xp] of [['tap_500',150],['tap_50',40],['tap_200',75]]){
   r=await claimMissionForTest(h,50003,key);
   assert.equal(r.status,200,await r.clone().text());
   assert.equal((await r.json()).awarded,xp);
  }
  assert.equal(h.player.confirmed_xp,265);
  r=await claimMissionForTest(h,50003,'tap_200');
  assert.equal((await r.json()).awarded,0);
  assert.equal(h.player.confirmed_xp,265);
 }finally{h.restore()}
});

test('channel missions require bot admin access and real membership, then reward once',async()=>{
 const h=harness();
 try{
  h.membership.botAdmin=false;
  let r=await claimMissionForTest(h,50004,'join_main');
  assert.equal(r.status,503);
  assert.equal((await r.json()).code,'BOT_NOT_ADMIN');
  h.membership.botAdmin=true;
  r=await claimMissionForTest(h,50004,'join_main');
  assert.equal(r.status,409);
  assert.equal((await r.json()).code,'NOT_JOINED');
  h.channelMembership.set('@mrxpronosfr','member');
  r=await claimMissionForTest(h,50004,'join_main');
  assert.equal(r.status,200);
  assert.equal((await r.json()).awarded,100);
  h.channelMembership.set('@actufoot_mrxp','member');
  r=await claimMissionForTest(h,50004,'join_foot');
  assert.equal((await r.json()).awarded,100);
  r=await claimMissionForTest(h,50004,'join_main');
  assert.equal((await r.json()).awarded,0);
  assert.equal(h.player.confirmed_xp,200);
 }finally{h.restore()}
});

test('unclaimed channel missions persist on subsequent visits until joined',async()=>{
 const h=harness();
 try{
  const signed=signedTelegramUser({id:50005,first_name:'Test'});
  const check=()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/missions',{headers:{'x-telegram-init-data':signed}}),h.env);
  let r=await check(),m=(await r.json()).missions;
  assert.equal(m.find(x=>x.key==='join_main').claimed,false);
  assert.equal(m.find(x=>x.key==='join_foot').claimed,false);
  h.channelMembership.set('@mrxpronosfr','member');
  await claimMissionForTest(h,50005,'join_main');
  r=await check();m=(await r.json()).missions;
  assert.equal(m.find(x=>x.key==='join_main').claimed,true);
  assert.equal(m.find(x=>x.key==='join_foot').claimed,false);
 }finally{h.restore()}
});

test('mission API blocks unauthenticated visitors and paused missions',async()=>{
 const h=harness();
 try{
  const unauth=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/missions'),h.env);
  assert.equal(unauth.status,401);
  h.settings.set('feature_missions','0');
  const res=await claimMissionForTest(h,50006,'first_open');
  assert.equal(res.status,423);
  assert.equal((await res.json()).code,'MISSIONS_PAUSED');
 }finally{h.restore()}
});

test('photo URL originates from validated signed Telegram initData',async()=>{
 const h=harness();
 try{
  const original='https://t.me/i/userpic/320/example.jpg';
  const signed=signedTelegramUser({id:50007,first_name:'Photo',photo_url:original});
  const result=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/bootstrap',{headers:{'x-telegram-init-data':signed}}),h.env);
  assert.equal(result.status,200);
  assert.equal((await result.json()).telegram_photo_url,original);
  const page=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await page.text();
  assert.ok(!html.includes('signedPhotoUrl=r.telegram_photo_url||""'));
  assert.ok(!html.includes('photo-refresh'));
  assert.ok(!html.includes('tryTelegramPhotoFallback()'));
  assert.ok(html.includes('RANK_AVATAR_ROOT'));
 }finally{h.restore()}
});

test('lot 6 retains its 16 files within the expanded 60-icon catalog',async()=>{
 const main=JSON.parse(await readFile(new URL('../assets-manifest.json',import.meta.url),'utf8'));
 const lot=JSON.parse(await readFile(new URL('../assets-manifest-lot6.json',import.meta.url),'utf8'));
 assert.equal(main.asset_count,60);
 assert.equal(main.assets.length,60);
 assert.equal(lot.assets.length,8);
 assert.deepEqual(main.assets.slice(50,58).map(x=>x.number),[51,52,53,54,55,56,57,58]);
 for(const x of lot.assets){
  assert.ok(main.assets.some(y=>y.number===x.number&&y.webp===x.webp&&y.png===x.png));
  const png=await readFile(new URL('../'+x.png,import.meta.url));
  const webp=await readFile(new URL('../'+x.webp,import.meta.url));
  assert.equal(png.length,x.png_size_bytes,x.png);
  assert.equal(webp.length,x.webp_size_bytes,x.webp);
  assert.equal(createHash('sha256').update(png).digest('hex'),x.sha256_png,x.png);
  assert.equal(png.toString('hex',0,8),'89504e470d0a1a0a');
  assert.equal(webp.toString('ascii',0,4),'RIFF');
  assert.equal(webp.toString('ascii',8,12),'WEBP');
 }
});

test('the Mini App loads lot 6 splash, spinner, mission status, energy and victory assets',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  for(const key of ['51-locked-padlock.webp','52-unlocked-padlock','53-launch-splash.webp','54-loading-spinner.webp','55-telegram-channel','56-victory-trophy.webp','57-energy-empty.webp','58-mission-complete','hideLaunchScreen']){
   assert.ok(html.includes(key),'Missing UI asset reference: '+key);
  }
  assert.ok(html.includes('mrxp-launch-overlay'));
  assert.ok(html.includes('setTimeout(hideLaunchScreen,9000)'));
 }finally{h.restore()}
});

test('rank avatar catalog has 11 validated African portraits and 22 hash-verified image files',async()=>{
 const highDefPng=await readFile(new URL('../assets/07-rank-avatars/rank-11-souverain-mx.png',import.meta.url));
 const highDefWebp=await readFile(new URL('../assets/07-rank-avatars/rank-11-souverain-mx.webp',import.meta.url));
 assert.equal(highDefPng.length,2616419);
 assert.equal(highDefWebp.length,237800);
 assert.equal(highDefPng.readUInt32BE(16),1254);
 assert.equal(highDefPng.readUInt32BE(20),1254);
 assert.ok(highDefWebp.length>200000);

 const manifest=JSON.parse(await readFile(new URL('../avatars-manifest.json',import.meta.url),'utf8'));
 assert.equal(manifest.avatar_count,11);
 assert.equal(manifest.avatars.length,11);
 assert.deepEqual(manifest.avatars.map(x=>[x.rank,x.slug,x.min_level,x.max_level]),[
  [1,'recrue',1,1],[2,'eclaireur',2,2],[3,'combattant',3,4],
  [4,'sentinelle',5,5],[5,'chevalier',6,9],
  [6,'elite',10,14],[7,'maitre',15,19],[8,'champion',20,29],
  [9,'legende',30,39],[10,'mythique',40,49],[11,'souverain-mx',50,999999]
 ]);
 for(const avatar of manifest.avatars){
  for(const kind of ['png','webp']){
   const p=avatar[kind];const buf=await readFile(new URL('../'+p.replace(/^mrxpronos-play\//,''),import.meta.url));
   assert.equal(buf.length,avatar[kind+'_bytes'],p);
   assert.equal(createHash('sha256').update(buf).digest('hex'),avatar['sha256_'+kind],p);
   if(kind==='png'){
    assert.equal(buf.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
    assert.equal(buf.readUInt8(25),6,'Expected RGBA PNG for '+p);
   }else{
    assert.equal(buf.toString('ascii',0,4),'RIFF');
    assert.equal(buf.toString('ascii',8,12),'WEBP');
   }
  }
  assert.equal(avatar.transparent,true);
 }
});

test('rank portrait mapping matches all 11 approved ranks including Souverain MX',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  for(const [start,stop,name,image] of [
   [1,1,'Recrue','rank-01-recrue.webp'],[2,2,'Éclaireur','rank-02-eclaireur.webp'],
   [3,4,'Combattant','rank-03-combattant.webp'],[5,5,'Sentinelle','rank-04-sentinelle.webp'],
   [6,9,'Chevalier','rank-05-chevalier.webp'],
   [10,14,'Élite','rank-06-elite.webp'],[15,19,'Maître','rank-07-maitre.webp'],
   [20,29,'Champion','rank-08-champion.webp'],[30,39,'Légende','rank-09-legende.webp'],
   [40,49,'Mythique','rank-10-mythique.webp'],[50,999999,'Souverain MX','rank-11-souverain-mx.webp']]){
    assert.ok(html.includes('from:'+start+',to:'+stop+',name:"'+name+'",image:"'+image+'"'),name);
  }
  assert.ok(html.includes('from:10,to:14,name:"Élite",image:"rank-06-elite.webp"'));
  assert.ok(html.includes('from:50,to:999999,name:"Souverain MX",image:"rank-11-souverain-mx.webp"'));
  assert.ok(html.includes('rank-11-souverain-mx.webp"?"?v=hd-20261119"'));
  assert.ok(html.includes('const servedSource=source+'));
  assert.ok(html.includes('RANK_BRAND_FALLBACK'));
  assert.ok(html.includes('window.refreshRankAvatar?.()'));
  assert.ok(html.includes('const source=rank.image?RANK_AVATAR_ROOT+rank.image:RANK_BRAND_FALLBACK'));
  assert.ok(!html.includes('getUserProfilePhotos?user_id'));
 }finally{h.restore()}
});

test('new information circle and crowned shield icons have intact PNG/WebP files',async()=>{
 const data=JSON.parse(await readFile(new URL('../assets-manifest-ui-actions.json',import.meta.url),'utf8'));
 const globalManifest=JSON.parse(await readFile(new URL('../assets-manifest.json',import.meta.url),'utf8'));
 assert.equal(globalManifest.asset_count,60);
 assert.equal(globalManifest.assets.length,60);
 assert.deepEqual(data.assets.map(x=>x.number),[59,60]);
 for(const item of data.assets){
  assert.equal(item.transparent,true);
  assert.deepEqual(item.dimensions_png,[1254,1254]);
  assert.deepEqual(item.dimensions_webp,[512,512]);
  for(const type of ['png','webp']){
   const filename='../'+item[type];
   const buffer=await readFile(new URL(filename,import.meta.url));
   assert.equal(buffer.length,item[type+'_bytes'],item[type]);
   assert.equal(createHash('sha256').update(buffer).digest('hex'),item['sha256_'+type],item[type]);
   if(type==='png'){
    assert.equal(buffer.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
    assert.equal(buffer.readUInt32BE(16),1254);
    assert.equal(buffer.readUInt32BE(20),1254);
    assert.equal(buffer[25],6);
   }else{
    assert.equal(buffer.toString('ascii',0,4),'RIFF');
    assert.equal(buffer.toString('ascii',8,12),'WEBP');
   }
  }
 }
});

test('Mini App actually renders the new information and crowned rank shield images',async()=>{
 const h=harness();
 try{
  const response=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(response.status,200);
  const html=await response.text();
  assert.ok(html.includes('59-info-circle.webp?v=20261119'));
  assert.ok(html.includes("rankShield:a('08-ui-actions','60-crowned-shield')+'?v=20261119'"));
  assert.ok(html.includes("profile.appendChild(img(asset.rankShield,'Bouclier de rang couronné','hero-badge'))"));
  assert.ok(html.includes('id="info-btn" aria-label="Informations"><img'));
  assert.ok(html.includes('$("info-btn").onclick='));
  assert.ok(!html.includes('Informations">ⓘ</button>'));
  assert.ok(!html.includes("profile.appendChild(img(asset.crown"));
 }finally{h.restore()}
});

test('V2 refuses progression queries without a valid signed Telegram identity',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression'),h.env);
  assert.equal(res.status,401);
 }finally{h.restore()}
});

test('V2 levels use only confirmed XP and preserve the previous confirmed-taps level',async()=>{
 const h=harness();h.env.DEV_MODE='true';const init=signedTelegramUser({id:77001,first_name:'Joueuse'});
 const get=async()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression',{headers:{'x-telegram-init-data':init}}),h.env);
 try{
  h.player.confirmed_xp=0;h.player.confirmed_taps=0;
  let r=await get();assert.equal(r.status,200,await r.clone().text());let data=(await r.json()).progression;
  assert.equal(data.level,1);assert.equal(data.version,2);assert.equal(data.xp_to_next,300);
  h.player.confirmed_xp=300;r=await get();assert.equal((await r.json()).progression.level,2);
  h.player.confirmed_xp=764;r=await get();assert.equal((await r.json()).progression.level,3);
  assert.equal(h.v2Progress.get('77001').legacy_level_floor,1);
 }finally{h.restore()}
});

test('V2 migration freezes the legacy level floor without resetting XP or tap counters',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=125;h.player.confirmed_taps=30250;
 const init=signedTelegramUser({id:77002,first_name:'Ancien'});
 const get=async()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression',{headers:{'x-telegram-init-data':init}}),h.env);
 try{
  let r=await get();assert.equal(r.status,200,await r.clone().text());let d=(await r.json()).progression;
  assert.equal(d.level,12);assert.equal(d.legacy_level_floor,12);
  assert.equal(h.player.confirmed_xp,125);assert.equal(h.player.confirmed_taps,30250);
  h.player.confirmed_taps=0;r=await get();d=(await r.json()).progression;
  assert.equal(d.level,12);assert.equal(d.legacy_level_floor,12);
 }finally{h.restore()}
});

test('V2 rank gates block on missing mastery and unlock automatically once independently verified',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=2330;h.player.confirmed_taps=0;
 const init=signedTelegramUser({id:77003,first_name:'Défis'});
 const get=async()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression',{headers:{'x-telegram-init-data':init}}),h.env);
 try{
  let r=await get();assert.equal(r.status,200,await r.clone().text());let d=(await r.json()).progression;
  assert.equal(d.level,4);assert.equal(d.blocked_by_mastery,true);
  assert.equal(d.required_mastery,2);
  h.player.confirmed_taps=200;
  r=await get();d=(await r.json()).progression;
  assert.equal(d.level,5);assert.equal(d.blocked_by_mastery,false);
  assert.ok(d.mastery.completed>=2);
 }finally{h.restore()}
});

test('V2 level 50 requires mastery gates and caps at 50 with no Telegram channel dependency',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=1000000;h.player.confirmed_taps=400000;
 h.v2Counts.daily=80;h.v2Counts.wheel=80;
 const init=signedTelegramUser({id:77004,first_name:'Souverain'});
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression',{headers:{'x-telegram-init-data':init}}),h.env);
  assert.equal(res.status,200,await res.clone().text());const p=(await res.json()).progression;
  assert.equal(p.level,50);assert.equal(p.rank,'Souverain MX');
  assert.equal(p.mastery.next_gate,null);assert.equal(p.xp_to_next,0);
  assert.ok(p.mastery.completed>=18);assert.equal(h.missionClaims.size,0);
 }finally{h.restore()}
});

test('V2 games hub shows Lucky Wheel as playable and Snake as a disabled future game',async()=>{
 const h=harness();
 try{
  const page=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(page.status,200);const html=await page.text();
  assert.ok(html.includes('>JEUX</button>'));assert.ok(html.includes('id="mrxp-games-hub"'));
  assert.ok(html.includes('id="mrxp-wheel-game" hidden'));assert.ok(html.includes('id="wheel-button"'));
  assert.ok(html.includes('id="mrxp-open-wheel"'));assert.ok(html.includes('Snake à venir'));
  assert.ok(html.includes('window.openWheel=openWheel'));assert.ok(html.includes('mrxp-mastery-list'));
  assert.ok(html.includes('state.progression=r.progression||null'));
 }finally{h.restore()}
});

test('V2 progression migration is strictly additive to D1',async()=>{
 const sql=await readFile(new URL('../migrations/002_hybrid_progression.sql',import.meta.url),'utf8');
 assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS player_progress_v2'));
 assert.ok(!/DROP TABLE|DELETE FROM players|UPDATE players SET confirmed_xp/i.test(sql));
 const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
 assert.ok(schema.includes('CREATE TABLE IF NOT EXISTS player_progress_v2'));
});

test('V2 initializes a legacy migration before a direct /api/sync request, even without bootstrap',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_taps=30250;h.player.confirmed_xp=120;
 const init=signedTelegramUser({id:77005,first_name:'Synchronisation directe'});
 try{
  const req=new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/sync',{method:'POST',headers:{'x-telegram-init-data':init,'content-type':'application/json'},body:JSON.stringify({batch_id:'invalid',taps:999})});
  const res=await worker.fetch(req,h.env);
  assert.equal(res.status,400);
  const migrated=h.v2Progress.get('77005');
  assert.ok(migrated);assert.equal(migrated.legacy_level_floor,12);
  assert.equal(h.player.confirmed_taps,30250);
  h.player.confirmed_taps=0;
  const get=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/progression',{headers:{'x-telegram-init-data':init}}),h.env);
  assert.equal((await get.json()).progression.level,12);
 }finally{h.restore()}
});

test('V2 bootstrap and missions both return one coherent server-backed progression',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=764;h.player.confirmed_taps=200;
 const init=signedTelegramUser({id:77006,first_name:'Test api'});
 try{
  for(const path of ['/api/bootstrap','/api/missions']){
   const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev'+path,{headers:{'x-telegram-init-data':init}}),h.env);
   assert.equal(res.status,200,await res.clone().text());const data=await res.json();
   assert.equal(data.progression.level,3);
   assert.equal(data.progression.confirmed_xp,764);
   assert.ok(Array.isArray(data.progression.mastery.challenges));
   assert.ok(data.progression.mastery.challenges.length>=20);
  }
 }finally{h.restore()}
});

test('V2 sent levels never trust browser stored levels for authenticated rankings',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  assert.ok(html.includes('state.progression=null;/* Never trust locally restored ranks as official. */'));
  assert.ok(html.includes('const source=rank.image?RANK_AVATAR_ROOT+rank.image:RANK_BRAND_FALLBACK'));
  assert.ok(!html.includes('function level(){return Math.max(1,Math.floor(Math.sqrt('));
 }finally{h.restore()}
});
