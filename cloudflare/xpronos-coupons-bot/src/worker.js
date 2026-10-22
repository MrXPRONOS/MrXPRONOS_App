// FREE PRONOS : webhook Telegram Cloudflare Workers + D1.
// Aucune dépendance Supabase. Les crédits XP sont virtuels et non monétaires.
import {parseCouponCommand} from './logic.js';
import {APP_URL,navKeyboard,navigate,dashboard,xpScreen,xpHistory,showMissions,claimEngagement,alerts,toggleAlert,referrals,couponsFiltered,results,adminResult,adminAnalytics,faqText,notificationBatch,statusLabel} from './features.js';
import {miniApi} from './miniapp.js';
import {miniPage} from './minipage.js';

const POINTS_REFERRAL=30,POINTS_BONUS=5,DAILY_CAP=10,COOLDOWN=2*3600000;
const SITE='https://mrxpronos.github.io/MrXPRONOS_App/';
// Styles officiels Telegram : primary (bleu), success (vert), danger (rouge).
// Les thèmes et versions des clients Telegram peuvent adapter leur rendu.
export const MENU={keyboard:[
  [{text:'🏠 Mon espace',style:'primary'},{text:'🎟️ Coupons cote 4+',style:'primary'}],
  [{text:'🎫 Mes coupons',style:'primary'},{text:'🚩 Tâche',style:'primary'}],
  [{text:'🎁 Bonus',style:'success'},{text:'⭐ Mes XP',style:'primary'}],
  [{text:'↗️ Partager',style:'success'},{text:'✅ Vérifier',style:'success'}],
  [{text:'📋 Procédure',style:'primary'},{text:'📣 Alertes',style:'primary'}],
  [{text:'📱 Mini App Free Pronos',web_app:{url:APP_URL},style:'success'}]
],resize_keyboard:true};
const inline=(rows)=>({inline_keyboard:rows});
const html=(s)=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const pad=(s)=>String(s??'').slice(0,3600);
const safeJson=(s,fallback)=>{try{return JSON.parse(s)}catch{return fallback}};
const out=(x)=>new Response(x,{headers:{'content-type':'text/plain; charset=utf-8'}});

