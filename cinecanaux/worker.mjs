import {botUpdate,miniAppAPI,initializeProfile,maintenance,telegram} from "./radar-features.mjs";
import {APP_HTML} from "./app-page.mjs";
const APP_URL="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app";
function sameString(a,b){
 const x=new TextEncoder().encode(String(a||"")),y=new TextEncoder().encode(String(b||""));
 if(!x.length||x.length!==y.length)return false;
 let difference=0;for(let i=0;i<x.length;i++)difference|=x[i]^y[i];
 return difference===0;
}
async function receiveTelegram(request,env){
 if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET)return new Response("Telegram credentials missing",{status:503});
 if(!sameString(request.headers.get("X-Telegram-Bot-Api-Secret-Token"),env.TELEGRAM_WEBHOOK_SECRET))return new Response("Forbidden",{status:403});
 if(Number(request.headers.get("content-length")||0)>750000)return new Response("Too large",{status:413});
 const update=await request.json();
 if(!Number.isSafeInteger(update?.update_id))return Response.json({ok:true});
 const id=update.update_id;
 const stored=await env.DB.prepare("INSERT OR IGNORE INTO update_log(update_id) VALUES(?)").bind(id).run();
 if(stored.meta?.changes===0)return Response.json({ok:true});
 try{await botUpdate(env,update);return Response.json({ok:true});}
 catch(e){
  console.error(JSON.stringify({event:"cine_radar_update_failure",error:String(e).slice(0,180)}));
  await env.DB.prepare("DELETE FROM update_log WHERE update_id=?").bind(id).run();
  return new Response("Retry",{status:500});
 }
}
function banner(){
 const svg=String.raw`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 460" width="960" height="460" role="img" aria-labelledby="title"><title id="title">Ciné Radar, le cinéma à portée de clic</title><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111a39"/><stop offset=".65" stop-color="#263b76"/><stop offset="1" stop-color="#653fa4"/></linearGradient><radialGradient id="light"><stop stop-color="#8662fd" stop-opacity=".42"/><stop offset="1" stop-color="#8662fd" stop-opacity="0"/></radialGradient></defs><rect width="960" height="460" rx="25" fill="url(#bg)"/><circle cx="745" cy="160" r="255" fill="url(#light)"/><g fill="none" stroke="#adbcff" opacity=".15" stroke-width="24"><circle cx="770" cy="230" r="139"/><circle cx="770" cy="230" r="68"/></g><path d="M713 135l180 38-35 173-181-38z" fill="#3e71df" stroke="#c6d4ff" stroke-width="5"/><path d="M690 98l205 42-10 45-205-42z" fill="#101b39" stroke="#b9c8ff" stroke-width="5"/><path d="M715 105l-30 46m90-34-30 46m90-34-30 46" stroke="#f8fbff" stroke-width="15"/><path d="M737 204l89 44-89 52z" fill="#fff"/><text x="76" y="145" fill="#d6dfff" font-family="Arial, sans-serif" font-size="24" font-weight="bold" letter-spacing="6">DÉCOUVRE • EXPLORE</text><text x="70" y="251" fill="#fff" font-family="Arial, sans-serif" font-size="86" font-weight="bold">CINÉ RADAR</text><text x="77" y="311" fill="#d5dfff" font-family="Arial, sans-serif" font-size="30">Films  •  Séries  •  Animés</text><rect x="75" y="346" width="250" height="52" rx="26" fill="#437dfa"/><text x="118" y="381" fill="#fff" font-family="Arial, sans-serif" font-weight="bold" font-size="21">LE BON CANAL</text></svg>`;
 return new Response(svg,{headers:{"content-type":"image/svg+xml; charset=utf-8","cache-control":"public, max-age=86400","x-content-type-options":"nosniff"}});
}

