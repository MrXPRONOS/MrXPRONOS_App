import {readFileSync} from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import {
 isD1QuotaError,nextRecoveryUTC,markD1Maintenance,d1MaintenanceActive,
 maintenanceResponse,maintenanceDetails,telegramMaintenanceReply,
 resetMaintenanceForTests
} from "../quota-maintenance.mjs";
import worker from "../worker.mjs";

const quota=()=>new Error("D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or wait until tomorrow (midnight UTC) to continue.");
const mockDB=()=>({prepare(){throw quota();}});

test("only D1 daily quota exhaustion enters maintenance, not ordinary SQL failures",()=>{
 resetMaintenanceForTests();
 assert.equal(isD1QuotaError(quota()),true);
 assert.equal(isD1QuotaError(new Error("D1_ERROR: no such table: channels")),false);
 assert.equal(isD1QuotaError(new Error("SQLITE_BUSY")),false);
 assert.equal(markD1Maintenance(new Error("SQLITE_BUSY")),false);
 assert.equal(d1MaintenanceActive(),false);
 assert.equal(markD1Maintenance({cause:{message:"Cloudflare D1 free tier daily row read limit exceeded",code:7500}}),true);
 assert.equal(d1MaintenanceActive(),true);
 resetMaintenanceForTests();
});

test("next reset is 00h05 UTC/Togo, including when issue arises after midnight",()=>{
 assert.equal(nextRecoveryUTC(new Date("2026-11-25T23:50:00Z")).toISOString(),"2026-11-26T00:05:00.000Z");
 assert.equal(nextRecoveryUTC(new Date("2026-11-26T00:02:00Z")).toISOString(),"2026-11-26T00:05:00.000Z");
 assert.equal(nextRecoveryUTC(new Date("2026-11-26T00:06:00Z")).toISOString(),"2026-11-27T00:05:00.000Z");
 resetMaintenanceForTests();
 markD1Maintenance(quota(),new Date("2026-11-25T23:50:00Z"));
 assert.equal(d1MaintenanceActive(new Date("2026-11-26T00:04:59Z")),true);
 assert.equal(d1MaintenanceActive(new Date("2026-11-26T00:05:00Z")),false);
 resetMaintenanceForTests();
});

test("D1 quota returns a readable maintenance page, 503 and no-cache headers",async()=>{
 resetMaintenanceForTests();
 markD1Maintenance(quota(),new Date("2026-11-25T23:50:00Z"));
 const response=maintenanceResponse(new Request("https://cine.test/app"),{now:new Date("2026-11-25T23:51:00Z")});
 assert.equal(response.status,503);
 assert.equal(response.headers.get("cache-control").includes("no-store"),true);
 assert.equal(response.headers.get("retry-after"),"840");
 assert.equal(response.headers.get("x-cineradar-maintenance"),"d1-quota");
 const html=await response.text();
 assert.match(html,/CinéRadar est en maintenance/);
 assert.match(html,/00h05/);
 assert.match(html,/26 novembre 2026/);
 assert.match(html,/Heure du Togo/);
 assert.match(html,/Réessayer/);
 resetMaintenanceForTests();
});

test("D1 quota returns structured API maintenance JSON, not misleading empty listings",async()=>{
 resetMaintenanceForTests();
 const e={DB:mockDB()};
 const r=await worker.fetch(new Request("https://cine.test/api/catalog"),e);
 assert.equal(r.status,503);
 const data=await r.json();
 assert.equal(data.maintenance,true);
 assert.equal(data.code,"D1_QUOTA_MAINTENANCE");
 assert.equal(data.timezone,"Africa/Lome");
 resetMaintenanceForTests();
});

test("site and admin display maintenance if D1 is exhausted; no empty page",async()=>{
 resetMaintenanceForTests();
 const env={DB:mockDB()};
 const app=await worker.fetch(new Request("https://cine.test/app"),env);
 assert.equal(app.status,503);
 assert.match(await app.text(),/CinéRadar est en maintenance/);
 const admin=await worker.fetch(new Request("https://cine.test/admin"),env);
 assert.equal(admin.status,503);
 assert.match(await admin.text(),/00h05/);
 resetMaintenanceForTests();
});

test("admin probes real D1 availability and shows maintenance on fresh isolated request",async()=>{
 resetMaintenanceForTests();
 const response=await worker.fetch(new Request("https://cine.test/admin"),{DB:mockDB()});
 assert.equal(response.status,503);
 assert.match(await response.text(),/maintenance/);
 resetMaintenanceForTests();
});

test("authenticated Telegram private message receives a maintenance reply",async()=>{
 resetMaintenanceForTests();
 const calls=[];
 const send=async(env,method,payload)=>{calls.push({method,payload});return {ok:true}};
 const update={message:{chat:{id:12001,type:"private"},text:"/start"},update_id:205};
 const result=await telegramMaintenanceReply(update,send,{});
 assert.equal(result.status,200);
 assert.equal(calls.length,1);
 assert.equal(calls[0].method,"sendMessage");
 assert.match(calls[0].payload.text,/00h05/);
 assert.match(calls[0].payload.text,/Togo/);
});

