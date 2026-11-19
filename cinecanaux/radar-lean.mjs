// Ciné Radar — annuaire minimal. Aucun compte, favori, parrainage ou suivi de clic.
import {radarOwnerDigest,authorizeRadarTitle,runTrendRefresh,reconcileRadarPosts} from "./trend-radar.mjs";
import {bindPrimaryRadarChannels,missingRadarTitles,formatRadarMissing,notifyOwnerMissingRadarTitles} from "./radar-owner-ops.mjs";
const BASE="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev";
const TYPES=[["films","🎬 Films"],["series","📺 Séries"],["animes","🎌 Animés"]];
const LINK=/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/;
const PRIVATE_LINK=/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})\/?$/;
const validTelegramLink=url=>LINK.test(url)||PRIVATE_LINK.test(url);
const esc=t=>String(t??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const button=(text,data,url)=>url?{text,url}:{text,callback_data:data};
const keyboard=rows=>({inline_keyboard:rows});
const categoryCache=new Map();
let catalogCache=null;
export function invalidateDirectoryCache(){categoryCache.clear();catalogCache=null;}
async function categoryRows(env,kind){
 const now=Date.now(),saved=categoryCache.get(kind);
 if(saved&&saved.expires>now)return saved.value;
 const pending=env.DB.prepare("SELECT title,link FROM channels WHERE status='approved' AND (content_type=? OR EXISTS (SELECT 1 FROM channel_categories cc WHERE cc.channel_id=channels.id AND cc.category=?)) AND NOT EXISTS (SELECT 1 FROM channel_index_meta m WHERE m.channel_id=channels.id AND m.listing_status<>'listed') ORDER BY COALESCE((SELECT priority FROM owned_channel_features f WHERE f.channel_id=channels.id AND f.enabled=1),0) DESC,updated_at DESC LIMIT 160").bind(kind,kind).all().then(x=>x.results||[]);
 categoryCache.set(kind,{expires:now+60000,value:pending});
 try{return await pending;}catch(e){categoryCache.delete(kind);throw e;}
}
async function catalogRows(env){
 if(catalogCache&&catalogCache.expires>Date.now())return catalogCache.value;
 const pending=env.DB.prepare("SELECT c.id,c.title,c.link,c.content_type,c.genre,COALESCE(NULLIF(p.post_image_url,''),NULLIF(p.avatar_url,''),'') avatar_url FROM channels c LEFT JOIN channel_profile_cache p ON c.id=p.channel_id WHERE c.status='approved' AND NOT EXISTS (SELECT 1 FROM channel_index_meta m WHERE m.channel_id=c.id AND m.listing_status<>'listed') ORDER BY c.updated_at DESC LIMIT 400").all().then(x=>x.results||[]);
 catalogCache={expires:Date.now()+90000,value:pending};
 try{return await pending;}catch(e){catalogCache=null;throw e;}
}
export async function telegram(env,method,data){
 const r=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data),signal:AbortSignal.timeout(method==="answerCallbackQuery"?3500:7500)});
 const d=await r.json();
 if(!d.ok)console.warn(JSON.stringify({event:"telegram_api_error",method,code:d.error_code}));
 return d;
}
async function display(env,chat,callback,text,markup){
 if(callback?.message?.message_id){
  const r=await telegram(env,"editMessageText",{chat_id:chat,message_id:callback.message.message_id,parse_mode:"HTML",text,disable_web_page_preview:true,reply_markup:markup});
  if(r.ok||r.description?.includes("message is not modified"))return;
 }
 const r=await telegram(env,"sendMessage",{chat_id:chat,text,parse_mode:"HTML",disable_web_page_preview:true,reply_markup:markup});
 if(!r.ok)throw Error("Cannot display Telegram directory");
}
const miniAppKeyboard=(owner=false,privateChat=true)=>{
 const rows=[[privateChat
  ?{text:"🎬 Ouvrir la Mini App",web_app:{url:BASE+"/app"}}
  :{text:"🎬 Découvrir Ciné Radar",url:BASE+"/app"}]];
 if(owner&&privateChat)rows.push([{text:"🔐 Administration",web_app:{url:BASE+"/admin"}}]);
 return keyboard(rows);
};
const INTRO=[
 "🎬 <b>Bienvenue sur CINÉ RADAR !</b>",
 "",
 "🍿 <b>Tout ton univers cinéma sur Telegram.</b>",
 "",
 "Avec Ciné Radar, tu peux :",
 "🔎 <b>Rechercher</b> des canaux de films, séries et animés.",
 "🎞 <b>Découvrir</b> les affiches et les sélections mises en avant.",
 "📺 <b>Explorer</b> les catégories et les recommandations.",
 "🔗 <b>Ouvrir</b> directement les canaux et les publications Telegram.",
 "",
 "✨ Tout se passe dans la Mini App. Appuie sur le bouton ci-dessous pour commencer 👇"
].join("\n");
const isOwner=async(env,user,privateChat)=>{
 if(!privateChat||!Number.isSafeInteger(Number(user))||Number(user)<=0)return false;
 const role=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(Number(user)).first();
 return role?.role==="owner";
};
async function processBotUpdate(env,update){
 const callback=update.callback_query, msg=callback?.message||update.message;
 const chat=msg?.chat?.id;
 if(!chat)return;
 const privateChat=msg?.chat?.type==="private";
 const sender=callback?.from?.id||update.message?.from?.id;
 const owner=await isOwner(env,sender,privateChat);
 const markup=miniAppKeyboard(owner,privateChat);
 const value=String(callback?.data||"");
 const text=String(update.message?.text||"").trim();

 // All legacy category/menu callbacks now lead back to the Mini App.
 // No channel listings or multi-step selection menus remain in the bot chat.
 if(value){await display(env,chat,callback,INTRO,markup);return;}

 const command=/^\/([a-z_]+)(?:@[A-Za-z0-9_]+)?(?:\s+(.*))?$/i.exec(text);
 const name=command?.[1]?.toLowerCase()||"";
 const arg=String(command?.[2]||"").trim();

 // Administrative commands are never shown or executed for other users.
 if(!owner||!privateChat||!["admin","tendances","manquants","canaux","autoriser","actualiser"].includes(name)){
  await display(env,chat,null,INTRO,markup);
  return;
 }
 if(name==="admin"){
  await display(env,chat,null,"🔐 <b>Ciné Radar — espace propriétaire</b>\n\nGère les canaux et le catalogue depuis l'administration.",markup);
  return;
 }
 if(name==="actualiser"){
  const binding=await bindPrimaryRadarChannels(env);
  const result=await runTrendRefresh(env,{force:true});
  await reconcileRadarPosts(env,120);
  const notices=await notifyOwnerMissingRadarTitles(env);
  await display(env,chat,null,esc("Tendances : "+result.updated+" fiches mises à jour ; "+notices.sent+" digest(s) privés ; "+binding.bound+" canal(aux) rattaché(s) ; "+(result.errors.length+notices.errors.length+binding.errors.length)+" erreur(s)."),markup);
  return;
 }
 if(name==="manquants"){
  const rows=await missingRadarTitles(env,sender,{limit:24});
  const count=rows.length?1:Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM radar_titles").first())?.n||0);
  await display(env,chat,null,esc(count?formatRadarMissing(rows):"Aucune tendance encore collectée. Utilise /actualiser ou vérifie les sources TMDB/AniList."),markup);
  return;
 }
 if(name==="canaux"){
  const result=await bindPrimaryRadarChannels(env);
  const channels=(await env.DB.prepare("SELECT kind,username,chat_id IS NOT NULL AS connected FROM radar_primary_channels ORDER BY kind").all()).results||[];
  const report="📡 Vérification des canaux officiels\n"+
   channels.map(x=>(Number(x.connected)?"✅ ":"⏳ ")+x.kind+" : @"+x.username).join("\n")+
   (result.errors.length?"\nDétails : "+result.errors.join("; "):"");
  await display(env,chat,null,esc(report),markup);
  return;
 }
 if(name==="tendances"){
  await display(env,chat,null,esc(await radarOwnerDigest(env)),markup);
  return;
 }
 if(!arg){await display(env,chat,null,"Usage : /autoriser ID_TITRE\nRéservé aux publications pour lesquelles tu disposes des droits de diffusion.",markup);return;}
 const approved=await authorizeRadarTitle(env,arg,sender);
 await display(env,chat,null,approved?"✅ Titre autorisé pour l’affichage si une publication vidéo correspondante est vérifiée.":"Titre introuvable ou identifiant invalide.",markup);
}
// Acknowledge the Telegram tap in parallel with loading and editing the message.
export async function botUpdate(env,update){
 const cb=update.callback_query;
 const ack=cb?.id?telegram(env,"answerCallbackQuery",{callback_query_id:cb.id}).catch(e=>{console.warn("callback_ack_failed",String(e).slice(0,80));}):Promise.resolve();
 const outcome=await Promise.allSettled([ack,processBotUpdate(env,update)]);
 if(outcome[1].status==="rejected")throw outcome[1].reason;
}
export async function listPublicChannels(env){
 const rows=await catalogRows(env);
 return rows.filter(c=>validTelegramLink(c.link)).map(x=>({
  id:x.id,title:x.title,link:x.link,type:x.content_type,
  photo:x.avatar_url||null,genre:x.genre
 }));
}
export async function miniAppAPI(env,request,previewFn){
 const json=(obj,status=200)=>Response.json(obj,{status,headers:{"Cache-Control":"public, max-age=120","X-Content-Type-Options":"nosniff"}});
 const u=new URL(request.url);
 if(request.method!=="GET")return json({error:"Méthode non disponible"},405);
 if(u.pathname==="/api/catalog"){
  const type=String(u.searchParams.get("type")||"all");
  if(!["all","films","series","animes"].includes(type))return json({error:"Catégorie inconnue"},400);
  const q=String(u.searchParams.get("q")||"").trim().toLowerCase().slice(0,70);
  const channels=await listPublicChannels(env);
  const eligible=channels.filter(c=>(type==="all"||c.type===type)&&(!q||String(c.title+" "+c.genre).toLocaleLowerCase().includes(q)));
  return json({channels:eligible,total:eligible.length});
 }
 if(u.pathname==="/api/channel-preview"){
  const id=Number(u.searchParams.get("id"));
  if(!Number.isSafeInteger(id)||id<1)return json({error:"Canal invalide"},400);
  const result=await previewFn(env,id);
  if(result.status!==200)return json({error:result.error||"Aperçu indisponible"},result.status);
  const p=result.data;
  // Expose only essential public-facing data.
  return json({channel:{id:p.id,title:p.title,description:p.description||"",photo:p.avatar_url||null,post_image:p.post_image_url||null,link:p.link}});
 }
 return json({error:"Route non trouvée"},404);
}
export async function initializeProfile(env){
 const v=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='profile_version'").first();
 if(v?.value==="9")return;
 const tasks=[
  ["setMyName",{name:"Ciné Radar"}],
  ["setMyShortDescription",{short_description:"🎬 Trouve rapidement des canaux publics de films, séries et animés."}],
  ["setMyDescription",{description:"🎬 Ciné Radar : choisis une catégorie, découvre des canaux Telegram publics et ouvre celui qui t'intéresse."}],
  ["setMyCommands",{commands:[{command:"start",description:"🎬 Rechercher un canal"},{command:"menu",description:"🍿 Catégories"},{command:"tendances",description:"📈 Tendances (propriétaire)"},{command:"manquants",description:"📬 Titres à rechercher (propriétaire)"},{command:"actualiser",description:"🔄 Actualiser les tendances (propriétaire)"}]}],
  ["setChatMenuButton",{menu_button:{type:"web_app",text:"🎬 Voir les canaux",web_app:{url:BASE+"/app"}}}]
 ];
 for(const [method,data] of tasks){const r=await telegram(env,method,data);if(!r.ok)throw Error("Telegram profile update failed: "+method);}
 await env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('profile_version','9') ON CONFLICT(setting_key) DO UPDATE SET value='9',updated_at=CURRENT_TIMESTAMP").run();
}
// Health probes may be incomplete on Telegram; two independent checks are needed before deleting.
export async function maintenance(env){
 const channels=(await env.DB.prepare(
  "SELECT c.id,c.link,COALESCE(t.check_status,'unknown') prior FROM channels c LEFT JOIN channel_telemetry t ON t.channel_id=c.id WHERE c.status='approved' AND (t.last_checked_at IS NULL OR t.last_checked_at < datetime('now','-4 hours') OR (t.check_status='not_found' AND t.last_checked_at < datetime('now','-5 minutes'))) ORDER BY c.updated_at DESC LIMIT 24"
 ).all()).results||[];
 for(const item of channels){
  const match=/^https:\/\/t\.me\/([A-Za-z][A-Za-z0-9_]{4,31})\/?$/.exec(item.link);
  if(!match)continue;
  let status="unverifiable";
  try{
   const sampled=await fetch("https://t.me/s/"+match[1],{method:"GET",redirect:"error",signal:AbortSignal.timeout(6500)});
   if(sampled.status===404){
    const landing=await fetch("https://t.me/"+match[1],{method:"GET",redirect:"error",signal:AbortSignal.timeout(6500)});
    if(landing.status===404)status="not_found";
   }else if(sampled.status===200)status="reachable";
  }catch(e){console.warn(JSON.stringify({event:"public_link_check_unavailable",id:item.id,error:String(e).slice(0,90)}));}
  if(status==="not_found"&&item.prior==="not_found"){
   await env.DB.batch([
    env.DB.prepare("UPDATE discovery_candidates SET technical_status='rejected_format',rights_status='link_dead',updated_at=CURRENT_TIMESTAMP WHERE link=?").bind(item.link),
    env.DB.prepare("DELETE FROM channel_profile_cache WHERE channel_id=?").bind(item.id),
    env.DB.prepare("DELETE FROM channel_telemetry WHERE channel_id=?").bind(item.id),
    env.DB.prepare("DELETE FROM channels WHERE id=?").bind(item.id)
   ]);
   console.log(JSON.stringify({event:"invalid_public_link_removed",id:item.id}));
  }else{
   await env.DB.prepare(
    "INSERT INTO channel_telemetry(channel_id,check_status,last_checked_at,last_good_at) VALUES(?,?,CURRENT_TIMESTAMP,CASE WHEN ?='reachable' THEN CURRENT_TIMESTAMP END) ON CONFLICT(channel_id) DO UPDATE SET check_status=excluded.check_status,last_checked_at=CURRENT_TIMESTAMP,last_good_at=CASE WHEN excluded.check_status='reachable' THEN CURRENT_TIMESTAMP ELSE channel_telemetry.last_good_at END"
   ).bind(item.id,status,status).run();
  }
 }
}
export async function cleanup(env){
 // No per-user update history or browsing events are stored.
 await env.DB.prepare("DELETE FROM channel_profile_cache WHERE channel_id NOT IN (SELECT id FROM channels)").run();
 await env.DB.prepare("DELETE FROM discovery_candidates WHERE technical_status='rejected_format' AND updated_at < datetime('now','-120 days')").run();
}