async function provisionTelegramWebhook(env) {
  const current=await env.DB.prepare("SELECT status FROM bot_webhook_status WHERE id=1").first();
  if(current?.status==="ok")return;
  if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET) {
    await env.DB.prepare("INSERT INTO bot_webhook_status(id,status,detail) VALUES(1,'error','Secrets Telegram manquants') ON CONFLICT(id) DO UPDATE SET status=excluded.status,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP").run();
    return;
  }
  const target="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram";
  const r=await telegram(env,"setWebhook",{url:target,secret_token:env.TELEGRAM_WEBHOOK_SECRET,allowed_updates:["message","callback_query"]});
  const status=r.ok?"ok":"error";
  const detail=r.ok?"Webhook accepté par Telegram":("Telegram HTTP "+String(r.error_code||"") + ": " + String(r.description||"").slice(0,140));
  await env.DB.prepare("INSERT INTO bot_webhook_status(id,status,detail) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP").bind(status,detail).run();
  if(!r.ok)throw Error("Configuration webhook refusée par Telegram");
}


const DISCOVERY_STATE_URL = "https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/telegram-film-relay/state/discovery_daily_state.json";
const DISCOVERY_MAP = {
  films: {content_type: "films", genre: "general"},
  comedie: {content_type: "films", genre: "comedie"},
  desir: {content_type: "films", genre: "romance"},
  anime: {content_type: "animes", genre: "general"},
  series: {content_type: "series", genre: "general"}
};
const CHANNEL_USERNAME_RE = /^[a-zA-Z][a-zA-Z0-9_]{4,31}$/;
async function syncGitHubDiscovery(env) {
  let scanDate = "";
  try {
    // The existing GitHub Actions system uses the personal Telegram session.
    // This Worker only reads the public, already-committed discovery results.
    const response = await fetch(DISCOVERY_STATE_URL, {
      headers: {"Accept": "application/json", "Cache-Control": "no-cache"}
    });
    if (!response.ok) throw new Error("GitHub HTTP " + response.status);
    if (Number(response.headers.get("content-length") || "0") > 262144) throw new Error("Discovery state too large");
    let body = "";
    if (response.body) {
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let length = 0;
      for (;;) {
        const {value, done} = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > 262144) {await reader.cancel();throw new Error("Discovery state exceeds 256 KiB");}
        body += decoder.decode(value,{stream:true});
      }
      body += decoder.decode();
    } else throw new Error("No JSON body");
    const state = JSON.parse(body);
    scanDate = String(state?.last_scan || "");
    if (!scanDate || !Number.isFinite(Date.parse(scanDate))) throw new Error("Invalid scan timestamp");
    const old = await env.DB.prepare("SELECT scan_date FROM discovery_sync_status WHERE id=1").first();
    if (old && old.scan_date >= scanDate) return;
    const rows = [], used = new Set();
    // Prefer specific tags when one channel is found in multiple categories.
    for (const category of ["anime","series","desir","comedie","films"]) {
      const cat = DISCOVERY_MAP[category];
      const channels = state?.categories?.[category]?.channels;
      if (!Array.isArray(channels)) continue;
      for (const item of channels.slice(0,30)) {
        const username = String(item?.username || "").replace(/^@/,"");
        const key = username.toLowerCase();
        if (!CHANNEL_USERNAME_RE.test(username) || used.has(key)) continue;
        used.add(key);
        const pairs = Number.isFinite(Number(item?.matching_pairs)) ? Math.max(0, Math.min(10000, Number(item.matching_pairs))) : 0;
        const verified = item.format_verified === true && pairs >= 2 && item.transfer_restricted !== true && item.joined_by_tool === false;
        const title = String(item.title || username).trim().slice(0,120) || username;
        rows.push({username,title,link:"https://t.me/"+username,content_type:cat.content_type,
          genre:cat.genre,source_category:category,pairs,technical_status:verified?"qualified":"rejected_format"});
      }
    }
    const statements = rows.map(x => env.DB.prepare(
      `INSERT INTO discovery_candidates(username,title,link,content_type,genre,source_category,matching_pairs,technical_status,last_scan)
       VALUES(?,?,?,?,?,?,?,?,?)
       ON CONFLICT(username) DO UPDATE SET
       title=excluded.title, link=excluded.link, source_category=excluded.source_category,
       matching_pairs=excluded.matching_pairs, technical_status=excluded.technical_status,
       content_type=excluded.content_type,
       genre=CASE WHEN excluded.genre='general' AND discovery_candidates.genre!='general'
                  THEN discovery_candidates.genre ELSE excluded.genre END,
       last_scan=excluded.last_scan, last_seen=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP, rights_status=CASE WHEN discovery_candidates.rights_status='link_dead' AND excluded.last_scan > discovery_candidates.last_scan THEN 'unverified' ELSE discovery_candidates.rights_status END`
    ).bind(x.username,x.title,x.link,x.content_type,x.genre,x.source_category,x.pairs,x.technical_status,scanDate));
    const qualified = rows.filter(x=>x.technical_status==="qualified").length;
    statements.push(env.DB.prepare(
      `INSERT INTO discovery_sync_status(id,scan_date,imported,qualified,rejected,last_error)
       VALUES(1,?,?,?,?,'') ON CONFLICT(id) DO UPDATE SET scan_date=excluded.scan_date,
       imported=excluded.imported,qualified=excluded.qualified,rejected=excluded.rejected,
       last_error='',updated_at=CURRENT_TIMESTAMP`
    ).bind(scanDate,rows.length,qualified,rows.length-qualified));
    await env.DB.batch(statements);
    console.log(JSON.stringify({event:"github_discovery_synced",scanDate,imported:rows.length,qualified}));
  } catch (error) {
    const detail = String(error).slice(0,180);
    console.error(JSON.stringify({event:"github_discovery_failed",error:detail}));
    await env.DB.prepare(
      `INSERT INTO discovery_sync_status(id,scan_date,last_error) VALUES(1,?,?)
       ON CONFLICT(id) DO UPDATE SET last_error=excluded.last_error,updated_at=CURRENT_TIMESTAMP`
    ).bind(scanDate || "unavailable",detail).run();
    throw error;
  }
}


