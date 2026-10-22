// Smoke test against the actual production Cloudflare Worker, no Telegram secrets.
import assert from "node:assert/strict";
const base=process.env.CINE_RADAR_URL||"https://cinecanaux-bot.cinecanaux-xpronos.workers.dev";
async function get(path,headers={}){
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),18000);
 try{
  const response=await fetch(base+path,{headers,signal:controller.signal,cache:"no-store"});
  const text=await response.text();
  return {status:response.status,data:response.headers.get("content-type")?.includes("json")?JSON.parse(text):text};
 }finally{clearTimeout(timeout);}
}
async function main(){
 const health=await get("/health");
 assert.equal(health.status,200,"/health must be available");
 assert.ok(health.data.database,"D1 binding must be available");
 assert.equal(health.data.service,"cine-radar");
 console.log("PASS: public health, D1 binding");
 const app=await get("/app");
 assert.equal(app.status,200,"Mini App HTML must load");
 assert.ok(app.data.includes("● Catalogue public"),"New public catalog UI must be deployed");
 assert.ok(app.data.includes('showChannelPreview'),"Channel preview sheet must be active");
 console.log("PASS: new Mini App UI deployed");
 const listing=await get("/api/catalog");
 assert.equal(listing.status,200,"Public catalog without Telegram authentication must load");
 assert.equal(listing.data.authenticated,false,"Guests are not allowed to impersonate logged-in users");
 assert.ok(Array.isArray(listing.data.channels));
 assert.ok(listing.data.channels.length>0,"Published catalog should not be empty");
 console.log("PASS: "+listing.data.channels.length+" public channels load without Telegram session");
 const invalid=await get("/api/catalog",{"X-Telegram-Init-Data":"not-a-valid-telegram-session"});
 assert.equal(invalid.status,200,"Broken Telegram initData must not block public directory");
 assert.equal(invalid.data.authenticated,false);
 console.log("PASS: rejected Telegram session still displays public channels");
 const profile=await get("/api/profile");
 assert.equal(profile.status,401,"Personal profile must require signed Telegram initData");
 assert.equal(profile.data.code,"telegram_session_required");
 console.log("PASS: private personal information remains protected");
 const id=Number(listing.data.channels[0].id);
 assert.ok(Number.isSafeInteger(id)&&id>0);
 const preview=await get("/api/channel-preview?id="+id);
 assert.equal(preview.status,200,"Channel public preview must work for guests");
 assert.equal(preview.data.channel.id,id);
 assert.ok(/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(preview.data.channel.link));
 console.log("PASS: guest channel preview opens for channel #"+id);
}
await main();
