import {searchRank,qualityScore,recommendations,extractTelegramActivity,notificationEligible} from "./radar-intelligence.mjs";
// Cine Radar V2 — Cloudflare Workers / Telegram API / D1. No Supabase dependency.
const BASE="https://cinecanaux-bot.cinecanaux-xpronos.workers.dev";
const BOT_LINK_RE=/^https:\/\/t\.me\/[a-zA-Z][a-zA-Z0-9_]{4,31}\/?$/;
const START_REF_RE=/^ref_([a-f0-9]{16})$/;
const CATEGORY=[["films","🎬 Films"],["series","📺 Séries"],["animes","🎌 Animés"]];
const GENRES={films:[["general","Tous les films"],["action","Action"],["comedie","Comédie"],["horreur","Horreur"],["romance","Romance"],["sciencefiction","Science-fiction"],["drame","Drame"]],series:[["general","Toutes les séries"],["action","Action"],["comedie","Comédie"],["drame","Drame"],["policier","Policier"]],animes:[["general","Tous les animés"],["shonen","Shōnen"],["seinen","Seinen"],["romance","Romance"],["fantasy","Fantasy"]]};
const LANG=[["tous","🌍 Toutes langues"],["VF","🇫🇷 VF"],["VOSTFR","💬 VOSTFR"],["VO","🎞 VO"]];
const esc=v=>String(v??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const clean=v=>String(v??"").trim().slice(0,140);
const strip=v=>String(v||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim();
const bx=(text,callback,url,style)=>({...{text},...(url?{url}:{callback_data:callback}),...(style?{style}:{})});
const kb=rows=>({inline_keyboard:rows});
const navHome=()=>[bx("⌂ Accueil","home",null,"primary")];
const botName="Ciné Radar";
const genTag=(k)=>GENRES[k]||[];
const regularHeader=(heading,body,quote)=>"🎬 <b>"+heading+"</b>\n\n"+body+(quote?"\n\n<blockquote>"+quote+"</blockquote>":"");
export async function telegram(env,method,data){
 const r=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data)});
 const value=await r.json();
 if(!value.ok)console.error(JSON.stringify({type:"telegram",method,code:value.error_code,description:value.description}));
 return value;
}
async function send(env,id,text,reply,extra={}){
 const r=await telegram(env,"sendMessage",{chat_id:id,text,parse_mode:"HTML",disable_web_page_preview:true,reply_markup:reply,...extra});
 if(!r.ok)throw Error("Telegram sendMessage failed "+r.error_code);
 return r.result;
}
async function edit(env,cb,text,reply){
 if(cb?.message?.message_id){
  const r=await telegram(env,"editMessageText",{chat_id:cb.message.chat.id,message_id:cb.message.message_id,text,parse_mode:"HTML",disable_web_page_preview:true,reply_markup:reply});
  if(r.ok)return;
  // Older clients and uneditable media messages must still support the flow.
 }
 return send(env,cb.message.chat.id,text,reply);
}
async function show(env,id,cb,text,reply){return cb?edit(env,cb,text,reply):send(env,id,text,reply);}
async function responseCb(env,id,text){if(id)await telegram(env,"answerCallbackQuery",{callback_query_id:id,...(text?{text}:{})});}
async function isAdmin(env,userId){return Boolean(await env.DB.prepare("SELECT 1 FROM admin_users WHERE user_id=?").bind(userId).first());}
async function ownChannels(env){return (await env.DB.prepare("SELECT chat_id,title,link FROM owned_channels WHERE enabled=1 ORDER BY id").all()).results||[];}
async function membership(env,uid){
 const list=await ownChannels(env);const missing=[];
 for(const c of list){
  try{
   const res=await telegram(env,"getChatMember",{chat_id:c.chat_id,user_id:uid});
   const s=res.result?.status;
   if(!res.ok||!(["creator","administrator","member"].includes(s)||(s==="restricted"&&res.result.is_member===true)))missing.push(c);
  }catch{missing.push(c);}
 }
 if(list.length>0&&missing.length===0){
  await env.DB.prepare("UPDATE referral_visits SET confirmed_at=CURRENT_TIMESTAMP WHERE invited_id=? AND confirmed_at IS NULL").bind(uid).run();
 }
 return missing;
}
async function access(env,uid,chat,cb){
 const missing=await membership(env,uid);
 if(missing.length===0)return true;
 const msg=regularHeader("ACCÈS AUX CANAUX OFFICIELS","<i>Rejoins les canaux suivants pour profiter des fonctionnalités de Ciné Radar.</i>","Une fois abonné, appuie sur <b>✅ Vérifier mon abonnement</b>.");
 const buttons=missing.filter(c=>BOT_LINK_RE.test(c.link)).map(c=>[bx("📣 "+clean(c.title),null,c.link,"primary")]);
 buttons.push([bx("✅ Vérifier mon abonnement","verify",null,"success")]);
 await show(env,chat,cb,msg,kb(buttons));return false;
}
async function prefs(env,uid){
 return (await env.DB.prepare("SELECT category,language,notification_enabled,onboarded FROM preferences WHERE user_id=?").bind(uid).first())||{category:"films",language:"tous",notification_enabled:0,onboarded:0};
}
async function setPrefs(env,uid,changes){
 const p=await prefs(env,uid),c={...p,...changes};
 await env.DB.prepare("INSERT INTO preferences(user_id,category,language,notification_enabled,onboarded) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET category=excluded.category,language=excluded.language,notification_enabled=excluded.notification_enabled,onboarded=excluded.onboarded,updated_at=CURRENT_TIMESTAMP").bind(uid,c.category,c.language,c.notification_enabled?1:0,c.onboarded?1:0).run();
}
async function startMessage(env,id,uid,cb){
 const p=await prefs(env,uid);
 const msg=regularHeader("BIENVENUE SUR CINÉ RADAR 🍿",
  "Ton <b>radar cinéma</b> : découvre des chaînes vérifiées et explore tes genres préférés.\n\n<i>Films • Séries • Animés • Favoris</i>",
  "✨ <b>Que souhaites-tu découvrir aujourd'hui ?</b>");
 const rows=[
  [bx("🎬 Films","type:films",null,"primary"),bx("📺 Séries","type:series",null,"primary")],
  [bx("🎌 Animés","type:animes",null,"primary"),bx("🔎 Rechercher","search",null,"primary")],
  [bx("⭐ Mes favoris","favorites"),bx("🆕 Nouveautés","latest",null,"success")],
  [bx("✨ Pour moi","recommend"),bx("🎛 Mes préférences","preferences")],
  [bx("🎁 Parrainage","referral",null,"success"),bx("📊 Mes filleuls","refstats")],
  [bx("📣 Nos canaux","owned"),bx("🖥 Mini App","miniapp",null,"primary")],
  [bx("📨 Proposer","suggest"),bx("💡 Aide","help")]
 ];
 if(!p.onboarded&&!cb){
  const picture=await telegram(env,"sendPhoto",{chat_id:id,photo:BASE+"/assets/welcome.png",
   caption:"🎬 <b>CINÉ RADAR</b> — Ton cinéma, tes découvertes. 🍿",parse_mode:"HTML"});
  if(!picture.ok)console.warn(JSON.stringify({event:"welcome_photo_fallback",code:picture.error_code}));
  rows.push([bx("🎓 Guide de démarrage (3 étapes)","guide:0",null,"success")]);
  await setPrefs(env,uid,{onboarded:1});
 }
 await show(env,id,cb,msg,kb(rows));
}
async function showCategory(env,id,uid,cb,kind){
 await setPrefs(env,uid,{category:kind});
 const label=CATEGORY.find(x=>x[0]===kind)?.[1]||"Catalogue";
 const rows=genTag(kind).map(([genre,name])=>[bx("🎞 "+name,"list:"+kind+":"+genre+":0",null,genre==="general"?"success":"primary")]);
 rows.push(navHome());
 await show(env,id,cb,regularHeader(esc(label.toUpperCase()),"<i>Choisis ton style de contenu :</i>","Les résultats sont classés et actualisés régulièrement."),kb(rows));
}
async function listRows(env,kind,genre,language,search,sort="recent"){
 const all=(await env.DB.prepare("SELECT c.id,c.title,c.link,c.description,c.content_type,c.genre,c.language,c.updated_at,c.last_post_at,c.banner_url,COALESCE(t.opens,0) opens,COALESCE(t.shares,0) shares,t.check_status,COALESCE((SELECT COUNT(*) FROM favorites f WHERE f.channel_id=c.id),0) favorites_count FROM channels c LEFT JOIN channel_telemetry t ON t.channel_id=c.id WHERE c.status='approved' AND c.rights_confirmed=1 ORDER BY c.updated_at DESC LIMIT 1500").all()).results||[];
 let filtered=all.filter(c=>BOT_LINK_RE.test(c.link));
 if(kind)filtered=filtered.filter(c=>c.content_type===kind);
 if(genre&&genre!=="general")filtered=filtered.filter(c=>c.genre===genre);
 if(language&&language!=="tous")filtered=filtered.filter(c=>c.language===language);
 if(search){
  filtered=filtered.map(c=>({...c,_search_rank:searchRank(c,search)}))
    .filter(c=>c._search_rank>0)
    .sort((a,b)=>b._search_rank-a._search_rank||qualityScore(b)-qualityScore(a));
 } else if(sort==="popular"||sort==="quality"){
  filtered.sort((a,b)=>qualityScore(b)-qualityScore(a)||Number(b.favorites_count)-Number(a.favorites_count));
 } else if(sort==="active"){
  filtered.sort((a,b)=>String(b.last_post_at||"").localeCompare(String(a.last_post_at||""))||qualityScore(b)-qualityScore(a));
 } else{
  filtered.sort((a,b)=>String(b.updated_at).localeCompare(String(a.updated_at)));
 }
 return filtered;
}

