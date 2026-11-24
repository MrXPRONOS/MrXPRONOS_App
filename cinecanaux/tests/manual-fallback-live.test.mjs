import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {D1Remote,TelegramBot,FallbackPublisher,
 publicKeyboard,privateKeyboard,internalMessageUrl}
 from '../manual-fallback-live.mjs';

const src='-1001111111111',priv='-1002222222222',
 pub='-1003333333333',stock='-1004444444444';
const folder='https://t.me/addlist/ZmW4vfwcrMAwNzJk';
const rescue='https://t.me/+abcdefghijklmnop';
const handle='@cinexfilms_vf';
function fixtures(){
 const sqlite=new DatabaseSync(':memory:');
 sqlite.exec(readFileSync(new URL('../migrations/029_cinex_manual_fallback.sql',import.meta.url),'utf8'));
 sqlite.exec(
  "CREATE TABLE cine_private_stock_config(singleton INTEGER PRIMARY KEY,stock_chat_id TEXT,radar_bot_id INTEGER,ready INTEGER);"+
  "CREATE TABLE bot_settings(setting_key TEXT,value TEXT);"+
  "CREATE TABLE cine_private_stock_bots(bot_id INTEGER PRIMARY KEY,can_post INTEGER);"+
  "CREATE TABLE cine_classic_links(token TEXT PRIMARY KEY,source_chat_id TEXT,source_message_id INTEGER,title TEXT,public_handle TEXT,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(source_chat_id,source_message_id));"+
  "CREATE TABLE cine_classic_rescue_config(public_handle TEXT,invite_url TEXT);"
 );
 sqlite.prepare("INSERT INTO cine_private_stock_config VALUES(1,?,123,1)").run(stock);
 sqlite.prepare("INSERT INTO bot_settings VALUES('cine_delivery_enabled','1')").run();
 sqlite.prepare("INSERT INTO cine_private_stock_bots VALUES(98765,1)").run();
 sqlite.prepare("INSERT INTO cine_classic_rescue_config VALUES(?,?)").run(handle,rescue);
 const db={
  async query(sql,params=[]){
   const statement=sqlite.prepare(sql);
   if(sql.trim().toUpperCase().startsWith('SELECT'))
    return {results:statement.all(...params)};
   return {results:[],meta:{changes:statement.run(...params).changes}};
  },
  env(){
   return {DB:{prepare(sql){
    let params=[];
    return {
     bind(...xs){params=xs;return this},
     async run(){return {meta:(await db.query(sql,params)).meta||{changes:0}}},
     async first(){return (await db.query(sql,params)).results?.[0]||null},
     async all(){return {results:(await db.query(sql,params)).results||[]}},
    };
   }}};
  }
 };
 const calls=[];
 let counter=100;
 const bot={
  async identity(){return {id:98765,is_bot:true,username:'mrxp_bot'}},
  async verifyChannel(chat){
   const id=chat===handle?pub:chat;
   return {id:Number(id),username:chat===handle?handle.slice(1):undefined,
    type:'channel'};
  },
  async api(method,body){
   calls.push({method,body});
   return {message_id:++counter};
  },
 };
 const publisher=new FallbackPublisher({
  db,categoryBots:{films:bot,series:bot,animes:bot,formation_business:bot},
  targets:{
   films:{private:priv,public:handle},
   series:{private:priv,public:handle},
   animes:{private:priv,public:handle},
  },
  formationTargets:{business:'-1005555555555'},stage:'-1006666666666',
  folder,tokenGenerator:()=>'abcdefghijklmnopqrstuvwx'
 });
 return {sqlite,db,bot,calls,publisher};
}

