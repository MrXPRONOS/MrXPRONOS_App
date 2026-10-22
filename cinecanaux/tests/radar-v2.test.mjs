import test from "node:test";
import assert from "node:assert/strict";
import {createHmac} from "node:crypto";
import worker from "../worker.mjs";
import {botUpdate,miniAppAPI} from "../radar-features.mjs";
import {APP_HTML} from "../app-page.mjs";

const token="123456789:test_mock_token";
const encoder=new TextEncoder();
const originalFetch=globalThis.fetch;
const messages=[];
globalThis.fetch=async(url,options={})=>{
 const method=String(url).split("/").pop();
 const body=JSON.parse(options.body||"{}");
 messages.push({method,body});
 if(method==="getMe")return Response.json({ok:true,result:{id:111111111,username:"CineRadarTestBot",first_name:"Ciné Radar"}});
 return Response.json({ok:true,result:{message_id:messages.length,ok:true}});
};
const state={preferences:new Map(),favorites:new Set(),refcodes:new Map(),refvisits:new Map(),modes:new Map(),reports:[],channels:[{id:42,title:"Le Cinéma Autorisé",link:"https://t.me/TestCinemaPublic",description:"Une chaîne sous licence",content_type:"films",genre:"action",language:"VF",updated_at:"2026-10-22 00:00:00",rights_confirmed:1,status:"approved"}],admin:new Set([999])};
function db(){
 return {
 prepare(sql){let args=[];return {
 bind(...values){args=values;return this},
 async first(){
 if(sql.includes("SELECT chat_id,title,link FROM owned_channels"))return null;
 if(sql.includes("FROM preferences WHERE user_id"))return state.preferences.get(args[0])||null;
 if(sql.includes("FROM referral_codes WHERE user_id"))return state.refcodes.has(args[0])?{code:state.refcodes.get(args[0])}:null;
 if(sql.includes("FROM referral_codes WHERE code")){for(const [k,v] of state.refcodes)if(v===args[0])return {user_id:k};return null;}
 if(sql.includes("FROM user_states WHERE user_id"))return state.modes.has(args[0])?{mode:state.modes.get(args[0])}:null;
 if(sql.includes("SELECT 1 FROM admin_users"))return state.admin.has(args[0])?{one:1}:null;
 if(sql.includes("COUNT(*) total"))return {total:state.refvisits.size,confirmed:0};
 if(sql.includes("SELECT 1 FROM favorites"))return state.favorites.has(args[0]+":"+args[1])?{one:1}:null;
 if(sql.includes("SELECT id FROM channels")||sql.includes("SELECT 1 FROM channels"))return state.channels.find(x=>x.id===args[0])||null;
 if(sql.includes("SELECT link FROM channels"))return state.channels.find(x=>x.id===args[0])||null;
 if(sql.includes("SELECT c.*"))return state.channels.find(x=>x.id===args[0])||null;
 if(sql.includes("COUNT(*) n FROM favorites"))return {n:state.favorites.size};
 if(sql.includes("COUNT(*) n FROM referral_visits"))return {n:state.refvisits.size};
 if(sql.includes("FROM bot_webhook_status"))return {status:"ok"};
 if(sql.includes("FROM discovery_sync_status"))return {scan_date:"2026-10-21"};
 if(sql.includes("COUNT(*) AS value"))return {value:state.channels.length};
 if(sql.includes("SELECT status FROM bot_webhook_status"))return {status:"ok"};
 if(sql.includes("FROM bot_settings"))return {value:"2"};
 return null;
 },
 async all(){
 if(sql.includes("FROM owned_channels"))return {results:[]};
 if(sql.includes("FROM channels c LEFT JOIN channel_telemetry"))return {results:state.channels};
 if(sql.includes("SELECT channel_id FROM favorites"))return {results:[...state.favorites].filter(x=>x.startsWith(args[0]+":")).map(x=>({channel_id:Number(x.split(":")[1])}))};
 if(sql.includes("FROM favorites f JOIN channels"))return {results:[]};
 return {results:[]};
 },
 async run(){
 if(sql.includes("INSERT INTO preferences"))state.preferences.set(args[0],{category:args[1],language:args[2],notification_enabled:args[3],onboarded:args[4]});
 if(sql.includes("INSERT OR IGNORE INTO referral_codes"))state.refcodes.set(args[0],args[1]);
 if(sql.includes("INSERT OR IGNORE INTO referral_visits")&&!state.refvisits.has(args[0]))state.refvisits.set(args[0],args[1]);
 if(sql.includes("INSERT INTO user_states"))state.modes.set(args[0],args[1]||"search");
 if(sql.includes("DELETE FROM user_states"))state.modes.delete(args[0]);
 if(sql.includes("INSERT OR IGNORE INTO favorites"))state.favorites.add(args[0]+":"+args[1]);
 if(sql.includes("DELETE FROM favorites"))state.favorites.delete(args[0]+":"+args[1]);
 if(sql.includes("INSERT OR IGNORE INTO channel_reports"))state.reports.push(args);
 return {meta:{changes:1}};
 }
 }},
 async batch(statements){return statements.map(()=>({success:true}))}
 };
}
const env={DB:db(),TELEGRAM_TOKEN:token,TELEGRAM_WEBHOOK_SECRET:"test_webhook_secret"};
const message=(uid,text)=>({message:{message_id:11,chat:{id:uid,type:"private"},from:{id:uid},text}});
const callback=(uid,data)=>({callback_query:{id:"callback"+messages.length,from:{id:uid},data,message:{chat:{id:uid,type:"private"},message_id:11}}});
function last(method){return [...messages].reverse().find(x=>x.method===method)?.body;}
async function signInit(uid){
 const auth_date=Math.floor(Date.now()/1000).toString();
 const user=JSON.stringify({id:uid,first_name:"Test"});
 const pairs=[["auth_date",auth_date],["user",user]];
 const dc=pairs.map(x=>x[0]+"="+x[1]).join("\n");
 const secret=createHmac("sha256","WebAppData").update(token).digest();
 const hash=createHmac("sha256",secret).update(dc).digest("hex");
 return new URLSearchParams({auth_date,user,hash}).toString();
}
test("1 — Branding, banner and Mini App are embedded",()=>{
 assert.match(APP_HTML,/Ciné Radar/);assert.match(APP_HTML,/data-tab="favorites"/);
 assert.match(APP_HTML,/id="genre"/);assert.match(APP_HTML,/id="language"/);
});
test("2 — First start and styled Telegram keyboard",async()=>{
 await botUpdate(env,message(104,"/start"));
 const sent=last("sendMessage");
 assert.ok(messages.some(x=>x.method==="sendMessage"&&x.body.text.includes("BIENVENUE SUR CINÉ RADAR")));
 assert.ok(messages.some(x=>x.method==="sendMessage"&&x.body.reply_markup?.inline_keyboard?.flat().some(b=>b.style==="primary")));
 assert.equal(sent.parse_mode,"HTML");
});
test("3 — Single-message navigation uses editMessageText",async()=>{
 await botUpdate(env,callback(104,"type:films"));
 assert.match(last("editMessageText").text,/Choisis ton style/);
 await botUpdate(env,callback(104,"list:films:general:0"));
 assert.match(last("editMessageText").text,/Le Cinéma Autorisé/);
});
test("4 — Favorites are added and removed",async()=>{
 await botUpdate(env,callback(104,"fav:42:latest"));
 assert.ok(state.favorites.has("104:42"));
 await botUpdate(env,callback(104,"fav:42:latest"));
 assert.ok(!state.favorites.has("104:42"));
});
test("5 — One personal invite, no self-referral, unique attribution",async()=>{
 const count=messages.length;
 await botUpdate(env,message(104,"/parrainage"));
 const sent=messages.slice(count).filter(x=>x.method==="sendMessage");
 assert.equal(sent.length,2);
 assert.match(sent[0].body.text,/https:\/\/t.me\/CineRadarTestBot\?start=ref_/);
 assert.ok(!sent[0].body.text.includes("message précédent"));
 assert.ok(sent[1].body.text.includes("message précédent"));
 const code=state.refcodes.get(104);
 await botUpdate(env,message(205,"/start ref_"+code));
 await botUpdate(env,message(205,"/start ref_"+code));
 await botUpdate(env,message(104,"/start ref_"+code));
 assert.equal(state.refvisits.size,1);assert.equal(state.refvisits.get(205),104);
});
test("6 — Telegram Mini App rejects unsigned browser requests",async()=>{
 const r=await miniAppAPI(env,new Request("https://test.workers.dev/api/catalog"));
 assert.equal(r.status,401);
});
test("7 — Signed Telegram Mini App initData returns only eligible catalog",async()=>{
 const init=await signInit(104);
 const r=await miniAppAPI(env,new Request("https://test.workers.dev/api/catalog?type=films&genre=general&language=VF",{headers:{"X-Telegram-Init-Data":init}}));
 assert.equal(r.status,200);
 const obj=await r.json();
 assert.equal(obj?.channels?.length,1);
});
test("8 — Mini App favorites and reports work with signed user",async()=>{
 const init=await signInit(104);
 const headers={"X-Telegram-Init-Data":init,"content-type":"application/json"};
 const fav=await miniAppAPI(env,new Request("https://test.workers.dev/api/favorite",{method:"POST",headers,body:JSON.stringify({id:42})}));
 assert.equal(fav.status,200);
 const report=await miniAppAPI(env,new Request("https://test.workers.dev/api/report",{method:"POST",headers,body:JSON.stringify({id:42,reason:"broken"})}));
 assert.equal(report.status,200);
 assert.equal(state.reports.length,1);
});
test("8bis — Mini App saves language, favorite category and opt-in notifications",async()=>{
 const init=await signInit(104);
 const headers={"X-Telegram-Init-Data":init,"content-type":"application/json"};
 const response=await miniAppAPI(env,new Request("https://test.workers.dev/api/preferences",{
   method:"POST",headers,body:JSON.stringify({category:"animes",language:"VOSTFR",notifications:true})
 }));
 assert.equal(response.status,200);
 const saved=await response.json();
 assert.equal(saved.preferences.category,"animes");
 assert.equal(saved.preferences.language,"VOSTFR");
 assert.equal(saved.preferences.notification_enabled,1);
 const invalid=await miniAppAPI(env,new Request("https://test.workers.dev/api/preferences",{
   method:"POST",headers,body:JSON.stringify({category:"unknown",language:"VF",notifications:true})
 }));
 assert.equal(invalid.status,400);
});
test("8ter — Welcome photo is delivered on first start",async()=>{
 assert.ok(messages.some(x=>x.method==="sendPhoto"&&x.body.photo.endsWith("/assets/welcome.png")));
});
test("8quad — Native Telegram /profil remains accessible without opening Mini App",async()=>{
 const prev=messages.length;
 await botUpdate(env,message(104,"/profil"));
 const sent=messages.slice(prev).find(x=>x.method==="sendMessage");
 assert.ok(sent);
 assert.match(sent.body.text,/MON PROFIL CINÉ RADAR/);
 assert.ok(sent.body.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="preferences"));
});
test("8quin — Profile renders even when Telegram getMe fails temporarily",async()=>{
 const signed=await signInit(104);
 const prevFetch=globalThis.fetch;
 globalThis.fetch=async(url,opts)=>{
  if(String(url).includes("/getMe"))return Response.json({ok:false,error_code:502,description:"Temporary failure"});
  return prevFetch(url,opts);
 };
 try{
  const r=await miniAppAPI(env,new Request("https://test.workers.dev/api/profile",{headers:{"X-Telegram-Init-Data":signed}}));
  assert.equal(r.status,200);
  const body=await r.json();
  assert.equal(body.first_name,"Test");
  assert.equal(body.referral_link,null);
  assert.ok(body.preferences);
 }finally{globalThis.fetch=prevFetch;}
});
test("9 — Worker health and HTML Mini App routes",async()=>{
 const h=await worker.fetch(new Request("https://test.workers.dev/health"),env,{waitUntil(){}});
 assert.equal(h.status,200);assert.equal((await h.json()).version,3);
 const r=await worker.fetch(new Request("https://test.workers.dev/app"),env,{waitUntil(){}});
 assert.equal(r.status,200);assert.match(await r.text(),/Ciné Radar/);
});
test("10 — Invalid webhook signature is rejected",async()=>{
 const r=await worker.fetch(new Request("https://test.workers.dev/telegram",{method:"POST",headers:{"content-type":"application/json"},body:"{}"}),env,{waitUntil(){}});
 assert.equal(r.status,403);
});
test("11 — Only approved channel redirects can be opened",async()=>{
 const r=await worker.fetch(new Request("https://test.workers.dev/go/42"),env,{waitUntil(){}});
 assert.equal(r.status,302);assert.match(r.headers.get("location"),/t\.me\/TestCinemaPublic/);
 const x=await worker.fetch(new Request("https://test.workers.dev/go/999"),env,{waitUntil(){}});
 assert.equal(x.status,404);
});
