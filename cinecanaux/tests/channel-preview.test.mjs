import test from "node:test";
import assert from "node:assert/strict";
import {parseTelegramPublicProfile,channelPreview,htmlDecode} from "../channel-preview.mjs";
const sample=[
 '<html><head>',
 '<meta property="og:title" content="Cinéma de Test | Telegram"/>',
 '<meta content="Films de science-fiction &amp; animations publics." property="og:description"/>',
 '<meta property="og:image" content="https://cdn4.telesco.pe/file/test-avatar.jpg"/>',
 '</head><body><time datetime="2026-10-21T12:30:00+00:00"></time></body></html>'
].join("");
test("28 — Extract title, bio and avatar from Telegram public HTML metadata",()=>{
 const p=parseTelegramPublicProfile(sample,"PublicCinema2026");
 assert.equal(p.title,"Cinéma de Test");
 assert.equal(p.description,"Films de science-fiction & animations publics.");
 assert.equal(p.avatar_url,"https://cdn4.telesco.pe/file/test-avatar.jpg");
});
test("29 — Restrict external image hosts and escape user supplied text",()=>{
 const p=parseTelegramPublicProfile('<meta property="og:title" content="Telegram"/><meta property="og:image" content="https://evil.invalid/steal.png"/>',"TestChannel2026");
 assert.equal(p.title,null);assert.equal(p.avatar_url,null);
 assert.equal(htmlDecode('&lt;img src=x onerror=alert(1)&gt;'),'<img src=x onerror=alert(1)>');
});
test("30 — Channel metadata is cached and only public approved links can be inspected",async()=>{
 const oldFetch=globalThis.fetch,state={cache:null,calls:0};
 const db={prepare(sql){let args=[];return {bind(...v){args=v;return this},async first(){
  if(sql.includes("FROM channels c LEFT JOIN channel_profile_cache")){
    if(args[0]!==17)return null;
    const cached=state.cache;
    return {id:17,title:"Catalogue original",link:"https://t.me/PublicCinema2026",description:"Référencé",last_post_at:null,
      cached_title:cached?.title,cached_description:cached?.description,cached_avatar_url:cached?.avatar_url,
      cached_post_image_url:cached?.post_image_url,cached_last_post_at:cached?.last_post_at,
      cached_preview_status:cached?.preview_status,cached_checked_at:cached?.checked_at};
  }
  return null;
 },async run(){
  if(sql.includes("INSERT INTO channel_profile_cache"))state.cache={title:args[1],description:args[2],avatar_url:args[3],last_post_at:args[4],preview_status:args[5],checked_at:new Date().toISOString().replace("T"," ").replace(/\.\d+Z$/,"")};
  return {meta:{changes:1}};
 }}}};
 globalThis.fetch=async url=>{state.calls++;assert.ok(String(url).startsWith("https://t.me/"));return new Response(sample,{status:200,headers:{"content-type":"text/html; charset=utf-8"}})};
 try{
  const a=await channelPreview({DB:db},17);
  assert.equal(a.status,200);assert.equal(a.data.title,"Cinéma de Test");
  assert.equal(a.data.preview_status,"available");
  const b=await channelPreview({DB:db},17);
  assert.equal(b.status,200);assert.equal(state.calls,2);assert.equal(b.data.cached,true);
  assert.equal((await channelPreview({DB:db},42)).status,404);
 }finally{globalThis.fetch=oldFetch;}
});
test("31 — Network outage leaves a usable in-app basic public profile",async()=>{
 const oldFetch=globalThis.fetch;
 const db={prepare(sql){return {bind(){return this},async first(){
  if(sql.includes("FROM channels c LEFT JOIN channel_profile_cache"))return {id:6,title:"Public fallback",link:"https://t.me/TestPublic123",description:"Description enregistrée",last_post_at:null};
  return null;
 },async run(){return {meta:{changes:1}}}}}};
 globalThis.fetch=async()=>{throw Error("Telegram temporarily unavailable")};
 try{
  const x=await channelPreview({DB:db},6);
  assert.equal(x.status,200);assert.equal(x.data.title,"Public fallback");
  assert.equal(x.data.description,"Description enregistrée");
  assert.equal(x.data.preview_status,"unavailable");
 }finally{globalThis.fetch=oldFetch;}
});
