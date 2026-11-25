import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ingestPinUpdate,servePinned} from '../pinned-showcase.mjs';
import {APP_HTML} from '../app-page.mjs';
const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
const pinSource=readFileSync(new URL('../pinned-showcase.mjs',import.meta.url),'utf8');
const IMAGE_ID='AgACAgQAAxkBAAIBtestIMAGESAFE_'+'x'.repeat(45);
const CHANNEL=-1003921647496;

test('home has no duplicated poster shortcuts before Explore par univers',()=>{
 assert.ok(!APP_HTML.includes('Les affiches par univers'));
 assert.ok(!APP_HTML.includes('cine-pinned-category-quick'));
 assert.ok(APP_HTML.includes('sectionTitle(home,"Explore par univers",null)'));
 assert.ok(APP_HTML.includes('quickButton("film","Films","films")'));
 assert.ok(APP_HTML.includes('quickButton("tv","Séries","series")'));
 assert.ok(APP_HTML.includes('quickButton("gamepad","Animés","animes")'));
});

test('À l’affiche preserves heading and Films Séries Animés label and highlights Tout voir like Chercher',()=>{
 assert.ok(APP_HTML.includes('document.createTextNode("À l\'affiche")'));
 assert.ok(APP_HTML.includes('Films · Séries · Animés'));
 assert.ok(APP_HTML.includes('node("button","cine-link cine-showcase-all","Tout voir")'));
 assert.ok(APP_HTML.includes('.cine-home-search button,.cine-primary{border:0;background:linear-gradient(115deg,#7157e9,#367cf5)'));
 assert.ok(APP_HTML.includes('.cine-showcase-all{border:0;background:linear-gradient(115deg,#7157e9,#367cf5)'));
});

test('All Films Series Animes gallery buttons reuse existing 3D illustrations, not emoji',()=>{
 assert.ok(APP_HTML.includes('["all","Tout","affiches"],["films","Films","film"],["series","Séries","tv"],["animes","Animés","gamepad"]'));
 assert.ok(APP_HTML.includes('if(kind==="all")b.append(cineCategoryIcon(iconKey))'));
 assert.ok(APP_HTML.includes('node("span","icon cine-3d-icon cine-icon-"+iconKey)'));
 assert.ok(APP_HTML.includes('.cine-pinned-filters button .cine-3d-icon'));
 assert.ok(APP_HTML.includes('.cine-pinned-filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))'));
});

function dbFixture({edit=false}={}){
 const writes=[];const db={prepare(sql){let args=[];const q={
  bind(...v){args=v;return q},
  async first(){
   if(sql.includes('SELECT chat_id FROM radar_primary_channels'))return {chat_id:String(CHANNEL)};
   if(sql.includes('FROM cine_pinned_posts')&&sql.includes('active=1'))return edit?{message_id:52}:null;
   return null;
  },
  async all(){return {results:[]}},
  async run(){writes.push({sql,args});return {meta:{changes:1}}}
 };return q;}};
 return {DB:db,writes};
}
const pinned={message_id:52,caption:'Nouveau film VF',photo:[{file_id:IMAGE_ID,file_size:100000}]};
const chat={type:'channel',username:'CineXFilms_vf',id:CHANNEL};

test('new Telegram pin event indexes poster immediately and does not poll getChat',async()=>{
 const f=dbFixture();const old=globalThis.fetch;let external=0;
 globalThis.fetch=async()=>{external++;throw Error('No external Telegram API request on webhook pin update')};
 try{
  const ok=await ingestPinUpdate({DB:f.DB,TELEGRAM_TOKEN:'token'},{channel_post:{chat,pinned_message:pinned}});
  assert.equal(ok,true);
  const upsert=f.writes.find(w=>w.sql.includes('INSERT INTO cine_pinned_posts'));
  assert.ok(upsert,'Pin must enter D1 immediately from channel_post');
  assert.equal(upsert.args[0],'films');
  assert.equal(upsert.args[2],52);
  assert.equal(external,0);
 }finally{globalThis.fetch=old}
});

test('an edited pinned poster is updated but an unrelated edited channel post is ignored',async()=>{
 const old=globalThis.fetch;
 try{
  globalThis.fetch=async()=>{throw Error('Editing should not call Telegram')};
  const known=dbFixture({edit:true});
  const updated=await ingestPinUpdate({DB:known.DB},{edited_channel_post:{chat,...pinned,caption:'Nouveau titre officiel'}});
  assert.equal(updated,true);
  assert.ok(known.writes.some(w=>w.sql.includes('INSERT INTO cine_pinned_posts')&&w.args[3]==='Nouveau titre officiel'));
  const editedWrite=known.writes.find(w=>w.sql.includes('INSERT INTO cine_pinned_posts'));
  assert.equal(editedWrite.args[7],'pin_event','D1 CHECK source must accept edited pinned-post updates');
  assert.ok(['getchat','pin_event','owner_forward'].includes(editedWrite.args[7]));
  const unrelated=dbFixture({edit:false});
  assert.equal(await ingestPinUpdate({DB:unrelated.DB},{edited_channel_post:{chat,...pinned}}),false);
  assert.ok(!unrelated.writes.some(w=>w.sql.includes('INSERT INTO cine_pinned_posts')));
 }finally{globalThis.fetch=old}
});

test('GET pinned gallery reads only D1 and never makes extra Telegram getChat requests',async()=>{
 const f=dbFixture();const old=globalThis.fetch;let network=0;
 globalThis.fetch=async()=>{network++;throw Error('Unexpected external call')};
 try{
  const result=await servePinned({DB:f.DB,TELEGRAM_TOKEN:'token'},new Request('https://cine.example/api/pinned-showcase'));
  assert.equal(result.status,200);
  assert.equal((await result.json()).total,0);
  assert.equal(network,0,'Only opening the app must not invoke Telegram API');
  assert.ok(!pinSource.includes('try{await syncLatestPinned(env);}catch'));
 }finally{globalThis.fetch=old}
});

test('Telegram webhook is immediate; existing six-hour cron reconciles pins only at UTC 00 and 12',()=>{
 assert.ok(worker.includes('if(update.channel_post||update.edited_channel_post){'));
 assert.ok(worker.includes('await ingestPinUpdate(env,update);'));
 assert.ok(!worker.includes('observeChannelPublication'),'Reaction observation now belongs exclusively to GitHub');
 assert.ok(!worker.includes('processReactionQueue'));
 assert.ok(!worker.includes('enqueueChannelReactions'));
 assert.ok(!worker.includes('setMessageReaction'));

 assert.ok(worker.includes('if(hour===0||hour===12)jobs.push(syncLatestPinned(env,{force:true}))'));
 assert.ok(worker.includes('controller.cron==="0 */6 * * *"'));
 assert.ok(!APP_HTML.includes('setInterval(()=>{if(!document.hidden)refreshPinnedFeed()},90000)'));
 assert.ok(APP_HTML.includes('document.addEventListener("visibilitychange"'));
});
