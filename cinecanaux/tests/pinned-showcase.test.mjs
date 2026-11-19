import test from 'node:test';
import assert from 'node:assert/strict';
import {pinCoverFile,pinnedTitle,PRIMARY_PINS,ingestOwnerForward,ingestPinUpdate,syncLatestPinned,listPinned,registerPinClick} from '../pinned-showcase.mjs';
import {APP_HTML} from '../app-page.mjs';
const imageId='AgACAgQAAxkBAAIBtestIMAGESAFE_'+'x'.repeat(45);
function dbFixture({lastCheck=null}={}){
 const writes=[],pins=[],primary=[
  {kind:'films',username:'CineXFilms_vf',chat_id:'-1003921647496'},
  {kind:'series',username:'seriesvf_cinex',chat_id:'-1004406527554'},
  {kind:'animes',username:'CineXAnimeFR',chat_id:'-1004347937458'}];
 const DB={prepare(sql){
  let args=[];const statement={
   bind(...x){args=x;return statement;},
   async first(){
    if(sql.includes('FROM radar_primary_channels')){
     if(sql.includes('WHERE kind='))return primary.find(x=>x.kind===args[0])||null;
     return primary.find(x=>x.chat_id===args[0])||null;
    }
    if(sql.includes('FROM cine_pins_poll'))return {last_attempt_at:lastCheck};
    if(sql.includes('FROM admin_users'))return {role:'owner'};
    return null;
   },
   async all(){
    if(sql.includes('FROM cine_pinned_posts'))return {results:pins};
    return {results:[]};
   },
   async run(){
    writes.push({sql,args});
    if(sql.includes('INSERT INTO cine_pinned_posts')){
     pins.push({kind:args[0],message_id:args[2],title:args[3],media_kind:args[6],click_count:0,last_seen_at:'2026-11-18 22:00:00',username:primary.find(x=>x.kind===args[0])?.username});
    }
    return {meta:{changes:1}};
   }
  };return statement;
 }};
 return {DB,writes,pins,primary};
}
const pin={message_id:52,caption:'THE ODYSSEY (2026) VF',photo:[{file_id:imageId,file_size:95000}],date:1795000000};
test('only the 3 official Telegram primary channels are trusted',()=>{
 assert.deepEqual(PRIMARY_PINS.map(x=>x.username),['CineXFilms_vf','seriesvf_cinex','CineXAnimeFR']);
});
test('image extraction chooses Telegram photo or video thumbnail, never the video itself',()=>{
 assert.equal(pinCoverFile(pin),imageId);
 assert.equal(pinCoverFile({video:{file_id:'video-do-not-use',thumbnail:{file_id:imageId}}}),imageId);
 assert.equal(pinCoverFile({video:{file_id:'only-video'}}),'');
 assert.equal(pinnedTitle(pin),'THE ODYSSEY (2026) VF');
});
test('getChat indexes only the image-bearing latest pinned message from each trusted channel',async()=>{
 const old=globalThis.fetch;const fixture=dbFixture();const requests=[];
 globalThis.fetch=async(url,options)=>{
  requests.push({url,body:JSON.parse(options.body)});
  const name=JSON.parse(options.body).chat_id.replace('@','');
  const matched=fixture.primary.find(x=>x.username===name);
  return Response.json({ok:true,result:{id:Number(matched.chat_id),type:'channel',username:name,pinned_message:pin}});
 };
 try{
  const result=await syncLatestPinned({DB:fixture.DB,TELEGRAM_TOKEN:'test-secret'},{force:true});
  assert.equal(result.checked,3);assert.equal(result.stored,3);assert.equal(result.errors.length,0);
  assert.equal(fixture.pins.length,3);
  assert.equal(requests.length,3);
  assert.ok(fixture.writes.filter(x=>x.sql.includes('INSERT INTO cine_pinned_posts')).every(x=>x.args[5]===imageId));
  assert.ok(!JSON.stringify(fixture).includes('video-do-not-use'));
 }finally{globalThis.fetch=old}
});
test('an unknown or re-assigned Telegram username cannot inject a pinned message',async()=>{
 const fixture=dbFixture();const out=await ingestPinUpdate({DB:fixture.DB},{
  channel_post:{chat:{type:'channel',username:'NotOfficial',id:-1003921647496},pinned_message:pin}});
 assert.equal(out,false);assert.equal(fixture.pins.length,0);
 const other=await ingestPinUpdate({DB:fixture.DB},{
  channel_post:{chat:{type:'channel',username:'CineXFilms_vf',id:-100777},pinned_message:pin}});
 assert.equal(other,false);assert.equal(fixture.pins.length,0);
});
test('owner can forward older pinned photo or video from a verified channel; no other origin accepted',async()=>{
 const fixture=dbFixture();const good={chat:{id:885,type:'private'},from:{id:885},
  forward_origin:{type:'channel',chat:{id:-1003921647496,username:'CineXFilms_vf'},message_id:389},
  caption:'Un film sélectionné',photo:[{file_id:imageId}]};
 const approved=await ingestOwnerForward({DB:fixture.DB},good);
 assert.equal(approved.handled,true);assert.equal(approved.stored,true);
 assert.equal(fixture.pins[0].message_id,389);
 const unknown=await ingestOwnerForward({DB:fixture.DB},{...good,forward_origin:{...good.forward_origin,chat:{id:-100555,username:'CineXFilms_vf'}}});
 assert.equal(unknown.handled,true);assert.equal(unknown.stored,false);
 assert.equal(fixture.pins.length,1);
});
test('public pinned feed contains direct Telegram post links, never fictional URLs',async()=>{
 const fixture=dbFixture();
 fixture.pins.push({kind:'films',message_id:9,title:'Film',media_kind:'photo',click_count:50,last_seen_at:'2026-11-18 20:00:00',username:'CineXFilms_vf'});
 fixture.pins.push({kind:'series',message_id:24,title:'Série',media_kind:'video',click_count:1,last_seen_at:'2026-11-18 20:00:00',username:'seriesvf_cinex'});
 const response=await listPinned({DB:fixture.DB});
 assert.equal(response.total,2);
 assert.ok(response.items.every(x=>/^https:\/\/t\.me\/(?:CineXFilms_vf|seriesvf_cinex|CineXAnimeFR)\/\d+$/.test(x.link)));
 assert.ok(response.items.every(x=>/^\/assets\/pin-cover\/(films|series|animes)\/\d+\.jpg$/.test(x.poster)));
 assert.ok(response.items.some(x=>x.type==='series'));
});
test('click analytics rejects malformed ID and cross-origin calls',async()=>{
 const fixture=dbFixture();
 let r=await registerPinClick({DB:fixture.DB},new Request('https://example.test/api/pinned-click',{method:'POST',headers:{origin:'https://evil.test'},body:'{"kind":"films","message_id":9}'}));
 assert.equal(r.status,403);
 r=await registerPinClick({DB:fixture.DB},new Request('https://example.test/api/pinned-click',{method:'POST',body:'{"kind":"films","message_id":-1}'}));
 assert.equal(r.status,400);
 assert.equal(fixture.writes.length,0);
});
test('requested compact home order and pinned only À l’affiche, no duplicate nouveautés panel',()=>{
 const pos=[
  APP_HTML.indexOf('home.append(showcaseSection);'),
  APP_HTML.indexOf('home.append(form);'),
  APP_HTML.indexOf('home.append(quick);'),
  APP_HTML.indexOf('home.append(picks);')
 ];
 assert.ok(pos.every(x=>x>0)&&pos.every((x,i)=>i===0||x>pos[i-1]),'Wrong home order');
 assert.ok(APP_HTML.includes('fetch("/api/pinned-showcase"'));
 assert.ok(APP_HTML.includes('.cine-quick button{min-height:42px;flex-direction:row;'));
 assert.ok(!APP_HTML.includes('home.append(homeRadar)'));
 assert.ok(!APP_HTML.includes('panel.decouvrir.append(radarSection'));
});

test('pinned posters render independently of the slower decorative hero API',()=>{
 const start=APP_HTML.indexOf('async function loadCinemaShowcase(){');
 const end=APP_HTML.indexOf('function miniFeatured(){',start);
 assert.ok(start!==-1&&end>start);
 const segment=APP_HTML.slice(start,end);
 assert.ok(segment.includes('const pins=fetch("/api/pinned-showcase"'));
 assert.ok(segment.includes('const art=fetch("/api/showcase"'));
 assert.equal(segment.split('.finally(renderCinemaShowcase)').length-1,2);
});
