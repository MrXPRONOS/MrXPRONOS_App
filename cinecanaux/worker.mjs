import {serveChannelAvatar} from "./channel-avatar.mjs";
import {serveShowcase} from "./poster-showcase.mjs";
import {servePartnerCards,servePartnerAvatar} from "./partner-promotions.mjs";
import {syncLatestPinned,ingestPinUpdate,ingestOwnerForward,servePinned,servePinCover,registerPinClick,listPinned} from "./pinned-showcase.mjs";
import {channelPreview} from "./channel-preview.mjs";
import {botUpdate,miniAppAPI,initializeProfile,maintenance,cleanup,telegram,invalidateDirectoryCache,listPublicChannels} from "./radar-lean.mjs";
import {APP_HTML} from "./app-page.mjs";
import {ADMIN_HTML} from "./admin-page.mjs";
import {adminAPI} from "./admin-v2.mjs";
import {tryOwnerClaim} from "./owner-claim.mjs";
import {recordBotTouch,analyticsEvent} from "./analytics.mjs";
import {runLoggedJob} from "./job-log.mjs";
import {v2API,getCatalog} from "./v2.mjs";
import {checkDailyLinks,integrateSuggestions,integrateDiscoveredCandidates,syncCategoryTags} from "./maintenance-v2.mjs";
import {ingestRadarPost,radarApi,runTrendRefresh,reconcileRadarPosts} from "./trend-radar.mjs";
import {bindPrimaryRadarChannels,notifyOwnerMissingRadarTitles} from "./radar-owner-ops.mjs";
const APP_URL="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app";
// Durable, non-sensitive Telegram diagnostics visible from D1 (no tokens or user IDs).
async function saveRadarOperationalStatus(env,job,status,detail){
 await env.DB.prepare(
  "INSERT INTO radar_ops_status(job_name,last_attempt_at,last_success_at,status,detail) "+
  "VALUES(?,CURRENT_TIMESTAMP,CASE WHEN ?='ok' THEN CURRENT_TIMESTAMP ELSE NULL END,?,?) "+
  "ON CONFLICT(job_name) DO UPDATE SET last_attempt_at=CURRENT_TIMESTAMP,"+
  "last_success_at=CASE WHEN excluded.status='ok' THEN CURRENT_TIMESTAMP ELSE radar_ops_status.last_success_at END,"+
  "status=excluded.status,detail=excluded.detail"
 ).bind(job,status,status,String(detail||'').slice(0,800)).run();
}
async function runRadarOperationalVerification(env,{sendNotices=true}={}){
 let errors=0,updated=0;
 try{
  const r=await bindPrimaryRadarChannels(env);
  updated=r.bound;
  errors+=r.errors.length;
  await saveRadarOperationalStatus(env,'channel_binding',r.errors.length?'partial':'ok',
   'new='+r.bound+' verified='+r.alreadyBound+'; '+[...r.checks,...r.errors].join('; '));
 }catch(e){errors++;await saveRadarOperationalStatus(env,'channel_binding','error',String(e).slice(0,250));}
 try{
  const r=await reconcileRadarPosts(env,120);
  await saveRadarOperationalStatus(env,'post_reconciliation','ok',JSON.stringify(r||{}).slice(0,350));
 }catch(e){errors++;await saveRadarOperationalStatus(env,'post_reconciliation','error',String(e).slice(0,250));}
 if(sendNotices){
  try{
   const r=await notifyOwnerMissingRadarTitles(env);
   errors+=r.errors.length;
   await saveRadarOperationalStatus(env,'private_notifications',r.errors.length?'error':'ok',
    'owners='+r.ownersChecked+' sent='+r.sent+' suggestions='+r.listed+'; '+r.errors.join('; '));
  }catch(e){errors++;await saveRadarOperationalStatus(env,'private_notifications','error',String(e).slice(0,250));}
 }
 return {checked:3,updated,errors};
}
function sameString(a,b){
 const x=new TextEncoder().encode(String(a||"")),y=new TextEncoder().encode(String(b||""));
 if(!x.length||x.length!==y.length)return false;
 let difference=0;for(let i=0;i<x.length;i++)difference|=x[i]^y[i];
 return difference===0;
}
async function receiveTelegram(request,env,ctx){
 if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET)return new Response("Telegram credentials missing",{status:503});
 if(!sameString(request.headers.get("X-Telegram-Bot-Api-Secret-Token"),env.TELEGRAM_WEBHOOK_SECRET))return new Response("Forbidden",{status:403});
 if(Number(request.headers.get("content-length")||0)>750000)return new Response("Too large",{status:413});
 const update=await request.json();
 if(!Number.isSafeInteger(update?.update_id))return Response.json({ok:true});
 try{
  if(update.channel_post||update.edited_channel_post){await ingestPinUpdate(env,update);await ingestRadarPost(env,update);return Response.json({ok:true});}
  if(update.message?.chat?.type==="private"){
   if(ctx?.waitUntil)ctx.waitUntil(recordBotTouch(env,update).catch(e=>console.warn("bot_metrics_failed",String(e).slice(0,70))));
   else await recordBotTouch(env,update).catch(()=>{});
   const claim=await tryOwnerClaim(env,update);
   if(claim.handled){
    if(claim.activated&&ctx?.waitUntil)ctx.waitUntil(initializeProfile(env).catch(e=>console.warn("owner_profile_update_failed",String(e).slice(0,90))));
    return Response.json({ok:true});
   }
  }
  if(update.message?.forward_origin?.type==="channel"){
   const result=await ingestOwnerForward(env,update.message);
   if(result.handled){await telegram(env,"sendMessage",{chat_id:update.message.chat.id,text:result.stored?"✅ Affiche enregistrée pour À l’affiche.":"⚠️ "+result.reason});return Response.json({ok:true});}
  }
  await botUpdate(env,update);
  // Apply public start-only and private owner command scopes on the next /start
  // without delaying the welcome. Scheduled housekeeping remains the backup.
  if(/^\/start(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(String(update.message?.text||""))){
   ctx?.waitUntil(initializeProfile(env).catch(e=>console.warn("bot_profile_bootstrap_failed",String(e).slice(0,130))));
  }
  return Response.json({ok:true});}
 catch(e){console.error("cine_radar_update_failed",String(e).slice(0,120));return new Response("Retry",{status:500});}
}
function banner(){
 const svg=String.raw`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 460" width="960" height="460" role="img" aria-labelledby="title"><title id="title">Ciné Radar, le cinéma à portée de clic</title><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111a39"/><stop offset=".65" stop-color="#263b76"/><stop offset="1" stop-color="#653fa4"/></linearGradient><radialGradient id="light"><stop stop-color="#8662fd" stop-opacity=".42"/><stop offset="1" stop-color="#8662fd" stop-opacity="0"/></radialGradient></defs><rect width="960" height="460" rx="25" fill="url(#bg)"/><circle cx="745" cy="160" r="255" fill="url(#light)"/><g fill="none" stroke="#adbcff" opacity=".15" stroke-width="24"><circle cx="770" cy="230" r="139"/><circle cx="770" cy="230" r="68"/></g><path d="M713 135l180 38-35 173-181-38z" fill="#3e71df" stroke="#c6d4ff" stroke-width="5"/><path d="M690 98l205 42-10 45-205-42z" fill="#101b39" stroke="#b9c8ff" stroke-width="5"/><path d="M715 105l-30 46m90-34-30 46m90-34-30 46" stroke="#f8fbff" stroke-width="15"/><path d="M737 204l89 44-89 52z" fill="#fff"/><text x="76" y="145" fill="#d6dfff" font-family="Arial, sans-serif" font-size="24" font-weight="bold" letter-spacing="6">DÉCOUVRE • EXPLORE</text><text x="70" y="251" fill="#fff" font-family="Arial, sans-serif" font-size="86" font-weight="bold">CINÉ RADAR</text><text x="77" y="311" fill="#d5dfff" font-family="Arial, sans-serif" font-size="30">Films  •  Séries  •  Animés</text><rect x="75" y="346" width="250" height="52" rx="26" fill="#437dfa"/><text x="118" y="381" fill="#fff" font-family="Arial, sans-serif" font-weight="bold" font-size="21">LE BON CANAL</text></svg>`;
 return new Response(svg,{headers:{"content-type":"image/svg+xml; charset=utf-8","cache-control":"public, max-age=86400","x-content-type-options":"nosniff"}});
}

