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
   const method=String(url).split('/').pop(),body=JSON.parse(options.body||'{}');
   calls.push({method,body});
   return Response.json({ok:true,result:true});
  };
  return ()=>{globalThis.fetch=previous;};
 }};
}
const update=(uid,text)=>({message:{chat:{type:'private',id:uid},from:{id:uid},message_id:3,text}});
const lastMessage=calls=>calls.filter(x=>x.method==='sendMessage').at(-1)?.body;

test('a new visitor only sees the Mini App, not categories or admin controls',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,update(123,'/start'));
  const sent=lastMessage(f.calls);
  assert.match(sent.text,/Bienvenue sur CINÉ RADAR/);
  assert.match(sent.text,/Rechercher/);
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
test('owner gets a private administration button while retaining the Mini App',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,update(900,'/start'));
  const buttons=lastMessage(f.calls).reply_markup.inline_keyboard.flat();
  assert.equal(buttons.length,2);
  assert.equal(buttons[0].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app');
  assert.equal(buttons[1].web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/admin');
  await botUpdate(f.env,update(900,'/admin'));
  assert.match(lastMessage(f.calls).text,/espace propriétaire/);
  assert.equal(lastMessage(f.calls).reply_markup.inline_keyboard.flat().length,2);
 }finally{restore()}
});
test('old category inline callbacks are acknowledged and replaced with Mini App shortcut',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await botUpdate(f.env,{callback_query:{id:'legacy-42',from:{id:123},message:{message_id:4,chat:{id:123,type:'private'}},data:'category:series:2'}});
  assert.ok(f.calls.some(x=>x.method==='answerCallbackQuery'));
  const message=f.calls.find(x=>x.method==='editMessageText')?.body;
  assert.ok(message);
  assert.match(message.text,/Mini App/);
  assert.equal(message.reply_markup.inline_keyboard.length,1);
  assert.ok(!JSON.stringify(message.reply_markup).includes('category:'));
 }finally{restore()}
});
test('Telegram default command list has only start, owner receives scoped admin commands',async()=>{
 const f=setup();const restore=f.mock();
 try{
  await initializeProfile(f.env);
  const list=f.calls.filter(x=>x.method==='setMyCommands');
  assert.equal(list.length,2);
  assert.deepEqual(list[0].body.scope,{type:'default'});
  assert.deepEqual(list[0].body.commands.map(x=>x.command),['start']);
  assert.deepEqual(list[1].body.scope,{type:'chat',chat_id:900});
  assert.deepEqual(list[1].body.commands.map(x=>x.command),['start','admin','tendances','manquants','canaux','actualiser','autoriser']);
  const menu=f.calls.filter(x=>x.method==='setChatMenuButton');
  assert.equal(menu.length,2);
  assert.equal(menu[0].body.menu_button.type,'commands');
  assert.deepEqual(menu[1].body.chat_id,900);
  assert.equal(menu[1].body.menu_button.web_app.url,'https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/admin');
  assert.ok(f.calls.some(x=>x.method==='setMyDescription'&&/Mini App/.test(x.body.description)));
  assert.ok(f.writes.some(x=>x.includes("'10'")));
 }finally{restore()}
});
