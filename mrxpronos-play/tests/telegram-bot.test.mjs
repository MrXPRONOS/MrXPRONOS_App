import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHmac, createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const code = await readFile(new URL('../worker.js',import.meta.url), 'utf8');
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
const url = 'https://mrxpronos-play.cinecanaux-xpronos.workers.dev/telegram/webhook';
const publicId = 222;
const adminId = 111;

function harness(){
 const calls = [], settings = new Map([['welcome','🎮 Bienvenue sur Mr XPRONOS Play. Tapote et gagne des XP.']]),balanceAudit=[],settingUpdated=new Map();
 const pending = new Map(),missionClaims=new Map(),channelMembership=new Map(),v2Progress=new Map(),avatarPrefs=new Map(),creditBaselines=new Map(),creditEvents=new Map();
 const verifiedDaily=[],verifiedWheel=[],verifiedTaps=[],boostInventory=new Map(),boostReceipts=new Map();
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
        if(lower.includes('from player_credit_state'))return creditBaselines.get(String(values[0]))||null;
        if(lower.includes('from mrxp_credit_events')&&lower.includes('sum(amount)')){const list=[...creditEvents.values()].filter(x=>x.user_id===String(values[0]));return {balance:list.reduce((a,x)=>a+x.amount,0),event_count:list.length}}
        if(lower.includes('count(*) as total from mission_claims'))return {total:[...missionClaims.keys()].filter(x=>x.startsWith(String(values[0])+':')).length};
        if(lower.includes('from mrxp_boost_inventory')){
         const id=String(values[0]),list=[...boostInventory.values()].filter(x=>x.user_id===id);
         if(lower.includes('count(*) as n'))return {n:list.filter(x=>x.bought_ms>=Number(values[1])).length};
         if(lower.includes('purchase_id=?'))return list.find(x=>x.purchase_id===String(values[1]))||null;
         if(lower.includes("kind='tap'"))return list.find(x=>x.kind==='tap'&&(x.state==='queued'||(x.state==='active'&&x.expires_ms>Number(values[1]))))||null;
         if(lower.includes("kind='energy'"))return list.find(x=>x.kind==='energy'&&x.state==='charged'&&x.expires_ms>Number(values[1]))||null;
         if(lower.includes('kind=?'))return list.find(x=>x.kind===String(values[1])&&[String(values[2]),String(values[3])].includes(x.state))||null;
         return null;
        }
        if(lower.includes('from player_avatar_prefs'))return avatarPrefs.has(String(values[0]))?{selected_rank:avatarPrefs.get(String(values[0]))}:null;
        if(lower.includes('from player_progress_v2'))return v2Progress.get(String(values[0]))||null;
        if(lower.includes('from mission_claims'))return missionClaims.has(String(values[0])+':'+String(values[1]))?{mission_key:String(values[1])}:null;
        if(lower.includes('select * from players'))return {...player};
        if(lower.includes('from players'))return {n:rows.players,xp:180};
        if(lower.includes('select xp_awarded from sync_receipts'))return boostReceipts.get(String(values[0])+':'+String(values[1]))||null;
        if(lower.includes('from sync_receipts'))return {n:rows.sync_receipts};
        if(lower.includes('from wheel_claims'))return {n:rows.wheel_claims};
        if(lower.includes('from daily_claims'))return {n:rows.daily_claims};
        return null;
       },
       async run(){
        if(lower.includes("update mrxp_boost_inventory set state='expired'")){
          let changes=0;
          for(const b of boostInventory.values()){if(b.user_id===String(values[0])&&['active','charged'].includes(b.state)&&b.expires_ms>0&&b.expires_ms<=Number(values[1])){b.state='expired';changes++}}
          return {success:true,meta:{changes}};
        }
        if(lower.includes("update mrxp_boost_inventory set state='queued'")){
          const b=boostInventory.get(String(values[0])+':'+String(values[1]));
          const active=[...boostInventory.values()].some(x=>x.user_id===String(values[0])&&x.purchase_id!==String(values[1])&&x.kind==='tap'&&['queued','active'].includes(x.state));
          if(!b||b.state!=='owned'||active)return {success:true,meta:{changes:0}};
          b.state='queued';return {success:true,meta:{changes:1}};
        }
        if(lower.includes("update mrxp_boost_inventory set state='charged'")){
          const b=boostInventory.get(String(values[2])+':'+String(values[3]));
          const active=[...boostInventory.values()].some(x=>x.user_id===String(values[2])&&x.purchase_id!==String(values[3])&&x.kind==='energy'&&x.state==='charged');
          if(!b||b.state!=='owned'||active)return {success:true,meta:{changes:0}};
          b.state='charged';b.activated_ms=values[0];b.expires_ms=values[1];return {success:true,meta:{changes:1}};
        }
        if(lower.includes('insert or ignore into player_credit_state')&&!creditBaselines.has(String(values[0])))creditBaselines.set(String(values[0]),{baseline_level:values[1],activated_ms:values[2]});
        if(lower.includes('insert into player_avatar_prefs'))avatarPrefs.set(String(values[0]),values[1]);
        if(lower.includes('insert or ignore into player_progress_v2')&&!v2Progress.has(String(values[0])))v2Progress.set(String(values[0]),{user_id:String(values[0]),legacy_level_floor:values[1],current_level:values[2]});
        if(lower.includes('update player_progress_v2 set current_level')){const row=v2Progress.get(String(values[2]));if(row)row.current_level=Math.max(Number(row.current_level),Number(values[0]));}
        if(lower.includes('insert into bot_admin_pending'))pending.set(String(values[0]),{edit_key:values[1],expires_ms:values[2]});
        if(lower.includes('delete from bot_admin_pending'))pending.delete(String(values[0]));
        if(lower.includes('insert into bot_settings'))settings.set(values[0],values[1]);
        if(lower.includes('update players set username')){player.username=values[0];player.display_name=values[1];player.user_id=values[3]}
        return {success:true};
       },
       get _sql(){return lower},get _values(){return values},
       async all(){
        const id=String(values[0]);
        if(lower.includes('from mrxp_boost_inventory'))return {results:[...boostInventory.values()].filter(x=>x.user_id===id).sort((a,b)=>b.bought_ms-a.bought_ms).slice(0,100)};
        if(lower.includes('from mrxp_credit_events')){
          const list=[...creditEvents.values()].filter(x=>x.user_id===id);
          if(lower.includes('select event_key from'))return {results:list.map(x=>({event_key:x.event_key}))};
          return {results:list.sort((a,b)=>b.created_ms-a.created_ms).slice(0,50).map(x=>({...x}))};
        }
        if(lower.includes('from daily_claims'))return {results:verifiedDaily.filter(x=>x.user_id===id&&x.created_ms>=Number(values[1]))};
        if(lower.includes('from wheel_claims'))return {results:verifiedWheel.filter(x=>x.user_id===id&&x.created_ms>=Number(values[1]))};
        if(lower.includes('from sync_receipts'))return {results:verifiedTaps.filter(x=>x.user_id===id&&x.created_ms>=Number(values[1])&&x.taps>=50)};
        if(lower.includes('from mission_claims')){
         if(lower.includes('select mission_key,created_ms'))return {results:[...missionClaims.entries()].filter(([k,v])=>k.startsWith(id+':')&&Number(v.created_ms||0)>=Number(values[1])).map(([k,v])=>({mission_key:k.slice(id.length+1),created_ms:v.created_ms}))};
         return {results:[...missionClaims.keys()].filter(x=>x.startsWith(id+':')).map(x=>({mission_key:x.slice(id.length+1)}))}
        }
        return {results:[]}
       }
      };
     },
     async all(){if(lower.includes('from bot_admins'))return {results:[{telegram_id:String(adminId)}]};if(lower.includes('from bot_settings'))return {results:[...settings].map(([key,value])=>({key,value,updated_ms:settingUpdated.get(key)||0}))};return {results:[]}},
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
    if(ops[0]?._sql?.includes('insert into mrxp_balance_audit')){
     const [admin_id,setting_key,old_value,new_value,created_ms]=ops[0]._values;
     balanceAudit.push({admin_id,setting_key,old_value,new_value,created_ms});
     settings.set(ops[1]._values[0],ops[1]._values[1]);settingUpdated.set(ops[1]._values[0],ops[1]._values[2]);
     return ops.map(()=>({success:true,meta:{changes:1}}))
    }
    if(ops[0]?._sql?.includes('insert or ignore into mrxp_boost_inventory')){
     const [id,purchaseId,sku,kind,cost,ms]=ops[0]._values;
     const key=String(id)+':'+purchaseId,balance=[...creditEvents.values()].filter(x=>x.user_id===String(id)).reduce((a,x)=>a+Number(x.amount),0);
     const limit=Number(ops[0]._values[10]),start=Number(ops[0]._values[9]);const count=[...boostInventory.values()].filter(x=>x.user_id===String(id)&&x.bought_ms>=start).length;
     if(boostInventory.has(key)||balance<Number(cost)||count>=limit)return [{success:true,meta:{changes:0}},{success:true,meta:{changes:0}}];
     boostInventory.set(key,{user_id:String(id),purchase_id:purchaseId,sku,kind,cost,state:'owned',bought_ms:ms,activated_ms:0,expires_ms:0,carry_milli:0});
     const eventKey=String(id)+':buy:'+purchaseId;
     if(creditEvents.has(eventKey))throw Error('Duplicate purchase debit');
     creditEvents.set(eventKey,{user_id:String(id),event_key:'buy:'+purchaseId,event_type:'purchase',amount:-cost,label:'shop',created_ms:ms});
     return [{success:true,meta:{changes:1}},{success:true,meta:{changes:1}}];
    }
    if(ops[0]?._sql?.includes('update players set confirmed_xp=confirmed_xp+')&&ops[0]?._sql?.includes('confirmed_taps')){
     const p=ops[0]._values,now=p[2],batchId=p[8],id=String(p[5]),receiptKey=id+':'+batchId;
     if(boostReceipts.has(receiptKey)||player.next_sync_ms>now)return ops.map(()=>({success:true,meta:{changes:0}}));
     player.confirmed_xp+=p[0];player.confirmed_taps+=p[1];player.last_sync_ms=now;player.next_sync_ms=p[3];
     boostReceipts.set(receiptKey,{xp_awarded:p[0],taps:p[1]});
     for(const op of ops.slice(2)){
      const row=op._values||[];
      if(op._sql.includes("update mrxp_boost_inventory set state='active'")){
       const b=boostInventory.get(String(row[3])+':'+String(row[4]));if(b){
        if(b.state==='queued'){b.state='active';b.activated_ms=row[0];b.expires_ms=row[1]}
        b.carry_milli=row[2]
       }
      }
      if(op._sql.includes("update mrxp_boost_inventory set state='used'")){
       const b=boostInventory.get(String(row[0])+':'+String(row[1]));if(b)b.state='used'
      }
     }
     return ops.map(()=>({success:true,meta:{changes:1}}))
    }
    if(ops.length&&ops.every(op=>op._sql?.includes('insert or ignore into mrxp_credit_events'))){
      return ops.map(op=>{const [user_id,event_key,event_type,amount,label,created_ms]=op._values,key=String(user_id)+':'+event_key;
       const isNew=!creditEvents.has(key);
       if(isNew)creditEvents.set(key,{user_id:String(user_id),event_key,event_type,amount,label,created_ms});
       return {success:true,meta:{changes:isNew?1:0}}
      })
    }
    let applied=0;
    for(const op of ops){
     if(op._sql?.includes('insert or ignore into mission_claims')){
      const [id,key,xp]=op._values;const claimId=String(id)+':'+String(key);
      applied=missionClaims.has(claimId)?0:1;
      if(applied)missionClaims.set(claimId,{xp,created_ms:Date.now()});
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
  env,calls,settings,pending,missionClaims,channelMembership,membership,player,v2Progress,v2Counts,avatarPrefs,creditBaselines,creditEvents,verifiedDaily,verifiedWheel,verifiedTaps,boostInventory,boostReceipts,balanceAudit,settingUpdated,
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
  assert.ok(html.includes('const source=selectedPortrait.image?RANK_AVATAR_ROOT+selectedPortrait.image:RANK_BRAND_FALLBACK'));
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
  assert.ok(html.includes("profile.appendChild(img(a('09-rank-badges','61-recrue-badge'),'Badge officiel de rang','hero-badge'))"));
  assert.ok(html.includes('heroBadge.dataset.rankBadge'),'Hero shield must follow the official rank');
  assert.ok(html.includes('mrxpV2RankIcon(officialIndex+1)'));
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
  assert.ok(html.includes('state.progression=null;state.profile=null;mrxpConfirmedWallet=null;mrxpShop=null;/* Never trust locally restored ranks, avatar choices, shop objects or credit balances as official. */'));
  assert.ok(html.includes('const source=selectedPortrait.image?RANK_AVATAR_ROOT+selectedPortrait.image:RANK_BRAND_FALLBACK'));
  assert.ok(!html.includes('function level(){return Math.max(1,Math.floor(Math.sqrt('));
 }finally{h.restore()}
});