// Public-directory indexing; validates technical metadata, does not mirror media.
export async function indexQualifiedChannels(env){
 const eligible=(await env.DB.prepare(
  "SELECT username,title,link,content_type,genre,matching_pairs FROM discovery_candidates WHERE technical_status='qualified' AND matching_pairs>=2 AND rights_status NOT IN ('link_dead','rejected') ORDER BY last_seen DESC LIMIT 350"
 ).all()).results||[];
 const check=/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/;
 const rows=eligible.filter(x=>check.test(x.link));
 if(!rows.length)return {indexed:0};
 const stmts=rows.map(x=>env.DB.prepare(
  "INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed,language,verified_at) VALUES(?,?,?, ?,?,'approved',0,'VF',CURRENT_TIMESTAMP) ON CONFLICT(link) DO UPDATE SET title=excluded.title,description=excluded.description,content_type=excluded.content_type,genre=excluded.genre,status=CASE WHEN channels.status='blocked' THEN channels.status ELSE 'approved' END,updated_at=CURRENT_TIMESTAMP"
 ).bind(x.title,x.link,"Canal Telegram public • "+x.matching_pairs+" correspondance(s) photo/vidéo ou fichier MKV observée(s)",x.content_type,x.genre));
 await env.DB.batch(stmts);
 console.log(JSON.stringify({event:"public_channels_indexed",count:rows.length}));
 return {indexed:rows.length};
}


