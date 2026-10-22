const categories = [
["films","🎬 Films"],["series","📺 Séries"],["animes","🎌 Animés"]
];
const genres={films:[["general","🎬 Tous les films"],["action","💥 Action"],["comedie","😂 Comédie"],["horreur","👻 Horreur"],["romance","💕 Romance"],["sciencefiction","🚀 Science-fiction"],["drame","🎭 Drame"]],series:[["action","💥 Action"],["comedie","😂 Comédie"],["drame","🎭 Drame"],["policier","🕵️ Policier"]],animes:[["general","🎌 Tous les animés"],["shonen","⚔️ Shōnen"],["seinen","🌙 Seinen"],["romance","💕 Romance"],["fantasy","✨ Fantasy"]]};
const keyboard=(rows)=>({inline_keyboard:rows.map(row=>row.map(([text,data,url])=>url?{text,url}:{text,callback_data:data}))});
const menu=()=>keyboard([[["🎬 Films","type:films"],["📺 Séries","type:series"]],[["🎌 Animés","type:animes"]],[["🔎 Rechercher","search"],["📨 Proposer un canal","suggest"]],[["📣 Nos canaux","owned"]]]);
async function api(env,method,data){if(!env.TELEGRAM_TOKEN)throw Error("TELEGRAM_TOKEN manquant");const response=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data)});const result=await response.json();if(!result.ok)console.log("telegram_error",method,result.error_code,result.description);return result;}
async function send(env,chat_id,text,reply_markup){return api(env,"sendMessage",{chat_id,text,reply_markup,disable_web_page_preview:true});}
async function answer(env,id){if(id)await api(env,"answerCallbackQuery",{callback_query_id:id});}
async function listOwned(env){return (await env.DB.prepare("SELECT chat_id,title,link FROM owned_channels WHERE enabled=1 ORDER BY id").all()).results||[];}
async function gate(env,userId){const owned=await listOwned(env);const missing=[];for(const c of owned){try{const r=await api(env,"getChatMember",{chat_id:c.chat_id,user_id:userId});if(!r.ok||!["creator","administrator","member"].includes(r.result.status))missing.push(c);}catch{missing.push(c);}}return missing;}
async function requireJoin(env,chatId,userId){const missing=await gate(env,userId);if(!missing.length)return true;await send(env,chatId,"🔐 Pour consulter notre annuaire, rejoins d'abord nos canaux, puis clique sur Vérifier.",keyboard([...missing.map(c=>[[ "📣 "+c.title, null,c.link ]]),[["✅ Vérifier mon abonnement","verify"]]]));return false;}
async function home(env,chatId,userId){if(!(await requireJoin(env,chatId,userId)))return;await send(env,chatId,"🍿 Bienvenue sur CinéCanaux !\nChoisis ce que tu veux découvrir. Nous référençons uniquement les canaux vérifiés et autorisés.",menu());}
async function results(env,chatId,kind,genre,q){let rows=[];if(q){rows=(await env.DB.prepare("SELECT title,link,description,content_type,genre FROM channels WHERE status='approved' AND rights_confirmed=1 AND (title LIKE ? OR description LIKE ?) ORDER BY updated_at DESC LIMIT 12").bind("%"+q+"%","%"+q+"%").all()).results||[];}else{rows=(await env.DB.prepare("SELECT title,link,description FROM channels WHERE status='approved' AND rights_confirmed=1 AND content_type=? AND genre=? ORDER BY updated_at DESC LIMIT 12").bind(kind,genre).all()).results||[];}if(!rows.length){await send(env,chatId,"Aucun canal validé pour le moment. Reviens bientôt ou propose un canal.",keyboard([[["🏠 Accueil","home"]]]));return;}for(const c of rows){await send(env,chatId,"🎞 "+c.title+"\n"+(c.description||"Canal vérifié")+"\n✅ Canal approuvé",keyboard([[["🔗 Ouvrir le canal",null,c.link]]]));}await send(env,chatId,"Fin des résultats.",keyboard([[["🏠 Accueil","home"]]]));}
async function handle(env,u){
const m=u.message||u.callback_query?.message;const cb=u.callback_query;const chatId=m?.chat?.id;const userId=cb?.from?.id||m?.from?.id;
if(!chatId||!userId)return;
const val=cb?.data;
if(cb)await answer(env,cb.id);
if(val==="verify"||val==="home"||m?.text==="/start"||m?.text==="/menu"){await home(env,chatId,userId);return;}
if(!(await requireJoin(env,chatId,userId)))return;
if(val==="owned"){const owned=await listOwned(env);if(!owned.length){await send(env,chatId,"Nos canaux seront annoncés prochainement.",menu());return;}await send(env,chatId,"📣 Nos canaux officiels",keyboard(owned.map(c=>[["📣 "+c.title,null,c.link]]).concat([[["🏠 Accueil","home"]]])));return;}
if(val?.startsWith("type:")){const kind=val.slice(5);if(!genres[kind])return;await send(env,chatId,"Choisis un genre :",keyboard(genres[kind].map(g=>[[g[1],"genre:"+kind+":"+g[0]]]).concat([[["🏠 Accueil","home"]]])));return;}
if(val?.startsWith("genre:")){const parts=val.split(":");await results(env,chatId,parts[1],parts[2],null);return;}
if(val==="search"){await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'search') ON CONFLICT(user_id) DO UPDATE SET mode='search'").bind(userId).run();await send(env,chatId,"🔎 Envoie le mot-clé à rechercher (titre, thème, genre).");return;}
if(val==="suggest"){await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'suggest') ON CONFLICT(user_id) DO UPDATE SET mode='suggest'").bind(userId).run();await send(env,chatId,"📨 Envoie le lien public t.me du canal à proposer. La publication nécessite une vérification manuelle des droits de diffusion.");return;}
const input=m?.text?.trim();if(!input)return;
const state=await env.DB.prepare("SELECT mode FROM user_states WHERE user_id=?").bind(userId).first();
if(state?.mode==="search"){await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(userId).run();await results(env,chatId,null,null,input.slice(0,100));return;}
if(state?.mode==="suggest"){await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(userId).run();const url=input.match(/^https:\/\/t\.me\/[a-zA-Z0-9_]{5,32}\/?$/)?.[0];if(!url){await send(env,chatId,"Lien invalide. Utilise un lien public https://t.me/nomducanal");return;}await env.DB.prepare("INSERT INTO suggestions(user_id,link,status) VALUES(?,?,'pending')").bind(userId,url).run();await send(env,chatId,"✅ Proposition enregistrée. Un administrateur vérifiera le canal et ses droits de diffusion avant son référencement.");return;}
await send(env,chatId,"Utilise le menu pour naviguer.",menu());
}
async function webhook(request,env){if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET)return new Response("Configuration Telegram incomplète",{status:503});const received=request.headers.get("X-Telegram-Bot-Api-Secret-Token")||"";const expected=env.TELEGRAM_WEBHOOK_SECRET;const a=new TextEncoder().encode(received),b=new TextEncoder().encode(expected);if(a.length!==b.length||!crypto.subtle.timingSafeEqual(a,b))return new Response("Forbidden",{status:403});const data=await request.json();if(!data.update_id)return Response.json({ok:true});const id=data.update_id;const written=await env.DB.prepare("INSERT OR IGNORE INTO update_log(update_id) VALUES(?)").bind(id).run();if(written.meta.changes===0)return Response.json({ok:true});try{await handle(env,data);}catch(e){console.error("update_failed",String(e));await env.DB.prepare("DELETE FROM update_log WHERE update_id=?").bind(id).run();return new Response("Retry",{status:500});}return Response.json({ok:true});}

