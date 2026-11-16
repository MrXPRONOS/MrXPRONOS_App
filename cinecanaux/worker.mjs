import {channelPreview} from "./channel-preview.mjs";
import {botUpdate,miniAppAPI,initializeProfile,maintenance,cleanup,telegram,invalidateDirectoryCache,listPublicChannels} from "./radar-lean.mjs";
import {APP_HTML} from "./app-page.mjs";
import {ADMIN_HTML} from "./admin-page.mjs";
import {adminAPI} from "./admin-v2.mjs";
import {runLoggedJob} from "./job-log.mjs";
import {v2API,getCatalog} from "./v2.mjs";
import {checkDailyLinks,integrateSuggestions,integrateDiscoveredCandidates,syncCategoryTags} from "./maintenance-v2.mjs";
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
 try{await botUpdate(env,update);return Response.json({ok:true});}
 catch(e){console.error("cine_radar_update_failed",String(e).slice(0,120));return new Response("Retry",{status:500});}
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
        // Directory discovery only: verify actual public-link accessibility before indexing.
        const verified = true;
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
 const result=await integrateDiscoveredCandidates(env,15);
 return {...result,indexed:result.inserted};
}

export default {
 async fetch(request,env){
  const u=new URL(request.url);
  if(request.method==="GET"&&(u.pathname==="/app"||u.pathname==="/")){
   let html=APP_HTML;
   try{
    // Send the full public listing with the HTML: no second network RTT on first open.
    // Escape HTML-breaking characters: titles come from third-party channels.
    const data=JSON.stringify((await getCatalog(env,{limit:80})).channels)
     .replace(/[<>&\u2028\u2029]/g,c=>({"<":"\\u003c",">":"\\u003e","&":"\\u0026","\u2028":"\\u2028","\u2029":"\\u2029"}[c]));
    html=APP_HTML.replace("const PRELOADED_CATALOG=null;","const PRELOADED_CATALOG="+data+";");
   }catch(e){
    console.warn(JSON.stringify({event:"catalog_html_preload_fallback",error:String(e).slice(0,90)}));
    // The client still supports its original /api/catalog fetch.
   }
   return new Response(html,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: https://*.telesco.pe https://*.telegram.org https://*.telegram-cdn.org https://t.me; base-uri 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"}});
  }
  if(request.method==="GET"&&u.pathname==="/admin"){
   return new Response(ADMIN_HTML,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'"}});
  }
  if(u.pathname.startsWith("/api/admin/"))return adminAPI(env,request);
  const avatarMatch=new RegExp("^/assets/channel-avatar/([A-Za-z][A-Za-z0-9_]{4,31})[.]jpg$").exec(u.pathname);
  if(request.method==="GET"&&avatarMatch){
   const handle=avatarMatch[1].toLowerCase();
   const indexed=await env.DB.prepare("SELECT id FROM channels WHERE LOWER(link)=? AND status='approved'").bind('https://t.me/'+handle).first();
   if(!indexed)return new Response("Not found",{status:404,headers:{"cache-control":"public,max-age=300"}});
   const base="https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/avatars/";
   try{
    const image=await fetch(base+encodeURIComponent(handle)+".jpg",{signal:AbortSignal.timeout(6000),cf:{cacheEverything:true,cacheTtl:3600}});
    const type=String(image.headers.get("content-type")||"");
    if(!image.ok||!type.toLowerCase().includes("image/"))return new Response("No public avatar",{status:404,headers:{"cache-control":"public,max-age=300"}});
    return new Response(image.body,{headers:{"content-type":"image/jpeg","cache-control":"public,max-age=3600","x-content-type-options":"nosniff"}});
   }catch(e){console.warn("cineradar_avatar_unavailable",String(e).slice(0,90));return new Response("Avatar temporarily unavailable",{status:503,headers:{"cache-control":"no-store"}});}
  }
  if(request.method==="GET"&&u.pathname==="/assets/banner.svg")return banner();
  if(request.method==="GET"&&["/assets/welcome.png","/assets/avatar.jpg"].includes(u.pathname)){
   const name=u.pathname.endsWith(".jpg")?"avatar.jpg":"welcome.png";
   const image=await fetch("https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/"+name,{cf:{cacheTtl:86400,cacheEverything:true}});
   if(!image.ok)return new Response("Image indisponible",{status:503});
   return new Response(image.body,{headers:{"content-type":name.endsWith(".jpg")?"image/jpeg":"image/png","cache-control":"public,max-age=86400"}});
  }
  if(u.pathname==="/api/catalog"||u.pathname==="/api/search"||u.pathname==="/api/reports"||u.pathname==="/api/suggestions"||/^\/api\/channels\/\d+\/reviews$/.test(u.pathname))return v2API(env,request);
  if(u.pathname.startsWith("/api/"))return miniAppAPI(env,request,channelPreview);
  if(request.method==="POST"&&u.pathname==="/telegram")return receiveTelegram(request,env);
  if(request.method==="GET"&&u.pathname==="/health"){
   // One D1 round trip for service health, instead of two sequential queries.
   const state=await env.DB.prepare("SELECT (SELECT status FROM bot_webhook_status WHERE id=1) AS webhook,(SELECT COUNT(*) FROM channels WHERE status='approved') AS n").first();
   return Response.json({service:"cine-radar",version:6,database:!!env.DB,webhook:state?.webhook||"waiting",publicChannels:Number(state?.n||0),miniApp:APP_URL},{headers:{"cache-control":"no-store"}});
  }
  return new Response("Not found",{status:404});
 },
 async scheduled(controller,env,ctx){
  if(controller.cron==="0 */4 * * *")ctx.waitUntil(runLoggedJob(env,'discovery',async()=>{
   try{await syncGitHubDiscovery(env);}catch(e){console.error("sync_failed",String(e).slice(0,120));}
   const discovered=await indexQualifiedChannels(env);
   await syncCategoryTags(env);
   const suggested=await integrateSuggestions(env,12);
   await cleanup(env);
   return {inspected:discovered.inspected||0,inserted:(discovered.inserted||0)+(suggested.indexed||0),errors:discovered.unverifiable||0};
  }));
  else if(controller.cron==="0 3 * * *")ctx.waitUntil(runLoggedJob(env,'link_check',()=>checkDailyLinks(env,10)));
  else ctx.waitUntil(runLoggedJob(env,'housekeeping',async()=>{
   const result=await Promise.allSettled([provisionTelegramWebhook(env),initializeProfile(env)]);
   return {errors:result.filter(x=>x.status==='rejected').length};
  }));
 }
};