test("callback receives alert without sending duplicate messages",async()=>{
 const calls=[];
 const result=await telegramMaintenanceReply({
  callback_query:{id:"cb-99",message:{chat:{id:12001,type:"private"}}}
 },async(env,method,payload)=>{calls.push({method,payload});return {ok:true};},{});
 assert.equal(result.status,200);
 assert.equal(calls.length,1);
 assert.equal(calls[0].method,"answerCallbackQuery");
 assert.equal(calls[0].payload.show_alert,true);
});

test("Telegram channel updates remain retryable, not silently discarded",async()=>{
 const calls=[];
 const result=await telegramMaintenanceReply({
  channel_post:{chat:{id:-100111222333,type:"channel"},message_id:55}
 },async()=>{calls.push("should-not-call");return {ok:true};},{});
 assert.equal(result.status,503);
 assert.equal(calls.length,0);
});

test("a Telegram webhook without the correct secret is still rejected during maintenance",async()=>{
 resetMaintenanceForTests();
 markD1Maintenance(quota());
 const update={update_id:551,message:{chat:{id:1201,type:"private"},text:"/start"}};
 const result=await worker.fetch(new Request("https://cine.test/telegram",{
  method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"wrong"},body:JSON.stringify(update)
 }),{TELEGRAM_TOKEN:"123:test",TELEGRAM_WEBHOOK_SECRET:"correct"});
 assert.equal(result.status,403);
 resetMaintenanceForTests();
});

test("an authenticated Telegram webhook is answered during D1 maintenance",async()=>{
 resetMaintenanceForTests();
 markD1Maintenance(quota());
 const oldFetch=globalThis.fetch;
 const calls=[];
 globalThis.fetch=async(url,init)=>{
  const method=String(url).split("/").pop();
  const payload=JSON.parse(init.body);
  calls.push({method,payload});
  return Response.json({ok:true,result:{message_id:123}});
 };
 try{
  const update={update_id:552,message:{chat:{id:1201,type:"private"},text:"/start"}};
  const r=await worker.fetch(new Request("https://cine.test/telegram",{
   method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"correct"},
   body:JSON.stringify(update)
  }),{TELEGRAM_TOKEN:"123:test",TELEGRAM_WEBHOOK_SECRET:"correct"});
  assert.equal(r.status,200);
  assert.equal(calls.length,1);
  assert.equal(calls[0].method,"sendMessage");
  assert.match(calls[0].payload.text,/00h05/);
 }finally{
  globalThis.fetch=oldFetch;
  resetMaintenanceForTests();
 }
});

test("maintenance page polls after 00h05 and automatically reopens the app only when health is healthy",async()=>{
 resetMaintenanceForTests();
 markD1Maintenance(quota(),new Date("2026-11-25T23:56:00Z"));
 const r=maintenanceResponse(new Request("https://cine.test/app"),{now:new Date("2026-11-25T23:59:00Z")});
 const page=await r.text();
 assert.match(page,/new Date\("2026-11-26T00:05:00\.000Z"\)/);
 assert.match(page,/\/health\?recovery=/);
 assert.match(page,/result\.database===true/);
 assert.match(page,/location\.replace\("\/app"\)/);
 assert.match(r.headers.get("content-security-policy"),/connect-src 'self'/);
 resetMaintenanceForTests();
});

test("independent GitHub Pages backup is static, verifies D1 and returns to CineRadar without touching secrets",()=>{
 const page=readFileSync(new URL("../../cineradar-secours/index.html",import.meta.url),"utf8");
 assert.match(page,/CinéRadar est en maintenance/);
 assert.match(page,/00h05/);
 assert.match(page,/github-standby/);
 assert.match(page,/window\.location\.replace\(MAIN\+"\/app"\)/);
 assert.match(page,/body\.database===true/);
 assert.doesNotMatch(page,/TELEGRAM_TOKEN|TELEGRAM_WEBHOOK_SECRET|SUPABASE_SERVICE_ROLE|CLOUDFLARE_API_TOKEN/);
});

test("public health exposes narrow CORS to GitHub Pages but no credentials",async()=>{
 resetMaintenanceForTests();
 const DB={prepare(){return {async first(){return {webhook:"ok",n:5}}}}};
 const r=await worker.fetch(new Request("https://cine.test/health"),{DB});
 assert.equal(r.status,200);
 assert.equal(r.headers.get("access-control-allow-origin"),"https://mrxpronos.github.io");
 const data=await r.json();
 assert.equal(data.database,true);
 assert.equal(data.service,"cine-radar");
 resetMaintenanceForTests();
});

test("quota health response exposes the same CORS authority to independent standby",async()=>{
 resetMaintenanceForTests();
 markD1Maintenance(quota());
 const r=await worker.fetch(new Request("https://cine.test/health"),{DB:mockDB()});
 assert.equal(r.status,503);
 assert.equal(r.headers.get("access-control-allow-origin"),"https://mrxpronos.github.io");
 resetMaintenanceForTests();
});