test('V2 phase 2 requires signed Telegram identity to read or edit profile avatars',async()=>{
 const h=harness();
 try{
  const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
  const get=await worker.fetch(new Request(root+'/api/profile'),h.env);
  const change=await worker.fetch(new Request(root+'/api/profile/avatar',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({rank:11})}),h.env);
  assert.equal(get.status,401);assert.equal(change.status,401);assert.equal(h.avatarPrefs.size,0);
 }finally{h.restore()}
});

test('V2 phase 2 returns 11 official African avatars with server-verified lock states',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const init=signedTelegramUser({id:88001,first_name:'Joueuse',username:'mrxp_test'});
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/profile',{headers:{'x-telegram-init-data':init}}),h.env);
  assert.equal(res.status,200,await res.clone().text());const {progression:p,profile}=await res.json();
  assert.equal(p.level,1);assert.equal(profile.current_rank_id,1);assert.equal(profile.selected_rank_id,1);
  assert.equal(profile.selection_mode,'auto');assert.equal(profile.collection.length,11);
  assert.equal(profile.unlocked_count,1);assert.equal(profile.collection[0].unlocked,true);
  assert.equal(profile.collection[0].selected,true);assert.equal(profile.collection[1].unlocked,false);
  assert.equal(profile.collection[10].from,50);assert.equal(profile.collection[10].name,'Souverain MX');
  assert.equal(profile.cosmetics_only,true);
 }finally{h.restore()}
});

test('V2 phase 2 blocks locked avatars, invalid rank IDs and cannot grant an upgrade by selecting appearance',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=300;h.player.confirmed_taps=0;
 const init=signedTelegramUser({id:88002,first_name:'Nouveau'});
 const post=async body=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/profile/avatar',{method:'POST',headers:{'x-telegram-init-data':init,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  const invalid=[{rank:-1},{rank:12},{rank:1.5},{rank:"2"},{rank:null},{rank:99999}];
  for(const body of invalid){const r=await post(body);assert.equal(r.status,400,await r.clone().text())}
  const locked=await post({rank:11});assert.equal(locked.status,403,await locked.clone().text());
  assert.equal((await locked.json()).code,'AVATAR_LOCKED');
  assert.equal(h.avatarPrefs.size,0);
  assert.equal(h.player.confirmed_xp,300);assert.equal(h.v2Progress.get('88002').current_level,2);
 }finally{h.restore()}
});

test('V2 phase 2 saves unlocked avatar choices per account without changing the official badge and resets to automatic',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=2330;h.player.confirmed_taps=200;
 const alice=signedTelegramUser({id:88003,first_name:'Alice'});
 const bob=signedTelegramUser({id:88004,first_name:'Bob'});
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 const read=async (init=alice)=>worker.fetch(new Request(root+'/api/profile',{headers:{'x-telegram-init-data':init}}),h.env);
 const choose=async (init,rank)=>worker.fetch(new Request(root+'/api/profile/avatar',{method:'POST',headers:{'x-telegram-init-data':init,'content-type':'application/json'},body:JSON.stringify({rank})}),h.env);
 try{
  const first=await read();const initial=await first.json();assert.equal(initial.progression.level,5);
  assert.equal(initial.profile.current_rank_id,4);assert.equal(initial.profile.unlocked_count,4);
  const changed=await choose(alice,2);assert.equal(changed.status,200,await changed.clone().text());
  const data=await changed.json();assert.equal(data.profile.selected_rank_id,2);
  assert.equal(data.profile.avatar_image,'rank-02-eclaireur.webp');
  assert.equal(data.profile.selection_mode,'custom');
  assert.equal(data.profile.current_rank_id,4);assert.equal(data.progression.level,5);
  assert.equal(data.profile.rank,'Sentinelle');
  assert.equal(h.player.confirmed_xp,2330);assert.equal(h.player.confirmed_taps,200);
  assert.equal((await (await read()).json()).profile.selected_rank_id,2);
  assert.equal((await (await read(bob)).json()).profile.selected_rank_id,4);
  assert.equal(h.avatarPrefs.get('88003'),2);
  assert.ok(!h.avatarPrefs.has('88004'));
  const reset=await choose(alice,0);assert.equal(reset.status,200,await reset.clone().text());
  const automatic=(await reset.json()).profile;
  assert.equal(automatic.selected_rank_id,4);assert.equal(automatic.selection_mode,'auto');
  assert.equal(h.avatarPrefs.get('88003'),0);
 }finally{h.restore()}
});

test('V2 phase 2 profile clearly distinguishes next-rank XP requirements from mastery challenges',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=2330;h.player.confirmed_taps=0;
 const init=signedTelegramUser({id:88005,first_name:'Progression'});
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/profile',{headers:{'x-telegram-init-data':init}}),h.env);
  assert.equal(res.status,200);const {progression:p}=await res.json();
  assert.equal(p.level,4);assert.equal(p.blocked_by_mastery,true);
  assert.equal(p.next_rank.level,5);assert.equal(p.next_rank.xp_remaining,0);
  assert.equal(p.next_rank.mastery_required,2);assert.equal(p.next_rank.mastery_missing,2);
  assert.equal(p.mastery.completed,0);
 }finally{h.restore()}
});

test('V2 phase 2 profile has 11 selectable avatar cards with provisional stars and badge styling',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  assert.ok(html.includes('mrxp-avatar-grid'));assert.ok(html.includes('mrxp-auto-avatar'));
  assert.ok(html.includes('mrxp-rank-badge-level'));assert.ok(html.includes('mrxp-rank-stars'));
  assert.ok(html.includes('mrxp-next-rank-details'));assert.ok(html.includes('mrxp-avatar-choice-notice'));
  assert.ok(html.includes('async function selectProfileAvatar(rank)'));
  assert.ok(html.includes('"/api/profile/avatar","POST",{rank}'));
  assert.ok(html.includes('state.profile=r.profile||null'));
  assert.ok(html.includes('state.profile=null;mrxpConfirmedWallet=null;mrxpShop=null;/* Never trust locally restored ranks, avatar choices, shop objects or credit balances as official. */'));
  assert.ok(html.includes('mrxp-rank-up'));
 }finally{h.restore()}
});

