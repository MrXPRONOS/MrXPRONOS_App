// Free Pronos V2: tableau de bord, classement, historique, missions,
// résultats revus, notifications opt-in et navigation inline.
const H=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const SQL={
  user:'SELECT * FROM users WHERE id=?',
  lifetime:"SELECT coalesce(sum(delta),0) AS total FROM ledger WHERE user_id=? AND delta>0",
  earnedToday:"SELECT coalesce(sum(delta),0) AS total FROM ledger WHERE user_id=? AND delta>0 AND created_at>=?",
  taskCount:'SELECT count(*) AS total FROM task_claims WHERE user_id=?',
  couponCount:'SELECT count(*) AS total FROM redemptions WHERE user_id=?',
  referralCount:'SELECT count(*) AS total FROM users WHERE referred_by=? AND referral_rewarded=1'
};
const one=async(env,sql,...params)=>env.DB.prepare(sql).bind(...params).first();
const all=async(env,sql,...params)=>(await env.DB.prepare(sql).bind(...params).all()).results||[];
const run=async(env,sql,...params)=>env.DB.prepare(sql).bind(...params).run();
const pretty=x=>Number(x||0).toLocaleString('fr-FR');
export const TIERS=[
  {min:0,name:'Débutant',icon:'🌱'},
  {min:100,name:'Amateur',icon:'🥉'},
  {min:300,name:'Expert',icon:'🥇'},
  {min:800,name:'Légende',icon:'👑'}
];
export function levelFor(earned){
  const n=Math.max(0,Number(earned)||0);
  const level=TIERS.slice().reverse().find(x=>n>=x.min)||TIERS[0];
  const i=TIERS.indexOf(level),next=TIERS[i+1]||null;
  const progress=next?Math.min(1,(n-level.min)/(next.min-level.min)):1;
  return {name:level.name,icon:level.icon,earned:n,next:next?next.name:null,remaining:next?next.min-n:0,progress};
}
export function periodKey(kind,date=new Date()){
  const d=new Date(date);
  if(kind==='daily')return d.toISOString().slice(0,10);
  const utc=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate()));
  const offset=(utc.getUTCDay()+6)%7;
  utc.setUTCDate(utc.getUTCDate()-offset);
  return utc.toISOString().slice(0,10);
}
const progressBar=p=>'🟦'.repeat(Math.floor(p*8))+'▫️'.repeat(8-Math.floor(p*8));
export const APP_URL='https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev/app';
export const navKeyboard=(current='home')=>({inline_keyboard:[
  [{text:'🏠 Tableau de bord',callback_data:'nav:dashboard',style:'primary'},{text:'🎟️ Coupons',callback_data:'nav:coupons',style:'primary'}],
  [{text:'💎 Mes XP',callback_data:'nav:xp',style:'primary'},{text:'🚩 Missions',callback_data:'nav:missions',style:'primary'}],
  [{text:'📣 Alertes',callback_data:'nav:alerts',style:'success'},{text:'👥 Parrainages',callback_data:'nav:referrals',style:'primary'}],
  [{text:'📊 Résultats',callback_data:'nav:results',style:'primary'},{text:'❓ Aide',callback_data:'nav:faq',style:'primary'}],
  [{text:'📱 Ouvrir Free Pronos',web_app:{url:APP_URL},style:'success'}]
]});
export async function summary(env,uid){
  const today=periodKey('daily')+'T00:00:00.000Z';
  const [u,earned,todayEarned,tasks,coupons,referrals]=await Promise.all([
    one(env,SQL.user,uid),one(env,SQL.lifetime,uid),one(env,SQL.earnedToday,uid,today),
    one(env,SQL.taskCount,uid),one(env,SQL.couponCount,uid),one(env,SQL.referralCount,uid)
  ]);
  if(!u)return null;
  return {id:uid,name:u.name,adult:!!u.adult_confirmed,verified:!!u.required_verified,
    xp:u.xp,earned:Number(earned.total),earnedToday:Number(todayEarned.total),
    tasks:Number(tasks.total),coupons:Number(coupons.total),referrals:Number(referrals.total),
    level:levelFor(Number(earned.total))};
}
export function dashboardText(u){
  const level=u.level;
  return '⚽ <b>FREE PRONOS — MON ESPACE</b>\n\n'+
    '👤 <b>'+H(u.name)+'</b>  •  '+level.icon+' <b>'+level.name+'</b>\n\n'+
    '<blockquote>💎 Mes XP : <b>'+pretty(u.xp)+'</b>\n'+
    '✨ XP gagnés aujourd’hui : <b>+'+pretty(u.earnedToday)+'</b>\n'+
    '🎟️ Coupons débloqués : <b>'+u.coupons+'</b>\n'+
    '🚩 Missions terminées : <b>'+u.tasks+'</b>\n'+
    '👥 Parrainages validés : <b>'+u.referrals+'</b></blockquote>\n\n'+
    (level.next?'📈 <b>Progression vers '+level.next+'</b>\n'+progressBar(level.progress)+'\n<i>Encore '+pretty(level.remaining)+' XP cumulés pour atteindre le prochain niveau.</i>':
      '🏆 <b>Rang Légende atteint !</b>')+
    '\n\n<i>Les XP sont virtuels, sans valeur monétaire. 18+ • Joue responsablement.</i>';
}
async function deliver(env,chat,text,send,telegram,editId,keyboard=navKeyboard()){
  if(editId&&telegram){
    try{
      return await telegram(env,'editMessageText',{chat_id:chat,message_id:editId,text,
        parse_mode:'HTML',reply_markup:keyboard,disable_web_page_preview:true});
    }catch(error){
      if(String(error).includes('message is not modified'))return;
      console.warn('Free Pronos navigation edit fallback',String(error));
    }
  }
  return send(env,chat,text,keyboard);
}
export async function dashboard(env,uid,chat,send,telegram,editId){
  const u=await summary(env,uid);
  if(!u)return deliver(env,chat,'👋 <b>Bienvenue sur Free Pronos</b>\n<i>Commence par /start.</i>',send,telegram,editId);
  return deliver(env,chat,dashboardText(u),send,telegram,editId);
}
export async function xpHistory(env,uid,chat,send,telegram,editId){
  const rows=await all(env,'SELECT delta,reason,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 12',uid);
  const labels={bonus:'Bonus',admin:'Crédit administrateur'};
  let text='📜 <b>HISTORIQUE DE MES XP</b>\n\n';
  text+=rows.length?rows.map(x=>{
    const reason=String(x.reason||'');
    let name=labels[reason]||reason.split(':')[0];
    if(reason.startsWith('task:'))name='Mission';
    if(reason.startsWith('coupon:'))name='Coupon débloqué';
    if(reason.startsWith('referral:'))name='Parrainage vérifié';
    if(reason.startsWith('daily:'))name='Récompense du jour';
    if(reason.startsWith('weekly:'))name='Récompense hebdomadaire';
    return (x.delta>=0?'🟢 +':'🔴 ')+x.delta+' XP · <b>'+H(name)+'</b>\n<i>'+H(String(x.created_at).slice(0,16).replace('T',' '))+' UTC</i>';
  }).join('\n\n'):'<i>Aucune opération XP pour le moment.</i>';
  return deliver(env,chat,text,send,telegram,editId);
}
export async function xpScreen(env,uid,chat,send,telegram,editId){
  const u=await summary(env,uid);
  if(!u)return deliver(env,chat,'Envoie /start pour commencer.',send,telegram,editId);
  const level=u.level;
  return deliver(env,chat,'💎 <b>MES XP ET MON NIVEAU</b>\n\n'+
    '<blockquote>⭐ Solde disponible : <b>'+pretty(u.xp)+' XP</b>\n'+
    '✨ XP cumulés : <b>'+pretty(u.earned)+' XP</b>\n'+
    level.icon+' Rang : <b>'+level.name+'</b></blockquote>\n\n'+
    (level.next?'📈 '+progressBar(level.progress)+'\n<i>Encore '+level.remaining+' XP pour le rang '+level.next+'.</i>':
      '👑 <b>Tu as atteint le rang maximum !</b>')+
    '\n\n<i>Ton niveau dépend des XP gagnés au total, pas de tes dépenses.</i>',
    send,telegram,editId,{inline_keyboard:[
      [{text:'📜 Voir mon historique XP',callback_data:'nav:history',style:'primary'}],
      [{text:'🎁 Récompense quotidienne',callback_data:'claim:daily',style:'success'}],
      [{text:'🎯 Récompense hebdomadaire',callback_data:'claim:weekly',style:'success'}],
      ...navKeyboard().inline_keyboard
    ]});
}
export async function claimEngagement(env,uid,kind){
  const weekly=kind==='weekly';
  if(kind!=='daily'&&!weekly)return {status:'invalid'};
  const amount=weekly?10:3,period=periodKey(kind);
  const result=await one(env,
    'INSERT OR IGNORE INTO engagement_claims(user_id,kind,period_key,xp) '+
    'SELECT id,?,?,? FROM users WHERE id=? AND adult_confirmed=1 AND required_verified=1 '+
    'RETURNING xp',kind,period,amount,uid);
  if(result)return {status:'ok',xp:amount};
  const user=await one(env,SQL.user,uid);
  if(!user?.adult_confirmed||!user?.required_verified)return {status:'locked'};
  return {status:'already',xp:amount};
}
export async function showMissions(env,uid,chat,send,telegram,editId){
  const claims=await all(env,'SELECT kind FROM engagement_claims WHERE user_id=? AND ((kind=? AND period_key=?) OR (kind=? AND period_key=?))',
    uid,'daily',periodKey('daily'),'weekly',periodKey('weekly'));
  const done=new Set(claims.map(x=>x.kind));
  const text='🚩 <b>MISSIONS FREE PRONOS</b>\n\n'+
    '<blockquote>📅 <b>Visite du jour : +3 XP</b>\n'+(done.has('daily')?'✅ Réclamée':'🟡 Disponible')+
    '\n\n🎯 <b>Mission de la semaine : +10 XP</b>\n'+(done.has('weekly')?'✅ Réclamée':'🟡 Disponible')+'</blockquote>\n\n'+
    '📢 <i>Les autres missions de canaux restent accessibles avec /tasks.</i>\n\n'+
    '<i>Récompenses sans mise ni achat. Une seule validation par période UTC.</i>';
  return deliver(env,chat,text,send,telegram,editId,{inline_keyboard:[
    [{text:'📅 +3 XP aujourd’hui',callback_data:'claim:daily',style:'success'}],
    [{text:'🎯 +10 XP cette semaine',callback_data:'claim:weekly',style:'success'}],
    [{text:'📢 Missions des canaux',callback_data:'nav:channeltasks',style:'primary'}],
    ...navKeyboard().inline_keyboard
  ]});
}
async function ensurePrefs(env,uid){
  await run(env,'INSERT OR IGNORE INTO user_preferences(user_id) SELECT id FROM users WHERE id=?',uid);
  return one(env,'SELECT * FROM user_preferences WHERE user_id=?',uid);
}
export async function alerts(env,uid,chat,send,telegram,editId){
  const p=await ensurePrefs(env,uid);
  if(!p)return deliver(env,chat,'Commence par /start.',send,telegram,editId);
  return deliver(env,chat,'📣 <b>MES NOTIFICATIONS</b>\n\n'+
    '<blockquote>🎟️ Nouveaux coupons : <b>'+(p.notify_coupons?'✅ Activées':'⭕ Désactivées')+'</b>\n'+
    '📊 Résultats vérifiés : <b>'+(p.notify_results?'✅ Activées':'⭕ Désactivées')+'</b></blockquote>\n\n'+
    '<i>Tu restes libre de les activer ou désactiver à tout moment. Aucun envoi promotionnel sans ton accord.</i>',
    send,telegram,editId,{inline_keyboard:[
      [{text:(p.notify_coupons?'🔕 Désactiver':'🔔 Activer')+' nouveaux coupons',callback_data:'pref:coupons',style:p.notify_coupons?'danger':'success'}],
      [{text:(p.notify_results?'🔕 Désactiver':'🔔 Activer')+' résultats',callback_data:'pref:results',style:p.notify_results?'danger':'success'}],
      ...navKeyboard().inline_keyboard
    ]});
}
export async function toggleAlert(env,uid,category){
  const col=category==='coupons'?'notify_coupons':category==='results'?'notify_results':null;
  if(!col)return {status:'invalid'};
  const user=await one(env,SQL.user,uid);
  if(!user?.adult_confirmed||!user?.required_verified)return {status:'locked'};
  await ensurePrefs(env,uid);
  const r=await one(env,
    'UPDATE user_preferences SET '+col+'=CASE WHEN '+col+'=1 THEN 0 ELSE 1 END,'+
    "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE user_id=? RETURNING "+col+' AS enabled',uid);
  return {status:'ok',enabled:!!r.enabled};
}
export async function referrals(env,uid,chat,send,telegram,editId){
  const rows=await all(env,'SELECT name,referral_rewarded,created_at FROM users WHERE referred_by=? ORDER BY created_at DESC LIMIT 12',uid);
  const validated=rows.filter(r=>r.referral_rewarded).length;
  const text='👥 <b>MON PARRAINAGE</b>\n\n'+
    '<blockquote>👤 Filleuls récents : <b>'+rows.length+'</b>\n'+
    '✅ Vérifiés dans cette liste : <b>'+validated+'</b>\n'+
    '🎁 Récompense : <b>30 XP par filleul vérifié</b></blockquote>\n\n'+
    (rows.length?rows.map(r=>(r.referral_rewarded?'✅ ':'⏳ ')+H(r.name)+' — <i>'+(r.referral_rewarded?'Validé':'En attente de vérification')+'</i>').join('\n'):
      '<i>Aucun filleul enregistré. Partage ton lien pour inviter tes amis.</i>')+
    '\n\n<i>Les données présentées concernent uniquement tes filleuls.</i>';
  return deliver(env,chat,text,send,telegram,editId,{inline_keyboard:[
    [{text:'↗️ Obtenir mon message à partager',callback_data:'nav:share',style:'success'}],
    ...navKeyboard().inline_keyboard
  ]});
}
export async function couponsFiltered(env,uid,chat,send,telegram,editId,tier='ALL'){
  const u=await one(env,SQL.user,uid);
  if(!u?.adult_confirmed||!u?.required_verified)
    return deliver(env,chat,'🔒 <b>Accès verrouillé.</b>\n<i>Confirme ton âge et vérifie les canaux depuis /start.</i>',send,telegram,editId);
  if(!['ALL','SIMPLE','PRO','VIP'].includes(tier))tier='ALL';
  const clauses="active=1 AND expires_at>? AND stock<>0 AND result_status='available'";
  const rows=await all(env,'SELECT id,title,total_odds,xp_cost,tier,expires_at FROM coupons WHERE '+clauses+
    (tier==='ALL'?'':' AND tier=?')+' ORDER BY created_at DESC,id DESC LIMIT 12',
    ...[new Date().toISOString(),...(tier==='ALL'?[]:[tier])]);
  const text='🎟️ <b>CATALOGUE DES COUPONS</b>\n\n'+
    '🏷️ Catégorie : <b>'+tier+'</b>\n'+
    (rows.length?rows.map(c=>'🎯 <b>'+H(c.title)+'</b> ['+H(c.tier)+']\n📊 Cote : <b>'+H(c.total_odds)+'</b> · 💎 '+c.xp_cost+' XP\n⏳ Jusqu’au '+H(c.expires_at.slice(0,16).replace('T',' '))+' UTC').join('\n\n'):
      '<i>Aucun coupon disponible pour cette catégorie.</i>')+
    '\n\n<i>Les cotes peuvent évoluer ; aucun résultat n’est garanti.</i>';
  const buttons=rows.slice(0,8).map(c=>[{text:'🔓 '+c.id+' · '+c.xp_cost+' XP',callback_data:'coupon:'+c.id,style:'success'}]);
  return deliver(env,chat,text,send,telegram,editId,{inline_keyboard:[
    [{text:'Tous',callback_data:'filter:ALL',style:'primary'},
     {text:'Simple',callback_data:'filter:SIMPLE',style:'primary'},
     {text:'Pro',callback_data:'filter:PRO',style:'primary'},
     {text:'VIP',callback_data:'filter:VIP',style:'primary'}],
    ...buttons,...navKeyboard().inline_keyboard
  ]});
}
const STATUS={available:'⏳ Disponible',live:'🔵 En cours',won:'✅ Gagné',lost:'❌ Perdu',void:'↩️ Annulé'};
export function statusLabel(status){return STATUS[status]||'En attente';}
export async function results(env,uid,chat,send,telegram,editId){
  const rows=await all(env,
    "SELECT id,title,result_status,result_reviewed_at,result_source FROM coupons WHERE result_status IN ('won','lost','void','live') ORDER BY coalesce(result_reviewed_at,created_at) DESC LIMIT 12");
  const txt='📊 <b>RÉSULTATS DES COUPONS</b>\n\n'+
    (rows.length?rows.map(c=>
      '<b>#'+c.id+' · '+H(c.title)+'</b>\n'+statusLabel(c.result_status)+
      (c.result_reviewed_at?'\n<i>Mise à jour : '+H(c.result_reviewed_at.slice(0,16).replace('T',' '))+' UTC</i>':'')+
      (typeof c.result_source==='string'&&c.result_source.startsWith('https://')?'\n🔎 <a href="'+H(c.result_source)+'">Consulter la source du résultat</a>':'')).join('\n\n'):
      '<i>Aucun résultat confirmé pour le moment.</i>')+
    '\n\n<blockquote>Résultats renseignés par un administrateur après contrôle des matchs, sans garantie de données automatiques.</blockquote>';
  return deliver(env,chat,txt,send,telegram,editId);
}
export async function adminResult(env,raw){
  const m=/^(\d+)\s+(live|won|lost|void|available)\s+(\S{8,700})$/.exec(raw.trim());
  if(!m||!/^https:\/\//.test(m[3]))return {status:'format'};
  const couponId=Number(m[1]),status=m[2],url=m[3];
  if(!Number.isSafeInteger(couponId)||couponId<1)return {status:'format'};
  const change=await one(env,
    "UPDATE coupons SET result_status=?,result_reviewed_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),result_source=? WHERE id=? RETURNING id",
    status,url,couponId);
  return change?{status:'ok',id:couponId,label:statusLabel(status)}:{status:'missing'};
}
export function faqText(){
  return '❓ <b>CENTRE D’AIDE · FREE PRONOS</b>\n\n'+
    '<b>💎 À quoi servent les XP ?</b>\n<i>Ils permettent de débloquer des coupons. Ils ne sont ni de l’argent ni un gain garanti.</i>\n\n'+
    '<b>🎟️ Où sont mes coupons ?</b>\n<i>Dans le bouton 🎫 Mes coupons.</i>\n\n'+
    '<b>👥 Quand mon parrain gagne-t-il 30 XP ?</b>\n<i>Lorsque le filleul majeur valide les canaux obligatoires.</i>\n\n'+
    '<b>🔕 Puis-je couper les notifications ?</b>\n<i>Oui, dans Mes alertes (/alerts).</i>\n\n'+
    '<b>💬 Besoin d’aide ?</b>\n<i>Contacte notre équipe directement : /support ton message, puis suis tes demandes avec /mytickets.</i>\n\n'+
    '<blockquote>🔞 18+ · Aucun résultat garanti. Joue responsablement.</blockquote>';
}
export async function adminAnalytics(env,chat,send){
  const info=await one(env,
    "SELECT (SELECT count(*) FROM users) AS users,(SELECT count(*) FROM users WHERE required_verified=1) AS verified,"+
    "(SELECT count(*) FROM user_preferences WHERE notify_coupons=1) AS subscribers,"+
    "(SELECT count(*) FROM coupons) AS coupons,(SELECT count(*) FROM redemptions) AS redeemed,"+
    "(SELECT count(*) FROM engagement_claims) AS engagements,(SELECT count(*) FROM ledger) AS xp_events");
  return send(env,chat,'📈 <b>FREE PRONOS · ADMIN ANALYTICS</b>\n\n'+
    '<blockquote>👥 Membres : <b>'+info.users+'</b>\n✅ Vérifiés : <b>'+info.verified+'</b>\n'+
    '📣 Abonnés aux alertes : <b>'+info.subscribers+'</b>\n🎟️ Coupons : <b>'+info.coupons+'</b>\n'+
    '🔓 Déblocages : <b>'+info.redeemed+'</b>\n🏅 Missions quotidiennes/hebdo : <b>'+info.engagements+'</b>\n'+
    '💎 Opérations XP : <b>'+info.xp_events+'</b></blockquote>');
}
export async function navigate(env,uid,chat,callback,send,telegram,editId){
  if(callback==='nav:dashboard')return dashboard(env,uid,chat,send,telegram,editId);
  if(callback==='nav:xp')return xpScreen(env,uid,chat,send,telegram,editId);
  if(callback==='nav:history')return xpHistory(env,uid,chat,send,telegram,editId);
  if(callback==='nav:missions')return showMissions(env,uid,chat,send,telegram,editId);
  if(callback==='nav:alerts')return alerts(env,uid,chat,send,telegram,editId);
  if(callback==='nav:referrals')return referrals(env,uid,chat,send,telegram,editId);
  if(callback==='nav:coupons')return couponsFiltered(env,uid,chat,send,telegram,editId);
  if(callback.startsWith('filter:'))return couponsFiltered(env,uid,chat,send,telegram,editId,callback.slice(7));
  if(callback==='nav:results')return results(env,uid,chat,send,telegram,editId);
  if(callback==='nav:faq')return deliver(env,chat,faqText(),send,telegram,editId);
  return false;
}
export async function notificationBatch(env,telegram,max=12){
  // Envois soumis à consentement explicite; pas plus de 12 messages par cron.
  const queue=await all(env,
    "SELECT c.id AS coupon_id,c.title,c.total_odds,p.user_id AS uid,'new' AS kind,c.created_at AS date "+
    "FROM coupons c JOIN user_preferences p ON p.notify_coupons=1 "+
    "JOIN users u ON u.id=p.user_id AND u.adult_confirmed=1 AND u.required_verified=1 "+
    "WHERE c.active=1 AND c.result_status='available' AND c.expires_at>strftime('%Y-%m-%dT%H:%M:%fZ','now') "+
    "AND c.created_at>=strftime('%Y-%m-%dT%H:%M:%fZ','now','-3 days') "+
    "AND NOT EXISTS(SELECT 1 FROM coupon_notifications n WHERE n.user_id=p.user_id AND n.coupon_id=c.id AND n.kind='new') "+
    "ORDER BY c.created_at ASC LIMIT ?",Math.min(max,12));
  let sent=0;
  for(const item of queue){
    const reserved=await one(env,
      "INSERT OR IGNORE INTO coupon_notifications(user_id,coupon_id,kind) VALUES(?,?,'new') RETURNING user_id",item.uid,item.coupon_id);
    if(!reserved)continue;
    try{
      const delivered=await telegram(env,'sendMessage',{chat_id:item.uid,
        text:'🎟️ <b>NOUVEAU COUPON FREE PRONOS</b>\n\n🎯 <b>'+H(item.title)+'</b>\n📊 Cote totale : <b>'+H(item.total_odds)+'</b>\n\n<i>Ouvre le bot pour consulter les détails. Aucun résultat garanti.</i>',
        parse_mode:'HTML',reply_markup:{inline_keyboard:[[{text:'🎟️ Voir les coupons',callback_data:'nav:coupons',style:'primary'}]]}});
      await run(env,"UPDATE coupon_notifications SET sent_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE user_id=? AND coupon_id=? AND kind='new'",item.uid,item.coupon_id);
      try{await run(env,"INSERT INTO delivery_audit(user_id,delivery_type,coupon_id,telegram_message_id,status) VALUES(?,'coupon',?,?,'sent')",item.uid,item.coupon_id,delivered?.message_id||null);}catch(logError){console.warn('Audit log failure; message already sent',String(logError))}
      sent++;
    }catch(err){
      console.warn('Free Pronos notification failed',item.uid,String(err).slice(0,120));
      await run(env,"DELETE FROM coupon_notifications WHERE user_id=? AND coupon_id=? AND kind='new' AND sent_at IS NULL",item.uid,item.coupon_id);
    }
  }
  return {queued:queue.length,sent};
}

export async function resultNotificationBatch(env,telegram,max=8){
  // Utilisateurs ayant explicitement choisi les alertes de résultats.
  // Seuls les statuts finaux saisis par un administrateur sont annoncés.
  const queue=await all(env,
    "SELECT r.user_id AS uid,c.id AS coupon_id,c.title,c.result_status FROM coupons c "+
    "JOIN redemptions r ON r.coupon_id=c.id "+
    "JOIN user_preferences p ON p.user_id=r.user_id AND p.notify_results=1 "+
    "JOIN users u ON u.id=r.user_id AND u.adult_confirmed=1 AND u.required_verified=1 "+
    "WHERE c.result_status IN ('won','lost','void') AND c.result_reviewed_at IS NOT NULL "+
    "AND NOT EXISTS(SELECT 1 FROM coupon_notifications n WHERE n.user_id=r.user_id AND n.coupon_id=c.id AND n.kind='result') "+
    "ORDER BY c.result_reviewed_at ASC LIMIT ?",Math.min(max,8));
  let sent=0;
  for(const item of queue){
    const reserved=await one(env,
      "INSERT OR IGNORE INTO coupon_notifications(user_id,coupon_id,kind) VALUES(?,?,'result') RETURNING user_id",
      item.uid,item.coupon_id);
    if(!reserved)continue;
    try{
      const delivered=await telegram(env,'sendMessage',{
        chat_id:item.uid,text:'📊 <b>FREE PRONOS · RÉSULTAT VÉRIFIÉ</b>\n\n'+
          '🎟️ '+H(item.title)+'\n'+statusLabel(item.result_status)+
          '\n\n<i>Résultat renseigné par l’équipe après vérification. Aucun pronostic n’est garanti.</i>',
        parse_mode:'HTML'
      });
      await run(env,"UPDATE coupon_notifications SET sent_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE user_id=? AND coupon_id=? AND kind='result'",item.uid,item.coupon_id);
      try{await run(env,"INSERT INTO delivery_audit(user_id,delivery_type,coupon_id,telegram_message_id,status) VALUES(?,'result',?,?,'sent')",item.uid,item.coupon_id,delivered?.message_id||null);}catch(logError){console.warn('Audit log failure; message already sent',String(logError))}
      sent++;
    }catch(err){
      console.warn('Free Pronos results notification failed',item.uid,String(err).slice(0,120));
      await run(env,"DELETE FROM coupon_notifications WHERE user_id=? AND coupon_id=? AND kind='result' AND sent_at IS NULL",item.uid,item.coupon_id);
    }
  }
  return {queued:queue.length,sent};
}