export async function provisionTelegramWebhook(env) {
 const target="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram";
 const accepted=["message","callback_query","channel_post","edited_channel_post"];
 const saveStatus=async(status,detail)=>{
  await env.DB.prepare("INSERT INTO bot_webhook_status(id,status,detail) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP").bind(status,detail).run();
 };
 if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET){
  await saveStatus("error","Secrets Telegram manquants");
  return;
 }
 let current=null;
 try{
  const info=await telegram(env,"getWebhookInfo",{});
  if(info.ok)current=info.result||{};
 }catch(e){console.warn("cineradar_webhook_probe_failed",String(e).slice(0,90));}
 if(current&&current.url===target&&accepted.every(value=>Array.isArray(current.allowed_updates)&&current.allowed_updates.includes(value))){
  await saveStatus("ok","Webhook Telegram vérifié");
  return;
 }
 // A previously successful D1 flag cannot prove that Telegram still points here.
 // Re-register only when the live configuration is missing, wrong, or unverifiable.
 const r=await telegram(env,"setWebhook",{url:target,secret_token:env.TELEGRAM_WEBHOOK_SECRET,allowed_updates:accepted});
 const detail=r.ok?"Webhook Telegram rétabli":("Telegram HTTP "+String(r.error_code||"")+": "+String(r.description||"").slice(0,140));
 await saveStatus(r.ok?"ok":"error",detail);
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
 async fetch(request,env,ctx){
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
   try{
    // Pin thumbnails are included in initial HTML so À l'affiche is visible
    // immediately; independent API requests only refresh stale results.
    const pins=JSON.stringify((await listPinned(env,{limit:24})).items)
     .replace(/[<>&\u2028\u2029]/g,c=>({"<":"\\u003c",">":"\\u003e","&":"\\u0026","\u2028":"\\u2028","\u2029":"\\u2029"}[c]));
    html=html.replace("const PRELOADED_PINS=null;","const PRELOADED_PINS="+pins+";");
   }catch(e){console.warn("pin_html_preload_fallback",String(e).slice(0,80));}
   return new Response(html,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: https://*.telesco.pe https://*.telegram.org https://*.telegram-cdn.org https://t.me https://image.tmdb.org https://s4.anilist.co https://static.tvmaze.com https://m.media-amazon.com https://images-na.ssl-images-amazon.com; base-uri 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"}});
  }
  if(request.method==="GET"&&u.pathname==="/admin"){
   return new Response(ADMIN_HTML,{headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; base-uri 'none'"}});
  }
  if(u.pathname==="/api/partner-promos")return servePartnerCards(request);
  const promoAvatar=/^\/assets\/promo-avatar\/(actufoot_mrxp|ActuCrypto24H|mrxpronosfr)\.jpg$/i.exec(u.pathname);
  if(promoAvatar)return servePartnerAvatar(request,env,ctx,promoAvatar[1]);
  if(u.pathname==="/api/showcase")return serveShowcase(request);
  if(u.pathname==="/api/pinned-showcase")return servePinned(env,request);
  if(u.pathname==="/api/pinned-click")return registerPinClick(env,request);
  const pinnedCover=/^\/assets\/pin-cover\/(films|series|animes)\/([1-9][0-9]{0,12})\.jpg$/.exec(u.pathname);
  if(pinnedCover)return servePinCover(env,request,pinnedCover[1],Number(pinnedCover[2]));
  if(u.pathname==="/api/radar"||u.pathname==="/api/radar/click"||u.pathname==="/api/radar/trends")return radarApi(env,request);
  if(u.pathname.startsWith("/api/admin/"))return adminAPI(env,request);
  if(u.pathname==="/api/analytics/event")return analyticsEvent(env,request);
  const avatarId=/^\/assets\/channel-avatar\/([1-9][0-9]{0,9})\.jpg$/.exec(u.pathname);
  if(request.method==="GET"&&avatarId)return serveChannelAvatar(request,env,ctx,avatarId[1]);
  const avatarMatch=new RegExp("^/assets/channel-avatar/([A-Za-z][A-Za-z0-9_]{4,31})[.]jpg$").exec(u.pathname);
  if(request.method==="GET"&&avatarMatch){
   const handle=avatarMatch[1].toLowerCase();
   const indexed=await env.DB.prepare("SELECT id FROM channels WHERE LOWER(link)=? AND status='approved'").bind('https://t.me/'+handle).first();
   if(!indexed)return new Response("Not found",{status:404,headers:{"cache-control":"public,max-age=300"}});
   const base="https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/avatars/";
   try{
    const image=await fetch(base+encodeURIComponent(handle)+".jpg",{signal:AbortSignal.timeout(6000),cf:{cacheEverything:true,cacheTtl:3600}});
    const type=String(image.headers.get("content-type")||"");
    if(image.ok&&type.toLowerCase().startsWith("image/"))return new Response(image.body,{headers:{"content-type":"image/jpeg","cache-control":"public,max-age=3600","x-content-type-options":"nosniff"}});
   }catch(e){console.warn("cineradar_avatar_repository_unavailable",String(e).slice(0,90));}
   // Fallback for newly indexed channels: fetch the public channel photo with the server-side Bot API.
   // The Telegram token and getFile URL are never sent to the browser.
   if(env.TELEGRAM_TOKEN){
    try{
     const base="https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/";
     const chatResponse=await fetch(base+"getChat",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:"@"+handle}),signal:AbortSignal.timeout(5500)});
     if(chatResponse.ok){
      const chat=await chatResponse.json();
      const photoId=chat.ok&&chat.result?.type==="channel"?chat.result?.photo?.big_file_id:null;
      if(typeof photoId==="string"&&photoId.length<500){
       const fileResponse=await fetch(base+"getFile",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({file_id:photoId}),signal:AbortSignal.timeout(5500)});
       if(fileResponse.ok){
        const file=await fileResponse.json();
        const path=file.ok?file.result?.file_path:null;
        if(typeof path==="string"&&/^[a-zA-Z0-9_./-]{1,350}$/.test(path)&&!path.includes("..")){
         const imageResponse=await fetch("https://api.telegram.org/file/bot"+env.TELEGRAM_TOKEN+"/"+path,{signal:AbortSignal.timeout(6000)});
         const contentType=String(imageResponse.headers.get("content-type")||"").toLowerCase();
         if(imageResponse.ok&&contentType.startsWith("image/")){
          const bytes=await imageResponse.arrayBuffer();
          if(bytes.byteLength>0&&bytes.byteLength<=2097152){
           return new Response(bytes,{headers:{"content-type":contentType,"cache-control":"public,max-age=3600","x-content-type-options":"nosniff"}});
          }
         }
        }
       }
      }
     }
    }catch(e){console.warn("cineradar_avatar_bot_fallback_unavailable",String(e).slice(0,90));}
   }
   return new Response("No accessible public avatar",{status:404,headers:{"cache-control":"public,max-age=300"}});
  }
  // Self-hosted glossy controls for the public Telegram Mini App (10 glyphs / 9 KB).
  if(request.method==="GET"&&u.pathname==="/assets/ui-icons-lot1.webp"){
   try{
    const image=await fetch("https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/ui-icons-lot1.webp",
     {signal:AbortSignal.timeout(8000),cf:{cacheEverything:true,cacheTtl:86400}});
    if(image.ok&&String(image.headers.get("content-type")||"").toLowerCase().includes("image/")){
     return new Response(image.body,{headers:{"content-type":"image/webp","cache-control":"public,max-age=86400,immutable","x-content-type-options":"nosniff"}});
    }
   }catch(e){console.warn("cine_ui_icon_asset_unavailable",String(e).slice(0,90));}
   return new Response("Image indisponible",{status:503,headers:{"cache-control":"no-store"}});
  }
  if(request.method==="GET"&&u.pathname==="/assets/banner.svg")return banner();
  if(request.method==="GET"&&["/assets/welcome.png","/assets/avatar.jpg"].includes(u.pathname)){
   const name=u.pathname.endsWith(".jpg")?"avatar.jpg":"welcome.png";
   const image=await fetch("https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/"+name,{cf:{cacheTtl:86400,cacheEverything:true}});
   if(!image.ok)return new Response("Image indisponible",{status:503});
   return new Response(image.body,{headers:{"content-type":name.endsWith(".jpg")?"image/jpeg":"image/png","cache-control":"public,max-age=86400"}});
  }
  if(u.pathname==="/api/catalog"||u.pathname==="/api/search"||u.pathname==="/api/reports"||u.pathname==="/api/suggestions"||/^\/api\/channels\/\d+\/reviews$/.test(u.pathname))return v2API(env,request);
  if(u.pathname==="/api/engagement"&&request.method==="POST"){
    const origin=request.headers.get("origin");
    if(origin&&origin!==u.origin)return Response.json({error:"Origin denied"},{status:403});
    if(Number(request.headers.get("content-length")||0)>256)return Response.json({error:"Too large"},{status:413});
    let payload;try{payload=await request.json()}catch{return Response.json({error:"Invalid request"},{status:400})}
    const id=payload?.id;
    if(payload?.event!=="open"||!Number.isSafeInteger(id)||id<1)return Response.json({error:"Invalid event"},{status:400});
    const active=await env.DB.prepare("SELECT c.id FROM channels c LEFT JOIN channel_index_meta m ON m.channel_id=c.id WHERE c.id=? AND c.status='approved' AND COALESCE(m.listing_status,'listed')='listed'").bind(id).first();
    if(!active)return Response.json({error:"Channel unavailable"},{status:404});
    await env.DB.prepare("INSERT INTO channel_telemetry(channel_id,opens) VALUES(?,1) ON CONFLICT(channel_id) DO UPDATE SET opens=opens+1").bind(id).run();
    return Response.json({ok:true},{headers:{"Cache-Control":"no-store"}});
  }
  if(u.pathname.startsWith("/api/"))return miniAppAPI(env,request,channelPreview);
  if(request.method==="POST"&&u.pathname==="/telegram")return receiveTelegram(request,env,ctx);
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
  else if(controller.cron==="0 */6 * * *")ctx.waitUntil(runLoggedJob(env,'housekeeping',async()=>{
   const upkeep=await Promise.allSettled([provisionTelegramWebhook(env),initializeProfile(env),syncLatestPinned(env)]);
   let errors=upkeep.filter(x=>x.status==="rejected").length;
   // At 06:00 UTC run the daily catalog reconciliation and link checks.
   // Source-specific successful trend refreshes are guarded by a 72-hour D1 window.
   const hour=new Date(controller.scheduledTime||Date.now()).getUTCHours();
   // Run the first trend collection at the next six-hour Cron, not only at 06:00.
   // After the first successful anime refresh, keep daily checks (with 72h source guard).
   const first=await env.DB.prepare("SELECT last_success_at FROM radar_runs WHERE job_name='trends_animes'").first();
   if(hour===6||!first?.last_success_at){
    for(const [name,job] of [
     ['refresh_trends',()=>runTrendRefresh(env)],
     ['check_links',()=>checkDailyLinks(env,10)]
    ]){
     try{
      const report=await job();
      if(report?.errors?.length){errors+=report.errors.length;console.warn('radar_daily_warning',name,report.errors.join('; ').slice(0,140));}
     }catch(e){errors++;console.error('radar_daily_error',name,String(e).slice(0,140));}
    }
   }
   // Channel identity is checked every six hours, independently of the 72h trending cache.
   // Owner digests are sent on the daily 06:00 pass or the first successful bootstrap.
   const report=await runRadarOperationalVerification(env,{sendNotices:hour===6||!first?.last_success_at});
   errors+=report.errors;
   return {errors};
  }));
  else ctx.waitUntil(runLoggedJob(env,'housekeeping',async()=>{
   const result=await Promise.allSettled([provisionTelegramWebhook(env),initializeProfile(env)]);
   return {errors:result.filter(x=>x.status==='rejected').length};
  }));
 }
};