test('V2 phase 2 migration is additive and does not touch XP or other player data',async()=>{
 const sql=await readFile(new URL('../migrations/003_avatar_profiles.sql',import.meta.url),'utf8');
 assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS player_avatar_prefs'));
 assert.ok(!/DROP TABLE|DELETE FROM players|UPDATE players|UPDATE .*confirmed_xp/i.test(sql));
 const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
 assert.ok(schema.includes('CREATE TABLE IF NOT EXISTS player_avatar_prefs'));
});

test('V2 phase 2 Mini App inline scripts parse successfully in the browser',async()=>{
 const h=harness();
 try{
  const r=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await r.text();
  const inline=[];
  let cursor=0;
  while((cursor=html.indexOf('<script',cursor))>=0){
   const gt=html.indexOf('>',cursor),close=html.indexOf('</script>',gt);
   if(gt<0||close<0)break;
   const content=html.slice(gt+1,close).trim();
   if(content)inline.push(content);
   cursor=close+9;
  }
  assert.ok(inline.length>=2);
  for(const [i,js] of inline.entries())assert.doesNotThrow(()=>new vm.Script(js,{filename:'miniapp-inline-'+i+'.js'}));
 }finally{h.restore()}
});


test('phase 3 shares only authenticated, confirmed server stats with optional name hiding',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=764;h.player.confirmed_taps=200;
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 const init=signedTelegramUser({id:91001,first_name:'Fatou',last_name:'Diop',username:'personnel'});
 const make=(payload,header=init)=>worker.fetch(new Request(root+'/api/share/profile',{method:'POST',headers:{'x-telegram-init-data':header,'content-type':'application/json'},body:JSON.stringify(payload)}),h.env);
 try{
  assert.equal((await make({hide_name:false},'')).status,401);
  assert.equal((await make({})).status,400);
  const valid=await make({hide_name:false});assert.equal(valid.status,200,await valid.clone().text());
  const data=await valid.json();
  assert.equal(data.snapshot.display_name,'Fatou Diop');
  assert.equal(data.snapshot.level,3);assert.equal(data.snapshot.xp,764);
  assert.equal(data.snapshot.rank,'Combattant');assert.equal(data.snapshot.avatar_rank,3);
  assert.ok(data.verify_url.includes('/share/verify?token='));
  assert.ok(!data.verify_url.includes('91001'));assert.ok(!data.token.includes('91001'));
  const publicCheck=await worker.fetch(new Request(data.verify_url),h.env);
  assert.equal(publicCheck.status,200);const text=await publicCheck.text();
  assert.ok(text.includes('Fatou Diop'));assert.ok(text.includes('764 XP confirmés'));
  assert.ok(!text.includes('91001'));assert.ok(!text.includes('personnel'));
  const hidden=await make({hide_name:true});assert.equal(hidden.status,200);
  assert.equal((await hidden.json()).snapshot.display_name,'Joueur MRXP');
 }finally{h.restore()}
});

test('phase 3 verifies signed snapshot proof and rejects tampering or forged ranks',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 const init=signedTelegramUser({id:91002,first_name:'Alpha'});
 try{
  const res=await worker.fetch(new Request(root+'/api/share/profile',{method:'POST',headers:{'x-telegram-init-data':init,'content-type':'application/json'},body:JSON.stringify({hide_name:true})}),h.env);
  assert.equal(res.status,200,await res.clone().text());const out=await res.json();
  const good=await worker.fetch(new Request(root+'/api/share/verify?token='+encodeURIComponent(out.token)),h.env);
  assert.equal(good.status,200);assert.equal((await good.json()).snapshot.xp,0);
  const broken=out.token.slice(0,-5)+'abcde';
  const bad=await worker.fetch(new Request(root+'/api/share/verify?token='+encodeURIComponent(broken)),h.env);
  assert.equal(bad.status,400);assert.equal((await bad.json()).valid,false);
  const invalidHtml=await worker.fetch(new Request(root+'/share/verify?token='+encodeURIComponent(broken)),h.env);
  assert.equal(invalidHtml.status,400);
  assert.equal((await worker.fetch(new Request(root+'/share/avatar/999'),h.env)).status,404);
  assert.equal((await worker.fetch(new Request(root+'/share/avatar/0'),h.env)).status,404);
 }finally{h.restore()}
});

test('phase 3 Mini App has two high resolution PNG formats and real download/share alternatives',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  for(const needle of ['mrxp-share-format','mrxp-share-hide-name','mrxp-share-create','mrxp-share-preview','mrxp-share-download','mrxp-share-native','mrxp-share-telegram','mrxp-share-copy','1080 × 1920','1080 × 1080','mrxpDrawShareImage(snapshot,vertical,avatar)','canvas.toBlob','navigator.share','/api/share/profile','/share/avatar/']){
   assert.ok(html.includes(needle),needle);
  }
 }finally{h.restore()}
});

test('phase 4 requires Telegram authentication for private free MRXP wallet',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits'),h.env);
  assert.equal(res.status,401);
  assert.equal(h.creditEvents.size,0);
 }finally{h.restore()}
});

test('phase 4 wallet starts at zero and does not retroactively pay historical levels',async()=>{
 const h=harness();h.env.DEV_MODE='true';h.player.confirmed_xp=56000;h.player.confirmed_taps=1200;
 const init=signedTelegramUser({id:93001,first_name:'Historique'});
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits',{headers:{'x-telegram-init-data':init}}),h.env);
  assert.equal(res.status,200,await res.clone().text());const wallet=(await res.json()).wallet;
  assert.equal(wallet.balance,0);assert.equal(wallet.ledger.length,0);
  assert.ok(wallet.baseline_level>=5);assert.equal(wallet.spend_enabled,true);
  assert.equal(wallet.transfer_enabled,false);assert.equal(wallet.cash_value,false);
 }finally{h.restore()}
});

test('phase 4 credits server-verified daily, wheel, sync and permanent mission exactly once',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='93002',init=signedTelegramUser({id:Number(id),first_name:'Binta'});
 const get=()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits',{headers:{'x-telegram-init-data':init}}),h.env);
 try{
  let res=await get();assert.equal(res.status,200,await res.clone().text());assert.equal((await res.json()).wallet.balance,0);
  const today=new Date().toISOString().slice(0,10),ms=Date.now()+3;
  h.verifiedDaily.push({user_id:id,day:today,created_ms:ms});
  h.verifiedWheel.push({user_id:id,day:today,created_ms:ms});
  h.verifiedTaps.push({user_id:id,created_ms:ms,taps:55});
  h.missionClaims.set(id+':first_open',{xp:25,created_ms:ms});
  res=await get();assert.equal(res.status,200,await res.clone().text());
  const wallet=(await res.json()).wallet;assert.equal(wallet.balance,30); // 5 daily + 5 daily quest + 5 wheel + 5 taps + 10 mission
  assert.equal(wallet.total_events,5);assert.equal(wallet.today_goals.length,3);
  assert.equal(wallet.today_goals.filter(x=>x.done).length,3);
  const repeat=await get();assert.equal((await repeat.json()).wallet.balance,30);
  assert.equal(h.creditEvents.size,5);
  assert.equal(h.player.confirmed_xp,0); // currencies fully separate
 }finally{h.restore()}
});

test('phase 4 weekly bonus and level gains are awarded once without affecting XP',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='93003',init=signedTelegramUser({id:Number(id),first_name:'Koffi'});
 const ms=Date.now();
 const weekday=(new Date().getUTCDay()+6)%7;
 const thisMonday=Date.UTC(new Date().getUTCFullYear(),new Date().getUTCMonth(),new Date().getUTCDate())-weekday*86400000;
 const prevMonday=thisMonday-7*86400000;
 h.creditBaselines.set(id,{baseline_level:1,activated_ms:Date.now()-30*86400000});
 for(let i=0;i<4;i++)h.verifiedDaily.push({user_id:id,day:new Date(prevMonday+i*86400000).toISOString().slice(0,10),created_ms:ms-86400000});
 const get=()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits',{headers:{'x-telegram-init-data':init}}),h.env);
 try{
  h.player.confirmed_xp=300;let res=await get();assert.equal(res.status,200,await res.clone().text());
  const wallet=(await res.json()).wallet;
  assert.equal(wallet.balance,80); // four days * (5+5) + weekly 30 + level2 10
  assert.equal(h.v2Progress.get(id).current_level,2);
  const second=(await (await get()).json()).wallet;assert.equal(second.balance,80);
  assert.equal(h.player.confirmed_xp,300);assert.equal(h.creditEvents.size,10);
 }finally{h.restore()}
});

