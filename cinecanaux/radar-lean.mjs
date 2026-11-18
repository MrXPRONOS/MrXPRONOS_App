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
const homeButtons=()=>keyboard([
 [button("🎬 Films","category:films"),button("📺 Séries","category:series"),button("🎌 Animés","category:animes")],
 [{text:"🍿 Voir tous les canaux",web_app:{url:BASE+"/app"}}]
]);
function categoriesLabel(k){return TYPES.find(x=>x[0]===k)?.[1]||"Films";}
async function processBotUpdate(env,update){
 const cb=update.callback_query, msg=cb?.message||update.message;
 const chat=msg?.chat?.id;
 if(!chat)return;
 const value=String(cb?.data||"");
 const text=String(update.message?.text||"").trim();
 const ownerCommand=/^\/(tendances|manquants|canaux|autoriser|actualiser)(?:@[A-Za-z0-9_]+)?(?:\s+([a-z0-9-]{6,70}))?$/i.exec(text);
 if(ownerCommand){
  const uid=update.message?.from?.id;
  const owner=Number.isSafeInteger(uid)&&msg?.chat?.type==="private"
   ?await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(uid).first():null;
  if(owner?.role!=="owner"){await display(env,chat,cb,"Commande réservée au propriétaire en message privé.",homeButtons());return;}
  if(ownerCommand[1].toLowerCase()==="actualiser"){
   const binding=await bindPrimaryRadarChannels(env);
   const result=await runTrendRefresh(env,{force:true});
   await reconcileRadarPosts(env,120);
   const notices=await notifyOwnerMissingRadarTitles(env);
   await display(env,chat,cb,esc("Tendances : "+result.updated+" fiches mises à jour ; "+notices.sent+" digest(s) privés ; "+binding.bound+" canal(aux) rattaché(s) ; "+(result.errors.length+notices.errors.length+binding.errors.length)+" erreur(s)."),homeButtons());return;
  }
  if(ownerCommand[1].toLowerCase()==="manquants"){
   const rows=await missingRadarTitles(env,uid,{limit:24});
   const count=rows.length?1:Number((await env.DB.prepare("SELECT COUNT(*) AS n FROM radar_titles").first())?.n||0);
   await display(env,chat,cb,esc(count?formatRadarMissing(rows):"Aucune tendance encore collectée. Utilise /actualiser ou vérifie les sources TMDB/AniList."),homeButtons());return;
  }
  if(ownerCommand[1].toLowerCase()==="canaux"){
   const result=await bindPrimaryRadarChannels(env);
   const channels=(await env.DB.prepare("SELECT kind,username,chat_id IS NOT NULL AS connected FROM radar_primary_channels ORDER BY kind").all()).results||[];
   const report="📡 Vérification des canaux officiels\\n"+
    channels.map(x=>(Number(x.connected)?"✅ ":"⏳ ")+x.kind+" : @"+x.username).join("\\n")+
    (result.errors.length?"\\nDétails : "+result.errors.join("; "):"");
   await display(env,chat,cb,esc(report),homeButtons());return;
  }
  if(ownerCommand[1].toLowerCase()==="tendances"){
   await display(env,chat,cb,esc(await radarOwnerDigest(env)),homeButtons());return;
  }
  const id=ownerCommand[2]||"";
  if(!id){await display(env,chat,cb,"Usage : /autoriser ID_TITRE\nRéservé aux publications dont tu possèdes les droits de diffusion.",homeButtons());return;}
  const approved=await authorizeRadarTitle(env,id,uid);
  await display(env,chat,cb,approved?"✅ Titre autorisé pour l’affichage si une publication vidéo correspondante est vérifiée.":"Titre introuvable ou identifiant invalide.",homeButtons());
  return;
 }
 if(/^\/admin(?:@[A-Za-z0-9_]+)?$/i.test(text)){
  const uid=update.message?.from?.id;
  const admin=Number.isSafeInteger(uid)?await env.DB.prepare('SELECT role FROM admin_users WHERE user_id=?').bind(uid).first():null;
  if(!admin){await display(env,chat,cb,"Accès réservé.",homeButtons());return;}
  await display(env,chat,cb,"🔐 <b>Ciné Radar — administration</b>",keyboard([[{text:"Ouvrir l'administration",web_app:{url:BASE+"/admin"}}]]));
  return;
 }
 if(value==="home"||/^\/(start|menu|aide|help|profil|favoris|parrainage|preferences)(?:@[A-Za-z0-9_]+)?(?:\s+.*)?$/i.test(text)||(!value&&!text)){
  await display(env,chat,cb,"🎬 <b>CINÉ RADAR</b>\n\nChoisis une catégorie 👇",homeButtons());return;
 }
 let match=/^category:(films|series|animes)(?::([0-9]{1,3}))?$/.exec(value);
 if(!match){
  // Accept intuitive menu commands, but do not create personal state.
  const cmd=/^\/(films|series|animes)(?:@[A-Za-z0-9_]+)?$/i.exec(text);
  if(cmd)match=[text,cmd[1].toLowerCase(),"0"];
 }
 if(!match){await display(env,chat,cb,"🎬 <b>CINÉ RADAR</b>\n\nChoisis une catégorie 👇",homeButtons());return;}
 const kind=match[1],requested=Math.min(50,Math.max(0,Number(match[2]||0)));
 const rows=await categoryRows(env,kind);
 const filtered=rows.filter(c=>validTelegramLink(c.link));
 const page=Math.min(requested,Math.max(0,Math.ceil(filtered.length/8)-1)),slice=filtered.slice(page*8,page*8+8);
 const nav=slice.map(c=>[button("🎞 "+String(c.title||"Canal public").slice(0,43),null,c.link)]);
 const pages=[];
 if(page>0)pages.push(button("◀ Précédents","category:"+kind+":"+(page-1)));
 if((page+1)*8<filtered.length)pages.push(button("Suivants ▶","category:"+kind+":"+(page+1)));
 if(pages.length)nav.push(pages);
 nav.push([button("⬅ Catégories","home")]);
 const msgText=esc(categoriesLabel(kind))+" <b>— Canaux Telegram</b>\n\n"+
 (slice.length?"Appuie sur un canal pour l'ouvrir 👇":"Aucun canal disponible pour le moment.");
 await display(env,chat,cb,msgText,keyboard(nav));
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