async function provisionTelegramWebhook(env) {
  const current=await env.DB.prepare("SELECT status FROM bot_webhook_status WHERE id=1").first();
  if(current?.status==="ok")return;
  if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET) {
    await env.DB.prepare("INSERT INTO bot_webhook_status(id,status,detail) VALUES(1,'error','Secrets Telegram manquants') ON CONFLICT(id) DO UPDATE SET status=excluded.status,detail=excluded.detail,updated_at=CURRENT_TIMESTAMP").run();
    return;
  }
  const target="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram";
  const r=await api(env,"setWebhook",{url:target,secret_token:env.TELEGRAM_WEBHOOK_SECRET,allowed_updates:["message","callback_query"]});
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
  anime: {content_type: "animes", genre: "general"}
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
    for (const category of ["anime","desir","comedie","films"]) {
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
       last_scan=excluded.last_scan, last_seen=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP`
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

export default {
 async fetch(request,env){
   const url=new URL(request.url);
   if(url.pathname==="/health"){
     const state=await env.DB.prepare("SELECT status,detail,updated_at FROM bot_webhook_status WHERE id=1").first();
     const discovery=await env.DB.prepare("SELECT scan_date,imported,qualified,rejected,last_error,updated_at FROM discovery_sync_status WHERE id=1").first();
     return Response.json({service:"cinecanaux",database:!!env.DB,telegram_configured:!!env.TELEGRAM_TOKEN,webhook:state||{status:"waiting"},discovery:discovery||{status:"waiting"}});
   }
   if(url.pathname==="/telegram"&&request.method==="POST")return webhook(request,env);
   return new Response("CinéCanaux Telegram directory • use /health",{status:200});
 },
 async scheduled(controller,env,ctx){
   if(controller.cron==="0 */4 * * *")ctx.waitUntil(syncGitHubDiscovery(env));
   else ctx.waitUntil(provisionTelegramWebhook(env));
 }
};