// Telegram webhook autonome : prêt pour Supabase Edge Functions.
import { createClient } from 'npm:@supabase/supabase-js@2.57.0';
import { parseCouponCommand, type Selection } from './coupon_logic.ts';

const token = Deno.env.get('XPRONOS_COUPON_BOT_TOKEN') || '';
const webhookSecret = Deno.env.get('XPRONOS_COUPON_WEBHOOK_SECRET') || '';
const adminIds = new Set((Deno.env.get('XPRONOS_COUPON_ADMIN_IDS') || '').split(',').map((x) => Number(x.trim())).filter((x) => Number.isSafeInteger(x) && x > 0));
const required: { id: string; url: string }[] = (() => {
  try {
    const a = JSON.parse(Deno.env.get('XPRONOS_COUPON_CHANNELS_JSON') || '[]');
    return Array.isArray(a) ? a.filter((x) => x && typeof x.id === 'string' && typeof x.url === 'string' && x.url.startsWith('https://t.me/')) : [];
  } catch { return []; }
})();
const siteUrl = 'https://mrxpronos.github.io/MrXPRONOS_App/';
const referralXp = 30;
const bonusXp = 5;
const requiredXp = 10;
const bonusCooldown = 2 * 3600;
const dbUrl = Deno.env.get('SUPABASE_URL') || '';
const secretKey = (() => {
  try { return JSON.parse(Deno.env.get('SUPABASE_SECRET_KEYS') || '{}').default || Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || ''; }
  catch { return Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || ''; }
})();
const db = createClient(dbUrl, secretKey, { auth: { persistSession: false, autoRefreshToken: false } });
const TG_API = `https://api.telegram.org/bot${token}/`;
const buttons = [['🎟️ Coupons cote 4+', '🎫 Mes coupons'], ['🚩 Tâche', '🎁 Bonus'], ['⭐ Mes XP', '↗️ Partager'], ['✅ Vérifier', '📋 Procédure']];
const keyboard = { keyboard: buttons.map((r) => r.map((text) => ({ text }))), resize_keyboard: true };
const json = (x: unknown) => JSON.stringify(x);
const limit = (s: string) => s.slice(0, 3600);
function escapeHtml(s: unknown): string { return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'); }

async function tg(method: string, data: Record<string, unknown>): Promise<any> {
  const resp = await fetch(TG_API + method, { method: 'POST', headers: { 'content-type':'application/json' }, body: json(data), signal: AbortSignal.timeout(8500) });
  const parsed = await resp.json();
  if (!resp.ok || !parsed.ok) throw Error(`Telegram ${method}: ${resp.status} ${String(parsed.description || '').slice(0,160)}`);
  return parsed.result;
}
async function say(chatId: number, text: string, markup?: unknown) {
  return tg('sendMessage', { chat_id:chatId, text:limit(text), parse_mode:'HTML', reply_markup: markup || keyboard, disable_web_page_preview:true });
}
async function ack(id: string, text = '') { try { await tg('answerCallbackQuery',{callback_query_id:id,text: text.slice(0,180)}); } catch(err){console.warn('ack',String(err));} }
function menu() { return keyboard; }
function inline(rows: { text: string; callback_data?: string; url?: string }[][]) { return { inline_keyboard: rows }; }
async function rpc(name:string, args:Record<string,unknown>):Promise<any> {
  const { data, error } = await db.rpc(name, args);
  if (error) throw Error(`${name}: ${error.message}`);
  return data;
}
async function query(table:string, spec:(q:any)=>any) {
  const { data, error } = await spec(db.from(table).select('*'));
  if(error) throw Error(`${table}: ${error.message}`);
  return data || [];
}
async function user(uid:number) {
  const arr=await query('xpronos_bot_users',(q:any)=>q.eq('id',uid).limit(1));
  return arr[0] || null;
}
async function joined(uid:number,channel:string):Promise<boolean> {
  try {
    const member=await tg('getChatMember',{chat_id:channel,user_id:uid});
    return member.status==='creator'||member.status==='administrator'||member.status==='member'||(member.status==='restricted'&&member.is_member===true);
  } catch(err){console.warn('membership failed',channel,String(err)); return false;}
}
async function requirements(uid:number):Promise<boolean> {
  for(const c of required) if(!(await joined(uid,c.id))) return false;
  return true;
}
async function verify(uid:number, chatId:number) {
  const u=await user(uid);
  if(!u?.adult_confirmed) return say(chatId,'🔞 Confirme d’abord que tu as 18 ans ou plus avec /start.');
  if(!(await requirements(uid))) {
    const rows: {text:string;url?:string;callback_data?:string}[][]=required.map((c)=>[{text:'📢 Rejoindre le canal',url:c.url}]);
    rows.push([{text:'✅ Vérifier',callback_data:'verify'}]);
    return say(chatId,'Rejoins les canaux ci-dessous puis appuie sur ✅ Vérifier. Le bot doit être administrateur du canal pour contrôler l’abonnement.',inline(rows));
  }
  const result=await rpc('xpronos_bot_verify',{p_uid:uid,p_reward:referralXp,p_enabled:required.length>0});
  await say(chatId,`✅ Abonnement vérifié !${result.status==='credited'?' Le parrain a reçu ses XP.':''}`,menu());
}
async function showTasks(uid:number,chatId:number) {
  const u=await user(uid);
  if(!u?.adult_confirmed||!u?.required_verified) return say(chatId,'🔒 Confirme ton âge et valide les canaux via ✅ Vérifier.');
  const tasks=await query('xpronos_bot_tasks',(q:any)=>q.eq('active',true).order('id',{ascending:false}).limit(25));
  const claims=await query('xpronos_bot_task_claims',(q:any)=>q.eq('user_id',uid));
  const done=new Set(claims.map((c:any)=>String(c.task_id)));
  const rows:any[][]=[];
  for(const task of tasks) {
    if(done.has(String(task.id))) continue;
    rows.push([{text:`📢 Canal (+${task.xp} XP)`,url:task.url},{text:'✅ Check',callback_data:`task:${task.id}`}]);
  }
  return say(chatId, rows.length?'🚩 Missions disponibles : rejoins le canal, puis appuie sur Check.':'✅ Toutes les missions disponibles sont terminées.',rows.length?inline(rows):menu());
}
async function claimTask(uid:number,chatId:number,id:number) {
  const rows=await query('xpronos_bot_tasks',(q:any)=>q.eq('id',id).eq('active',true).limit(1));
  const task=rows[0];
  if(!task) return say(chatId,'Mission indisponible.');
  if(!(await joined(uid,task.chat_id))) return say(chatId,'Tu dois d’abord rejoindre ce canal, puis appuyer sur Check.',inline([[{text:'📢 Rejoindre',url:task.url}],[{text:'✅ Check',callback_data:`task:${id}`}]]));
  const response=await rpc('xpronos_bot_claim_task',{p_uid:uid,p_task:id});
  const messages:Record<string,string>={ok:`✅ +${response.xp} XP ajoutés !`,already:'Cette mission a déjà été récompensée.',locked:'🔒 Vérifie d’abord les canaux requis.',missing:'Mission non disponible.'};
  return say(chatId,messages[response.status]||'Mission indisponible.');
}
async function bonus(uid:number, chatId:number) {
  const r=await rpc('xpronos_bot_bonus',{p_uid:uid,p_points:bonusXp,p_cooldown_seconds:bonusCooldown,p_daily_cap:requiredXp});
  const text:Record<string,string>={ok:`🎁 Bravo ! +${bonusXp} XP.`,cap:'🎁 Plafond quotidien atteint. Reviens demain (UTC).',locked:'🔒 Confirme ton âge et vérifie les canaux requis.',invalid:'Bonus temporairement indisponible.'};
  return say(chatId,r.status==='wait'?`⏳ Prochain bonus dans ${Math.ceil((r.seconds||0)/60)} minutes.`:text[r.status]||'Bonus indisponible.');
}
function displayCoupon(c:any, details=false):string {
  let t=`🎟️ <b>${escapeHtml(c.title)}</b> [${escapeHtml(c.tier)}]\nCote totale : <b>${escapeHtml(c.total_odds)}</b>\nCoût : ${c.xp_cost} XP`;
  if(details) for(const s of (c.selections || []) as Selection[]) t+=`\n• ${escapeHtml(s.match)} — ${escapeHtml(s.market)} (${escapeHtml(s.odds)})`;
  return t;
}
async function coupons(uid:number,chatId:number) {
  const u=await user(uid);
  if(!u?.adult_confirmed||!u?.required_verified) return say(chatId,'🔒 Confirme ton âge et valide les canaux requis.');
  const now=new Date().toISOString();
  const rows=await query('xpronos_bot_coupons',(q:any)=>q.eq('active',true).gt('expires_at',now).neq('stock',0).order('created_at',{ascending:false}).limit(10));
  if(!rows.length) return say(chatId,'📭 Aucun coupon cote 4+ disponible actuellement.');
  await say(chatId,`🎟️ Coupons actuellement disponibles (${rows.length}) :\nLes cotes sont indicatives, les paris comportent des risques.`,menu());
  for(const c of rows) await say(chatId,displayCoupon(c),inline([[{text:`🔓 Débloquer pour ${c.xp_cost} XP`,callback_data:`coupon:${c.id}`}]]));
}
async function redeem(uid:number,chatId:number,couponId:number) {
  const r=await rpc('xpronos_bot_redeem',{p_uid:uid,p_coupon:couponId});
  const messages:Record<string,string>={ok:'✅ Coupon débloqué. Consulte 🎫 Mes coupons pour voir les détails.',locked:'🔒 Confirme ton âge et valide les canaux.',unavailable:'Coupon épuisé ou expiré.',already:'Ce coupon est déjà dans 🎫 Mes coupons.',xp:'XP insuffisants. Accomplis des missions ou réclame ton bonus.'};
  return say(chatId,messages[r.status]||'Impossible de débloquer ce coupon.');
}
async function mine(uid:number,chatId:number) {
  const rows=await query('xpronos_bot_redemptions',(q:any)=>q.eq('user_id',uid).order('claimed_at',{ascending:false}).limit(10));
  if(!rows.length) return say(chatId,'🎫 Tu n’as pas encore débloqué de coupon.');
  for(const r of rows) {
    const c={...r.snapshot,xp_cost:r.xp_spent};
    await say(chatId,`${displayCoupon(c,true)}\n\n⚠️ Vérifie les cotes en direct avant tout pari. 18+ • Joue responsablement.`,menu());
  }
}
async function share(uid:number,chatId:number) {
  const me=await tg('getMe',{});
  const refLink=`https://t.me/${me.username}?start=ref_${uid}`;
  return say(chatId,`↗️ <b>Ton lien de parrainage</b>\n${escapeHtml(refLink)}\n\n${required.length ? `Invite des amis : +${referralXp} XP après vérification réelle de leurs abonnements.` : 'Le parrainage est temporairement désactivé tant qu’aucun canal obligatoire n’est configuré.'}`);
}
async function showXp(uid:number,chatId:number) {
  const u=await user(uid);
  if(!u) return say(chatId,'Commence par /start.');
  const referrals=await query('xpronos_bot_users',(q:any)=>q.eq('referred_by',uid).eq('referral_rewarded',true));
  return say(chatId,`⭐ <b>Mes XP</b>\nSolde : <b>${u.xp} XP</b>\nParrainages validés : ${referrals.length}\n\nLes XP sont virtuels, non convertibles en argent et non retirables.`);
}
async function admin(uid:number,chatId:number,raw:string) {
  if(!adminIds.has(uid)) return say(chatId,'⛔ Commande réservée aux administrateurs.');
  const [name]=raw.split(/\s+/);
  const arg=raw.slice(name.length).trim();
  if(name==='/admin') return say(chatId,'🛠️ <b>Administration XPRONOS 4+</b>\n/addcoupon PRO | 50 | 2099-01-01T18:00 | -1 | Titre | Équipe A - B ; Plus 1,5 ; 1.70 | Équipe C - D ; 1X ; 2.40\n/listcoupons\n/delcoupon ID\n/activatecoupon ID\n/addtask @canal https://t.me/canal 15\n/listtasks\n/deltask ID\n/grantxp USER_ID 30\n/stats');
  if(name==='/addcoupon') {
    const coupon=parseCouponCommand(arg);
    const {error}=await db.from('xpronos_bot_coupons').insert(coupon);
    if(error) throw Error(error.message);
    return say(chatId,`✅ Coupon ajouté : cote ${coupon.total_odds}, ${coupon.xp_cost} XP.`);
  }
  if(name==='/listcoupons') {
    const rows=await query('xpronos_bot_coupons',(q:any)=>q.order('id',{ascending:false}).limit(20));
    return say(chatId,rows.map((c:any)=>`#${c.id} ${c.active?'✅':'❌'} ${escapeHtml(c.tier)} • ${escapeHtml(c.title)} • ${c.total_odds} • stock ${c.stock}`).join('\n')||'Aucun coupon.');
  }
  if(name==='/delcoupon'||name==='/activatecoupon') {
    const id=Number(arg);
    if(!Number.isSafeInteger(id)||id<1) return say(chatId,'ID invalide.');
    const upd=db.from('xpronos_bot_coupons').update({active:name==='/activatecoupon'}).eq('id',id);
    const {error}=await (name==='/activatecoupon'?upd.gt('expires_at',new Date().toISOString()):upd);
    if(error)throw Error(error.message);
    return say(chatId,'✅ Modification du coupon enregistrée.');
  }
  if(name==='/addtask') {
    const parts=arg.split(/\s+/);
    if(parts.length!==3 || !/^(@[A-Za-z0-9_]{5,}|-100\d{5,})$/.test(parts[0]) || !/^https:\/\/t\.me\//.test(parts[1]) || !/^\d{1,5}$/.test(parts[2]) || Number(parts[2])<1) return say(chatId,'Format : /addtask @canal https://t.me/canal 15');
    const {error}=await db.from('xpronos_bot_tasks').insert({chat_id:parts[0],url:parts[1],xp:Number(parts[2])});
    if(error)return say(chatId,`Mission non ajoutée (canal déjà présent ou données invalides) : ${escapeHtml(error.message)}`);
    return say(chatId,'✅ Mission ajoutée.');
  }
  if(name==='/listtasks') {
    const rows=await query('xpronos_bot_tasks',(q:any)=>q.order('id',{ascending:false}).limit(30));
    return say(chatId,rows.map((t:any)=>`#${t.id} ${t.active?'✅':'❌'} ${escapeHtml(t.chat_id)} (+${t.xp} XP)`).join('\n')||'Aucune mission.');
  }
  if(name==='/deltask') {
    const id=Number(arg); if(!Number.isSafeInteger(id)||id<1) return say(chatId,'ID invalide.');
    const {error}=await db.from('xpronos_bot_tasks').update({active:false}).eq('id',id);if(error)throw Error(error.message);
    return say(chatId,'✅ Mission désactivée.');
  }
  if(name==='/grantxp') {
    const parts=arg.split(/\s+/);const u=Number(parts[0]);const xp=Number(parts[1]);
    if(parts.length!==2||!Number.isSafeInteger(u)||u<1||!Number.isInteger(xp)||xp<1||xp>100000)return say(chatId,'Format : /grantxp 123456789 30');
    const r=await rpc('xpronos_bot_grant',{p_uid:u,p_xp:xp});
    return say(chatId,r.status==='ok'?'✅ XP crédités.':'Utilisateur introuvable.');
  }
  if(name==='/stats') {
    const count=async(table:string)=>{ const {count,error}=await db.from(table).select('*',{count:'exact',head:true});if(error)throw Error(error.message);return count??0;};
    const [users,tasks,coupons,redemptions]=await Promise.all(['xpronos_bot_users','xpronos_bot_tasks','xpronos_bot_coupons','xpronos_bot_redemptions'].map(count));
    return say(chatId,`📊 Membres : ${users}\nMissions : ${tasks}\nCoupons : ${coupons}\nCoupons débloqués : ${redemptions}`);
  }
}
async function handle(update:any) {
  const q=update.callback_query;
  const m=q?.message || update.message;
  const from=q?.from || update.message?.from;
  if(!m||!from||m.chat?.type!=='private'||!Number.isSafeInteger(from.id))return;
  const uid=from.id as number;
  const chatId=m.chat.id as number;
  const text=String(update.message?.text||'').trim();
  const fullName=[from.first_name||'',from.last_name||''].join(' ').trim()||from.username||'Membre';
  const referral=/^\/start(?:@\w+)?\s+ref_(\d+)$/.exec(text)?.[1];
  await rpc('xpronos_bot_register',{p_uid:uid,p_name:fullName,p_ref:referral?Number(referral):null});
  if(q){
    const data=String(q.data||'');
    await ack(q.id);
    if(data==='adult_yes'){
      const {error}=await db.from('xpronos_bot_users').update({adult_confirmed:true}).eq('id',uid);if(error)throw Error(error.message);
      await say(chatId,'✅ Merci. Vérifie maintenant les canaux pour activer tes récompenses.');
      return verify(uid,chatId);
    }
    if(data==='adult_no')return say(chatId,'🔞 Ce service est réservé aux adultes.');
    if(data==='verify')return verify(uid,chatId);
    if(/^task:\d+$/.test(data))return claimTask(uid,chatId,Number(data.split(':')[1]));
    if(/^coupon:\d+$/.test(data))return redeem(uid,chatId,Number(data.split(':')[1]));
    return;
  }
  if(/^\/start(?:@\w+)?(?:\s|$)/.test(text)){
    const userRow=await user(uid);
    await say(chatId,`⚽ Bienvenue sur <b>XPRONOS 4+</b> !\n\nAccomplis des missions, gagne des XP et débloque des coupons de cote <b>4.00 ou plus</b>.\n\n⚠️ Aucun résultat n’est garanti. 18+ • Joue responsablement.`);
    if(!userRow?.adult_confirmed) return say(chatId,'🔞 Confirme que tu as 18 ans ou plus :',inline([[{text:'✅ Oui, 18 ans ou plus',callback_data:'adult_yes'}],[{text:'❌ Non',callback_data:'adult_no'}]]));
    return verify(uid,chatId);
  }
  if(text.startsWith('/')) {
    const cmd=text.split(/\s+/)[0].split('@')[0];
    const adminCommands=new Set(['/admin','/addcoupon','/listcoupons','/delcoupon','/activatecoupon','/addtask','/listtasks','/deltask','/grantxp','/stats']);
    if(adminCommands.has(cmd))return admin(uid,chatId,cmd+text.slice(text.split(/\s+/)[0].length));
  }
  if(text==='✅ Vérifier'||text==='/verify')return verify(uid,chatId);
  if(text==='🚩 Tâche'||text==='/tasks')return showTasks(uid,chatId);
  if(text==='🎁 Bonus'||text==='/bonus')return bonus(uid,chatId);
  if(text==='⭐ Mes XP'||text==='/xp')return showXp(uid,chatId);
  if(text==='🎟️ Coupons cote 4+'||text==='/coupons')return coupons(uid,chatId);
  if(text==='🎫 Mes coupons'||text==='/mine')return mine(uid,chatId);
  if(text==='↗️ Partager'||text==='/share')return share(uid,chatId);
  if(text==='📋 Procédure'||text==='/help')return say(chatId,`1️⃣ Confirme tes 18 ans et vérifie les canaux.\n2️⃣ Accomplis des tâches pour gagner des XP.\n3️⃣ Récupère un bonus toutes les 2 heures (maximum 10 XP/jour).\n4️⃣ Débloque des coupons cote 4+ avec tes XP.\n\nLes XP ne sont jamais échangeables contre de l'argent.\n${siteUrl}`);
  return say(chatId,'Utilise les boutons du menu ou envoie /start.');
}
Deno.serve(async(req:Request)=>{
  if(req.method!=='POST')return new Response('Not found',{status:404});
  if(!token||!webhookSecret||!dbUrl||!secretKey||!adminIds.size)return new Response('Not configured',{status:503});
  const incoming=req.headers.get('x-telegram-bot-api-secret-token')||'';
  if(incoming!==webhookSecret)return new Response('Forbidden',{status:403});
  try{
    const data=await req.json();
    if(!Number.isSafeInteger(data.update_id))return new Response('Bad request',{status:400});
    await handle(data);
    return new Response('ok',{status:200});
  }catch(err){console.error('Webhook processing failed',String(err));return new Response('retry',{status:500});}
});