test('every public film card has exactly four correct buttons',()=>{
 const b=publicKeyboard('films',internalMessageUrl(priv,50),
  'https://t.me/CineRadarFr_Bot?start=d_abcdefghijklmnopqrstuvwx',
  rescue,folder);
 assert.equal(b.inline_keyboard.length,4);
 assert.match(b.inline_keyboard[0][0].text,/VOIR LE FILM/);
 assert.throws(()=>publicKeyboard('films',internalMessageUrl(priv,50),
  'https://fraud.example/fake',rescue,folder));
});
test('private card is exactly three independent verified links',()=>{
 const b=privateKeyboard(handle,'https://t.me/CineRadarFr_Bot?start=d_abcdefghijklmnopqrstuvwx',folder);
 assert.equal(b.inline_keyboard.length,3);
 assert.equal(b.inline_keyboard[0][0].url,'https://t.me/cinexfilms_vf');
});
test('legacy private message IDs never guess a public URL',()=>{
 assert.equal(internalMessageUrl(priv,5),'https://t.me/c/2222222222/5');
 assert.throws(()=>internalMessageUrl('@not_private',3));
});
test('one film creates central, private and public receipts with no repeat on rerun',async()=>{
 const {sqlite,publisher,calls}=fixtures();
 const film={category:'films',key:'films:sample movie:2025',source_chat_id:src,
  video_message_id:11,poster_message_id:10,file_unique_id:'unique-film-001'};
 await publisher.copyFilm(film);
 assert.equal(calls.length,5);
 assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM cine_manual_fallback_receipts WHERE status=?').get('complete').n,5);
 assert.equal(sqlite.prepare('SELECT COUNT(*) AS n FROM cine_classic_links').get().n,1);
 assert.equal(calls.filter(x=>x.body.reply_markup).length,2);
 await publisher.copyFilm(film);
 assert.equal(calls.length,5);
});
test('owner stock can be the same channel as private library without copying video',async()=>{
 const f=fixtures();
 f.publisher.targets.films.private=src;
 const film={category:'films',key:'films:private source:2026',
  source_chat_id:src,video_message_id:13,poster_message_id:12};
 await f.publisher.copyFilm(film);
 assert.equal(f.calls.length,4);
 const video=f.sqlite.prepare("SELECT target_message_id FROM cine_manual_fallback_receipts WHERE stage='private_video'").get();
 assert.equal(video.target_message_id,13);
});
test('uncertain send blocks second attempt',async()=>{
 const f=fixtures();let attempt=0;
 f.bot.api=async()=>{attempt++;throw Error('telegram_response_uncertain')};
 const film={category:'films',key:'films:crashed movie:2025',
  source_chat_id:src,video_message_id:18,poster_message_id:17};
 await assert.rejects(f.publisher.copyFilm(film));
 assert.equal(attempt,1);
 await assert.rejects(f.publisher.copyFilm(film));
 assert.equal(attempt,1);
 assert.equal(f.sqlite.prepare("SELECT status FROM cine_manual_fallback_receipts").get().status,'uncertain');
});
test('season uses central delivery links, one index and ordered public videos',async()=>{
 const f=fixtures();
 const series={category:'series',key:'series:sample series:S01',
  title:'sample series',season:1,source_chat_id:src,poster_message_id:20,
  episodes:[{number:1,video_message_id:21,file_unique_id:'ep-1'},
            {number:2,video_message_id:22,file_unique_id:'ep-2'}]};
 await f.publisher.copySeason(series);
 assert.equal(f.calls.filter(x=>x.method==='sendMessage').length,1);
 assert.equal(f.calls.filter(x=>x.body.reply_markup).length,2);
 assert.equal(f.sqlite.prepare("SELECT COUNT(*) AS n FROM cine_classic_links").get().n,2);
 await f.publisher.copySeason(series);
 assert.equal(f.calls.length,9);
});
test('formation copies numbered parts through verified technical stage to destination',async()=>{
 const f=fixtures();
 const training={category:'formation_business',key:'formation_business:entreprise2026',
  source_chat_id:src,poster_message_id:22,parts:[
   {number:1,message_id:25,file_unique_id:'part-a'},
   {number:2,message_id:26,file_unique_id:'part-b'},
  ]};
 await f.publisher.copyCourse(training);
 assert.equal(f.calls.length,4);
 await f.publisher.copyCourse(training);
 assert.equal(f.calls.length,4);
});
test('publisher fails closed before first video when bot lacks a verified destination',async()=>{
 const f=fixtures();delete f.publisher.targets.films;
 await assert.rejects(f.publisher.copyFilm({category:'films',
  key:'films:no dest:2025',source_chat_id:src,poster_message_id:1,
  video_message_id:2}));
 assert.equal(f.calls.length,0);
});
