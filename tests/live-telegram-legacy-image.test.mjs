import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {resolve,dirname} from "node:path";
import {createHmac} from "node:crypto";
import worker from "../../cloudflare/telegram-live-instant/worker.mjs";

const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const uuid="11111111-2222-4333-8444-555555555555";
const rawPng=async name=>new Uint8Array(await readFile(resolve(root,"assets/images",name)));
for(const name of ["telegram-xpvip-banner.png","telegram-xpvip-banner-1win-betwinner.png"]){
 const b=await rawPng(name);
 assert.deepEqual([...b.slice(0,8)],[137,80,78,71,13,10,26,10]);
}
const originalFetch=globalThis.fetch;
const sent=[];const claims=new Map();const posted=[];
globalThis.fetch=async (input,opts={})=>{
 const url=String(input);
 if(url.includes("raw.githubusercontent.com")){
  const filename=url.slice(url.lastIndexOf("/")+1);
  const bytes=await rawPng(filename);
  return new Response(bytes,{status:200,headers:{"content-type":"image/png"}});
 }
 if(url.endsWith("/sendPhoto")){
  const form=opts.body;
  const file=form.get("photo");
  const bytes=new Uint8Array(await file.arrayBuffer());
  assert.deepEqual([...bytes.slice(0,8)],[137,80,78,71,13,10,26,10]);
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  assert.equal(view.getUint32(16),640);
  assert(view.getUint32(20)>720,"banner must be appended to original 720px card");
  assert.equal(form.get("caption").includes("NOUVEAU"),true);
  const buttons=JSON.parse(form.get("reply_markup"));
  assert.equal(buttons.inline_keyboard.length,2);
  sent.push({image:bytes,buttons,chat:form.get("chat_id")});
  return Response.json({ok:true,result:{message_id:sent.length}});
 }
 if(url.endsWith("/sendMessage")) throw Error("Legacy text-only Telegram forbidden");
 throw Error("Unexpected network "+url);
};
const database={
 prepare(sql){return {
   bind(...params){return {
     async run(){
       if(sql.startsWith("INSERT")){
         const key=params[1]+":"+params[2]+":"+params[3];
         if(claims.has(key))return {meta:{changes:0}};
         claims.set(key,{status:"reserved"});return {meta:{changes:1}};
       }
       if(sql.startsWith("UPDATE")){posted.push(params);return {meta:{changes:1}}}
       if(sql.startsWith("DELETE"))return {meta:{changes:1}};
       throw Error("Unexpected D1 query");
     },
     async first(){return {delivery_status:"sent"}}
   }}
 }}
};
const env={DB:database,NEON_DELIVERY_HMAC_KEY:"test-secret",TELEGRAM_BOT_TOKEN:"fake",TELEGRAM_CHAT_ID:"@primary",TELEGRAM_CHAT_ID_SECONDARY:"@secondary"};
function signal(date){return {id:uuid,created_at:date,model_version:"neon-live-value-v2.3-playability-espn",
 pricing_mode:"model_only",type:"total_corners",signal_tier:"quality",home_team:"Arsenal",
 away_team:"Chelsea",home_score:2,away_score:1,league_name:"Premier League",
 probability:.79,threshold:8.5,signal_value:5,reliability:82,data_quality_score:89,minute:54}}
async function request(date){
 const body=JSON.stringify({signals:[signal(date)]});
 const ts=String(Date.now());
 const sig=createHmac("sha256",env.NEON_DELIVERY_HMAC_KEY).update(ts+"."+body).digest("hex");
 const req=new Request("https://worker.invalid/deliver",{method:"POST",body,headers:{"content-type":"application/json","x-mrx-timestamp":ts,"x-mrx-signature":sig}});
 const resp=await worker.fetch(req,env);
 return {status:resp.status,data:await resp.json()};
}
try{
 const health=await worker.fetch(new Request("https://worker.invalid/health"),env);
 assert.equal((await health.json()).format,"original-supabase-png");
 const a=await request(new Date().toISOString());
 assert.equal(a.status,200,JSON.stringify(a.data));
 assert.equal(a.data.all_sent,true);
 assert.equal(sent.length,2);
 const pngA=sent[0].image;
 for(const [key,file] of [["first","telegram-xpvip-banner.png"],["second","telegram-xpvip-banner-1win-betwinner.png"]]){
  const b=await rawPng(file);assert(b.length>1000,key);
 }
 const b=await request(new Date().toISOString());
 assert.equal(b.data.all_sent,true);
 assert.equal(sent.length,2,"D1 must prevent a duplicate send");
 console.log("PASS: png original 640-wide + real sponsor banner, buttons, HMAC, 2 destinations, no duplicate");
}finally{globalThis.fetch=originalFetch}
