import test from "node:test";
import assert from "node:assert/strict";
import {botUpdate,invalidateDirectoryCache,miniAppAPI} from "../radar-lean.mjs";
import {channelPreview} from "../channel-preview.mjs";
import {APP_HTML} from "../app-page.mjs";

const LINK="https://t.me/CinemaPublic2026";
function channel(){return {id:7,title:"Cinéma test",link:LINK,content_type:"films",genre:"general",avatar_url:""};}
function ctx(){const state={queries:0,calls:[],rows:[channel()]};return {state,env:{TELEGRAM_TOKEN:"123:test",DB:{prepare(sql){let args=[];return {bind(...v){args=v;return this},async all(){state.queries++;return {results:state.rows}},async first(){return null}}}}}};}
test("Category queries are cached across repeated clicks without user tracking",async()=>{
 invalidateDirectoryCache();
 const {env,state}=ctx();
 const previous=globalThis.fetch;
 globalThis.fetch=async(url,options={})=>{if(String(url).includes("api.telegram.org")){state.calls.push(String(url).split("/").pop());return Response.json({ok:true,result:{message_id:5}});}return previous(url,options);};
 try{
  const update={callback_query:{id:"callback-1",from:{id:10},message:{chat:{id:10},message_id:5},data:"category:films"}};
  await botUpdate(env,update);await botUpdate(env,update);
  assert.equal(state.queries,1);
  assert.ok(state.calls.includes("answerCallbackQuery"));
  assert.equal(state.calls.filter(x=>x==="editMessageText").length,2);
 }finally{globalThis.fetch=previous;invalidateDirectoryCache();}
});
test("Callback acknowledgement starts while database query is still waiting",async()=>{
 invalidateDirectoryCache();
 let unblock;
 const delayed=new Promise(resolve=>{unblock=resolve;});
 const state={calls:[]};
 const env={TELEGRAM_TOKEN:"123:test",DB:{prepare(){return {bind(){return this},async all(){await delayed;return {results:[channel()]};}}}}};
 const previous=globalThis.fetch;
 globalThis.fetch=async(url)=>{const method=String(url).split("/").pop();state.calls.push(method);return Response.json({ok:true,result:{message_id:5}});};
 try{
  const pending=botUpdate(env,{callback_query:{id:"early-ack",from:{id:10},message:{chat:{id:10},message_id:5},data:"category:films"}});
  await Promise.resolve();await Promise.resolve();
  assert.ok(state.calls.includes("answerCallbackQuery"),"click must be acknowledged before query completes");
  unblock();await pending;
  assert.ok(state.calls.includes("editMessageText"));
 }finally{globalThis.fetch=previous;invalidateDirectoryCache();}
});
test("Mini App gets one all-category payload and is locally filterable",async()=>{
 invalidateDirectoryCache();
 const {env,state}=ctx();
 const r=await miniAppAPI(env,new Request("https://worker.invalid/api/catalog"),async()=>{});
 assert.equal(r.status,200);
 const listing=await r.json();
 assert.equal(listing.channels.length,1);
 assert.equal(listing.channels[0].genre,"general");
 assert.ok(APP_HTML.includes('api("/api/catalog")'),"one initial catalog request");
 assert.ok(APP_HTML.includes("function applyFilters()"),"filters are local");
 assert.ok(!APP_HTML.includes('api("/api/catalog?'),"no network query for each tab");
 assert.ok(APP_HTML.includes('function showPreview(c){'),"sheet is shown without awaiting remote preview");
 assert.ok(APP_HTML.includes("fillPreview(c,images.get(c.id))"),"basic preview paints immediately");
 assert.equal(state.queries,1);
 invalidateDirectoryCache();
});
test("Telegram home and public posts URLs start in parallel",async()=>{
 const previous=globalThis.fetch;
 const calls=[];
 let settle;
 const gate=new Promise(resolve=>{settle=resolve;});
 const sample='<meta property="og:title" content="Cinéma test | Telegram"/>';
 const env={DB:{prepare(sql){return {bind(){return this},async first(){if(sql.includes("FROM channels WHERE id="))return {id:7,title:"Cinema",link:LINK,description:"Info",last_post_at:null};return null;},async run(){return {meta:{changes:1}};}}}}};
 globalThis.fetch=async url=>{calls.push(String(url));await gate;return new Response(sample,{status:200,headers:{"content-type":"text/html"}});};
 try{
  const pending=channelPreview(env,7);
  await Promise.resolve();await Promise.resolve();await Promise.resolve();
  assert.ok(calls.some(x=>x.endsWith("/CinemaPublic2026")));
  assert.ok(calls.some(x=>x.includes("/s/CinemaPublic2026")),"both Telegram pages must start concurrently");
  settle();const response=await pending;
  assert.equal(response.status,200);
 }finally{globalThis.fetch=previous;}
});
