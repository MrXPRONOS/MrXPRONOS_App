// XPRONOS 4+ : webhook Telegram Cloudflare Workers + D1.
// Aucune dépendance Supabase. Les crédits XP sont virtuels et non monétaires.
import {parseCouponCommand} from './logic.js';

const POINTS_REFERRAL=30,POINTS_BONUS=5,DAILY_CAP=10,COOLDOWN=2*3600000;
const SITE='https://mrxpronos.github.io/MrXPRONOS_App/';
const MENU={keyboard:[
  [{text:'🎟️ Coupons cote 4+'},{text:'🎫 Mes coupons'}],
  [{text:'🚩 Tâche'},{text:'🎁 Bonus'}],
  [{text:'⭐ Mes XP'},{text:'↗️ Partager'}],
  [{text:'✅ Vérifier'},{text:'📋 Procédure'}]
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
const send=(env,chat,text,reply=MENU)=>telegram(env,'sendMessage',{
  chat_id:chat,text:pad(text),parse_mode:'HTML',reply_markup:reply,disable_web_page_preview:true
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
  if(!u?.adult_confirmed)return send(env,chat,'🔞 Confirme d’abord que tu as 18 ans ou plus avec /start.');
  const required=channels(env);
  if(!(await requirements(env,uid))){
    const rows=required.map(c=>[{text:'📢 Rejoindre le canal',url:c.url}]);
    rows.push([{text:'✅ Vérifier',callback_data:'verify'}]);
    return send(env,chat,'Rejoins les canaux obligatoires, puis appuie sur ✅ Vérifier. Le bot doit être administrateur du canal.',inline(rows));
  }
  const ref=required.length>0 && !!u.referred_by && !u.referral_rewarded;
  await run(env,'UPDATE users SET required_verified=1, referral_rewarded=CASE WHEN ?=1 THEN 1 ELSE referral_rewarded END WHERE id=? AND adult_confirmed=1',ref?1:0,uid);
  return send(env,chat,'✅ Abonnement vérifié !'+(ref?' Le parrain a reçu '+POINTS_REFERRAL+' XP.':''));
}
async function tasks(env,uid,chat) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 Confirme ton âge et valide les canaux via ✅ Vérifier.');
  const ts=await all(env,'SELECT t.* FROM tasks t WHERE t.active=1 AND NOT EXISTS (SELECT 1 FROM task_claims c WHERE c.task_id=t.id AND c.user_id=?) ORDER BY t.id DESC LIMIT 25',uid);
  const rows=ts.map(t=>[{text:'📢 Canal (+'+t.xp+' XP)',url:t.url},{text:'✅ Check',callback_data:'task:'+t.id}]);
  return send(env,chat,rows.length?'🚩 Missions disponibles : rejoins chaque canal puis appuie sur Check.':'✅ Toutes les missions sont terminées.',rows.length?inline(rows):MENU);
}
async function claimTask(env,uid,chat,id) {
  const t=await one(env,'SELECT * FROM tasks WHERE id=? AND active=1',id);
  if(!t)return send(env,chat,'Mission indisponible.');
  if(!(await joined(env,uid,t.chat_id)))return send(env,chat,'Tu dois rejoindre ce canal avant la validation.',inline([[{text:'📢 Rejoindre',url:t.url}],[{text:'✅ Check',callback_data:'task:'+id}]]));
  const res=await one(env,'INSERT OR IGNORE INTO task_claims(user_id,task_id) SELECT ?,t.id FROM tasks t JOIN users u ON u.id=? WHERE t.id=? AND t.active=1 AND u.adult_confirmed=1 AND u.required_verified=1 RETURNING user_id',uid,uid,id);
  return send(env,chat,res?'✅ +'+t.xp+' XP ajoutés !':'Mission déjà récompensée ou compte non vérifié.');
}
async function bonus(env,uid,chat) {
  const now=new Date(),iso=now.toISOString(),day=iso.slice(0,10),cutoff=new Date(now.getTime()-COOLDOWN).toISOString();
  const r=await one(env,
    'UPDATE users SET xp=xp+5,bonus_last_at=?,bonus_day=?,bonus_day_total=CASE WHEN bonus_day=? THEN bonus_day_total+5 ELSE 5 END '+
    'WHERE id=? AND adult_confirmed=1 AND required_verified=1 AND (bonus_day IS NULL OR bonus_day<>? OR bonus_day_total<=?) '+
    'AND (bonus_last_at IS NULL OR bonus_last_at<=?) RETURNING xp',
    iso,day,day,uid,day,DAILY_CAP-POINTS_BONUS,cutoff);
  if(r)return send(env,chat,'🎁 Bravo ! +'+POINTS_BONUS+' XP.');
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 Confirme ton âge et vérifie les canaux requis.');
  if(u.bonus_day===day&&u.bonus_day_total+POINTS_BONUS>DAILY_CAP)return send(env,chat,'🎁 Plafond quotidien atteint. Reviens demain (UTC).');
  const minutes=Math.ceil((COOLDOWN-(now.getTime()-new Date(u.bonus_last_at).getTime()))/60000);
  return send(env,chat,'⏳ Prochain bonus dans '+Math.max(1,minutes)+' minutes.');
}
function pretty(c,details=false) {
  let txt='🎟️ <b>'+html(c.title)+'</b> ['+html(c.tier)+']\nCote totale : <b>'+html(c.total_odds)+'</b>\nCoût : '+c.xp_cost+' XP';
  if(details)for(const x of safeJson(c.selections,[]))txt+='\n• '+html(x.match)+' — '+html(x.market)+' ('+html(x.odds)+')';
  return txt;
}
async function coupons(env,uid,chat) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 Confirme ton âge et valide les canaux.');
  const rows=await all(env,'SELECT * FROM coupons WHERE active=1 AND expires_at>? AND stock<>0 ORDER BY created_at DESC,id DESC LIMIT 10',new Date().toISOString());
  if(!rows.length)return send(env,chat,'📭 Aucun coupon cote 4+ disponible actuellement.');
  await send(env,chat,'🎟️ Coupons disponibles ('+rows.length+') : les cotes sont indicatives, aucun résultat garanti.');
  for(const c of rows)await send(env,chat,pretty(c),inline([[{text:'🔓 Débloquer pour '+c.xp_cost+' XP',callback_data:'coupon:'+c.id}]]));
}
async function redeem(env,uid,chat,id) {
  const u=await user(env,uid);
  if(!u?.adult_confirmed||!u?.required_verified)return send(env,chat,'🔒 Confirme ton âge et valide les canaux.');
  // INSERT atomique + trigger : la déduction XP et la baisse du stock ne peuvent pas être séparées.
  const r=await one(env,
    "INSERT OR IGNORE INTO redemptions(user_id,coupon_id,snapshot,xp_spent) "+
    "SELECT ?,c.id,json_object('title',c.title,'tier',c.tier,'total_odds',c.total_odds,'selections',json(c.selections),'expires_at',c.expires_at),c.xp_cost "+
    "FROM coupons c JOIN users u ON u.id=? WHERE c.id=? AND c.active=1 AND c.expires_at>? AND c.stock<>0 "+
    "AND u.adult_confirmed=1 AND u.required_verified=1 AND u.xp>=c.xp_cost RETURNING coupon_id",
    uid,uid,id,new Date().toISOString());
  if(r)return send(env,chat,'✅ Coupon débloqué. Consulte 🎫 Mes coupons.');
  const already=await one(env,'SELECT 1 AS yes FROM redemptions WHERE user_id=? AND coupon_id=?',uid,id);
  if(already)return send(env,chat,'Ce coupon est déjà dans 🎫 Mes coupons.');
  const c=await one(env,'SELECT * FROM coupons WHERE id=?',id);
  if(!c||!c.active||c.stock===0||c.expires_at<=new Date().toISOString())return send(env,chat,'Coupon épuisé ou expiré.');
  return send(env,chat,'XP insuffisants. Accomplis des missions ou réclame ton bonus.');
}
async function mine(env,uid,chat) {
  const rows=await all(env,'SELECT snapshot,xp_spent FROM redemptions WHERE user_id=? ORDER BY claimed_at DESC LIMIT 10',uid);
  if(!rows.length)return send(env,chat,'🎫 Tu n’as pas encore débloqué de coupon.');
  for(const row of rows){
    const c=safeJson(row.snapshot,{});
    c.xp_cost=row.xp_spent;
    c.selections=JSON.stringify(c.selections||[]);
    await send(env,chat,pretty(c,true)+'\n\n⚠️ Vérifie les cotes en direct. 18+ • Joue responsablement.');
  }
}
async function xp(env,uid,chat) {
  const u=await user(env,uid);
  if(!u)return send(env,chat,'Commence par /start.');
  const refs=await one(env,'SELECT count(*) AS n FROM users WHERE referred_by=? AND referral_rewarded=1',uid);
  return send(env,chat,'⭐ <b>Mes XP</b>\nSolde : <b>'+u.xp+' XP</b>\nParrainages validés : '+refs.n+'\n\nLes XP sont virtuels, non convertibles en argent.');
}
async function share(env,uid,chat) {
  const me=await telegram(env,'getMe',{});
  return send(env,chat,'↗️ <b>Ton lien de parrainage</b>\nhttps://t.me/'+html(me.username)+'?start=ref_'+uid+'\n\n'+
    (channels(env).length?'Invite des amis : +'+POINTS_REFERRAL+' XP après vérification réelle des canaux.':'Le parrainage est désactivé jusqu’à configuration d’un canal obligatoire.'));
}
async function admin(env,uid,chat,raw,updateId){
  if(!admins(env).has(uid))return send(env,chat,'⛔ Commande réservée aux administrateurs.');
  const name=raw.split(/\s+/)[0],arg=raw.slice(name.length).trim();
  if(name==='/admin')return send(env,chat,'🛠️ <b>Administration XPRONOS 4+</b>\n/addcoupon PRO | 50 | 2099-01-01T18:00 | -1 | Titre | Équipe A - B ; Plus 1,5 ; 1.70 | Équipe C - D ; 1X ; 2.40\n/listcoupons\n/delcoupon ID\n/activatecoupon ID\n/addtask @canal https://t.me/canal 15\n/listtasks\n/deltask ID\n/grantxp USER_ID 30\n/stats');
  if(name==='/addcoupon'){
    const c=parseCouponCommand(arg);
    await run(env,'INSERT INTO coupons(tier,title,selections,total_odds,xp_cost,expires_at,stock) VALUES(?,?,?,?,?,?,?)',
      c.tier,c.title,c.selections,c.total_odds,c.xp_cost,c.expires_at,c.stock);
    return send(env,chat,'✅ Coupon ajouté : cote '+c.total_odds+', '+c.xp_cost+' XP.');
  }
  if(name==='/listcoupons'){
    const rows=await all(env,'SELECT * FROM coupons ORDER BY id DESC LIMIT 20');
    return send(env,chat,rows.map(c=>'#'+c.id+' '+(c.active?'✅':'❌')+' '+html(c.tier)+' • '+html(c.title)+' • '+c.total_odds+' • stock '+c.stock).join('\n')||'Aucun coupon.');
  }
  if(name==='/delcoupon'||name==='/activatecoupon'){
    const id=Number(arg);
    if(!Number.isSafeInteger(id)||id<1)return send(env,chat,'ID invalide.');
    const active=name==='/activatecoupon'?1:0;
    await run(env,'UPDATE coupons SET active=? WHERE id=? AND (?=0 OR expires_at>?)',active,id,active,new Date().toISOString());
    return send(env,chat,'✅ Modification du coupon enregistrée.');
  }
  if(name==='/addtask'){
    const bits=arg.split(/\s+/),[channel,url,cost]=bits;
    if(bits.length!==3||!/^(@[\w]{5,}|-100\d{5,})$/.test(channel)||!/^https:\/\/t\.me\//.test(url)||!/^\d{1,5}$/.test(cost)||Number(cost)<1)return send(env,chat,'Format : /addtask @canal https://t.me/canal 15');
    const r=await run(env,'INSERT OR IGNORE INTO tasks(chat_id,url,xp) VALUES(?,?,?)',channel,url,Number(cost));
    return send(env,chat,r.meta.changes?'✅ Mission ajoutée.':'Canal déjà enregistré.');
  }
  if(name==='/listtasks'){
    const rows=await all(env,'SELECT * FROM tasks ORDER BY id DESC LIMIT 30');
    return send(env,chat,rows.map(t=>'#'+t.id+' '+(t.active?'✅':'❌')+' '+html(t.chat_id)+' (+'+t.xp+' XP)').join('\n')||'Aucune mission.');
  }
  if(name==='/deltask'){
    const id=Number(arg);
    if(!Number.isSafeInteger(id)||id<1)return send(env,chat,'ID invalide.');
    await run(env,'UPDATE tasks SET active=0 WHERE id=?',id);
    return send(env,chat,'✅ Mission désactivée.');
  }
  if(name==='/grantxp'){
    const bits=arg.split(/\s+/),userId=Number(bits[0]),points=Number(bits[1]);
    if(bits.length!==2||!Number.isSafeInteger(userId)||userId<1||!Number.isInteger(points)||points<1||points>100000)
      return send(env,chat,'Format : /grantxp 123456789 30');
    const grant=await one(env,'INSERT OR IGNORE INTO manual_grants(user_id,xp,update_id) SELECT ?,?,? WHERE EXISTS(SELECT 1 FROM users WHERE id=?) RETURNING id',userId,points,updateId,userId);
    return send(env,chat,grant?'✅ XP crédités.':'Utilisateur introuvable ou commande déjà appliquée.');
  }
  if(name==='/stats'){
    const r=await one(env,'SELECT (SELECT count(*) FROM users) AS members,(SELECT count(*) FROM tasks) AS tasks,(SELECT count(*) FROM coupons) AS coupons,(SELECT count(*) FROM redemptions) AS redemptions');
    return send(env,chat,'📊 Membres : '+r.members+'\nMissions : '+r.tasks+'\nCoupons : '+r.coupons+'\nCoupons débloqués : '+r.redemptions);
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
    if(data==='adult_yes'){
      await run(env,'UPDATE users SET adult_confirmed=1 WHERE id=?',uid);
      await send(env,chat,'✅ Merci. Vérifie les canaux pour activer tes récompenses.');
      return verify(env,uid,chat);
    }
    if(data==='adult_no')return send(env,chat,'🔞 Ce service est réservé aux adultes.');
    if(data==='verify')return verify(env,uid,chat);
    if(/^task:\d+$/.test(data))return claimTask(env,uid,chat,Number(data.split(':')[1]));
    if(/^coupon:\d+$/.test(data))return redeem(env,uid,chat,Number(data.split(':')[1]));
    return;
  }
  if(/^\/start(?:@\w+)?(?:\s|$)/.test(txt)){
    const u=await user(env,uid);
    await send(env,chat,'⚽ Bienvenue sur <b>XPRONOS 4+</b> !\n\nAccomplis des missions, gagne des XP et débloque des coupons de cote <b>4.00 ou plus</b>.\n\n⚠️ Aucun résultat garanti. 18+ • Joue responsablement.');
    if(!u?.adult_confirmed)return send(env,chat,'🔞 Confirme que tu as 18 ans ou plus :',inline([[{text:'✅ Oui, 18 ans ou plus',callback_data:'adult_yes'}],[{text:'❌ Non',callback_data:'adult_no'}]]));
    return verify(env,uid,chat);
  }
  if(txt.startsWith('/')){
    const command=txt.split(/\s+/)[0].split('@')[0];
    const names=new Set(['/admin','/addcoupon','/listcoupons','/delcoupon','/activatecoupon','/addtask','/listtasks','/deltask','/grantxp','/stats']);
    if(names.has(command))return admin(env,uid,chat,command+txt.slice(txt.split(/\s+/)[0].length),update.update_id);
  }
  if(txt==='✅ Vérifier'||txt==='/verify')return verify(env,uid,chat);
  if(txt==='🚩 Tâche'||txt==='/tasks')return tasks(env,uid,chat);
  if(txt==='🎁 Bonus'||txt==='/bonus')return bonus(env,uid,chat);
  if(txt==='⭐ Mes XP'||txt==='/xp')return xp(env,uid,chat);
  if(txt==='🎟️ Coupons cote 4+'||txt==='/coupons')return coupons(env,uid,chat);
  if(txt==='🎫 Mes coupons'||txt==='/mine')return mine(env,uid,chat);
  if(txt==='↗️ Partager'||txt==='/share')return share(env,uid,chat);
  if(txt==='📋 Procédure'||txt==='/help')return send(env,chat,'1️⃣ Confirme tes 18 ans et vérifie les canaux.\n2️⃣ Accomplis des missions pour gagner des XP.\n3️⃣ Bonus de 5 XP toutes les 2 heures (maximum 10 XP/jour).\n4️⃣ Débloque les coupons cote 4+ avec tes XP.\n\nLes XP ne représentent pas de l’argent.\n'+SITE);
  return send(env,chat,'Utilise les boutons du menu ou envoie /start.');
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
    if(!env.DB||!env.CF_BOT_TOKEN||!env.CF_BOT_WEBHOOK_SECRET||!admins(env).size)return out('Not configured',{status:503});
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