test('phase 4 SQL migration is additive and credits are isolated per account',async()=>{
 const sql=await readFile(new URL('../migrations/004_free_mrxp_credits.sql',import.meta.url),'utf8');
 assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS mrxp_credit_events'));
 assert.ok(sql.includes('PRIMARY KEY(user_id,event_key)'));
 assert.ok(sql.includes('CREATE TABLE IF NOT EXISTS player_credit_state'));
 assert.ok(sql.includes('INSERT OR IGNORE INTO player_credit_state'));
 assert.ok(!/DROP TABLE|DELETE FROM players|UPDATE players/i.test(sql));
 const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
 assert.ok(schema.includes('mrxp_credit_events'));assert.ok(schema.includes('player_credit_state'));
 const h=harness();h.env.DEV_MODE='true';
 try{
  const user1=signedTelegramUser({id:93004,first_name:'A'});
  const user2=signedTelegramUser({id:93005,first_name:'B'});
  const base='https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits';
  let r=await worker.fetch(new Request(base,{headers:{'x-telegram-init-data':user1}}),h.env);
  assert.equal(r.status,200);let day=new Date().toISOString().slice(0,10);
  h.verifiedDaily.push({user_id:'93004',day,created_ms:Date.now()+10});
  r=await worker.fetch(new Request(base,{headers:{'x-telegram-init-data':user1}}),h.env);assert.equal((await r.json()).wallet.balance,10);
  r=await worker.fetch(new Request(base,{headers:{'x-telegram-init-data':user2}}),h.env);assert.equal((await r.json()).wallet.balance,0);
 }finally{h.restore()}
});

test('phase 4 wallet UI displays free currency, three daily quests and actual ledger',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  for(const term of ['mrxp-credit-balance','mrxp-credit-history','mrxp-credit-daily-goals','mrxp-credit-weekly','mrxp-credit-goal-count','/api/credits','mrxpConfirmedWallet=null','mrxpRenderWallet()','mrxp-credit-refresh']){
   assert.ok(html.includes(term),term)
  }
 }finally{h.restore()}
});


test('phase 4 economy admin dashboard remains private and never exposes credits to public callbacks',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(publicId,'mrxp:admin:credits'));
  assert.equal(h.calls.filter(x=>x.method==='sendMessage').length,0);
  await h.webhook(callback(adminId,'mrxp:admin:credits'));
  const lines=h.calls.filter(x=>x.method==='sendMessage').map(x=>x.args.text);
  assert.ok(lines.some(x=>x.includes('ÉCONOMIE MRXP')));
  assert.ok(lines.some(x=>x.includes('Crédits en circulation')));
  assert.ok(lines.some(x=>x.includes('Aucun retrait')));
 }finally{h.restore()}
});


test('phase 5 shop endpoints are authenticated and prices come only from server catalog',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 const id=94001,auth=signedTelegramUser({id,first_name:'Adama'}),uuid='a0a1a2a3-0000-4000-8000-aabbccddee01';
 const post=(path,body,headers={'x-telegram-init-data':auth,'content-type':'application/json'})=>worker.fetch(new Request(root+path,{method:'POST',headers,body:JSON.stringify(body)}),h.env);
 try{
  assert.equal((await worker.fetch(new Request(root+'/api/shop'),h.env)).status,401);
  assert.equal((await post('/api/shop/buy',{sku:'tap-110',purchase_id:uuid},{})).status,401);
  const before=await worker.fetch(new Request(root+'/api/shop',{headers:{'x-telegram-init-data':auth}}),h.env);
  assert.equal(before.status,200,await before.clone().text());const initial=(await before.json());
  assert.equal(initial.wallet.balance,0);assert.equal(initial.shop.catalog.length,6);
  assert.equal(initial.shop.catalog.find(x=>x.sku==='tap-110').price,25);
  let res=await post('/api/shop/buy',{sku:'tap-110',purchase_id:uuid,price:0,multiplier_milli:100000});
  assert.equal(res.status,409);
  res=await post('/api/shop/buy',{sku:'unknown',purchase_id:uuid});
  assert.equal(res.status,400);
  res=await post('/api/shop/buy',{sku:'tap-110',purchase_id:'not-a-uuid'});
  assert.equal(res.status,400);
  assert.equal(h.boostInventory.size,0);assert.equal(h.creditEvents.size,0);
 }finally{h.restore()}
});

