// CinéCanaux: Telegram HTML formatting + button styles + independent shareable referral cards.
// Telegram Bot API >= 9.4 supports primary / success / danger button styles.
const categories = [["films","🎬 Films"],["series","📺 Séries"],["animes","🎌 Animés"]];
const genres = {
  films:[["general","🎬 Tous les films"],["action","💥 Action"],["comedie","😂 Comédie"],["horreur","👻 Horreur"],["romance","💕 Romance"],["sciencefiction","🚀 Science-fiction"],["drame","🎭 Drame"]],
  series:[["general","📺 Toutes les séries"],["action","💥 Action"],["comedie","😂 Comédie"],["drame","🎭 Drame"],["policier","🕵️ Policier"]],
  animes:[["general","🎌 Tous les animés"],["shonen","⚔️ Shōnen"],["seinen","🌙 Seinen"],["romance","💕 Romance"],["fantasy","✨ Fantasy"]]
};
const html = value => String(value ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const LINK_RE = /^https:\/\/t\.me\/[a-zA-Z][a-zA-Z0-9_]{4,31}\/?$/;
const REF_RE = /^ref_([a-f0-9]{16})$/;
function keyboard(rows) {
  return {inline_keyboard: rows.map(row => row.map(([text,data,url,style]) => {
    const button = {text};
    if(url) button.url=url;
    else button.callback_data=data;
    if(["primary","success","danger"].includes(style))button.style=style;
    return button;
  }))};
}
function menu() {
  return keyboard([
    [["🎬 Films","type:films",null,"primary"],["📺 Séries","type:series",null,"primary"]],
    [["🎌 Animés","type:animes",null,"primary"],["🔎 Rechercher","search",null,"primary"]],
    [["🎁 Parrainage","referral",null,"success"],["📊 Mes filleuls","refstats"]],
    [["📣 Nos canaux","owned"],["📨 Proposer un canal","suggest"]],
  ]);
}
const back = () => keyboard([[["🏠 Retour à l'accueil","home",null,"primary"]]]);
async function api(env,method,data) {
  if(!env.TELEGRAM_TOKEN)throw Error("TELEGRAM_TOKEN manquant");
  const response=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{
    method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data)});
  const result=await response.json();
  if(!result.ok)console.error(JSON.stringify({event:"telegram_api_failed",method,code:result.error_code,description:result.description}));
  return result;
}
async function send(env,chat_id,text,reply_markup) {
  const response=await api(env,"sendMessage",{chat_id,text,parse_mode:"HTML",
    reply_markup,disable_web_page_preview:true});
  if(!response.ok)throw Error("Échec d'envoi Telegram");
  return response;
}
async function answer(env,id) {if(id)await api(env,"answerCallbackQuery",{callback_query_id:id});}
async function listOwned(env) {
  return (await env.DB.prepare("SELECT chat_id,title,link FROM owned_channels WHERE enabled=1 ORDER BY id").all()).results||[];
}
async function gate(env,userId) {
  const owned=await listOwned(env),missing=[];
  for(const ch of owned){
    try{
      const r=await api(env,"getChatMember",{chat_id:ch.chat_id,user_id:userId});
      if(!r.ok||!(["creator","administrator","member"].includes(r.result.status)||r.result.status==="restricted"&&r.result.is_member===true))missing.push(ch);
    }catch{missing.push(ch);}
  }
  return missing;
}
async function requireJoin(env,chatId,userId) {
  const missing=await gate(env,userId);
  if(missing.length===0) {
    await env.DB.prepare("UPDATE referral_visits SET confirmed_at=CURRENT_TIMESTAMP WHERE invited_id=? AND confirmed_at IS NULL").bind(userId).run();
    return true;
  }
  await send(env,chatId,[
    "🔐 <b>Accès réservé aux membres</b>",
    "",
    "<i>Rejoins d'abord nos canaux officiels pour débloquer l'annuaire.</i>",
    "<blockquote>Une fois abonné, appuie sur <b>✅ Vérifier mon abonnement</b>.</blockquote>"
  ].join("\n"),keyboard([
    ...missing.filter(ch=>LINK_RE.test(ch.link)).map(ch=>[["📣 "+ch.title,null,ch.link,"primary"]]),
    [["✅ Vérifier mon abonnement","verify",null,"success"]]
  ]));
  return false;
}
async function home(env,chatId,userId){
  if(!(await requireJoin(env,chatId,userId)))return;
  await send(env,chatId,[
    "🍿 <b>BIENVENUE SUR CINÉCANAUX</b>",
    "",
    "<i>Un espace pour explorer les chaînes de films, séries et animés.</i>",
    "",
    "<blockquote>🎞️ Choisis une catégorie, sélectionne ton genre et découvre les canaux disponibles.</blockquote>",
    "",
    "✨ <b>Que veux-tu regarder aujourd'hui ?</b>"
  ].join("\n"),menu());
}
async function results(env,chatId,kind,genre,q) {
  let rows=[];
  if(q){
    rows=(await env.DB.prepare("SELECT title,link,description,content_type,genre FROM channels WHERE status='approved' AND rights_confirmed=1 AND (title LIKE ? OR description LIKE ?) ORDER BY updated_at DESC LIMIT 12")
      .bind("%"+q+"%","%"+q+"%").all()).results||[];
  }else{
    rows=(await env.DB.prepare("SELECT title,link,description,content_type,genre FROM channels WHERE status='approved' AND rights_confirmed=1 AND content_type=? AND genre=? ORDER BY updated_at DESC LIMIT 12")
      .bind(kind,genre).all()).results||[];
  }
  if(!rows.length){
    await send(env,chatId,[
      "🎬 <b>Aucun canal disponible pour l'instant</b>",
      "",
      "<i>Nous ajoutons les chaînes après vérification.</i>",
      "<blockquote>Tu connais une chaîne intéressante ? Propose-la via le menu !</blockquote>"
    ].join("\n"),back());return;
  }
  await send(env,chatId,"🎞️ <b>Ta sélection CinéCanaux</b>\n<i>"+rows.length+" canal(aux) référencé(s).</i>");
  for(const ch of rows) {
    const link=LINK_RE.test(ch.link)?ch.link:null;
    const title=html(ch.title).slice(0,260);
    const description=html(ch.description||"Canal référencé et autorisé").slice(0,450);
    await send(env,chatId,[
      "🎬 <b>"+title+"</b>","",
      "<blockquote>"+description+"</blockquote>",
      "✅ <i>Canal vérifié et autorisé.</i>"
    ].join("\n"),link?keyboard([[["🔗 Ouvrir le canal",null,link,"success"]]]):undefined);
  }
  await send(env,chatId,"✨ <i>Fin de cette sélection.</i>",back());
}
async function findOrCreateCode(env,userId){
  const existing=await env.DB.prepare("SELECT code FROM referral_codes WHERE user_id=?").bind(userId).first();
  if(existing?.code)return existing.code;
  for(let tries=0;tries<4;tries++){
    const code=crypto.randomUUID().replace(/-/g,"").slice(0,16);
    await env.DB.prepare("INSERT OR IGNORE INTO referral_codes(user_id,code) VALUES(?,?)").bind(userId,code).run();
    const record=await env.DB.prepare("SELECT code FROM referral_codes WHERE user_id=?").bind(userId).first();
    if(record?.code)return record.code;
  }
  throw Error("Impossible de créer le code de parrainage");
}
async function trackInvite(env,invitedId,argument){
  const match=REF_RE.exec(String(argument||""));
  if(!match)return;
  const inviter=await env.DB.prepare("SELECT user_id FROM referral_codes WHERE code=?").bind(match[1]).first();
  if(!inviter?.user_id||Number(inviter.user_id)===Number(invitedId))return;
  await env.DB.prepare("INSERT OR IGNORE INTO referral_visits(invited_id,referrer_id) VALUES(?,?)")
    .bind(invitedId,inviter.user_id).run();
}
async function linkForReferrer(env,userId){
  const code=await findOrCreateCode(env,userId);
  const info=await api(env,"getMe",{});
  const username=info?.result?.username;
  if(!info.ok||!username||!/^[a-zA-Z0-9_]{5,32}$/.test(username))throw Error("Identifiant Telegram du bot indisponible");
  return "https://t.me/"+username+"?start=ref_"+code;
}
async function sendReferral(env,chatId,userId){
  const link=await linkForReferrer(env,userId);
  const message=[
    "🎬 <b>TON PROCHAIN COUP DE CŒUR CINÉ EST PEUT-ÊTRE ICI !</b>",
    "",
    "🍿 <b>Films • Séries • Animés</b>",
    "",
    "<blockquote>✨ Explore des canaux classés par genre et découvre de nouvelles idées de visionnage en quelques clics.</blockquote>",
    "",
    "💫 <i>Action, comédie, romance, animés… trouve ce qui te plaît.</i>",
    "",
    "🔗 <b>Découvre CinéCanaux avec mon invitation :</b>",
    "<code>"+html(link)+"</code>"
  ].join("\n");
  // Message 1: public invite to forward, containing no internal referral instructions.
  await send(env,chatId,message);
  // Message 2: private, separate instructions that must NOT be part of the forwarded invite.
  const shareUrl="https://t.me/share/url?url="+encodeURIComponent(link)+"&text="+encodeURIComponent("🎬 Découvre CinéCanaux ! 🍿 Films, séries et animés classés par genre.");
  await send(env,chatId,[
    "🎁 <b>TON MESSAGE DE PARRAINAGE EST PRÊT !</b>",
    "",
    "<i>Le message juste au-dessus est celui que tu peux partager.</i>",
    "",
    "<blockquote>👆 Appuie longuement sur le message précédent puis choisis <b>« Transférer »</b> pour conserver ses textes en gras, en italique et sa citation.</blockquote>",
    "",
    "📤 <b>Autre option :</b> utilise le bouton ci-dessous pour ouvrir le partage Telegram.",
    "",
    "✅ <i>Ces consignes sont dans un message séparé : elles ne feront pas partie du message transféré.</i>"
  ].join("\n"),keyboard([
    [["📤 Partager le lien",null,shareUrl,"success"]],
    [["📊 Mes filleuls","refstats",null,"primary"],["🏠 Accueil","home"]]
  ]));
}
async function referralStats(env,chatId,userId){
  const stats=await env.DB.prepare("SELECT COUNT(*) AS openings, COUNT(confirmed_at) AS confirmed FROM referral_visits WHERE referrer_id=?")
    .bind(userId).first();
  await send(env,chatId,[
    "📊 <b>MES PARRAINAGES</b>",
    "",
    "👥 <b>"+Number(stats?.openings||0)+"</b> personne(s) ayant démarré via ton lien",
    "✅ <b>"+Number(stats?.confirmed||0)+"</b> accès validé(s)",
    "",
    "<blockquote>Un filleul est compté une seule fois après son arrivée. Son accès est validé lorsqu'il remplit les conditions d'abonnement.</blockquote>",
    "",
    "<i>Invite tes proches pour leur faire découvrir CinéCanaux !</i>"
  ].join("\n"),keyboard([[["🎁 Partager mon invitation","referral",null,"success"]],[["🏠 Accueil","home"]]]));
}
async function handle(env,u){
  const m=u.message||u.callback_query?.message,cb=u.callback_query;
  const chatId=m?.chat?.id,userId=cb?.from?.id||m?.from?.id;
  if(!chatId||!userId)return;
  if(cb)await answer(env,cb.id);
  const val=cb?.data,raw=m?.text?.trim()||"";
  const start=/^\/start(?:@[a-zA-Z0-9_]+)?(?:\s+([A-Za-z0-9_-]+))?$/i.exec(raw);
  if(start){
    if(start[1])await trackInvite(env,userId,start[1]);
    await home(env,chatId,userId);return;
  }
  if(val==="verify"||val==="home"||/^\/menu(?:@[a-zA-Z0-9_]+)?$/.test(raw)){await home(env,chatId,userId);return;}
  if(!(await requireJoin(env,chatId,userId)))return;
  if(val==="referral"||raw==="/parrainage"||raw==="/inviter"){
    await sendReferral(env,chatId,userId);return;
  }
  if(val==="refstats"||raw==="/mesparrainages"){
    await referralStats(env,chatId,userId);return;
  }
  if(val==="owned"){
    const own=await listOwned(env);
    if(!own.length){await send(env,chatId,"📣 <b>Nos canaux officiels</b>\n<i>Ils seront annoncés prochainement.</i>",back());return;}
    await send(env,chatId,"📣 <b>NOS CANAUX OFFICIELS</b>\n<i>Retrouve-nous sur Telegram :</i>",keyboard([
      ...own.filter(c=>LINK_RE.test(c.link)).map(c=>[["📣 "+c.title,null,c.link,"primary"]]),
      [["🏠 Accueil","home"]]
    ]));return;
  }
  if(val?.startsWith("type:")){
    const kind=val.slice(5);if(!genres[kind])return;
    const label=categories.find(x=>x[0]===kind)?.[1]||"Catégorie";
    await send(env,chatId,"🎞️ <b>"+html(label)+"</b>\n<i>Choisis le genre qui t'intéresse :</i>",
      keyboard(genres[kind].map(([key,name])=>[[name,"genre:"+kind+":"+key,null,key==="general"?"success":"primary"]])
        .concat([[["🏠 Accueil","home"]]])));
    return;
  }
  if(val?.startsWith("genre:")){
    const parts=val.split(":");
    if(parts.length!==3||!genres[parts[1]]?.some(x=>x[0]===parts[2]))return;
    await results(env,chatId,parts[1],parts[2],null);return;
  }
  if(val==="search"||raw==="/recherche"){
    await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'search') ON CONFLICT(user_id) DO UPDATE SET mode='search'").bind(userId).run();
    await send(env,chatId,"🔎 <b>RECHERCHE</b>\n<i>Envoie un nom de canal ou un mot-clé (action, romance, animé…).</i>",back());return;
  }
  if(val==="suggest"||raw==="/proposer"){
    await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'suggest') ON CONFLICT(user_id) DO UPDATE SET mode='suggest'").bind(userId).run();
    await send(env,chatId,"📨 <b>PROPOSER UN CANAL</b>\n<blockquote>Envoie le lien public du canal (<code>https://t.me/nomducanal</code>).</blockquote>\n<i>Les droits de diffusion seront vérifiés avant toute publication.</i>",back());return;
  }
  if(/^\/aide$/.test(raw)){
    await send(env,chatId,[
      "💡 <b>BESOIN D'AIDE ?</b>","",
      "🎬 <b>/menu</b> — Explorer le catalogue",
      "🔎 <b>/recherche</b> — Rechercher",
      "🎁 <b>/parrainage</b> — Obtenir ton message à partager",
      "📊 <b>/mesparrainages</b> — Suivre tes invitations",
      "📨 <b>/proposer</b> — Suggérer un canal",
      "",
      "<blockquote>🔐 L'accès peut nécessiter un abonnement aux canaux officiels.</blockquote>"
    ].join("\n"),back());return;
  }
  if(!raw)return;
  const state=await env.DB.prepare("SELECT mode FROM user_states WHERE user_id=?").bind(userId).first();
  if(state?.mode==="search"){
    await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(userId).run();
    await results(env,chatId,null,null,raw.slice(0,100));return;
  }
  if(state?.mode==="suggest"){
    await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(userId).run();
    if(!LINK_RE.test(raw)){
      await send(env,chatId,"⚠️ <b>Lien invalide</b>\n<i>Utilise un lien public du type :</i>\n<code>https://t.me/nomducanal</code>",back());return;
    }
    await env.DB.prepare("INSERT INTO suggestions(user_id,link,status) VALUES(?,?,'pending')").bind(userId,raw).run();
    await send(env,chatId,"✅ <b>Proposition enregistrée !</b>\n<i>Merci ! Nous allons vérifier la chaîne et ses droits avant de l'ajouter.</i>",back());return;
  }
  await send(env,chatId,"🍿 <i>Utilise les boutons ci-dessous pour continuer.</i>",menu());
}
async function webhook(request,env){
  if(!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET)return new Response("Configuration Telegram incomplète",{status:503});
  const received=request.headers.get("X-Telegram-Bot-Api-Secret-Token")||"",expected=env.TELEGRAM_WEBHOOK_SECRET;
  const a=new TextEncoder().encode(received),b=new TextEncoder().encode(expected);
  if(a.length!==b.length||!crypto.subtle.timingSafeEqual(a,b))return new Response("Forbidden",{status:403});
  const data=await request.json();
  if(!data.update_id)return Response.json({ok:true});
  const id=data.update_id;
  const written=await env.DB.prepare("INSERT OR IGNORE INTO update_log(update_id) VALUES(?)").bind(id).run();
  if(written.meta.changes===0)return Response.json({ok:true});
  try{await handle(env,data);}
  catch(error){
    console.error(JSON.stringify({event:"telegram_update_failed",reason:String(error).slice(0,140)}));
    await env.DB.prepare("DELETE FROM update_log WHERE update_id=?").bind(id).run();
    return new Response("Retry",{status:500});
  }
  return Response.json({ok:true});
}

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