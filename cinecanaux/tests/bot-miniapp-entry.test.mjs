import test from 'node:test';
import assert from 'node:assert/strict';
import {botUpdate,initializeProfile} from '../radar-lean.mjs';

function setup({ownerId=900}={}){
 const calls=[],writes=[];
 const DB={prepare(sql){let values=[];const statement={
  bind(...args){values=args;return statement;},
  async first(){
   if(sql.includes('SELECT role FROM admin_users'))return values[0]===ownerId?{role:'owner'}:null;
   if(sql.includes('bot_settings'))return {value:'9'};
   return null;
  },
  async all(){
   if(sql.includes('SELECT user_id FROM admin_users'))return {results:[{user_id:ownerId}]};
   return {results:[]};
  },
  async run(){writes.push(sql);return {success:true};}
 };return statement;}};
 const env={DB,TELEGRAM_TOKEN:'test:token'};
 return {env,calls,writes, mock(){
  const previous=globalThis.fetch;
  globalThis.fetch=async(url,options={})=>{
   if(String(url).includes('raw.githubusercontent.com/')&&String(url).endsWith('/bot-profile.jpg')){
    const jpg=new Uint8Array(12000);jpg[0]=255;jpg[1]=216;jpg[2]=255;
    return new Response(jpg,{headers:{'content-type':'image/jpeg'}});
   }
   const method=String(url).split('/').pop();
   const body=options.body instanceof FormData?Object.fromEntries(options.body.entries()):JSON.parse(options.body||'{}');
   calls.push({method,body});
   return Response.json({ok:true,result:true});
  };
  return ()=>{globalThis.fetch=previous;};
 }};
}
const update=(uid,text)=>({message:{chat:{type:'private',id:uid},from:{id:uid},message_id:3,text}});
const lastMessage=calls=>{const m=calls.filter(x=>x.method==='sendMessage'||x.method==='sendPhoto').at(-1);return m?{...m.body,text:m.body.text||m.body.caption}:null};

test('a new visitor only sees the Mini App, not categories or admin controls',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,update(123,'/start'));
  const sent=lastMessage(f.calls);
  assert.ok(f.calls.some(x=>x.method==='sendPhoto'),'First /start must include the approved poster');
  assert.equal(sent.photo,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/assets/bot-start-poster.jpg');
  assert.match(sent.text,/BIENVENUE SUR CINÉ RADAR/);
  assert.match(sent.text,/<blockquote>/);
  assert.match(sent.text,/1️⃣/);
  assert.match(sent.text,/4️⃣/);
  assert.match(sent.text,/Explorer/);
  assert.equal(sent.reply_markup.inline_keyboard[0][0].style,"primary");
  assert.match(sent.text,/Mini App/);
  assert.equal(sent.reply_markup.inline_keyboard.length,1);
  assert.equal(sent.reply_markup.inline_keyboard[0][0].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app');
  assert.ok(!JSON.stringify(sent.reply_markup).includes('/admin'));
  assert.ok(!JSON.stringify(sent.reply_markup).includes('category:'));
  await botUpdate(f.env,update(123,'/films'));
  assert.equal(lastMessage(f.calls).reply_markup.inline_keyboard.length,1);
  await botUpdate(f.env,update(123,'/admin'));
  assert.equal(lastMessage(f.calls).reply_markup.inline_keyboard.length,1);
  assert.match(lastMessage(f.calls).text,/Mini App/);
 }finally{restore()}
});
test('owner receives two blue buttons after /start, visitor only the Mini App button',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,update(900,'/start'));
  const buttons=lastMessage(f.calls).reply_markup.inline_keyboard.flat();
  assert.equal(buttons.length,2);
  assert.equal(buttons[0].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app');
  assert.equal(buttons[1].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app?admin=1');
  assert.equal(buttons[0].style,'primary');
  assert.equal(buttons[1].style,'primary');
  assert.match(buttons[1].text,/Administration/);
  // Changing username without changing the enrolled ID must never grant privileges.
  await botUpdate(f.env,{message:{chat:{id:901,type:'private'},from:{id:901,username:'mr_xpronos'},text:'/start'}});
  const impostor=lastMessage(f.calls);
  assert.equal(impostor.reply_markup.inline_keyboard.length,1);
  assert.ok(!JSON.stringify(impostor.reply_markup).includes('Administration'));
  await botUpdate(f.env,update(900,'/admin'));
  assert.match(lastMessage(f.calls).text,/BIENVENUE SUR CINÉ RADAR/);
  assert.equal(lastMessage(f.calls).reply_markup.inline_keyboard.flat().length,1);
 }finally{restore()}
});
test('old category inline callbacks are acknowledged and replaced with Mini App shortcut',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,{callback_query:{id:'legacy-42',from:{id:123},message:{message_id:4,chat:{id:123,type:'private'}},data:'category:series:2'}});
  assert.ok(f.calls.some(x=>x.method==='answerCallbackQuery'));
  const message=f.calls.filter(x=>x.method==='sendPhoto').at(-1)?.body;
  assert.ok(message);
  assert.match(message.caption,/Mini App/);
  assert.equal(message.reply_markup.inline_keyboard.length,1);
  assert.ok(!JSON.stringify(message.reply_markup).includes('category:'));
 }finally{restore()}
});
test('Telegram menus open Mini App, and deprecated owner chat commands are cleared',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await initializeProfile(f.env);
  const list=f.calls.filter(x=>x.method==='setMyCommands');
  assert.equal(list.length,1);
  assert.deepEqual(list[0].body.scope,{type:'default'});
  assert.deepEqual(list[0].body.commands.map(x=>x.command),['start','aide','stop','confidentialite']);
  assert.ok(f.calls.some(x=>x.method==='deleteMyCommands'&&x.body.scope.chat_id===900));
  const menu=f.calls.filter(x=>x.method==='setChatMenuButton');
  assert.equal(menu.length,2);
  assert.equal(menu[0].body.menu_button.type,'web_app');
  assert.deepEqual(menu[1].body.chat_id,900);
  assert.equal(menu[1].body.menu_button.web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app');
  assert.ok(f.calls.some(x=>x.method==='setMyDescription'&&/Lancer Ciné Radar/.test(x.body.description)));
  assert.ok(f.calls.some(x=>x.method==='setMyShortDescription'&&/films, séries et animés/i.test(x.body.short_description)));
  assert.ok(f.writes.some(x=>x.includes("'13'")));
  assert.ok(f.calls.some(x=>x.method==='setMyProfilePhoto'),'Telegram bot avatar must be set');
 }finally{restore()}
});

test('visitor help, opt-out and privacy commands use formatted Telegram HTML',async()=>{
 const f=setup(),restore=f.mock();
 try{
  await botUpdate(f.env,update(123,'/aide'));
  assert.match(lastMessage(f.calls).text,/<blockquote>/);
  assert.match(lastMessage(f.calls).text,/5️⃣/);
  await botUpdate(f.env,update(123,'/stop'));
  assert.match(lastMessage(f.calls).text,/Annonces désactivées/);
  await botUpdate(f.env,update(123,'/confidentialite'));
  assert.match(lastMessage(f.calls).text,/identifiant de conversation/);
  assert.equal(lastMessage(f.calls).reply_markup.inline_keyboard[0][0].style,'primary');
 }finally{restore()}
});