test('phase 5 purchase atomically charges correct MRXP once and inventory persists',async()=>{
 const h=harness();h.env.DEV_MODE='true';const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94002';
 const auth=signedTelegramUser({id:Number(id),first_name:'Mariam'}),uuid='a0a1a2a3-0000-4000-8000-aabbccddee02';
 h.creditEvents.set(id+':welcome-credit',{user_id:id,event_key:'welcome-credit',amount:75,event_type:'test',label:'confirmed',created_ms:Date.now()});
 const post=(body)=>worker.fetch(new Request(root+'/api/shop/buy',{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  let r=await post({sku:'tap-110',purchase_id:uuid,price:1,multiplier_milli:9000});
  assert.equal(r.status,200,await r.clone().text());
  let data=await r.json();
  assert.equal(data.duplicate,false);assert.equal(data.wallet.balance,50);
  assert.equal(data.shop.inventory.length,1);
  assert.equal(data.shop.inventory[0].state,'owned');
  assert.equal(data.shop.inventory[0].item.multiplier_milli,1100);
  r=await post({sku:'tap-110',purchase_id:uuid});
  assert.equal(r.status,200);data=await r.json();
  assert.equal(data.duplicate,true);assert.equal(data.wallet.balance,50);
  assert.equal(h.boostInventory.size,1);
  assert.equal([...h.creditEvents.values()].filter(x=>x.amount<0).length,1);
  assert.equal((await post({sku:'energy-250',purchase_id:uuid})).status,409);
  assert.equal((await post({sku:'tap-200',purchase_id:'a0a1a2a3-0000-4000-8000-aabbccddee04'})).status,409);
  assert.equal(h.boostInventory.size,1);
 }finally{h.restore()}
});

test('phase 5 only owner activates boosts and conflicting multiplier activations are blocked',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94003',other='94004';
 const auth=signedTelegramUser({id:Number(id),first_name:'Aïssata'});
 const different=signedTelegramUser({id:Number(other),first_name:'Téko'});
 const uuid='a0a1a2a3-0000-4000-8000-aabbccddee05',uuid2='a0a1a2a3-0000-4000-8000-aabbccddee06';
 h.creditEvents.set(id+':welcome-credit',{user_id:id,event_key:'welcome-credit',amount:100,event_type:'test',label:'confirmed',created_ms:Date.now()});
 const post=(path,body,header=auth)=>worker.fetch(new Request(root+path,{method:'POST',headers:{'x-telegram-init-data':header,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  assert.equal((await post('/api/shop/buy',{sku:'tap-110',purchase_id:uuid})).status,200);
  assert.equal((await post('/api/shop/buy',{sku:'tap-120',purchase_id:uuid2})).status,200);
  assert.equal((await post('/api/shop/activate',{purchase_id:uuid},different)).status,404);
  let res=await post('/api/shop/activate',{purchase_id:uuid});
  assert.equal(res.status,200,await res.clone().text());
  assert.equal((await res.json()).shop.active_tap.state,'queued');
  assert.equal((await post('/api/shop/activate',{purchase_id:uuid2})).status,409);
  res=await post('/api/shop/activate',{purchase_id:uuid});
  assert.equal(res.status,200);assert.equal((await res.json()).duplicate,true);
  assert.equal(h.boostInventory.get(id+':'+uuid).state,'queued');
  assert.equal(h.boostInventory.get(id+':'+uuid2).state,'owned');
 }finally{h.restore()}
});

test('phase 5 applies x1.1 tap XP with exact carry on two server-confirmed syncs and no replay bonus',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94005',uuid='a0a1a2a3-0000-4000-8000-aabbccddee07';
 const auth=signedTelegramUser({id:Number(id),first_name:'Kouamé'});
 h.player.created_ms=Date.now()-24*3600000;
 h.creditEvents.set(id+':welcome-credit',{user_id:id,event_key:'welcome-credit',amount:100,event_type:'test',label:'confirmed',created_ms:Date.now()});
 const post=(path,body)=>worker.fetch(new Request(root+path,{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  assert.equal((await post('/api/shop/buy',{sku:'tap-110',purchase_id:uuid})).status,200);
  assert.equal((await post('/api/shop/activate',{purchase_id:uuid})).status,200);
  let res=await post('/api/sync',{batch_id:'boost-batch-000000001',taps:21,daily_days:[],wheel_days:[]});
  assert.equal(res.status,200,await res.clone().text());
  let body=await res.json();
  assert.equal(body.xp_awarded,23);assert.equal(body.boost_bonus_xp,2);
  assert.equal(body.boost_multiplier_milli,1100);
  assert.equal(h.player.confirmed_xp,23);
  assert.equal(h.boostInventory.get(id+':'+uuid).state,'active');
  assert.equal(h.boostInventory.get(id+':'+uuid).carry_milli,100);
  const repeat=await post('/api/sync',{batch_id:'boost-batch-000000001',taps:21,daily_days:[],wheel_days:[]});
  assert.equal(repeat.status,200);assert.equal((await repeat.json()).duplicate,true);
  assert.equal(h.player.confirmed_xp,23);
  h.player.next_sync_ms=0; // artificially advance the test clock to next admissible 12h sync
  h.player.last_sync_ms=Date.now()-13*3600000;
  res=await post('/api/sync',{batch_id:'boost-batch-000000002',taps:9,daily_days:[],wheel_days:[]});
  assert.equal(res.status,200,await res.clone().text());
  body=await res.json();assert.equal(body.xp_awarded,10);assert.equal(body.boost_bonus_xp,1);
  assert.equal(h.player.confirmed_xp,33);
  assert.equal(h.boostInventory.get(id+':'+uuid).carry_milli,0);
 }finally{h.restore()}
});

test('phase 5 refills energy once and prevents stacking charged energy packs',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94006';
 const auth=signedTelegramUser({id:Number(id),first_name:'Agbo'});
 h.creditEvents.set(id+':credit',{user_id:id,event_key:'credit',amount:150,event_type:'test',label:'confirmed',created_ms:Date.now()});
 const a='a0a1a2a3-0000-4000-8000-aabbccddee08',b='a0a1a2a3-0000-4000-8000-aabbccddee09';
 const post=(path,body)=>worker.fetch(new Request(root+path,{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  assert.equal((await post('/api/shop/buy',{sku:'energy-100',purchase_id:a})).status,200);
  assert.equal((await post('/api/shop/buy',{sku:'energy-250',purchase_id:b})).status,200);
  let r=await post('/api/shop/activate',{purchase_id:a});assert.equal(r.status,200,await r.clone().text());
  let data=await r.json();assert.equal(data.applied_energy,100);
  assert.equal(data.shop.energy_charged.state,'charged');
  r=await post('/api/shop/activate',{purchase_id:a});assert.equal(r.status,200);
  data=await r.json();assert.equal(data.duplicate,true);assert.equal(data.applied_energy,100);
  assert.equal((await post('/api/shop/activate',{purchase_id:b})).status,409);
  const pack=h.boostInventory.get(id+':'+a);
  pack.expires_ms=Date.now()-10;
  const page=await worker.fetch(new Request(root+'/api/shop',{headers:{'x-telegram-init-data':auth}}),h.env);
  assert.equal(page.status,200);assert.equal((await page.json()).shop.energy_charged,null);
  assert.equal(pack.state,'expired');
 }finally{h.restore()}
});

test('phase 5 schema is additive; new shop UI and sync logic preserve signed identity and games hub',async()=>{
 const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
 const migration=await readFile(new URL('../migrations/005_boost_store.sql',import.meta.url),'utf8');
 assert.ok(migration.includes('CREATE TABLE IF NOT EXISTS mrxp_boost_inventory'));
 assert.ok(migration.includes('PRIMARY KEY(user_id,purchase_id)'));
 assert.ok(migration.includes("CHECK(kind IN ('tap','energy'))"));
 assert.ok(!/DROP TABLE|DELETE FROM players|UPDATE players/i.test(migration));
 assert.ok(schema.includes('mrxp_boost_inventory'));
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  const html=await res.text();
  for(const marker of ['screen-shop','mrxp-store-catalog','mrxp-store-inventory','mrxp-shop-balance','mrxp-open-shop',
    'mrxpApplyEnergyReceipts','mrxpShopBuy','/api/shop','/api/shop/buy','/api/shop/activate','mrxp-games-hub','mrxp-share-create','mrxp-credit-history']){
   // The actual shop handler is mrxpBuyBoost, not a trusted frontend price function.
   if(marker==='mrxpShopBuy')assert.ok(html.includes('mrxpBuyBoost'),marker);
   else assert.ok(html.includes(marker),marker)
  }
 }finally{h.restore()}
});


test('phase 5 +100 energy is counted once in anti-cheat ceiling and consumed after accepted sync',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94007',uuid='a0a1a2a3-0000-4000-8000-aabbccddee10';
 const auth=signedTelegramUser({id:Number(id),first_name:'Nana'});
 h.player.created_ms=Date.now()-2000;
 h.creditEvents.set(id+':credit',{user_id:id,event_key:'credit',amount:50,event_type:'test',label:'earned',created_ms:Date.now()});
 const post=(path,body)=>worker.fetch(new Request(root+path,{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:JSON.stringify(body)}),h.env);
 try{
  assert.equal((await post('/api/shop/buy',{sku:'energy-100',purchase_id:uuid})).status,200);
  assert.equal((await post('/api/shop/activate',{purchase_id:uuid})).status,200);
  let r=await post('/api/sync',{batch_id:'energy-batch-000000001',taps:600,daily_days:[],wheel_days:[]});
  assert.equal(r.status,200,await r.clone().text());let data=await r.json();
  assert.equal(data.xp_awarded,600);assert.equal(data.energy_charge_used,100);
  assert.equal(h.boostInventory.get(id+':'+uuid).state,'used');
  assert.equal(h.player.confirmed_taps,600);
  h.player.next_sync_ms=0;h.player.last_sync_ms=Date.now()-1000;
  r=await post('/api/sync',{batch_id:'energy-batch-000000002',taps:600,daily_days:[],wheel_days:[]});
  assert.equal(r.status,422);assert.equal(h.player.confirmed_taps,600);
 }finally{h.restore()}
});

test('phase 5 expired tap boost cannot grant bonus XP, and queued status never expires before first sync',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',id='94008';
 const auth=signedTelegramUser({id:Number(id),first_name:'Sarah'}),now=Date.now();
 const old='a0a1a2a3-0000-4000-8000-aabbccddee11',queued='a0a1a2a3-0000-4000-8000-aabbccddee12';
 h.player.created_ms=now-24*3600000;
 h.boostInventory.set(id+':'+old,{user_id:id,purchase_id:old,sku:'tap-150',kind:'tap',cost:100,state:'active',bought_ms:now-5*3600000,activated_ms:now-5*3600000,expires_ms:now-1000,carry_milli:0});
 h.boostInventory.set(id+':'+queued,{user_id:id,purchase_id:queued,sku:'tap-110',kind:'tap',cost:25,state:'queued',bought_ms:now-1*3600000,activated_ms:0,expires_ms:0,carry_milli:0});
 try{
  const shop=await worker.fetch(new Request(root+'/api/shop',{headers:{'x-telegram-init-data':auth}}),h.env);
  assert.equal(shop.status,200);const payload=(await shop.json()).shop;
  assert.equal(h.boostInventory.get(id+':'+old).state,'expired');
  assert.equal(h.boostInventory.get(id+':'+queued).state,'queued');
  assert.equal(payload.active_tap.sku,'tap-110');
  const res=await worker.fetch(new Request(root+'/api/sync',{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:JSON.stringify({batch_id:'expire-batch-0000001',taps:10,daily_days:[],wheel_days:[]})}),h.env);
  assert.equal(res.status,200,await res.clone().text());const body=await res.json();
  assert.equal(body.boost_bonus_xp,1);assert.equal(body.boost_multiplier_milli,1100);
  assert.equal(h.boostInventory.get(id+':'+old).state,'expired');
 }finally{h.restore()}
});


test('phase 6 admin panel is private and exposes bounded pricing, rewards and release controls',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(publicId,'mrxp:admin:balance_price'));
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].method,'answerCallbackQuery');assert.equal(h.calls[0].args.show_alert,true);
  assert.equal(h.settings.size,1);
  h.calls.length=0;
  await h.webhook(callback(adminId,'mrxp:admin:balance_price'));
  const reply=h.calls.find(x=>x.method==='sendMessage')?.args;
  assert.ok(reply.text.includes('ÉQUILIBRAGE V2'));
  assert.ok(JSON.stringify(reply.reply_markup).includes('price_energy-250'));
  assert.ok(!JSON.stringify(reply.reply_markup).includes("ALTER TABLE"));
  assert.equal(h.balanceAudit.length,0)
 }finally{h.restore()}
});

test('phase 6 admin can change price with strict range, audit trail, and unchanged purchased effect',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='96101',user=signedTelegramUser({id:Number(id),first_name:'Amisi'});
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 h.creditEvents.set(id+':earned',{user_id:id,event_key:'earned',amount:200,event_type:'test',label:'earned',created_ms:Date.now()});
 try{
  await h.webhook(callback(adminId,'mrxp:admin:econ_edit_price_tap-110'));
  assert.equal(h.pending.get(String(adminId)).edit_key,'econ:price_tap-110');
  await h.webhook(message(adminId,'-5'));
  assert.equal(h.pending.has(String(adminId)),true);
  assert.equal(h.settings.has('mrxp_balance_price_tap-110'),false);
  await h.webhook(message(adminId,'12000'));
  assert.equal(h.pending.has(String(adminId)),true);
  await h.webhook(message(adminId,'80'));
  assert.equal(h.pending.has(String(adminId)),false);
  assert.equal(h.settings.get('mrxp_balance_price_tap-110'),'80');
  assert.equal(h.balanceAudit.length,1);
  assert.equal(h.balanceAudit[0].old_value,'25');
  assert.equal(h.balanceAudit[0].new_value,'80');
  const headers={'x-telegram-init-data':user,'content-type':'application/json'};
  const catalog=await worker.fetch(new Request(root+'/api/shop',{headers}),h.env);
  assert.equal(catalog.status,200,await catalog.clone().text());
  assert.equal((await catalog.json()).shop.catalog.find(x=>x.sku==='tap-110').price,80);
  const purchase=await worker.fetch(new Request(root+'/api/shop/buy',{method:'POST',headers,body:JSON.stringify({sku:'tap-110',purchase_id:'f0010000-0000-4000-8000-000000000001',price:1})}),h.env);
  assert.equal(purchase.status,200,await purchase.clone().text());
  const data=await purchase.json();
  assert.equal(data.wallet.balance,120);
  assert.equal(data.shop.inventory[0].price,80);
  assert.equal(data.shop.inventory[0].item.multiplier_milli,1100);
 }finally{h.restore()}
});

