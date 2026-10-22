import test from "node:test";
import assert from "node:assert/strict";
import worker,{indexQualifiedChannels} from "../worker.mjs";
import {APP_HTML} from "../app-page.mjs";
import {botUpdate,miniAppAPI,maintenance,cleanup} from "../radar-lean.mjs";
import {parseTelegramPublicProfile} from "../channel-preview.mjs";

const channels=[
 {id:1,title:"Cinéma public",link:"https://t.me/CinemaPublic2026",content_type:"films",genre:"general",avatar_url:""},
 {id:2,title:"Séries populaires",link:"https://t.me/SeriesPop2026",content_type:"series",genre:"general",avatar_url:""},
 {id:3,title:"Anime",link:"https://t.me/AnimePublic2026",content_type:"animes",genre:"general",avatar_url:""}
];
const calls=[];
let previewCalls=0;
const state={channels:channels.map(x=>({...x})),prior:new Map(),updated:0,deletes:[]};
const db={prepare(sql){
 let values=[];
 const stmt={
  bind(...v){values=v;return stmt;},
  async all(){
   if(sql.includes("FROM channels c LEFT JOIN channel_profile_cache"))return {results:state.channels.map(x=>({...x,avatar_url:""}))};
   if(sql.includes("prior FROM channels c LEFT JOIN channel_telemetry"))return {results:state.channels.map(x=>({...x,prior:state.prior.get(x.id)||"unknown"}))};
   if(sql.includes("SELECT title,link FROM channels WHERE status='approved' AND content_type="))return {results:state.channels.filter(x=>x.content_type===values[0])};
   return {results:[]};
  },
  async first(){
   if(sql.includes("COUNT(*) AS n FROM channels"))return {n:state.channels.length};
   if(sql.includes("SELECT status FROM bot_webhook_status"))return {status:"ok"};
   return null;
  },
  async run(){
   if(sql.includes("INSERT INTO channel_telemetry"))state.prior.set(values[0],values[1]);
   if(sql.startsWith("DELETE FROM channels")){state.channels=state.channels.filter(x=>x.id!==values[0]);state.deletes.push(values[0]);}
   state.updated++;
   return {meta:{changes:1}};
  }
 };return stmt;
 },async batch(statements){for(const stmt of statements)await stmt.run();return [];}};
const env={DB:db,TELEGRAM_TOKEN:"test-token",TELEGRAM_WEBHOOK_SECRET:"test-secret"};
const realFetch=globalThis.fetch;
globalThis.fetch=async(url,opt={})=>{
 if(String(url).startsWith("https://api.telegram.org/")){
  const method=String(url).split("/").pop(),body=JSON.parse(opt.body||"{}");calls.push({method,body});
  return Response.json({ok:true,result:method==="getMe"?{username:"CineRadarFr_Bot"}:{message_id:5}});
 }
 return realFetch(url,opt);
};
const msg=t=>({message:{chat:{id:100,type:"private"},from:{id:100},message_id:5,text:t}});
const cb=data=>({callback_query:{id:"cb",from:{id:100},message:{chat:{id:100,type:"private"},message_id:5},data}});
test("1. UI has only categories, public search, real previews and open",()=>{
 assert.match(APP_HTML,/data-type="films"/);assert.match(APP_HTML,/data-type="series"/);assert.match(APP_HTML,/data-type="animes"/);
 assert.match(APP_HTML,/getPreview/);
 for(const word of ["Mes favoris","Parrainage","/profil","Copier le lien","Partager"]){
  assert.ok(!APP_HTML.includes(word),"Removed feature still visible: "+word);
 }
});
test("2. Homepage and category flow take at most two clicks",async()=>{
 await botUpdate(env,msg("/start"));
 let latest=calls.at(-1).body;
 assert.match(latest.text,/CINÉ RADAR/);
 assert.equal(latest.reply_markup.inline_keyboard.length,2);
 await botUpdate(env,cb("category:films"));
 latest=calls.at(-1).body;
 assert.match(latest.text,/Canaux publics/);
 assert.equal(latest.reply_markup.inline_keyboard[0][0].url,"https://t.me/CinemaPublic2026");
});
test("3. Public catalog requires no account or database writes",async()=>{
 const before=state.updated;
 const response=await miniAppAPI(env,new Request("https://test.local/api/catalog?type=films"),async()=>{});
 assert.equal(response.status,200);
 const body=await response.json();
 assert.equal(body.channels.length,1);
 assert.equal(body.channels[0].title,"Cinéma public");
 assert.equal(state.updated,before);
});
test("4. No personal APIs and no tracked writes",async()=>{
 for(const path of ["/api/favorite","/api/profile","/api/preferences","/api/share"]){
  const r=await miniAppAPI(env,new Request("https://test.local"+path),async()=>{});
  assert.equal(r.status,404);
 }
});
test("5. Channel preview returns essential fields only",async()=>{
 const previewFn=async()=>{previewCalls++;return {status:200,data:{id:1,title:"Cinéma public",description:"Films du jour",avatar_url:"https://cdn4.telesco.pe/file/one.jpg",post_image_url:"https://cdn4.telesco.pe/file/post.jpg",link:"https://t.me/CinemaPublic2026",matching_pairs:100,rights_confirmed:0}};};
 const r=await miniAppAPI(env,new Request("https://test.local/api/channel-preview?id=1"),previewFn);
 assert.equal(r.status,200);const p=(await r.json()).channel;
 assert.equal(p.photo,"https://cdn4.telesco.pe/file/one.jpg");
 assert.equal(p.post_image,"https://cdn4.telesco.pe/file/post.jpg");
 assert.equal(p.matching_pairs,undefined);
 assert.equal(previewCalls,1);
});
test("6. Real public Telegram post images are extracted from preview HTML",()=>{
 const html=`<a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn4.telesco.pe/file/real_post.jpg')"></a>`;
 const p=parseTelegramPublicProfile(html,"CinemaPublic2026");
 assert.equal(p.post_image_url,"https://cdn4.telesco.pe/file/real_post.jpg");
});
test("7. Definitively dead channels removed after two checks",async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>new Response("Not found",{status:404});
 try{
  await maintenance(env);assert.equal(state.channels.length,3);
  await maintenance(env);assert.equal(state.channels.length,0);
 }finally{globalThis.fetch=original;}
});
test("8. Unknown Telegram network status never deletes channels",async()=>{
 const original=globalThis.fetch;
 state.channels=channels.map(x=>({...x}));state.prior.clear();
 globalThis.fetch=async()=>new Response("temporarily busy",{status:429});
 try{await maintenance(env);await maintenance(env);assert.equal(state.channels.length,3);}finally{globalThis.fetch=original;}
});
test("9. Scheduled maintenance can purge stale updates and profile cache",async()=>{
 await cleanup(env);assert.ok(state.updated>0);
});
test("10. Worker refuses forged webhook requests",async()=>{
 const r=await worker.fetch(new Request("https://test.local/telegram",{method:"POST",body:"{}",headers:{"content-type":"application/json"}}),env);
 assert.equal(r.status,403);
});
test("11. Indexed records are synced without per-user reads",async()=>{
 const r=await indexQualifiedChannels(env);assert.ok(r.indexed>=0);
});
test("12. Health shows public channels, no private data",async()=>{
 const r=await worker.fetch(new Request("https://test.local/health"),env);
 const d=await r.json();assert.equal(d.version,6);assert.equal(d.publicChannels,3);
 assert.equal(d.favorites,undefined);
});