function channels(env) {
  const arr=safeJson(env.CF_BOT_CHANNELS_JSON||'[]',[]);
  return Array.isArray(arr)?arr.filter(x=>x && /^(@[\w]{5,}|-100\d{5,})$/.test(String(x.id||'')) && /^https:\/\/t\.me\//.test(String(x.url||''))):[];
}
function admins(env) {
  return new Set(String(env.CF_BOT_ADMIN_IDS||'').split(',').map(x=>Number(x.trim())).filter(x=>Number.isSafeInteger(x)&&x>0));
}
async function telegram(env,method,data) {
  const response=await fetch('https://api.telegram.org/bot'+env.CF_BOT_TOKEN+'/'+method,{
    method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(10000)
  });
  const j=await response.json();
  if(!response.ok||!j.ok)throw Error('Telegram '+method+': HTTP '+response.status+' '+String(j.description||'').slice(0,130));
  return j.result;
}
// Passer null comme clavier pour produire un message facilement transférable.
const send=(env,chat,text,reply=MENU)=>telegram(env,'sendMessage',{
  chat_id:chat,text:pad(text),parse_mode:'HTML',
  ...(reply?{reply_markup:reply}:{}),
  disable_web_page_preview:true
});
const ack=async(env,id)=>{try{await telegram(env,'answerCallbackQuery',{callback_query_id:id})}catch(e){console.warn('Callback acknowledgment failed:',String(e))}};
const one=async(env,sql,...params)=>env.DB.prepare(sql).bind(...params).first();
const all=async(env,sql,...params)=>(await env.DB.prepare(sql).bind(...params).all()).results||[];
const run=async(env,sql,...params)=>env.DB.prepare(sql).bind(...params).run();
const user=(env,id)=>one(env,'SELECT * FROM users WHERE id=?',id);

async function joined(env,uid,channel) {
  try {
    const m=await telegram(env,'getChatMember',{chat_id:channel,user_id:uid});
    return ['creator','administrator','member'].includes(m.status) || (m.status==='restricted'&&m.is_member===true);
  }catch(e){console.warn('Membership check failed',String(channel),String(e));return false}
}
async function requirements(env,uid){
  for(const c of channels(env))if(!(await joined(env,uid,c.id)))return false;
  return true;
}
async function verify(env,uid,chat) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed)return send(env,chat,'🔞 <b>Accès réservé aux adultes</b>\n\n<i>Commence par /start et confirme avoir 18 ans ou plus.</i>');
  const required=channels(env);
  if(!(await requirements(env,uid))){
    const rows=required.map(c=>[{text:'📢 Rejoindre le canal',url:c.url,style:'primary'}]);
    rows.push([{text:'✅ Vérifier',callback_data:'verify',style:'success'}]);
    return send(env,chat,'🔒 <b>VALIDATION DE TON ACCÈS</b>\n\n<blockquote>Rejoins les canaux indiqués ci-dessous, puis appuie sur <b>✅ Vérifier</b>.</blockquote>\n\n<i>Déjà abonné ? Vérifie que le bot est administrateur de chaque canal.</i>',inline(rows));
  }
  const ref=required.length>0 && !!u.referred_by && !u.referral_rewarded;
  await run(env,'UPDATE users SET required_verified=1, referral_rewarded=CASE WHEN ?=1 THEN 1 ELSE referral_rewarded END WHERE id=? AND adult_confirmed=1',ref?1:0,uid);
  return send(env,chat,'✅ <b>ACCÈS VALIDÉ !</b>\n\n🎉 Tu as désormais accès aux missions, bonus et coupons FREE PRONOS.\n\n<i>Utilise les boutons du menu pour commencer.</i>'+(ref?'\n\n🎁 <b>'+POINTS_REFERRAL+' XP</b> attribués à ton parrain.':''));
}
async function tasks(env,uid,chat) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 <b>Missions verrouillées</b>\n\n<i>Confirme ton âge et valide les canaux avec ✅ Vérifier.</i>');
  const ts=await all(env,'SELECT t.* FROM tasks t WHERE t.active=1 AND NOT EXISTS (SELECT 1 FROM task_claims c WHERE c.task_id=t.id AND c.user_id=?) ORDER BY t.id DESC LIMIT 25',uid);
  const rows=ts.map(t=>[{text:'📢 Canal (+'+t.xp+' XP)',url:t.url,style:'primary'},{text:'✅ Check',callback_data:'task:'+t.id,style:'success'}]);
  return send(env,chat,rows.length?'🚩 <b>MISSIONS DISPONIBLES</b>\n\n<blockquote>Rejoins un canal pour gagner des <b>XP</b>, puis valide ta mission avec le bouton ✅ Check.</blockquote>':'✅ <b>Missions terminées !</b>\n\n<i>Reviens plus tard pour découvrir de nouvelles opportunités.</i>',rows.length?inline(rows):MENU);
}
async function claimTask(env,uid,chat,id) {
  const t=await one(env,'SELECT * FROM tasks WHERE id=? AND active=1',id);
  if(!t)return send(env,chat,'⚠️ <b>Mission indisponible.</b>\n<i>Elle a peut-être été retirée.</i>');
  if(!(await joined(env,uid,t.chat_id)))return send(env,chat,'📢 <b>Abonnement requis</b>\n\n<i>Rejoins ce canal, puis appuie sur ✅ Check pour réclamer tes XP.</i>',inline([[{text:'📢 Rejoindre',url:t.url,style:'primary'}],[{text:'✅ Check',callback_data:'task:'+id,style:'success'}]]));
  const res=await one(env,'INSERT OR IGNORE INTO task_claims(user_id,task_id) SELECT ?,t.id FROM tasks t JOIN users u ON u.id=? WHERE t.id=? AND t.active=1 AND u.adult_confirmed=1 AND u.required_verified=1 RETURNING user_id',uid,uid,id);
  return send(env,chat,res?'✅ <b>MISSION VALIDÉE !</b>\n\n🎁 <b>+'+t.xp+' XP</b> ajoutés à ton compte.':'ℹ️ <b>Récompense non disponible</b>\n\n<i>Mission déjà récompensée ou compte non vérifié.</i>');
}
async function bonus(env,uid,chat) {
  const now=new Date(),iso=now.toISOString(),day=iso.slice(0,10),cutoff=new Date(now.getTime()-COOLDOWN).toISOString();
  const r=await one(env,
    'UPDATE users SET xp=xp+5,bonus_last_at=?,bonus_day=?,bonus_day_total=CASE WHEN bonus_day=? THEN bonus_day_total+5 ELSE 5 END '+
    'WHERE id=? AND adult_confirmed=1 AND required_verified=1 AND (bonus_day IS NULL OR bonus_day<>? OR bonus_day_total<=?) '+
    'AND (bonus_last_at IS NULL OR bonus_last_at<=?) RETURNING xp',
    iso,day,day,uid,day,DAILY_CAP-POINTS_BONUS,cutoff);
  if(r)return send(env,chat,'🎉 <b>BONUS RÉCUPÉRÉ !</b>\n\n🎁 <b>+'+POINTS_BONUS+' XP</b> ajoutés à ton solde.\n\n<i>À bientôt pour ton prochain bonus !</i>');
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 <b>Bonus verrouillé</b>\n\n<i>Confirme ton âge et vérifie les canaux pour recevoir tes XP.</i>');
  if(u.bonus_day===day&&u.bonus_day_total+POINTS_BONUS>DAILY_CAP)return send(env,chat,'⏳ <b>Plafond du jour atteint</b>\n\nTu as déjà obtenu tous tes bonus du jour.\n<i>Reviens demain (UTC) !</i>');
  const minutes=Math.ceil((COOLDOWN-(now.getTime()-new Date(u.bonus_last_at).getTime()))/60000);
  return send(env,chat,'⏳ <b>Bonus en recharge</b>\n\nProchaine récompense dans <b>'+Math.max(1,minutes)+' minutes</b>.\n<i>Encore un peu de patience !</i>');
}
function pretty(c,details=false) {
  let txt='🎟️ <b>'+html(c.title)+'</b>\n'+
    '🏷️ <i>Catégorie : '+html(c.tier)+'</i>\n'+
    '📊 Cote totale : <b>'+html(c.total_odds)+'</b>\n'+
    '💎 Accès : <b>'+html(c.xp_cost)+' XP</b>';
  if(details) {
    const selections=safeJson(c.selections,[]);
    if(selections.length){
      txt+='\n\n<b>⚽ LES SÉLECTIONS</b>\n<blockquote>';
      txt+=selections.map((x,i)=>'🎯 <b>'+(i+1)+'. '+html(x.match)+'</b>\n'+html(x.market)+' • <b>'+html(x.odds)+'</b>').join('\n\n');
      txt+='</blockquote>';
    }
  }
  return txt;
}
async function coupons(env,uid,chat) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 <b>Accès verrouillé</b>\n\n<i>Confirme ton âge et valide les canaux pour débloquer cette fonctionnalité.</i>');
  const rows=await all(env,'SELECT * FROM coupons WHERE active=1 AND expires_at>? AND stock<>0 ORDER BY created_at DESC,id DESC LIMIT 10',new Date().toISOString());
  if(!rows.length)return send(env,chat,'📭 <b>AUCUN COUPON DISPONIBLE</b>\n\n<i>De nouveaux coupons de cote 4+ seront publiés ici. Reviens consulter le menu !</i>');
  await send(env,chat,'🎟️ <b>COUPONS FREE PRONOS</b>\n\n📊 <b>'+rows.length+'</b> coupon(s) disponible(s).\n<blockquote>Les cotes peuvent évoluer. Aucun résultat n’est garanti.</blockquote>');
  for(const c of rows)await send(env,chat,pretty(c),inline([[{text:'🔓 Débloquer pour '+c.xp_cost+' XP',callback_data:'coupon:'+c.id,style:'success'}]]));
}
async function redeem(env,uid,chat,id) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 <b>Accès verrouillé</b>\n\n<i>Confirme ton âge et valide les canaux pour débloquer cette fonctionnalité.</i>');
  // INSERT atomique + trigger : la déduction XP et la baisse du stock ne peuvent pas être séparées.
  const r=await one(env,
    "INSERT OR IGNORE INTO redemptions(user_id,coupon_id,snapshot,xp_spent) "+
    "SELECT ?,c.id,json_object('title',c.title,'tier',c.tier,'total_odds',c.total_odds,'selections',json(c.selections),'expires_at',c.expires_at),c.xp_cost "+
    "FROM coupons c JOIN users u ON u.id=? WHERE c.id=? AND c.active=1 AND c.expires_at>? AND c.stock<>0 "+
    "AND u.adult_confirmed=1 AND u.required_verified=1 AND u.xp>=c.xp_cost RETURNING coupon_id",
    uid,uid,id,new Date().toISOString());
  if(r)return send(env,chat,'✅ <b>COUPON DÉBLOQUÉ !</b>\n\n🎫 Retrouve les sélections dans <b>Mes coupons</b>.\n<i>Vérifie les cotes avant de jouer.</i>');
  const already=await one(env,'SELECT 1 AS yes FROM redemptions WHERE user_id=? AND coupon_id=?',uid,id);
  if(already)return send(env,chat,'ℹ️ <b>Déjà débloqué</b>\n\nRetrouve ce coupon dans <b>🎫 Mes coupons</b>.');
  const c=await one(env,'SELECT * FROM coupons WHERE id=?',id);
  if(!c||!c.active||c.stock===0||c.expires_at<=new Date().toISOString())return send(env,chat,'⏳ <b>Coupon indisponible</b>\n\n<i>Stock épuisé ou date dépassée.</i>');
  return send(env,chat,'💎 <b>XP insuffisants</b>\n\n<i>Accomplis des missions ou récupère ton bonus pour débloquer ce coupon.</i>');
}
async function mine(env,uid,chat) {
  const rows=await all(env,'SELECT snapshot,xp_spent FROM redemptions WHERE user_id=? ORDER BY claimed_at DESC LIMIT 10',uid);
  if(!rows.length)return send(env,chat,'🎫 <b>MES COUPONS</b>\n\n<blockquote>Aucun coupon débloqué pour le moment.</blockquote>\n<i>Découvre les coupons disponibles dans le menu principal.</i>');
  for(const row of rows){
    const c=safeJson(row.snapshot,{});
    c.xp_cost=row.xp_spent;
    c.selections=JSON.stringify(c.selections||[]);
    await send(env,chat,pretty(c,true)+'\n\n⚠️ Vérifie les cotes en direct. 18+ • Joue responsablement.');
  }
}
async function xp(env,uid,chat) {
  const u=await user(env,uid);
  if(!u)return send(env,chat,'👋 <b>Bienvenue !</b>\n\n<i>Envoie /start pour activer ton compte.</i>');
  const refs=await one(env,'SELECT count(*) AS n FROM users WHERE referred_by=? AND referral_rewarded=1',uid);
  return send(env,chat,'💎 <b>MON PORTEFEUILLE XP</b>\n\n<blockquote>⭐ Solde actuel : <b>'+u.xp+' XP</b>\n👥 Parrainages validés : <b>'+refs.n+'</b></blockquote>\n\n<i>Les XP sont des points virtuels, non convertibles en argent.</i>');
}
// Ce message est autonome : il ne contient ni solde, ni consignes privées.
export function referralCard(link) {
  return '⚽ <b>FREE PRONOS | DÉCOUVRE LES COUPONS</b>\n\n'+
    '<blockquote>🎯 Des coupons football de cote totale <b>4.00 ou plus</b>, débloqués grâce aux points XP.</blockquote>\n\n'+
    '✨ <b>Comment ça marche ?</b>\n'+
    '① Rejoins la communauté.\n'+
    '② Accomplis des missions et récolte des <b>XP</b>.\n'+
    '③ Utilise tes XP pour accéder aux coupons.\n\n'+
    '🚀 <b>Commence ici :</b>\n'+html(link)+'\n\n'+
    '<i>🔞 Réservé aux 18 ans et plus. Les pronostics ne garantissent aucun résultat. Joue avec modération.</i>';
}
// Le lien natif Telegram partage un texte simple ; pour garder les styles HTML,
// l'utilisateur doit transférer le premier message du bot.
export function telegramShareUrl(link) {
  const caption='⚽ FREE PRONOS | Coupons football cote 4+\n'+
    '🎯 Accomplis des missions, gagne des XP et débloque des coupons.\n'+
    '🔞 18+ • Aucun gain garanti. Joue responsablement.';
  return 'https://t.me/share/url?url='+encodeURIComponent(link)+'&text='+encodeURIComponent(caption);
}
async function share(env,uid,chat) {
  const me=await telegram(env,'getMe',{});
  const link='https://t.me/'+encodeURIComponent(me.username)+'?start=ref_'+uid;
  // 1. Message destiné uniquement au partage, sans bouton ni instructions.
  await send(env,chat,referralCard(link),null);
  // 2. Message distinct, destiné uniquement à la personne qui invite.
  return send(env,chat,'↗️ <b>TON PARRAINAGE</b>\n\n'+
    '👆 <b>Transfère le message précédent</b> à tes contacts pour conserver la mise en forme : gras, italique et citation.\n\n'+
    '📤 Sinon, utilise le bouton ci-dessous pour préparer un partage Telegram (texte simple).\n\n'+
    (channels(env).length
      ? '🎁 <b>+'+POINTS_REFERRAL+' XP</b> pour toi lorsque ton invité valide réellement les canaux obligatoires. Une récompense par filleul.'
      : '<i>ℹ️ Bonus de parrainage désactivé tant qu’aucun canal obligatoire n’est configuré.</i>'),
    inline([
      [{text:'📤 Partager sur Telegram',url:telegramShareUrl(link),style:'success'}],
      [{text:'🔗 Copier mon lien',copy_text:{text:link},style:'primary'}]
    ]));
}
async function admin(env,uid,chat,raw,updateId){
  if(!admins(env).has(uid))return send(env,chat,'⛔ <b>Accès administrateur uniquement</b>\n\n<i>Cette commande est réservée à l’équipe XPRONOS.</i>');
  const name=raw.split(/\s+/)[0],arg=raw.slice(name.length).trim();
  if(name==='/admin')return send(env,chat,'🛠️ <b>ESPACE ADMINISTRATEUR</b>\n\n<b>🎟️ Gestion des coupons</b>\n<code>/addcoupon</code> · <code>/listcoupons</code>\n<code>/delcoupon ID</code> · <code>/activatecoupon ID</code>\n\n<b>🚩 Missions et récompenses</b>\n<code>/addtask</code> · <code>/listtasks</code> · <code>/deltask ID</code>\n<code>/grantxp USER_ID 30</code>\n\n<b>📊 Statistiques</b>\n<code>/stats</code>\n\n<blockquote><b>Exemple de coupon :</b>\n<code>/addcoupon PRO | 50 | 2099-01-01T18:00 | -1 | Titre | Équipe A - B ; Plus 1,5 ; 1.70 | Équipe C - D ; 1X ; 2.40</code></blockquote>\n\n<i>Exemple fictif à remplacer par des matchs réels.</i>');
  if(name==='/addcoupon'){
    const c=parseCouponCommand(arg);
    await run(env,'INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,stock) VALUES(?,?,?,?,?,?,?)',
      c.tier,c.title,c.selections,c.total_odds,c.xp_cost,c.expires_at,c.stock);
    return send(env,chat,'✅ <b>COUPON PUBLIÉ !</b>\n\n📊 Cote totale : <b>'+html(c.total_odds)+'</b>\n💎 Coût : <b>'+c.xp_cost+' XP</b>');
  }
  if(name==='/listcoupons'){
    const rows=await all(env,'SELECT * FROM coupons ORDER BY id DESC LIMIT 20');
    return send(env,chat,'🎟️ <b>LISTE DES COUPONS</b>\n\n'+(rows.map(c=>'<b>#'+c.id+'</b> '+(c.active?'✅':'❌')+' '+html(c.tier)+' — '+html(c.title)+'\n📊 '+html(c.total_odds)+'  •  Stock : '+c.stock).join('\n\n')||'<i>Aucun coupon disponible.</i>'));
  }
  if(name==='/delcoupon'||name==='/activatecoupon'){
    const id=Number(arg);
    if(!Number.isSafeInteger(id)||id<1)return send(env,chat,'⚠️ <b>Identifiant invalide</b>\n\n<i>Indique un identifiant numérique valide.</i>');
    const active=name==='/activatecoupon'?1:0;
    await run(env,'UPDATE coupons SET active=? WHERE id=? AND (?=0 OR expires_at>?)',active,id,active,new Date().toISOString());
    return send(env,chat,'✅ <b>Coupon mis à jour.</b>');
  }
  if(name==='/addtask'){
    const bits=arg.split(/\s+/),[channel,url,cost]=bits;
    if(bits.length!==3||!/^(@[\w]{5,}|-100\d{5,})$/.test(channel)||!/^https:\/\/t\.me\//.test(url)||!/^\d{1,5}$/.test(cost)||Number(cost)<1)return send(env,chat,'⚠️ <b>Format attendu</b>\n<code>/addtask @canal https://t.me/canal 15</code>');
    const r=await run(env,'INSERT OR IGNORE INTO tasks(chat_id,url,xp) VALUES(?,?,?)',channel,url,Number(cost));
    return send(env,chat,r.meta.changes?'✅ <b>Mission créée avec succès !</b>':'ℹ️ <b>Ce canal possède déjà une mission.</b>');
  }
  if(name==='/listtasks'){
    const rows=await all(env,'SELECT * FROM tasks ORDER BY id DESC LIMIT 30');
    return send(env,chat,'🚩 <b>LISTE DES MISSIONS</b>\n\n'+(rows.map(t=>'<b>#'+t.id+'</b> '+(t.active?'✅':'❌')+' '+html(t.chat_id)+' — <b>+'+t.xp+' XP</b>').join('\n')||'<i>Aucune mission disponible.</i>'));
  }
  if(name==='/deltask'){
    const id=Number(arg);
    if(!Number.isSafeInteger(id)||id<1)return send(env,chat,'⚠️ <b>Identifiant invalide</b>\n\n<i>Indique un identifiant numérique valide.</i>');
    await run(env,'UPDATE tasks SET active=0 WHERE id=?',id);
    return send(env,chat,'✅ <b>Mission désactivée.</b>');
  }
  if(name==='/grantxp'){
    const bits=arg.split(/\s+/),userId=Number(bits[0]),points=Number(bits[1]);
    if(bits.length!==2||!Number.isSafeInteger(userId)||userId<1||!Number.isInteger(points)||points<1||points>100000)
      return send(env,chat,'⚠️ <b>Format attendu</b>\n<code>/grantxp 123456789 30</code>');
    const grant=await one(env,'INSERT OR IGNORE INTO manual_grants(user_id,xp,update_id) SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM users WHERE id=?) RETURNING id',userId,points,updateId,userId);
    return send(env,chat,grant?'✅ <b>XP crédités avec succès !</b>':'ℹ️ <b>Utilisateur introuvable</b> ou commande déjà appliquée.');
  }
  if(name==='/result'){
    const result=await adminResult(env,arg);
    return send(env,chat,result.status==='ok'?
      '✅ <b>RÉSULTAT ENREGISTRÉ</b>\n\n🎟️ Coupon #'+result.id+'\n📊 '+result.label+'\n\n<i>La mise à jour est identifiée comme validation administrative.</i>':
      result.status==='missing'?'⚠️ Coupon introuvable.':
      '⚠️ <b>Format attendu</b>\n<code>/result ID won|lost|void|live|available https://source-fiable.example</code>\n\n<i>Indique une source vérifiable et réelle.</i>');
  }
  if(name==='/adminstats')return adminAnalytics(env,chat,send);
  if(name==='/stats'){
    const r=await one(env,'SELECT (SELECT count(*) FROM users) AS members,(SELECT count(*) FROM tasks) AS tasks,(SELECT count(*) FROM coupons) AS coupons,(SELECT count(*) FROM redemptions) AS redemptions');
    return send(env,chat,'📊 <b>STATISTIQUES FREE PRONOS</b>\n\n<blockquote>👥 Membres : <b>'+r.members+'</b>\n🚩 Missions : <b>'+r.tasks+'</b>\n🎟️ Coupons : <b>'+r.coupons+'</b>\n🔓 Déblocages : <b>'+r.redemptions+'</b></blockquote>');
  }
}
async function handle(env,update) {
  const q=update.callback_query,m=q?.message||update.message,from=q?.from||update.message?.from;
  if(!m||!from||m.chat?.type!=='private'||!Number.isSafeInteger(from.id))return;
  const uid=from.id,chat=m.chat.id;
  const txt=String(update.message?.text||'').trim();
  const fullName=([from.first_name||'',from.last_name||''].join(' ').trim()||from.username||'Membre').slice(0,100);
  const ref=/^\/start(?:@\w+)?\s+ref_(\d+)$/.exec(txt)?.[1];
  await run(env,"INSERT OR IGNORE INTO users(id,name,referred_by) VALUES(?,?,(SELECT id FROM users WHERE id=? AND id<>?))",uid,fullName,ref?Number(ref):null,uid);
  await run(env,'UPDATE users SET name=? WHERE id=?',fullName,uid);
  if(q){
    const data=String(q.data||'');
    await ack(env,q.id);
    if(data==='nav:share')return share(env,uid,chat);
    if(data==='nav:channeltasks')return tasks(env,uid,chat);
    if(data.startsWith('nav:')||data.startsWith('filter:'))
      return navigate(env,uid,chat,data,send,telegram,m.message_id);
    if(data.startsWith('pref:')){
      const updated=await toggleAlert(env,uid,data.slice(5));
      if(updated.status==='locked')return send(env,chat,'🔒 <b>Valide ton accès pour régler les notifications.</b>');
      return alerts(env,uid,chat,send,telegram,m.message_id);
    }
    if(data.startsWith('claim:')){
      const kind=data.slice(6);
      const claim=await claimEngagement(env,uid,kind);
      const label=kind==='daily'?'du jour':'hebdomadaire';
      await send(env,chat,claim.status==='ok'?'🎉 <b>MISSION VALIDÉE !</b>\n\n💎 <b>+'+claim.xp+' XP</b> reçus pour ta mission '+label+'.':
        claim.status==='locked'?'🔒 Confirme ton âge et vérifie les canaux d’abord.':
        'ℹ️ <b>Récompense déjà reçue</b> pour cette période.');
      return showMissions(env,uid,chat,send);
    }
    if(data==='adult_yes'){
      await run(env,'UPDATE users SET adult_confirmed=1 WHERE id=?',uid);
      await send(env,chat,'✅ <b>Âge confirmé !</b>\n\n<i>Dernière étape : vérifie les canaux pour activer tes récompenses.</i>');
      return verify(env,uid,chat);
    }
    if(data==='adult_no')return send(env,chat,'🔞 <b>Accès réservé aux personnes de 18 ans ou plus.</b>\n\n<i>Merci de ta compréhension.</i>');
    if(data==='verify')return verify(env,uid,chat);
    if(/^task:\d+$/.test(data))return claimTask(env,uid,chat,Number(data.split(':')[1]));
    if(/^coupon:\d+$/.test(data))return redeem(env,uid,chat,Number(data.split(':')[1]));
    return;
  }
  if(/^\/start(?:@\w+)?(?:\s|$)/.test(txt)){
    const u=await user(env,uid);
    await send(env,chat,'⚽ <b>BIENVENUE SUR FREE PRONOS</b>\n\n<blockquote>🎯 Des coupons football de cote totale <b>4.00 ou plus</b>, accessibles grâce à tes <b>XP</b>.</blockquote>\n\n🚩 <b>Réalise des missions</b>\n🎁 <b>Récupère des bonus</b>\n🎟️ <b>Débloque des coupons</b>\n\n<i>🔞 18+ • Aucun résultat garanti. Joue avec modération.</i>');
    if(!u?.adult_confirmed)return send(env,chat,'🔞 <b>CONFIRMATION D’ÂGE</b>\n\n<i>Pour continuer, confirme que tu as 18 ans ou plus.</i>',inline([[{text:'✅ Oui, 18 ans ou plus',callback_data:'adult_yes',style:'success'}],[{text:'❌ Non',callback_data:'adult_no',style:'danger'}]]));
    return verify(env,uid,chat);
  }
  if(txt.startsWith('/')){
    const command=txt.split(/\s+/)[0].split('@')[0];
    const names=new Set(['/admin','/addcoupon','/listcoupons','/delcoupon','/activatecoupon','/addtask','/listtasks','/deltask','/grantxp','/stats','/adminstats','/result']);
    if(names.has(command))return admin(env,uid,chat,command+txt.slice(txt.split(/\s+/)[0].length),update.update_id);
  }
  if(txt==='🏠 Mon espace'||txt==='/dashboard'||txt==='/menu')return dashboard(env,uid,chat,send);
  if(txt==='/history'||txt==='/xphistory')return xpHistory(env,uid,chat,send);
  if(txt==='/levels'||txt==='/level')return xpScreen(env,uid,chat,send);
  if(txt==='/missions')return showMissions(env,uid,chat,send);
  if(txt==='/daily'||txt==='/weekly'){
    const kind=txt.slice(1),res=await claimEngagement(env,uid,kind);
    return send(env,chat,res.status==='ok'?'✅ <b>+'+res.xp+' XP</b> reçus !':
      res.status==='already'?'⏳ <b>Mission déjà réclamée</b> pour cette période.':
      '🔒 <b>Vérifie ton accès avant de participer.</b>',navKeyboard());
  }
  if(txt==='📣 Alertes'||txt==='/alerts')return alerts(env,uid,chat,send);
  if(txt==='/referrals')return referrals(env,uid,chat,send);
  if(txt==='/results')return results(env,uid,chat,send);
  if(/^\/coupons\s+(ALL|SIMPLE|PRO|VIP)$/i.test(txt))
    return couponsFiltered(env,uid,chat,send,telegram,undefined,txt.split(/\s+/)[1].toUpperCase());
  if(txt==='/faq')return send(env,chat,faqText(),navKeyboard());
  if(txt==='✅ Vérifier'||txt==='/verify')return verify(env,uid,chat);
  if(txt==='🚩 Tâche'||txt==='/tasks')return tasks(env,uid,chat);
  if(txt==='🎁 Bonus'||txt==='/bonus')return bonus(env,uid,chat);
  if(txt==='⭐ Mes XP'||txt==='/xp')return xpScreen(env,uid,chat,send);
  if(txt==='🎟️ Coupons cote 4+'||txt==='/coupons')return couponsFiltered(env,uid,chat,send);
  if(txt==='🎫 Mes coupons'||txt==='/mine')return mine(env,uid,chat);
  if(txt==='↗️ Partager'||txt==='/share')return share(env,uid,chat);
  if(txt==='📋 Procédure'||txt==='/help')return send(env,chat,'📋 <b>COMMENT ÇA MARCHE ?</b>\n\n<blockquote>① Confirme tes <b>18 ans ou plus</b> et vérifie les canaux.\n② Accomplis des missions pour gagner des <b>XP</b>.\n③ Récupère <b>5 XP</b> toutes les 2 heures, maximum <b>10 XP/jour</b>.\n④ Échange tes XP contre l’accès aux coupons <b>4+</b>.</blockquote>\n\n🌐 '+SITE+'\n\n<i>Les XP sont virtuels et ne représentent pas de l’argent. Joue responsablement.</i>');
  return send(env,chat,'👋 <b>Que souhaites-tu faire ?</b>\n\n<i>Utilise les boutons ci-dessous ou envoie /start pour afficher l’accueil.</i>');
}
export default {
  async fetch(req,env){
    const url=new URL(req.url);
    if(req.method==='GET'&&url.pathname==='/health'){
      return new Response(JSON.stringify({status:env.DB&&env.CF_BOT_TOKEN&&env.CF_BOT_WEBHOOK_SECRET&&admins(env).size?'ready':'not_configured'}),{
        status:env.DB&&env.CF_BOT_TOKEN&&env.CF_BOT_WEBHOOK_SECRET&&admins(env).size?200:503,
        headers:{'content-type':'application/json','cache-control':'no-store'}
      });
    }
    if(req.method!=='POST'||url.pathname!=='/telegram')return new Response('Not found',{status:404});
    if(!env.DB||!env.CF_BOT_TOKEN||!env.CF_BOT_WEBHOOK_SECRET||!admins(env).size)return new Response('Not configured',{status:503});
    const provided=req.headers.get('x-telegram-bot-api-secret-token')||'';
    if(!provided||provided!==env.CF_BOT_WEBHOOK_SECRET)return new Response('Forbidden',{status:403});
    try{
      const data=await req.json();
      if(!Number.isSafeInteger(data.update_id))return new Response('Bad request',{status:400});
      await handle(env,data);
      return out('ok');
    }catch(error){console.error('Webhook failed:',String(error));return new Response('retry',{status:500})}
  }
};