test('phase 6 changed MRXP rates apply prospectively and cannot reprice historical events',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='96102',auth=signedTelegramUser({id:Number(id),first_name:'Awa'});
 const now=Date.now(),today=new Date(now).toISOString().slice(0,10),yesterday=new Date(now-86400000).toISOString().slice(0,10);
 h.creditBaselines.set(id,{baseline_level:1,activated_ms:now-4*86400000});
 h.settings.set('mrxp_balance_reward_daily_base','20');
 h.settingUpdated.set('mrxp_balance_reward_daily_base',now-2*3600000);
 h.verifiedDaily.push({user_id:id,day:yesterday,created_ms:now-86400000});
 h.verifiedDaily.push({user_id:id,day:today,created_ms:now-1000});
 try{
  const req=()=>worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/api/credits',{headers:{'x-telegram-init-data':auth}}),h.env);
  let res=await req();assert.equal(res.status,200,await res.clone().text());
  let wallet=(await res.json()).wallet;
  assert.equal(wallet.balance,35); // yesterday 5+5; today 20+5
  h.settings.set('mrxp_balance_reward_daily_base','60');
  h.settingUpdated.set('mrxp_balance_reward_daily_base',now+1000);
  res=await req();wallet=(await res.json()).wallet;
  assert.equal(wallet.balance,35); // credits are immutable even after the admin changes a rate
  assert.equal(wallet.ledger.filter(x=>x.key.startsWith('daily:')).length,2);
 }finally{h.restore()}
});

test('phase 6 emergency pause and gradual rollout never delete already purchased inventory',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='96103',auth=signedTelegramUser({id:Number(id),first_name:'Abla'});
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 h.creditEvents.set(id+':earned',{user_id:id,event_key:'earned',amount:160,event_type:'test',label:'earned',created_ms:Date.now()});
 const headers={'x-telegram-init-data':auth,'content-type':'application/json'};
 const post=(path,body)=>worker.fetch(new Request(root+path,{method:'POST',headers,body:JSON.stringify(body)}),h.env);
 try{
  h.settings.set('mrxp_balance_shop_rollout','0');
  let res=await post('/api/shop/buy',{sku:'tap-110',purchase_id:'f0010000-0000-4000-8000-000000000002'});
  assert.equal(res.status,423);assert.equal(h.boostInventory.size,0);
  h.settings.set('mrxp_balance_shop_rollout','100');
  res=await post('/api/shop/buy',{sku:'tap-110',purchase_id:'f0010000-0000-4000-8000-000000000002'});
  assert.equal(res.status,200);
  h.settings.set('mrxp_balance_shop_enabled','0');
  res=await post('/api/shop/buy',{sku:'tap-120',purchase_id:'f0010000-0000-4000-8000-000000000003'});
  assert.equal(res.status,423);
  res=await post('/api/shop/activate',{purchase_id:'f0010000-0000-4000-8000-000000000002'});
  assert.equal(res.status,200);assert.equal((await res.json()).shop.active_tap.state,'queued');
  const get=await worker.fetch(new Request(root+'/api/shop',{headers}),h.env);
  assert.equal((await get.json()).shop.available,false);
  assert.equal(h.boostInventory.size,1)
 }finally{h.restore()}
});

test('phase 6 daily spend cap is enforced independently of untrusted browser payload',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const id='96104',auth=signedTelegramUser({id:Number(id),first_name:'Béa'});
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 h.settings.set('mrxp_balance_shop_daily_limit','1');
 h.creditEvents.set(id+':earned',{user_id:id,event_key:'earned',amount:100,event_type:'test',label:'earned',created_ms:Date.now()});
 const headers={'x-telegram-init-data':auth,'content-type':'application/json'};
 const post=(purchase_id)=>worker.fetch(new Request(root+'/api/shop/buy',{method:'POST',headers,body:JSON.stringify({sku:'tap-110',purchase_id})}),h.env);
 try{
  let r=await post('f0010000-0000-4000-8000-000000000004');assert.equal(r.status,200,await r.clone().text());
  r=await post('f0010000-0000-4000-8000-000000000005');assert.equal(r.status,429);
  r=await post('f0010000-0000-4000-8000-000000000004');assert.equal(r.status,200);
  const data=await r.json();assert.equal(data.duplicate,true);assert.equal(data.wallet.balance,75);
  assert.equal(h.boostInventory.size,1);
  assert.equal([...h.creditEvents.values()].filter(e=>e.amount<0).length,1)
 }finally{h.restore()}
});

test('phase 6 multiple signed Telegram accounts are separated for MRXP credits and boost activation',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev',one='96105',two='96106';
 const authA=signedTelegramUser({id:Number(one),first_name:'Fatou'}),authB=signedTelegramUser({id:Number(two),first_name:'Yao'});
 h.creditEvents.set(one+':earned',{user_id:one,event_key:'earned',amount:45,event_type:'test',label:'earned',created_ms:Date.now()});
 h.creditEvents.set(two+':earned',{user_id:two,event_key:'earned',amount:100,event_type:'test',label:'earned',created_ms:Date.now()});
 const id='f0010000-0000-4000-8000-000000000006',headers=a=>({'x-telegram-init-data':a,'content-type':'application/json'});
 try{
  const purchase=await worker.fetch(new Request(root+'/api/shop/buy',{method:'POST',headers:headers(authA),body:JSON.stringify({sku:'tap-110',purchase_id:id})}),h.env);
  assert.equal(purchase.status,200,await purchase.clone().text());
  const a=await worker.fetch(new Request(root+'/api/shop',{headers:headers(authA)}),h.env);
  const shopA=await a.json();assert.equal(shopA.wallet.balance,20);assert.equal(shopA.shop.inventory.length,1);
  const b=await worker.fetch(new Request(root+'/api/shop',{headers:headers(authB)}),h.env);
  const shopB=await b.json();assert.equal(shopB.wallet.balance,100);assert.equal(shopB.shop.inventory.length,0);
  const forbidden=await worker.fetch(new Request(root+'/api/shop/activate',{method:'POST',headers:headers(authB),body:JSON.stringify({purchase_id:id})}),h.env);
  assert.equal(forbidden.status,404);
  const signatureForged=authA.replace(/hash=[a-f0-9]+/,'hash='+'0'.repeat(64));
  assert.equal((await worker.fetch(new Request(root+'/api/shop',{headers:headers(signatureForged)}),h.env)).status,401);
 }finally{h.restore()}
});

test('phase 6 audit migration is additive and phase 5 monetization rules remain absent',async()=>{
 const sql=await readFile(new URL('../migrations/006_balance_audit.sql',import.meta.url),'utf8');
 assert.match(sql,/CREATE TABLE IF NOT EXISTS mrxp_balance_audit/);
 assert.match(sql,/CREATE INDEX IF NOT EXISTS idx_mrxp_balance_audit_created/);
 assert.doesNotMatch(sql,/\b(DROP TABLE|DELETE FROM players|UPDATE players)\b/i);
 const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
 assert.match(schema,/mrxp_balance_audit/);
 for(const name of ['mrxpBalanceCanBuy','mrxpBalanceRolloutBucket','mrxpBalanceChange','mrxpAdminBalancePanel','mrxpAdminBalanceAudit']){
  assert.ok(code.includes(name),'missing '+name)
 }
 assert.ok(code.includes('real_money:false'));assert.ok(code.includes('transfer_enabled:false'))
});


test('phase 6 simulator verifies all 50 official levels, 11 ranks and seven mastery gates',()=>{
 const from=code.indexOf('const V2_MAX_LEVEL=50;'),to=code.indexOf('async function v2Progression(env,player)');
 assert.ok(from>0&&to>from);
 const rules=new Function(code.slice(from,to)+'\nreturn {cap:V2_MAX_LEVEL,thresholds:V2_LEVEL_THRESHOLDS,ranks:V2_RANKS,gates:V2_GATES,mastery:V2_MASTERY,eligible:v2XpLevel,legacy:v2LegacyLevel};')();
 assert.equal(rules.cap,50);assert.equal(rules.thresholds.length,51);
 assert.equal(rules.ranks.length,11);assert.equal(rules.gates.length,7);
 assert.equal(rules.mastery.length,30);
 for(let n=2;n<=50;n++){
  assert.ok(Number.isInteger(rules.thresholds[n]));
  assert.ok(rules.thresholds[n]>rules.thresholds[n-1]);
  assert.equal(rules.eligible(rules.thresholds[n]-1),n-1);
  assert.equal(rules.eligible(rules.thresholds[n]),n);
  assert.equal(rules.ranks.filter(r=>n>=r.from&&n<=r.to).length,1)
 }
 assert.equal(rules.eligible(Number.MAX_SAFE_INTEGER),50);
 assert.equal(rules.legacy(0),1);
 assert.ok(rules.legacy(400000)>=40);
 assert.deepEqual(rules.gates.map(g=>g.level),[5,10,15,20,30,40,50]);
 assert.deepEqual(rules.gates.map(g=>g.required),[2,3,5,7,10,14,18]);
});