function editDistanceAtMostOne(a,b){if(a===b)return true;let i=0,j=0,edits=0;while(i<a.length&&j<b.length){if(a[i]===b[j]){i++;j++;continue;}if(++edits>1)return false;if(a.length>b.length)i++;else if(b.length>a.length)j++;else{i++;j++;}}return edits+Number(i<a.length||j<b.length)<=1;}
async function card(env,id,uid,cb,channelId,origin="latest"){
 const c=await env.DB.prepare("SELECT c.*,t.check_status,COALESCE(t.opens,0) opens FROM channels c LEFT JOIN channel_telemetry t ON c.id=t.channel_id WHERE c.id=? AND c.status='approved' AND c.rights_confirmed=1").bind(channelId).first();
 if(!c||!BOT_LINK_RE.test(c.link)){await show(env,id,cb,regularHeader("CANAL INTROUVABLE","<i>Ce lien n'est plus référencé.</i>"),kb([navHome()]));return;}
 const favorite=Boolean(await env.DB.prepare("SELECT 1 FROM favorites WHERE user_id=? AND channel_id=?").bind(uid,c.id).first());
 const kind=CATEGORY.find(x=>x[0]===c.content_type)?.[1]||"Cinéma";
 const body="📂 <b>"+esc(kind)+"</b> • "+esc(c.genre)+"\n🌐 <b>Langue :</b> "+esc(c.language||"VF")+
  "\n\n<blockquote>"+esc((c.description||"Canal référencé et vérifié.").slice(0,370))+"</blockquote>\n\n✅ <i>Canal autorisé</i>";
 const buttons=[
  [bx("🔗 Ouvrir le canal",null,BASE+"/go/"+c.id,"success")],
  [bx(favorite?"💔 Retirer des favoris":"⭐ Ajouter aux favoris","fav:"+c.id+":"+origin,null,"primary"),bx("📤 Partager","share:"+c.id)],
  [bx("🚩 Signaler","report:"+c.id,null,"danger"),bx("⬅️ Liste","return:"+origin)],
  navHome()
 ];
 await show(env,id,cb,"🎞️ <b>"+esc(c.title)+"</b>\n\n"+body,kb(buttons));
}
async function listPage(env,id,uid,cb,kind,genre,page,mode="recent",search=""){
 const p=await prefs(env,uid);
 let rows=await listRows(env,kind,genre,p.language,search,mode);
 if(mode==="recommend"){
  const fav=(await env.DB.prepare("SELECT c.id,c.genre FROM favorites f JOIN channels c ON c.id=f.channel_id WHERE f.user_id=? AND c.status='approved' AND c.rights_confirmed=1 LIMIT 60").bind(uid).all()).results||[];
  rows=recommendations(rows,fav,p,1500);
 }
 const total=rows.length,number=Math.min(Math.max(0,Number(page)||0),Math.max(0,Math.ceil(total/5)-1)),slice=rows.slice(number*5,number*5+5);
 if(!total){await show(env,id,cb,regularHeader("AUCUN RÉSULTAT","<i>Aucun canal approuvé ne correspond encore à ce choix.</i>","Essaie un autre genre ou une autre langue."),kb([[bx("🔎 Rechercher","search",null,"primary")],navHome()]));return;}
 const title=mode==="latest"?"🆕 <b>NOUVEAUX CANAUX</b>":mode==="recommend"?"✨ <b>POUR TOI</b>":mode==="popular"?"🏆 <b>CANAUX POPULAIRES</b>":"🎬 <b>CANAUX À DÉCOUVRIR</b>";
 const summary=title+"\n<i>"+total+" résultat(s) • Page "+(number+1)+"/"+Math.ceil(total/5)+" • Langue : "+esc(p.language)+"</i>\n\n"+slice.map((x,i)=>(number*5+i+1)+". <b>"+esc(x.title)+"</b>\n    <i>"+esc(x.genre)+" · "+esc(x.language||"VF")+"</i>").join("\n\n");
 const key=mode==="latest"?"latest":mode==="recommend"?"recommend":"list:"+kind+":"+genre;
 const buttons=slice.map(x=>[bx("🎞 "+clean(x.title).slice(0,32),"card:"+x.id+":"+key,"","primary")]);
 const paging=[];
 if(number>0)paging.push(bx("◀️ Précédent","p:"+mode+":"+(kind||"all")+":"+(genre||"general")+":"+(number-1)));
 if(number<Math.ceil(total/5)-1)paging.push(bx("Suivant ▶️","p:"+mode+":"+(kind||"all")+":"+(genre||"general")+":"+(number+1)));
 if(paging.length)buttons.push(paging);
 buttons.push([bx("🌐 Langue : "+p.language,"preferences"),bx("⬅️ Accueil","home")]);
 await show(env,id,cb,summary,kb(buttons));
}
async function favorites(env,id,uid,cb){
 const rows=(await env.DB.prepare("SELECT c.id,c.title,c.genre FROM favorites f JOIN channels c ON c.id=f.channel_id WHERE f.user_id=? AND c.status='approved' AND c.rights_confirmed=1 ORDER BY f.created_at DESC LIMIT 30").bind(uid).all()).results||[];
 if(!rows.length){await show(env,id,cb,regularHeader("MES FAVORIS ⭐","<i>Tu n'as pas encore enregistré de chaîne.</i>","Appuie sur ⭐ dans une fiche pour la retrouver ici."),kb([navHome()]));return;}
 await show(env,id,cb,"⭐ <b>MES FAVORIS</b>\n<i>"+rows.length+" chaîne(s) sauvegardée(s).</i>",kb([...rows.map(r=>[bx("🎬 "+clean(r.title).slice(0,35),"card:"+r.id+":favorites","", "primary")]),navHome()]));
}
async function toggleFavorite(env,id,uid,cb,channelId,origin){
 const valid=await env.DB.prepare("SELECT id FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(channelId).first();
 if(!valid)return;
 const prev=await env.DB.prepare("SELECT 1 FROM favorites WHERE user_id=? AND channel_id=?").bind(uid,channelId).first();
 if(prev)await env.DB.prepare("DELETE FROM favorites WHERE user_id=? AND channel_id=?").bind(uid,channelId).run();
 else await env.DB.prepare("INSERT OR IGNORE INTO favorites(user_id,channel_id) VALUES(?,?)").bind(uid,channelId).run();
 await card(env,id,uid,cb,channelId,origin);
}
async function preferencePanel(env,id,uid,cb){
 const p=await prefs(env,uid);
 const rows=[[bx("🎬 Films","prefcat:films",null,p.category==="films"?"success":undefined),bx("📺 Séries","prefcat:series",null,p.category==="series"?"success":undefined),bx("🎌 Animés","prefcat:animes",null,p.category==="animes"?"success":undefined)]];
 rows.push(...LANG.map(([code,label])=>[bx((p.language===code?"✅ ":"")+label,"lang:"+code,null,p.language===code?"success":undefined)]));
 rows.push([bx(p.notification_enabled?"🔕 Couper les alertes":"🔔 Activer les alertes","notify",null,p.notification_enabled?"danger":"success")]);
 rows.push(navHome());
 await show(env,id,cb,regularHeader("MES PRÉFÉRENCES 🎛","<b>Catégorie :</b> "+esc(p.category)+"\n<b>Langue :</b> "+esc(p.language)+"\n<b>Alertes :</b> "+(p.notification_enabled?"activées":"désactivées"),"Aucune notification n'est envoyée sans ton accord."),kb(rows));
}
async function referralCode(env,uid){
 const existing=await env.DB.prepare("SELECT code FROM referral_codes WHERE user_id=?").bind(uid).first();
 if(existing?.code)return existing.code;
 const code=crypto.randomUUID().replace(/-/g,"").slice(0,16);
 await env.DB.prepare("INSERT OR IGNORE INTO referral_codes(user_id,code) VALUES(?,?)").bind(uid,code).run();
 const row=await env.DB.prepare("SELECT code FROM referral_codes WHERE user_id=?").bind(uid).first();
 if(!row)throw Error("Referral code unavailable");
 return row.code;
}
async function referralLink(env,uid){
 const code=await referralCode(env,uid);const info=await telegram(env,"getMe",{});
 if(!info.ok||!info.result?.username)throw Error("Bot username unavailable");
 return "https://t.me/"+info.result.username+"?start=ref_"+code;
}
async function shareReferral(env,id,uid){
 const link=await referralLink(env,uid);
 await send(env,id,"🎬 <b>LE CINÉMA À PORTÉE DE CLIC !</b>\n\n🍿 <b>Films • Séries • Animés</b>\n\n<blockquote>✨ Découvre des canaux de cinéma classés par genre pour trouver plus facilement ce que tu aimes regarder.</blockquote>\n\n<i>Action, comédie, romance, animés…</i>\n\n🎁 <b>Découvre Ciné Radar avec mon invitation :</b>\n<code>"+esc(link)+"</code>");
 const share="https://t.me/share/url?url="+encodeURIComponent(link)+"&text="+encodeURIComponent("🍿 Découvre Ciné Radar ! Films, séries et animés.");
 await send(env,id,"🎁 <b>TON INVITATION EST PRÊTE</b>\n\n<i>Le message précédent est prêt à être transféré tel quel.</i>\n\n<blockquote>👆 Appuie longuement sur le message précédent et sélectionne <b>Transférer</b> pour conserver le gras, l'italique et la citation.</blockquote>\n\n✅ Ces instructions sont séparées et ne seront pas intégrées au message transféré.",kb([[bx("📤 Partager un lien simplifié",null,share,"success")],[bx("📊 Mes filleuls","refstats"),bx("⌂ Accueil","home")]]));
}
async function trackInvite(env,uid,argument){
 const match=START_REF_RE.exec(argument||"");if(!match)return;
 const row=await env.DB.prepare("SELECT user_id FROM referral_codes WHERE code=?").bind(match[1]).first();
 if(!row||Number(row.user_id)===Number(uid))return;
 await env.DB.prepare("INSERT OR IGNORE INTO referral_visits(invited_id,referrer_id) VALUES(?,?)").bind(uid,row.user_id).run();
}
async function referralStats(env,id,uid,cb){
 const s=await env.DB.prepare("SELECT COUNT(*) total, COUNT(confirmed_at) confirmed FROM referral_visits WHERE referrer_id=?").bind(uid).first();
 const total=Number(s?.total||0),confirmed=Number(s?.confirmed||0),ratio=total?Math.round(confirmed/total*100):0;
 let badge=confirmed>=50?"🏆 Super Ambassadeur":confirmed>=10?"🥈 Ambassadeur":confirmed>=1?"🥉 Explorateur":"🌱 Débutant";
 await show(env,id,cb,regularHeader("MON PARRAINAGE 🎁", "👥 <b>"+total+"</b> invitation(s) ouverte(s)\n✅ <b>"+confirmed+"</b> inscription(s) confirmée(s)\n📈 <b>"+ratio+" %</b> de conversion\n🏅 <b>"+badge+"</b>","Les comptes invités ne sont comptés qu'une fois. Aucun gain financier n'est promis."),kb([[bx("🎁 Envoyer mon invitation","referral",null,"success")],navHome()]));
}
async function shareChannel(env,id,uid,cb,channelId){
 const c=await env.DB.prepare("SELECT id,title,genre FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(channelId).first();
 if(!c)return;
 const info=await telegram(env,"getMe",{});
 const username=info.result?.username;
 if(!username)return;
 const ref=await referralCode(env,uid);
 const target="https://t.me/"+username+"?start=ch_"+channelId+"_ref_"+ref;
 const share="https://t.me/share/url?url="+encodeURIComponent(target)+"&text="+encodeURIComponent("🎬 "+c.title+" • Découvre cette chaîne sur Ciné Radar");
 await env.DB.prepare("INSERT INTO channel_telemetry(channel_id,shares) VALUES(?,1) ON CONFLICT(channel_id) DO UPDATE SET shares=channel_telemetry.shares+1").bind(channelId).run();
 await show(env,id,cb,regularHeader("PARTAGER CE CANAL","<b>"+esc(c.title)+"</b>\n\n<code>"+esc(target)+"</code>","Ce lien ramène ton ami vers le bot Ciné Radar, puis vers la fiche du canal."),kb([[bx("📤 Envoyer à un ami",null,share,"success")],[bx("🎬 Voir le canal","card:"+channelId+":latest")],navHome()]));
}
async function reportPanel(env,id,uid,cb,channelId){
 const c=await env.DB.prepare("SELECT title FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(channelId).first();
 if(!c)return;
 const types=[["broken","🔗 Lien inaccessible"],["category","📁 Mauvaise catégorie"],["content","⚠️ Contenu problématique"],["rights","©️ Droits de diffusion"]];
 await show(env,id,cb,regularHeader("SIGNALER UN CANAL 🚩","<b>"+esc(c.title)+"</b>\n\n<i>Quel problème rencontres-tu ?</i>"),kb([...types.map(([code,label])=>[bx(label,"flag:"+channelId+":"+code,null,"danger")]),navHome()]));
}
async function reportSubmit(env,id,uid,cb,cid,reason){
 if(!["broken","category","content","rights"].includes(reason))return;
 const exists=await env.DB.prepare("SELECT 1 FROM channels WHERE id=? AND status='approved'").bind(cid).first();if(!exists)return;
 await env.DB.prepare("INSERT OR IGNORE INTO channel_reports(channel_id,user_id,reason) VALUES(?,?,?)").bind(cid,uid,reason).run();
 await show(env,id,cb,regularHeader("SIGNALEMENT REÇU ✅","<i>Merci, ton signalement a été transmis pour vérification.</i>","Un administrateur examinera la fiche. Les signalements répétés ne créent pas de doublons."),kb([navHome()]));
}
async function promptSearch(env,id,uid,cb){
 await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'search') ON CONFLICT(user_id) DO UPDATE SET mode='search'").bind(uid).run();
 await show(env,id,cb,regularHeader("RECHERCHE INTELLIGENTE 🔎","<i>Écris un titre, un genre, une langue ou quelques mots.</i>","La recherche tolère les accents et certaines fautes de frappe."),kb([navHome()]));
}
async function submitSearch(env,id,uid,text){
 await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(uid).run();
 const p=await prefs(env,uid);
 const candidates=await listRows(env,null,null,p.language,text,"recent");
 if(!candidates.length){await send(env,id,regularHeader("AUCUN RÉSULTAT","<i>Aucun canal autorisé ne correspond à ta recherche :</i> <b>"+esc(text.slice(0,65))+"</b>","Essaie avec moins de mots ou change ta langue préférée."),kb([navHome()]));return;}
 await send(env,id,"🔎 <b>RÉSULTATS POUR « "+esc(text.slice(0,50))+" »</b>\n<i>"+candidates.length+" correspondance(s)</i>",kb([...candidates.slice(0,12).map(c=>[bx("🎞 "+clean(c.title).slice(0,35),"card:"+c.id+":latest",null,"primary")]),navHome()]));
}
async function suggest(env,id,uid,cb){
 await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,'suggest') ON CONFLICT(user_id) DO UPDATE SET mode='suggest'").bind(uid).run();
 await show(env,id,cb,regularHeader("PROPOSER UNE CHAÎNE 📨","<i>Envoie son lien public au format :</i>\n<code>https://t.me/nomducanal</code>","Une validation technique et une autorisation de diffusion sont nécessaires avant publication."),kb([navHome()]));
}
async function submitSuggestion(env,id,uid,text){
 await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(uid).run();
 if(!BOT_LINK_RE.test(text)){await send(env,id,"⚠️ <b>LIEN INVALIDE</b>\nUtilise <code>https://t.me/nomducanal</code>");return;}
 await env.DB.prepare("INSERT INTO suggestions(user_id,link,status) VALUES(?,?,'pending')").bind(uid,text).run();
 await send(env,id,regularHeader("MERCI POUR TA PROPOSITION ✅","<i>Le canal sera évalué par la modération avant son référencement.</i>"),kb([navHome()]));
}
async function adminHome(env,id,uid,cb){
 const stats=await env.DB.prepare("SELECT (SELECT COUNT(*) FROM discovery_candidates WHERE rights_status='unverified' AND technical_status='qualified') waiting,(SELECT COUNT(*) FROM channel_reports WHERE status='open') reports,(SELECT COUNT(*) FROM channels WHERE status='approved' AND rights_confirmed=1) live").first();
 const msg=regularHeader("ADMINISTRATION 🛡","⏳ <b>"+stats.waiting+"</b> candidature(s)\n🚩 <b>"+stats.reports+"</b> signalement(s)\n✅ <b>"+stats.live+"</b> canal(aux) publiés","Les droits doivent être documentés avant d'approuver un canal.");
 await show(env,id,cb,msg,kb([[bx("📥 En attente","admqueue:0",null,"primary"),bx("🚩 Signalements","admreports:0",null,"danger")],[bx("📊 Statistiques","admstats")],navHome()]));
}
async function adminQueue(env,id,uid,cb,page){
 const p=Math.max(0,Math.min(30,Number(page)||0));
 const rows=(await env.DB.prepare("SELECT username,title,matching_pairs,source_category FROM discovery_candidates WHERE technical_status='qualified' AND rights_status='unverified' ORDER BY last_seen DESC LIMIT 5 OFFSET ?").bind(p*5).all()).results||[];
 if(!rows.length){await show(env,id,cb,"🛡 <b>AUCUNE CANDIDATURE EN ATTENTE</b>",kb([[bx("⬅️ Administration","admin")]]));return;}
 const buttons=rows.map(x=>[bx("🔍 "+clean(x.title).slice(0,30),"admreview:"+x.username,"","primary")]);
 const controls=[];if(p>0)controls.push(bx("◀️","admqueue:"+(p-1)));
 if(rows.length===5)controls.push(bx("▶️","admqueue:"+(p+1)));
 if(controls.length)buttons.push(controls);
 buttons.push([bx("⬅️ Administration","admin")]);
 await show(env,id,cb,"🛡 <b>CANDIDATURES — PAGE "+(p+1)+"</b>\n<i>Consulte les informations et établis les droits avant publication.</i>",kb(buttons));
}
async function adminReview(env,id,uid,cb,username){
 if(!/^[a-zA-Z][a-zA-Z0-9_]{4,31}$/.test(username))return;
 const row=await env.DB.prepare("SELECT * FROM discovery_candidates WHERE username=?").bind(username).first();if(!row)return;
 const content="🎬 <b>"+esc(row.title)+"</b>\n\n🔗 <code>"+esc(row.link)+"</code>\n📁 "+esc(row.content_type)+" / "+esc(row.genre)+"\n🎞 "+Number(row.matching_pairs||0)+" paires vidéo\n🔒 <i>Droits : "+esc(row.rights_status)+"</i>\n\n<blockquote>Une vidéo présente sur Telegram ne constitue pas une autorisation de diffusion.</blockquote>";
 await show(env,id,cb,content,kb([[bx("📋 J'ai une preuve d'autorisation","admrequest:"+username,null,"success")],[bx("⛔ Rejeter","admreject:"+username,null,"danger")],[bx("◀️ En attente","admqueue:0")]]));
}
async function adminStartApproval(env,id,uid,cb,username){
 await env.DB.prepare("INSERT INTO user_states(user_id,mode) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode").bind(uid,"approve:"+username).run();
 await show(env,id,cb,regularHeader("JUSTIFICATIF DES DROITS","<i>Décris précisément l'autorisation obtenue : titulaire des droits, date, portée de la diffusion et référence documentaire.</i>","Une simple déclaration « canal public » ne constitue pas une preuve."),kb([[bx("Annuler","admqueue:0",null,"danger")]]));
}
async function adminApprove(env,id,uid,username,evidence){
 const row=await env.DB.prepare("SELECT * FROM discovery_candidates WHERE username=? AND technical_status='qualified'").bind(username).first();
 if(!row)return;
 const normalized=evidence.trim().slice(0,500);
 if(normalized.length<35){await send(env,id,"⚠️ <b>Justificatif trop court.</b> Précise le titulaire, la date et la portée de l'autorisation.");return;}
 await env.DB.batch([
   env.DB.prepare("INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed,rights_evidence,verified_at,language) VALUES(?,?,?, ?,?,'approved',1,?,CURRENT_TIMESTAMP,'VF') ON CONFLICT(link) DO UPDATE SET title=excluded.title,status='approved',rights_confirmed=1,rights_evidence=excluded.rights_evidence,verified_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP").bind(row.title,row.link,"Canal approuvé après contrôle des droits",row.content_type,row.genre,normalized),
   env.DB.prepare("UPDATE discovery_candidates SET rights_status='approved',updated_at=CURRENT_TIMESTAMP WHERE username=?").bind(username),
   env.DB.prepare("INSERT INTO channel_moderation_log(channel_id,admin_id,action,evidence) SELECT id,?,'approve',? FROM channels WHERE link=?").bind(uid,normalized,row.link)
 ]);
 await env.DB.prepare("DELETE FROM user_states WHERE user_id=?").bind(uid).run();
 await send(env,id,regularHeader("CANAL APPROUVÉ ✅","<b>"+esc(row.title)+"</b>\n<i>Le canal est maintenant présent dans le catalogue.</i>"),kb([[bx("◀️ Administration","admin",null,"primary")]]));
}
async function adminReject(env,id,uid,cb,username){
 const row=await env.DB.prepare("SELECT username FROM discovery_candidates WHERE username=?").bind(username).first();if(!row)return;
 await env.DB.prepare("UPDATE discovery_candidates SET rights_status='rejected',updated_at=CURRENT_TIMESTAMP WHERE username=?").bind(username).run();
 await show(env,id,cb,"⛔ <b>Canal rejeté et retiré de la file de validation.</b>",kb([[bx("◀️ En attente","admqueue:0")]]));
}
async function adminReports(env,id,uid,cb,page){
 const p=Math.min(30,Math.max(0,Number(page)||0));
 const rows=(await env.DB.prepare("SELECT r.id,r.reason,c.title FROM channel_reports r JOIN channels c ON c.id=r.channel_id WHERE r.status='open' ORDER BY r.created_at DESC LIMIT 5 OFFSET ?").bind(p*5).all()).results||[];
 const buttons=rows.map(x=>[bx("✅ Clore #"+x.id+" · "+clean(x.title).slice(0,20),"admclose:"+x.id,null,"success")]);
 if(rows.length===5)buttons.push([bx("Suivant ▶️","admreports:"+(p+1))]);
 buttons.push([bx("⬅️ Administration","admin")]);
 await show(env,id,cb,"🚩 <b>SIGNALEMENTS</b>\n"+(rows.map(x=>"#"+x.id+" · "+esc(x.title)+" · <i>"+esc(x.reason)+"</i>").join("\n")||"Aucun signalement ouvert."),kb(buttons));
}
export async function botUpdate(env,update){
 const msg=update.message||update.callback_query?.message,cb=update.callback_query;
 const chat=msg?.chat?.id,uid=cb?.from?.id||msg?.from?.id;
 if(!chat||!uid)return;
 await responseCb(env,cb?.id);
 const action=cb?.data||"",raw=msg?.text?.trim()||"",parts=action.split(":");
 if(raw==="/monid"){await send(env,chat,"🆔 <b>Ton identifiant Telegram</b>\n<code>"+uid+"</code>");return;}
 const start=/^\/start(?:@[a-zA-Z0-9_]+)?(?:\s+([a-zA-Z0-9_-]+))?$/i.exec(raw);
 if(start){
  const arg=start[1]||"";
  if(arg.startsWith("ref_"))await trackInvite(env,uid,arg);
  else if(/^ch_[0-9]+_ref_[a-f0-9]{16}$/.test(arg))await trackInvite(env,uid,arg.split("_").slice(2).join("_"));
  if(!(await access(env,uid,chat,cb)))return;
  if(arg.startsWith("ch_")){const channelId=Number(arg.split("_")[1]);if(Number.isSafeInteger(channelId))return card(env,chat,uid,cb,channelId);}
  return startMessage(env,chat,uid,cb);
 }
 if(action==="home"||action==="verify"||raw==="/menu"){
  if(await access(env,uid,chat,cb))await startMessage(env,chat,uid,cb);return;
 }
 if(raw==="/admin"||action==="admin"||action.startsWith("adm")){
  if(!(await isAdmin(env,uid))){await send(env,chat,"⛔ <b>Administration réservée.</b>");return;}
  if(raw==="/admin"||action==="admin")return adminHome(env,chat,uid,cb);
  if(parts[0]==="admqueue")return adminQueue(env,chat,uid,cb,parts[1]);
  if(parts[0]==="admreview")return adminReview(env,chat,uid,cb,parts[1]);
  if(parts[0]==="admrequest")return adminStartApproval(env,chat,uid,cb,parts[1]);
  if(parts[0]==="admreject")return adminReject(env,chat,uid,cb,parts[1]);
  if(parts[0]==="admreports")return adminReports(env,chat,uid,cb,parts[1]);
  if(parts[0]==="admclose"){
   await env.DB.prepare("UPDATE channel_reports SET status='closed' WHERE id=?").bind(Number(parts[1])).run();
   return adminReports(env,chat,uid,cb,0);
  }
  if(parts[0]==="admstats")return adminHome(env,chat,uid,cb);
 }
 if(!(await access(env,uid,chat,cb)))return;
 if(action==="referral"||raw==="/parrainage"||raw==="/inviter")return shareReferral(env,chat,uid);
 if(action==="refstats"||raw==="/mesparrainages")return referralStats(env,chat,uid,cb);
 if(action==="preferences")return preferencePanel(env,chat,uid,cb);
 if(parts[0]==="prefcat"&&CATEGORY.some(x=>x[0]===parts[1])){
  await setPrefs(env,uid,{category:parts[1]});return preferencePanel(env,chat,uid,cb);
 }
 if(action==="notify"){
  const p=await prefs(env,uid);await setPrefs(env,uid,{notification_enabled:p.notification_enabled?0:1});
  return preferencePanel(env,chat,uid,cb);
 }
 if(parts[0]==="lang"&&LANG.some(x=>x[0]===parts[1])){
  await setPrefs(env,uid,{language:parts[1]});return preferencePanel(env,chat,uid,cb);
 }
 if(action==="owned"){
  const channels=await ownChannels(env);
  return show(env,chat,cb,"📣 <b>CANAUX OFFICIELS</b>\n<i>Découvre les communautés Ciné Radar.</i>",kb([...channels.filter(x=>BOT_LINK_RE.test(x.link)).map(x=>[bx("📣 "+clean(x.title),null,x.link,"primary")]),navHome()]));
 }
 if(action==="miniapp"){
  // web_app buttons only work in private conversations and supported clients.
  return show(env,chat,cb,regularHeader("CINÉ RADAR MINI APP","<i>Explore le catalogue dans une interface visuelle avec filtres et favoris.</i>"),kb([[{text:"🖥 Ouvrir le catalogue",web_app:{url:BASE+"/app"},style:"success"}],navHome()]));
 }
 if(parts[0]==="type"&&GENRES[parts[1]])return showCategory(env,chat,uid,cb,parts[1]);
 if(parts[0]==="list"&&parts.length===4&&GENRES[parts[1]]&&GENRES[parts[1]].some(x=>x[0]===parts[2]))
  return listPage(env,chat,uid,cb,parts[1],parts[2],parts[3]);
 if(parts[0]==="p"&&parts.length===5){
  const mode=parts[1],kind=parts[2]==="all"?null:parts[2],genre=parts[3];
  if(!["recent","latest","recommend","popular"].includes(mode)||kind&&!GENRES[kind])return;
  return listPage(env,chat,uid,cb,kind,genre,parts[4],mode);
 }
 if(action==="latest")return listPage(env,chat,uid,cb,null,null,0,"latest");
 if(parts[0]==="guide"&&["0","1","2"].includes(parts[1])){
  const stage=Number(parts[1]);
  const lessons=[
   ["1/3 — DÉCOUVRIR","🎬 Choisis <b>Films</b>, <b>Séries</b> ou <b>Animés</b>, puis un genre.\n<i>La Mini App présente les résultats avec de jolies fiches.</i>"],
   ["2/3 — PERSONNALISER","⭐ Ajoute tes canaux préférés aux <b>Favoris</b>.\n🎛 Sélectionne tes langues et tes thèmes dans <b>Préférences</b>."],
   ["3/3 — PARTICIPER","🔎 Recherche avec des mots simples, même si tu fais une faute.\n🎁 Invite un ami avec ton lien personnel.\n🚩 Signale les liens qui ne fonctionnent plus."]
  ];
  const b=stage<2?[[bx("Suivant ▶️","guide:"+(stage+1),null,"success")]]:[];
  b.push([bx("Terminer ✅","home",null,"primary")]);
  return show(env,chat,cb,regularHeader("GUIDE CINÉ RADAR · "+lessons[stage][0],lessons[stage][1]),kb(b));
 }
 if(action==="popular")return listPage(env,chat,uid,cb,null,null,0,"popular");
 if(action==="recommend"){const p=await prefs(env,uid);return listPage(env,chat,uid,cb,p.category,"general",0,"recommend");}
 if(action==="favorites"||raw==="/favoris")return favorites(env,chat,uid,cb);
 if(parts[0]==="card"&&/^\d+$/.test(parts[1]||""))return card(env,chat,uid,cb,Number(parts[1]),parts.slice(2).join(":")||"latest");
 if(parts[0]==="fav"&&/^\d+$/.test(parts[1]||""))return toggleFavorite(env,chat,uid,cb,Number(parts[1]),parts.slice(2).join(":")||"latest");
 if(parts[0]==="share"&&/^\d+$/.test(parts[1]||""))return shareChannel(env,chat,uid,cb,Number(parts[1]));
 if(parts[0]==="report"&&/^\d+$/.test(parts[1]||""))return reportPanel(env,chat,uid,cb,Number(parts[1]));
 if(parts[0]==="flag"&&/^\d+$/.test(parts[1]||""))return reportSubmit(env,chat,uid,cb,Number(parts[1]),parts[2]);
 if(action==="return:favorites")return favorites(env,chat,uid,cb);
 if(action==="return:latest")return listPage(env,chat,uid,cb,null,null,0,"latest");
 if(parts[0]==="return"&&parts[1]==="list"&&GENRES[parts[2]])return listPage(env,chat,uid,cb,parts[2],parts[3]||"general",0);
 if(action==="search"||raw==="/recherche")return promptSearch(env,chat,uid,cb);
 if(action==="suggest"||raw==="/proposer")return suggest(env,chat,uid,cb);
 if(action==="help"||raw==="/aide"){
  return show(env,chat,cb,regularHeader("MODE D'EMPLOI 💡",
   "<b>/menu</b> — Accueil\n<b>/recherche</b> — Rechercher\n<b>/favoris</b> — Favoris\n<b>/parrainage</b> — Invitation\n<b>/mesparrainages</b> — Statistiques\n<b>/proposer</b> — Proposer un canal\n<b>/monid</b> — Ton identifiant","Utilise les boutons pour naviguer sans encombrer la discussion."),kb([navHome()]));
 }
 if(!raw)return;
 const state=await env.DB.prepare("SELECT mode FROM user_states WHERE user_id=?").bind(uid).first();
 if(state?.mode?.startsWith("approve:")&&await isAdmin(env,uid))return adminApprove(env,chat,uid,state.mode.slice(8),raw);
 if(state?.mode==="search")return submitSearch(env,chat,uid,raw.slice(0,100));
 if(state?.mode==="suggest")return submitSuggestion(env,chat,uid,raw);
 await send(env,chat,"🍿 <i>Choisis une option dans le menu :</i>",kb([navHome()]));
}
export async function initializeProfile(env){
 if(!env.TELEGRAM_TOKEN)return;
 const old=await env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='profile_version'").first();
 if(old?.value==="3")return;
 const tasks=[
  ["setMyName",{name:"Ciné Radar"}],
  ["setMyDescription",{description:"🎬 Ciné Radar — explore des canaux de films, séries et animés, classés par genre. Favoris, découverte et recommandations. 🍿"}],
  ["setMyShortDescription",{short_description:"🎬 Ton radar cinéma : films, séries, animés et favoris. 🍿"}],
  ["setMyCommands",{commands:[{command:"start",description:"🍿 Découvrir Ciné Radar"},{command:"menu",description:"🎬 Accueil"},{command:"recherche",description:"🔎 Rechercher"},{command:"favoris",description:"⭐ Mes favoris"},{command:"parrainage",description:"🎁 Inviter des amis"},{command:"mesparrainages",description:"📊 Mes filleuls"},{command:"proposer",description:"📨 Proposer un canal"},{command:"aide",description:"💡 Aide"}]}],
  ["setChatMenuButton",{menu_button:{type:"web_app",text:"🎬 Ciné Radar",web_app:{url:BASE+"/app"}}}]
 ];
 let failures=[];
 for(const [method,data] of tasks){try{const r=await telegram(env,method,data);if(!r.ok)failures.push(method+":"+(r.description||r.error_code));}catch(e){failures.push(method+":"+String(e));}}
 if(failures.length){console.error(JSON.stringify({event:"profile_setup_errors",failures}));return;}
 try{
   const avatar=await fetch(BASE+"/assets/avatar.jpg");
   if(!avatar.ok)throw Error("Branded avatar unavailable (HTTP "+avatar.status+")");
   const bytes=await avatar.arrayBuffer();
   if(bytes.byteLength<10000||bytes.byteLength>3000000)throw Error("Avatar JPEG invalid size");
   const form=new FormData();
   form.append("photo",JSON.stringify({type:"static",photo:"attach://avatar"}));
   form.append("avatar",new Blob([bytes],{type:"image/jpeg"}),"cine-radar-avatar.jpg");
   const response=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/setMyProfilePhoto",{method:"POST",body:form});
   const result=await response.json();
   if(!result.ok)throw Error("Telegram refused avatar: "+String(result.description||result.error_code).slice(0,100));
   console.log(JSON.stringify({event:"cine_radar_profile_photo_updated"}));
 }catch(e){
   console.error(JSON.stringify({event:"profile_photo_pending",error:String(e).slice(0,135)}));
   await env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('profile_photo_status',?) ON CONFLICT(setting_key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP").bind(("pending: "+String(e)).slice(0,170)).run();
   return; // Do not mark profile as completed. Next cron retries.
 }
 await env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('profile_version','3') ON CONFLICT(setting_key) DO UPDATE SET value='3',updated_at=CURRENT_TIMESTAMP").run();
 await env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('profile_photo_status','complete') ON CONFLICT(setting_key) DO UPDATE SET value='complete',updated_at=CURRENT_TIMESTAMP").run();
}
export async function maintenance(env,mode){
 if(mode==="activity"){
  const candidates=(await env.DB.prepare("SELECT c.id,c.link FROM channels c WHERE c.status='approved' AND c.rights_confirmed=1 AND (NOT EXISTS(SELECT 1 FROM channel_telemetry t WHERE t.channel_id=c.id) OR c.id IN (SELECT channel_id FROM channel_telemetry WHERE last_checked_at IS NULL OR last_checked_at < datetime('now','-24 hours'))) ORDER BY c.updated_at DESC LIMIT 12").all()).results||[];
  for(const c of candidates) {
   let status="unverifiable",lastPost=null;
   try{
    const name=new URL(c.link).pathname.replace(/^\//,"").replace(/\/$/,"");
    if(!/^[a-zA-Z][a-zA-Z0-9_]{4,31}$/.test(name))continue;
    const r=await fetch("https://t.me/s/"+name,{method:"GET",redirect:"follow",signal:AbortSignal.timeout(8000)});
    if(r.status===404)status="not_found";
    else if(r.status===200) {
      const body=await r.text();
      const parsed=extractTelegramActivity(body);
      status=parsed.status;
      lastPost=parsed.lastPost;
    }
   }catch(e){console.warn(JSON.stringify({event:"channel_activity_unverified",channel:c.id,reason:String(e).slice(0,70)}));}
   await env.DB.prepare("INSERT INTO channel_telemetry(channel_id,check_status,last_checked_at,last_good_at) VALUES(?,?,CURRENT_TIMESTAMP,CASE WHEN ?='reachable' THEN CURRENT_TIMESTAMP END) ON CONFLICT(channel_id) DO UPDATE SET check_status=excluded.check_status,last_checked_at=CURRENT_TIMESTAMP,last_good_at=CASE WHEN excluded.check_status='reachable' THEN CURRENT_TIMESTAMP ELSE channel_telemetry.last_good_at END").bind(c.id,status,status).run();
   if(lastPost)await env.DB.prepare("UPDATE channels SET last_post_at=? WHERE id=?").bind(lastPost,c.id).run();
   // Explicit admin review, not automatic suspension, to avoid false 404/Telegram bot-blocks.
  }

 }else if(mode==="notifications"){
  const channels=(await env.DB.prepare("SELECT id,title,content_type,genre,language FROM channels WHERE status='approved' AND rights_confirmed=1 AND verified_at>=datetime('now','-2 days') ORDER BY verified_at DESC LIMIT 8").all()).results||[];
  const users=(await env.DB.prepare("SELECT user_id,category,language,notification_enabled FROM preferences WHERE notification_enabled=1 ORDER BY updated_at LIMIT 200").all()).results||[];
  const totalCap=80;let delivered=0;
  for(const ch of channels)for(const u of users){
   if(delivered>=totalCap)break;
   try{
    const favoriteGenres=(await env.DB.prepare("SELECT DISTINCT c.genre FROM favorites f JOIN channels c ON c.id=f.channel_id WHERE f.user_id=? LIMIT 10").bind(u.user_id).all()).results?.map(x=>x.genre)||[];
    if(!notificationEligible(u,ch,favoriteGenres))continue;
    const old=await env.DB.prepare("SELECT 1 FROM notices_sent WHERE user_id=? AND channel_id=?").bind(u.user_id,ch.id).first();
    if(old||(await membership(env,u.user_id)).length)continue;
    await send(env,u.user_id,"🆕 <b>NOUVEAUTÉ CINÉ RADAR</b>\n<i>Une nouvelle chaîne dans tes thèmes préférés :</i>\n\n🎞️ <b>"+esc(ch.title)+"</b>\n🌐 "+esc(ch.language),kb([[bx("🎬 Voir la fiche","card:"+ch.id+":latest",null,"success")],[bx("🎛 Mes alertes","preferences")]]));
    await env.DB.prepare("INSERT OR IGNORE INTO notices_sent(user_id,channel_id) VALUES(?,?)").bind(u.user_id,ch.id).run();
    delivered++;
   }catch(e){console.error(JSON.stringify({event:"notify_failed",reason:String(e).slice(0,100)}));}
  }

 }
}


async function validateMiniApp(env,request){
 const input=request.headers.get("X-Telegram-Init-Data")||"";
 if(!env.TELEGRAM_TOKEN||input.length<30||input.length>8192)throw Error("Authentification Telegram requise.");
 const data=new URLSearchParams(input),hash=data.get("hash");
 if(!hash||!/^[a-f0-9]{64}$/.test(hash))throw Error("Signature Telegram invalide.");
 data.delete("hash");data.delete("signature");
 const authDate=Number(data.get("auth_date"));
 if(!Number.isFinite(authDate)||authDate>Math.floor(Date.now()/1000)+120||authDate<Math.floor(Date.now()/1000)-86400)throw Error("Session expirée : rouvre la Mini App.");
 const check=Array.from(data.entries()).sort(([a],[b])=>a.localeCompare(b,"en")).map(([k,v])=>k+"="+v).join("\n");
 const encoder=new TextEncoder();
 const baseKey=await crypto.subtle.importKey("raw",encoder.encode("WebAppData"),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
 const keyBytes=await crypto.subtle.sign("HMAC",baseKey,encoder.encode(env.TELEGRAM_TOKEN));
 const key=await crypto.subtle.importKey("raw",keyBytes,{name:"HMAC",hash:"SHA-256"},false,["sign"]);
 const bytes=new Uint8Array(await crypto.subtle.sign("HMAC",key,encoder.encode(check)));
 const expected=Array.from(bytes).map(b=>b.toString(16).padStart(2,"0")).join("");
 if(expected.length!==hash.length)throw Error("Signature invalide");
 let mismatch=0;for(let i=0;i<hash.length;i++)mismatch|=hash.charCodeAt(i)^expected.charCodeAt(i);
 if(mismatch!==0)throw Error("Signature invalide");
 let user;
 try{user=JSON.parse(data.get("user")||"null")}catch{throw Error("Profil Telegram invalide");}
 if(!user||!Number.isSafeInteger(Number(user.id))||Number(user.id)<=0)throw Error("Profil Telegram absent");
 return {id:Number(user.id),first_name:String(user.first_name||"Utilisateur").slice(0,80)};
}
export async function miniAppAPI(env,request){
 const hdr={"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"};
 function json(body,code=200){return new Response(JSON.stringify(body),{status:code,headers:hdr});}
 try{
  const user=await validateMiniApp(env,request);
  if((await membership(env,user.id)).length)return json({error:"Abonne-toi d'abord aux canaux officiels via le bot."},403);
  const url=new URL(request.url),path=url.pathname;
  if(path==="/api/catalog"&&request.method==="GET"){
   const type=url.searchParams.get("type"),kind=CATEGORY.some(x=>x[0]===type)?type:null;
   const genre=String(url.searchParams.get("genre")||"general").slice(0,40);
   const language=String(url.searchParams.get("language")||"tous").slice(0,20);
   const sort=String(url.searchParams.get("sort")||"recent");
   const q=String(url.searchParams.get("q")||"").slice(0,80);
   const tab=String(url.searchParams.get("tab")||"explore");
   let rows=await listRows(env,kind,genre,LANG.some(x=>x[0]===language)?language:"tous",q,["recent","popular","active","quality"].includes(sort)?sort:"recent");
   if(tab==="recommend"){
     const fv=(await env.DB.prepare("SELECT c.id,c.genre FROM favorites f JOIN channels c ON c.id=f.channel_id WHERE f.user_id=? AND c.status='approved' AND c.rights_confirmed=1 LIMIT 60").bind(user.id).all()).results||[];
     const own=await prefs(env,user.id);
     rows=recommendations(rows,fv,own,1500);
   }
   if(tab==="favorites"){
    const favorites=(await env.DB.prepare("SELECT channel_id FROM favorites WHERE user_id=?").bind(user.id).all()).results||[];
    const accepted=new Set(favorites.map(x=>Number(x.channel_id)));rows=rows.filter(x=>accepted.has(Number(x.id)));
   }
   if(tab==="new")rows=rows.filter(x=>Date.parse(x.updated_at?.replace(" ","T")+"Z")>Date.now()-14*86400000);
   const fav=(await env.DB.prepare("SELECT channel_id FROM favorites WHERE user_id=?").bind(user.id).all()).results||[];
   return json({channels:rows.slice(0,100).map(x=>({id:x.id,title:x.title,link:x.link,description:x.description,genre:x.genre,language:x.language,content_type:x.content_type,favorites_count:x.favorites_count,check_status:x.check_status,last_post_at:x.last_post_at,banner_url:x.banner_url,quality_score:qualityScore(x)})),favorite_ids:fav.map(x=>x.channel_id),total:rows.length});
  }
  if(path==="/api/report"&&request.method==="POST"){
   const data=await request.json(),id=Number(data?.id),reason=String(data?.reason||"broken").slice(0,20);
   if(!Number.isSafeInteger(id)||id<=0||!["broken","category","content","rights"].includes(reason))return json({error:"Signalement invalide"},400);
   const channel=await env.DB.prepare("SELECT 1 FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(id).first();
   if(!channel)return json({error:"Canal non disponible"},404);
   await env.DB.prepare("INSERT OR IGNORE INTO channel_reports(channel_id,user_id,reason) VALUES(?,?,?)").bind(id,user.id,reason).run();
   return json({ok:true});
  }
  if(path==="/api/open"&&request.method==="POST"){
   const data=await request.json(),id=Number(data?.id);
   if(!Number.isSafeInteger(id)||id<=0)return json({error:"Canal invalide"},400);
   const channel=await env.DB.prepare("SELECT link FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(id).first();
   if(!channel||!BOT_LINK_RE.test(channel.link))return json({error:"Canal indisponible"},404);
   await env.DB.prepare("INSERT INTO channel_telemetry(channel_id,opens) VALUES(?,1) ON CONFLICT(channel_id) DO UPDATE SET opens=channel_telemetry.opens+1").bind(id).run();
   return json({ok:true});
  }
  if(path==="/api/preferences"&&request.method==="POST"){
    if(Number(request.headers.get("content-length")||0)>4096)return json({error:"Requête trop grande"},413);
    const body=await request.json();
    const category=String(body?.category||""),language=String(body?.language||"");
    if(!CATEGORY.some(x=>x[0]===category)||!LANG.some(x=>x[0]===language)||typeof body?.notifications!=="boolean")
      return json({error:"Préférences non valides"},400);
    await setPrefs(env,user.id,{category,language,notification_enabled:body.notifications?1:0});
    return json({ok:true,preferences:await prefs(env,user.id)});
  }
  if(path==="/api/profile"&&request.method==="GET"){
   const f=await env.DB.prepare("SELECT COUNT(*) n FROM favorites WHERE user_id=?").bind(user.id).first();
   const r=await env.DB.prepare("SELECT COUNT(*) n FROM referral_visits WHERE referrer_id=?").bind(user.id).first();
   return json({first_name:user.first_name,favorites:f?.n||0,referrals:r?.n||0,preferences:await prefs(env,user.id),referral_link:await referralLink(env,user.id)});
  }
  if(path==="/api/favorite"&&request.method==="POST"){
   if(Number(request.headers.get("content-length")||0)>4096)return json({error:"Requête trop grande"},413);
   const data=await request.json(),id=Number(data?.id);
   if(!Number.isSafeInteger(id)||id<=0)return json({error:"Canal invalide"},400);
   const found=await env.DB.prepare("SELECT id FROM channels WHERE id=? AND status='approved' AND rights_confirmed=1").bind(id).first();
   if(!found)return json({error:"Canal indisponible"},404);
   const old=await env.DB.prepare("SELECT 1 FROM favorites WHERE user_id=? AND channel_id=?").bind(user.id,id).first();
   if(old)await env.DB.prepare("DELETE FROM favorites WHERE user_id=? AND channel_id=?").bind(user.id,id).run();
   else await env.DB.prepare("INSERT OR IGNORE INTO favorites(user_id,channel_id) VALUES(?,?)").bind(user.id,id).run();
   return json({favorite:!old});
  }
  return json({error:"Route inconnue"},404);
 }catch(error){
  console.error(JSON.stringify({event:"mini_app_api_error",reason:String(error).slice(0,100)}));
  return json({error:!String(error).includes("D1")?String(error.message||error):"Service indisponible"},401);
 }
}