export default {
 async fetch(request,env,ctx){
  const url=new URL(request.url);
  if(request.method==="GET"&&url.pathname==="/app"){
   return new Response(APP_HTML,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: https://*.telesco.pe https://*.telegram.org https://*.telegram-cdn.org https://t.me; base-uri 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"}});
  }
  if(request.method==="GET"&&url.pathname==="/assets/banner.svg")return banner();
  if(request.method==="GET"&&["/assets/welcome.png","/assets/avatar.jpg"].includes(url.pathname)){
   const name=url.pathname.endsWith(".jpg")?"avatar.jpg":"welcome.png";
   const remote="https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/"+name;
   const img=await fetch(remote,{cf:{cacheTtl:3600,cacheEverything:true}});
   if(!img.ok)return new Response("Image temporairement indisponible",{status:503});
   return new Response(img.body,{headers:{"content-type":name.endsWith(".jpg")?"image/jpeg":"image/png","cache-control":"public, max-age=3600","x-content-type-options":"nosniff"}});
  }

  if(request.method==="GET"&&/^\/go\/\d+$/.test(url.pathname)){
   const cid=Number(url.pathname.slice(4));
   if(!Number.isSafeInteger(cid))return new Response("Not found",{status:404});
   const target=await env.DB.prepare("SELECT link FROM channels WHERE id=? AND status='approved' ").bind(cid).first();
   if(!target||!/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(target.link))return new Response("Canal indisponible",{status:404});
   await env.DB.prepare("INSERT INTO channel_telemetry(channel_id,opens) VALUES(?,1) ON CONFLICT(channel_id) DO UPDATE SET opens=channel_telemetry.opens+1").bind(cid).run();
   return Response.redirect(target.link,302);
  }

  if(request.method==="GET"&&url.pathname==="/api/bot-info"){
   try{
    const me=await telegram(env,"getMe",{});
    if(me.ok&&/^[A-Za-z0-9_]{5,32}$/.test(me.result?.username||"")){
     return Response.json({username:me.result.username,name:"Ciné Radar"},{headers:{"cache-control":"public, max-age=300"}});
    }
   }catch(e){console.warn("bot_info_unavailable",String(e).slice(0,80));}
   return Response.json({error:"Bot momentanément indisponible"},{status:503,headers:{"cache-control":"no-store"}});
  }
  if(url.pathname.startsWith("/api/"))return miniAppAPI(env,request);
  if(request.method==="POST"&&url.pathname==="/telegram")return receiveTelegram(request,env);
  if(request.method==="GET"&&url.pathname==="/health"){
   const a=await env.DB.prepare("SELECT status,detail,updated_at FROM bot_webhook_status WHERE id=1").first();
   const b=await env.DB.prepare("SELECT scan_date,imported,qualified,last_error FROM discovery_sync_status WHERE id=1").first();
   const c=await env.DB.prepare("SELECT COUNT(*) AS value FROM channels WHERE status='approved' ").first();
   const profile=await env.DB.prepare("SELECT setting_key,value FROM bot_settings WHERE setting_key IN ('profile_version','profile_photo_status')").all();
   const status=Object.fromEntries((profile.results||[]).map(x=>[x.setting_key,x.value]));
   return Response.json({service:"cine-radar",version:3,database:!!env.DB,telegramConfigured:!!env.TELEGRAM_TOKEN,webhook:a?.status||"waiting",discovery:b||{status:"waiting"},publicChannels:c?.value||0,profile:status,miniApp:APP_URL},{headers:{"cache-control":"no-store"}});
  }
  return new Response("🎬 Ciné Radar — bot Telegram et Mini App",{headers:{"content-type":"text/plain; charset=utf-8"}});
 },
 async scheduled(controller,env,ctx){
  const cron=controller.cron;
  if(cron==="0 */4 * * *")ctx.waitUntil((async()=>{try{await syncGitHubDiscovery(env);}catch(e){console.error("discovery_error",String(e));}await indexQualifiedChannels(env);await maintenance(env,"activity");})());
  else if(cron==="0 8 * * *")ctx.waitUntil(maintenance(env,"notifications"));
  else ctx.waitUntil(Promise.allSettled([provisionTelegramWebhook(env),initializeProfile(env),(async()=>{await indexQualifiedChannels(env);await maintenance(env,"activity");})()]));
 }
};