test('phase 6 365-day simulated casual-to-intensive profiles never skip mastery or overspend MRXP',()=>{
 const from=code.indexOf('const V2_MAX_LEVEL=50;'),to=code.indexOf('async function v2Progression(env,player)');
 const g=new Function(code.slice(from,to)+'\nreturn {thresholds:V2_LEVEL_THRESHOLDS,gates:V2_GATES,mastery:V2_MASTERY,ranks:V2_RANKS,eligible:v2XpLevel};')();
 const simulation=(dailyTaps,wheelEvery,boosts)=>{
  let xp=0,taps=0,daily=0,wheel=0,missions=0,level=1,credits=0,spent=0,boostDay=-1,bought=0;
  const progress=[];
  for(let day=1;day<=365;day++){
   const spin=day%wheelEvery===0;
   daily++;taps+=dailyTaps;if(spin)wheel++;
   if([1,7,30,60].includes(day))missions++;
   credits+=5+5+(spin?5:0)+(dailyTaps>=50?5:0)+(day%7===0?30:0)+([1,7,30,60].includes(day)?10:0);
   if(boosts&&day%30===1&&credits>=180){credits-=180;spent+=180;boostDay=day;bought++}
   xp+=dailyTaps*(day===boostDay?2:1)+100+(spin?25:0);
   const earned=g.mastery.filter(c=>({taps,daily,wheel,missions})[c.kind]>=c.goal).length;
   const target=g.eligible(xp);
   for(let next=level+1;next<=target;next++){
    const gate=g.gates.find(x=>x.level===next);
    if(gate&&earned<gate.required)break;
    level=next;
    credits+=g.ranks.some(r=>r.from===next&&r.from>1)?40:10
   }
   assert.ok(credits>=0,'simulation never overspends');
   assert.ok(level>=1&&level<=50);
   assert.ok(xp>=0&&xp<Number.MAX_SAFE_INTEGER);
   for(const gate of g.gates)if(level>=gate.level)assert.ok(earned>=gate.required,'mastery was bypassed at gate '+gate.level);
   progress.push(level)
  }
  assert.ok(progress.every((l,i)=>i===0||l>=progress[i-1]));
  return {xp,level,taps,credits,spent,bought}
 };
 const profiles=[
  {taps:30,wheel:3},
  {taps:150,wheel:2},
  {taps:450,wheel:1},
  {taps:950,wheel:1}
 ];
 const results=profiles.map(x=>({base:simulation(x.taps,x.wheel,false),boost:simulation(x.taps,x.wheel,true)}));
 for(const [index,row] of results.entries()){
  assert.ok(row.boost.xp>=row.base.xp);
  assert.ok(row.boost.level>=row.base.level);
  assert.ok(row.boost.credits<=row.base.credits+500);
  assert.ok(row.boost.bought>=1);
  if(index)assert.ok(row.base.xp>=results[index-1].base.xp)
 }
 assert.ok(results[0].base.level<results[3].base.level);
});

test('phase 6 all numeric admin parameters are bounded and reject arbitrary SQL keys',async()=>{
 const h=harness();
 try{
  await h.webhook(callback(adminId,'mrxp:admin:econ_edit_reward_mission'));
  assert.equal(h.pending.get(String(adminId)).edit_key,'econ:reward_mission');
  await h.webhook(message(adminId,'0'));
  assert.equal(h.settings.has('mrxp_balance_reward_mission'),false);
  await h.webhook(message(adminId,'9999999'));
  assert.equal(h.settings.has('mrxp_balance_reward_mission'),false);
  await h.webhook(message(adminId,'40'));
  assert.equal(h.settings.get('mrxp_balance_reward_mission'),'40');
  assert.equal(h.balanceAudit.length,1);
  await h.webhook(callback(adminId,'mrxp:admin:econ_edit_not_an_allowlisted_key'));
  assert.equal(h.pending.has(String(adminId)),false);
  assert.equal(h.balanceAudit.length,1)
 }finally{h.restore()}
});


test('phase 6 oversized or non-object inputs are rejected before reaching credits or XP',async()=>{
 const h=harness();h.env.DEV_MODE='true';
 const root='https://mrxpronos-play.cinecanaux-xpronos.workers.dev';
 const auth=signedTelegramUser({id:96107,first_name:'Tina'});
 const post=(path,payload)=>worker.fetch(new Request(root+path,{method:'POST',headers:{'x-telegram-init-data':auth,'content-type':'application/json'},body:payload}),h.env);
 try{
  let r=await post('/api/shop/buy',JSON.stringify({sku:'tap-110',purchase_id:'f0010000-0000-4000-8000-000000000009',filler:'x'.repeat(5000)}));
  assert.equal(r.status,413);
  r=await post('/api/shop/activate',JSON.stringify({purchase_id:'f0010000-0000-4000-8000-000000000009',filler:'x'.repeat(5000)}));
  assert.equal(r.status,413);
  r=await post('/api/sync',JSON.stringify({batch_id:'security-batch-0001',taps:2,filler:'x'.repeat(17000)}));
  assert.equal(r.status,413);
  r=await post('/api/sync','null');
  assert.equal(r.status,400);
  r=await post('/api/sync','[]');
  assert.equal(r.status,400);
  assert.equal(h.creditEvents.size,0);
  assert.equal(h.boostInventory.size,0);
  assert.equal(h.player.confirmed_xp,0)
 }finally{h.restore()}
});

test('official existing graphics replace repeated Mini App emoji placeholders without changing game actions',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  assert.ok(html.includes('id="mrxp-existing-icon-cleanup"'));
  for(const filename of [
   '03-wheel-rewards/21-lucky-wheel-full.webp',
   '01-brand/06-mrxp-token-coin.webp',
   '03-wheel-rewards/25-gift-box.webp',
   '04-quests-progression/31-quests-target.webp',
   '11-progression-vfx/80-mastery-seal.webp',
   '11-progression-vfx/78-prestige-star.webp',
   '06-game-states/51-locked-padlock.webp',
   '04-quests-progression/38-level-crown.webp',
   '01-brand/07-energy-blue-bolt.webp',
   '06-game-states/55-telegram-channel.webp',
   '04-quests-progression/37-success-green-check.webp',
   '05-mrxp-legends-nft/50-nft-collection-chest.webp'
  ])assert.ok(html.includes(filename),'missing reused graphic: '+filename);
  // The two full-card V2 files remain in the SHA-verified asset manifest;
  // phase 4 correctly replaces their former dark button thumbnails with a camera glyph.
  assert.ok(html.includes('mrxp-camera-icon'),'new legible camera pictogram missing');
  assert.ok(!html.includes('<img class="mrxp-ui-pictogram mrxp-profile-card-pictogram"'),
    'old pre-painted square card thumbnail should not be used as an action glyph');
  for(const placeholder of [
   '<h2>🎡 LUCKY WHEEL</h2>',
   '<h3>🪙 CRÉDITS MRXP</h3>',
   '<span class="section-title">🏆 DÉFIS DE MAÎTRISE</span>',
   '<span class="section-title">⭐ PROGRESSION V2</span>',
   '<h3>🔒 PROCHAIN RANG</h3>',
   '<strong>👑 COLLECTION DES AVATARS</strong>',
   '<span class="section-title">⚡ BOOSTS DISPONIBLES</span>',
   'id="mrxp-share-telegram">✈️ Lien Telegram',
   '<h3>📸 PARTAGER MON PROFIL</h3>',
   'id="mrxp-share-create">🎨 CRÉER MA CARTE OFFICIELLE',
   '<span class="section-title">🎒 MON INVENTAIRE</span>'
  ])assert.ok(!html.includes(placeholder),'obsolete emoji remains: '+placeholder);
  assert.ok(html.includes('heroBadge.dataset.rankBadge'),'dynamic official rank shield not wired');
  assert.ok(html.includes('mrxp-avatar-lock'),'avatar lock handler missing');
  const inline=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
    .map(m=>m[1]).filter(Boolean);
  assert.ok(inline.length>=2,'inline Mini App scripts missing');
  for(const source of inline)assert.doesNotThrow(()=>new vm.Script(source),'inline UI JavaScript must parse');
 }finally{h.restore()}
});


test('approved icon library 86-92 is complete, transparent and wired to each action',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  assert.ok(html.includes('id="mrxp-icons-86-92-style"'));
  const manifest=JSON.parse(await readFile(new URL('../assets-manifest-86-92.json',import.meta.url),'utf8'));
  assert.equal(manifest.assets.length,7);
  assert.deepEqual(manifest.assets.map(x=>x.number),[86,87,88,89,90,91,92]);
  for(const item of manifest.assets){
   for(const ext of ['png','webp']){
    const bytes=await readFile(new URL('../'+item[ext],import.meta.url));
    assert.ok(bytes.length>1000,'icon too small: '+item[ext]);
    assert.equal(createHash('sha256').update(bytes).digest('hex'),item['sha256_'+ext]);
   }
   assert.ok(html.includes(item.webp),'icon not referenced from page: '+item.webp);
  }
  assert.ok(html.includes('id="mrxp-open-wheel"')&&html.includes('86-snake-mignon.webp'),'new cute Snake art missing');
  assert.ok(html.includes('id="mrxp-share-download"')&&html.includes('88-telecharger-png.webp'));
  assert.ok(html.includes('id="mrxp-share-native"')&&html.includes('89-partager-image.webp'));
  assert.ok(html.includes('id="mrxp-share-copy"')&&html.includes('90-copier-preuve.webp'));
  assert.ok(html.includes('id="mrxp-shop-back"')&&html.includes('91-retour-navigation.webp'));
  assert.ok(html.includes('id="mrxp-shop-refresh"')&&html.includes('92-actualiser-navigation.webp'));
  for(const text of ['>🐍</span>','🛍️ BOUTIQUE DE BOOSTS GRATUITS','🛍️ OUVRIR LA BOUTIQUE DE BOOSTS','⬇️ Enregistrer PNG','📤 Partager l\'image','🔗 Copier la preuve','← RETOUR AUX JEUX','↻ ACTUALISER'])
   assert.ok(!html.includes(text),'obsolete icon placeholder: '+text);
  const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]).filter(Boolean);
  assert.ok(scripts.length>=2);
  for(const source of scripts)assert.doesNotThrow(()=>new vm.Script(source),'Mini App inline script must remain valid');
  for(const handler of ['mrxpDownloadShareCard','mrxpNativeShareCard','mrxpCopyShareLink','mrxpRefreshShop'])
   assert.ok(html.includes(handler),'existing button handler missing: '+handler);
 }finally{h.restore()}
});


test('phase 1 shares only the short public Telegram bot link without session data',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  assert.ok(html.includes('const MRXP_PUBLIC_BOT_LINK="https://t.me/MrXpronosPlayBot"'));
  const begin=html.indexOf('const MRXP_PUBLIC_BOT_LINK=');
  const end=html.indexOf('async function authFetch(',begin);
  assert.ok(begin>0&&end>begin,'Public share handler not located');
  const handler=html.slice(begin,end);
  assert.ok(handler.includes('encodeURIComponent(MRXP_PUBLIC_BOT_LINK)'));
  for(const forbidden of ['location.href','location.hash','initData','tgWebAppData','window.Telegram.WebApp.initData'])
    assert.ok(!handler.includes(forbidden),'Session data must not be copied into share links: '+forbidden);
  assert.ok(html.includes('mrxpTelegramShareLink'),'Public profile proof share stays available and separate');
  assert.ok(html.includes('mrxpSharedCard.verify_url'),'Proof token remains distinct from bot invite');
 }finally{h.restore()}
});

test('phase 1 protects mobile missions, controls and profile card artwork from overflowing',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  assert.ok(html.includes('id="mrxp-phase1-mobile-safety"'),'Responsive fix stylesheet missing');
  for(const css of [
   '#screen-missions .mission .reward img',
   'width:17px!important;height:17px!important',
   '#screen-missions .mission.mrxp-daily-mission',
   '#screen-missions>.banner',
   '#screen-tap #wheel-shortcut',
   '.nav{background:#07162f',
   '@media(max-width:350px)',
   '#screen-profile #mrxp-share-preview'
  ])assert.ok(html.includes(css),'Missing mobile protection: '+css);
  assert.ok(html.includes('picture.className="mrxp-mission-reward-check"'));
  assert.ok(html.includes('daily.className="mission mrxp-daily-mission"'));
  assert.ok(!html.includes('c.drawImage(art,0,0,W,H)'),'Old illustrated card must not be overdrawn beneath live text');
  // Phase 4 has independent vertical / square footer geometry. All captions must fit.
  for(const safeFooter of ['vertical?1695:933','vertical?1750:963','vertical?1810:994','vertical?1863:1026'])
    assert.ok(html.includes(safeFooter),'Share card captions must remain within 1080×1080 and 1080×1920 bounds');
  const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m=>m[1]).filter(Boolean);
  for(const text of scripts)assert.doesNotThrow(()=>new vm.Script(text),'Inline JS must parse after phase 1');
 }finally{h.restore()}
});


test('phases 2 and 3 keep live home, wheel and profile actions while restoring mobile hierarchy',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const page=await res.text();
  for(const need of [
   'id="mrxp-mobile-phase2-3"',
   'mrxp-wheel-feature-copy',
   'mrxp-promo-refined',
   'mrxp-promo-copy',
   'Gagne des XP Points',
   'mrxp-games-grid-refined',
   'mrxp-profile-hero-art',
   'mrxp-profile-rank-stack',
   'MA PROGRESSION',
   'id="mrxp-progress-percent"',
   'background:none!important',
   'SOLDE MRXP',
   'BOUTIQUE DE BOOSTS',
   'id="mrxp-rank-stars"',
   'id="mrxp-next-rank-details"',
   'id="mrxp-refresh-progress"',
   'id="sync-button"',
   'id="tap-button"',
   'id="mrxp-open-wheel"',
   'id="mrxp-back-games"',
   'id="mrxp-share-create"',
   'id="mrxp-credit-history"'
  ]) assert.ok(page.includes(need),'Missing or renamed game/UI control '+need);
  for(const obsolete of ['> PROGRESSION V2</span>','> MON SOLDE MRXP</h3>','> OUVRIR LA BOUTIQUE DE BOOSTS</button>',
    'Gagne des <b>XP Points</b>Prépare ta progression'])
   assert.ok(!page.includes(obsolete),'Old presentation remains: '+obsolete);
  assert.ok(page.includes('promo.append(ps);'),'XP promotion must not load extra distracting rocket');
  assert.ok(page.includes('window.openWheel=openWheel'),'Wheel entry must preserve real click handler');
  assert.ok(page.includes('renderProfileCollection()'),'Profile collection must remain dynamic');
  assert.ok(page.includes('renderProgressionSummary()'),'Server progress must remain dynamic');
  assert.ok(page.includes('mrxpRefreshCredits()'),'Credit refresh must remain functional');
  assert.ok(page.includes('mrxpDrawShareImage(snapshot,vertical,avatar)'),'Share card rendering unaffected');
  for(const js of [...page.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]).filter(Boolean))
   assert.doesNotThrow(()=>new vm.Script(js),'Inline game code must parse after phases 2 and 3');
 }finally{h.restore()}
});


test('phase 4 final share card layouts keep signed server data and two real PNG formats',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  assert.ok(html.includes('id="mrxp-phase4-5-ui"'));
  for(const marker of [
   'function mrxpDrawShareImage(snapshot,vertical,avatar)',
   'const W=1080,H=vertical?1920:1080',
   'function mrxpShareBadgeArt(level)',
   'avatar.mrxpOfficialBadge=await mrxpShareBadgeArt(answer.snapshot.level)',
   'mrxpDrawShareImage(answer.snapshot,vertical,avatar)',
   'snapshot.display_name',
   'snapshot.xp',
   'snapshot.missions',
   'snapshot.mastery',
   'snapshot.issued_ms',
   'authFetch("/api/share/profile","POST",{hide_name:hide})',
   'mrxpSharedCard={blob,name,preview_url,snapshot:answer.snapshot,verify_url:answer.verify_url}',
   'mrxpCanvasBlob(canvas)',
   'navigator.share({title:"Mon profil Mr XPRONOS Play",text,files:[file]})',
   'mrxp-share-copy',
   'mrxp-share-download',
   'mrxp-share-native',
   'mrxp-share-telegram',
   'mrxp-camera-icon',
   'Preuve officielle accessible via le lien partagé'
  ])assert.ok(html.includes(marker),'Missing signed share feature '+marker);
  const renderer=html.slice(html.indexOf('function mrxpDrawShareImage('),html.indexOf('function mrxpCanvasBlob('));
  assert.ok(!renderer.includes('c.drawImage(art,0,0,W,H)'),'Pre-painted template causes duplicate text');
  for(const old of [
   '<img class="mrxp-ui-pictogram mrxp-profile-card-pictogram"',
   '<img class="mrxp-ui-pictogram mrxp-profile-card-button"'
  ]) assert.ok(!html.includes(old),'A dark old share thumbnail remains: '+old);
  const section=html.slice(html.indexOf('async function mrxpBuildShareCard('),html.indexOf('function mrxpDownloadShareCard('));
  assert.ok(!section.includes('location.href')&&!section.includes('window.Telegram.WebApp.initDataUnsafe'),
    'Share renderer must never serialize the Telegram session URL');
 }finally{h.restore()}
});

test('phase 5 friends and missions are compact, real-data-driven, and retain server rewards',async()=>{
 const h=harness();
 try{
  const res=await worker.fetch(new Request('https://mrxpronos-play.cinecanaux-xpronos.workers.dev/'),h.env);
  assert.equal(res.status,200);
  const html=await res.text();
  const friends=html.slice(html.indexOf('<section class="section" id="screen-friends">'),
                           html.indexOf('<section class="section" id="screen-profile">'));
  for(const marker of ['id="share-button"','id="mrxp-friends-copy"',
                       't.me/MrXpronosPlayBot','14-nav-friends.webp','mrxp-friends-actions',
                       'Aucune récompense de parrainage'])
    assert.ok(friends.includes(marker),'Friends screen missing '+marker);
  assert.ok(!friends.includes('TABLEAU DE BORD')&&!friends.includes('récompenses sociales seront disponibles'),
     'Do not invent referral dashboards or rewards');
  assert.ok(html.includes('$("mrxp-friends-copy").onclick=async()=>{'));
  assert.ok(html.includes('navigator.clipboard.writeText(MRXP_PUBLIC_BOT_LINK)'));
  assert.ok(html.includes('encodeURIComponent(MRXP_PUBLIC_BOT_LINK)'));
  assert.ok(html.includes('mrxp-credit-rules'));
  assert.ok(html.includes('mrxp-legends-teaser'));
  assert.ok(html.includes('mrxp-weekly-track'));
  assert.ok(html.includes('wallet.weekly||{}'));
  assert.ok(html.includes('meter.setAttribute("aria-valuenow"'));
  assert.ok(html.includes('if(m.kind==="tap")middle.append(bar)'), 'Non-numeric mission must not show false 0% bar');
  assert.ok(html.includes('mrxp-mission-reward-check'));
  for(const marker of ['mrxp-credit-daily-goals','mrxp-credit-weekly','mrxp-credit-history',
                       'missionServer','claimMission(m.key)','mrxpRefreshCredits()','mrxpRenderWallet()'])
    assert.ok(html.includes(marker),'Existing rewards/sync path removed: '+marker);
  const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(x=>x[1]).filter(Boolean);
  for(const code of scripts)assert.doesNotThrow(()=>new vm.Script(code),'Frontend JS must parse after phase 5');
 }finally{h.restore()}
});
