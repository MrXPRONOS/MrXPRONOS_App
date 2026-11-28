const now=()=>Math.floor(Date.now()/1000);
const id=x=>String(x);
const slug=s=>typeof s==='string' && /^[a-z0-9_-]{1,24}$/.test(s);
const row=(db,sql,...args)=>db.prepare(sql).bind(...args).first();
const run=(db,sql,...args)=>db.prepare(sql).bind(...args).run();
const all=async(db,sql,...args)=>(await db.prepare(sql).bind(...args).all()).results;
const stmt=(db,sql,...args)=>db.prepare(sql).bind(...args);
const cb=(text,callback_data)=>({text,callback_data});
const urlButton=(text,url)=>({text,url});
const menu=[[cb('📚 Catalogue','catalogue'),cb('📖 Livres gratuits','gratuit')],[cb('🎁 Parrainage','parrainage'),cb('📊 Mes invitations','progression')],[cb('📂 Ma bibliothèque','bibliotheque'),cb('❔ Assistance','help')]];
const home=[cb('🏠 Accueil','home')];
const member=m=>['member','administrator','creator'].includes(m?.status)||(m?.status==='restricted'&&m.is_member===true);
const validChannel=s=>typeof s==='string'&&/^-100\d+$/.test(s);
const validJoinURL=s=>typeof s==='string'&&/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]+|joinchat\/[A-Za-z0-9_-]+|[A-Za-z0-9_]{5,})$/.test(s);
const admins=e=>new Set(String(e.ADMIN_IDS||'').split(',').map(s=>s.trim()).filter(Boolean));
const telegramId=s=>typeof s==='string'&&/^\d{1,16}$/.test(s);
const timingSafe=(a,b)=>{if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let r=0;for(let i=0;i<a.length;i++)r|=a.charCodeAt(i)^b.charCodeAt(i);return r===0;};
export class TelegramError extends Error {constructor(method,status){super(`Telegram ${method}: ${status}`);this.status=status;}}
export async function tg(e,method,payload){
 const multipart=payload instanceof FormData;
 const res=await fetch(`https://api.telegram.org/bot${e.BOT_TOKEN}/${method}`,{method:'POST',headers:multipart?{}:{'Content-Type':'application/json'},body:multipart?payload:JSON.stringify(payload)});
 const j=await res.json();if(!res.ok||!j.ok)throw new TelegramError(method,j.error_code||res.status);return j.result;
}
const send=(e,chat,text,buttons)=>tg(e,'sendMessage',{chat_id:chat,text, ...(buttons?{reply_markup:{inline_keyboard:buttons}}:{})});
const getMember=async(e,channel,user)=>member(await tg(e,'getChatMember',{chat_id:channel,user_id:Number(user)}));
const touch=(e,user)=>run(e.DB,'INSERT OR IGNORE INTO users(id,created_at) VALUES (?,?)',user,now());
const product=(e,p)=>row(e.DB,'SELECT * FROM products WHERE id=?',p);
const campaign=(e,c)=>row(e.DB,`SELECT c.*,p.title,p.active AS product_active FROM campaigns c JOIN products p ON p.id=c.product_id WHERE c.id=?`,c);
const entitlement=(e,u,p)=>row(e.DB,'SELECT * FROM entitlements WHERE user_id=? AND product_id=?',u,p);
const grant=(e,u,p,source)=>run(e.DB,'INSERT OR IGNORE INTO entitlements(user_id,product_id,source,created_at) VALUES (?,?,?,?)',u,p,source,now());
const audit=(e,u,action,target)=>run(e.DB,'INSERT INTO audit(admin_id,action,target,created_at) VALUES (?,?,?,?)',u,action,target,now());
async function photo(e,chat,caption,buttons,key,fileId){
 if(fileId){try{return await tg(e,'sendPhoto',{chat_id:chat,photo:fileId,caption,reply_markup:{inline_keyboard:buttons||[]}});}catch(err){if(err.status!==400)throw err;}}
 return send(e,chat,caption,buttons);
}
async function welcome(e,u){
 const s=await row(e.DB,"SELECT value FROM settings WHERE key='welcome_key'");const f=await row(e.DB,"SELECT value FROM settings WHERE key='welcome_file_id'");
 return photo(e,u,'🎓 Bienvenue dans MR X ACADEMY !\n\nLivres, formations et guides pratiques.\nApprendre. Appliquer. Réussir.\n\nChoisissez une rubrique :',menu,s?.value,f?.value);
}
async function catalogue(e,u,filter='all',page=0){
 const condition=filter==='free'?' AND price_xof=0':filter==='premium'?' AND price_xof>0':'';
 const ps=await all(e.DB,`SELECT id,title,price_xof FROM products WHERE active=1${condition} ORDER BY category,title,id LIMIT 9 OFFSET ?`,page*8);
 const buttons=ps.slice(0,8).map(p=>[cb(`${p.price_xof===0?'📖':'🎓'} ${p.title.slice(0,50)}`,`p:${p.id}`)]);
 const nav=[];if(page>0)nav.push(cb('◀',`list:${filter}:${page-1}`));if(ps.length>8)nav.push(cb('▶',`list:${filter}:${page+1}`));if(nav.length)buttons.push(nav);buttons.push(home);
 return send(e,u,ps.length?'📚 Catalogue — choisissez un produit.':'Aucun produit disponible actuellement.',buttons);
}
async function showProduct(e,u,pid){
 const p=await product(e,pid);if(!p?.active&&!await entitlement(e,u,pid))return send(e,u,'Produit indisponible.',[home]);
 if(!p)return send(e,u,'Produit indisponible.',[home]);
 const access=await entitlement(e,u,pid);const cs=await all(e.DB,'SELECT id,target FROM campaigns WHERE product_id=? AND active=1 ORDER BY id',pid);
 const buttons=[];if(access||p.price_xof===0)buttons.push([cb('📥 Télécharger',`get:${pid}`)]);
 if(!access&&p.price_xof>0)for(const c of cs)buttons.push([cb(`🎁 Gratuit : ${c.target} invitations`,`c:${c.id}`)]);
 buttons.push(home);
 const price=p.price_xof===0?'Gratuit':`${p.price_xof.toLocaleString('fr-FR')} FCFA (tarif boutique web indépendante)`;
 const caption=`${p.title}\n${p.category} • ${price}\n\n${p.description}${access?'\n\n✅ Dans votre bibliothèque.':''}`.slice(0,1000);
 return photo(e,u,caption,buttons,p.cover_key,p.cover_file_id);
}
async function sendPDF(e,u,pid){
 const p=await product(e,pid);if(!p)return send(e,u,'Produit introuvable.',[home]);
 let access=await entitlement(e,u,pid);if(!access&&p.active&&p.price_xof===0){await grant(e,u,pid,'free');access=await entitlement(e,u,pid);}
 if(!access)return send(e,u,'🔒 Ce produit n’est pas encore débloqué.',[[cb('Voir le produit',`p:${pid}`)],home]);
 if(!p.file_id)return send(e,u,'Fichier temporairement indisponible. Votre accès est conservé.',[home]);
 let result;
 try{result=await tg(e,'sendDocument',{chat_id:u,document:p.file_id,caption:p.title,protect_content:p.price_xof>0});}
 catch(err){if(err.status!==400)throw err;return send(e,u,'Fichier temporairement indisponible. Votre accès est conservé.',[home]);}
 await run(e.DB,'INSERT OR IGNORE INTO deliveries(user_id,product_id,delivered_at) VALUES (?,?,?)',u,pid,now());
 return result;
}
async function library(e,u,page=0){
 const ps=await all(e.DB,`SELECT p.id,p.title FROM entitlements t JOIN products p ON p.id=t.product_id WHERE t.user_id=? ORDER BY t.created_at DESC,p.id LIMIT 9 OFFSET ?`,u,page*8);
 const b=ps.slice(0,8).map(p=>[cb(`📥 ${p.title.slice(0,50)}`,`get:${p.id}`)]);const n=[];if(page>0)n.push(cb('◀',`lib:${page-1}`));if(ps.length>8)n.push(cb('▶',`lib:${page+1}`));if(n.length)b.push(n);b.push(home);
 return send(e,u,ps.length?'📂 Ma bibliothèque':'Votre bibliothèque est vide.',b);
}
async function campaigns(e,u,onlyMine=false){
 const cs=await all(e.DB,`SELECT c.id,p.title,c.target FROM campaigns c JOIN products p ON p.id=c.product_id ${onlyMine?'JOIN links l ON l.campaign_id=c.id AND l.owner_id=?':''} WHERE c.active=1 AND p.active=1 ORDER BY c.id LIMIT 30`,...(onlyMine?[u]:[]));
 return send(e,u,cs.length?'🎁 Choisissez une campagne.':'Aucune campagne disponible.',[...cs.map(c=>[cb(`${c.title.slice(0,42)} · ${c.target}`,`c:${c.id}`)]),home]);
}
async function counts(e,c,u){const r=await all(e.DB,'SELECT state,COUNT(*) n FROM referrals WHERE campaign_id=? AND owner_id=? GROUP BY state',c,u);return Object.fromEntries(r.map(x=>[x.state,Number(x.n)]));}
async function showCampaign(e,u,cid){
 const c=await campaign(e,cid);if(!c?.active||!c.product_active)return send(e,u,'Campagne indisponible.',[home]);
 if(await entitlement(e,u,c.product_id))return send(e,u,'✅ Vous disposez déjà de ce produit.',[[cb('📥 Télécharger',`get:${c.product_id}`)],home]);
 if(!await getMember(e,c.channel_id,u))return send(e,u,'Rejoignez le canal pour participer, puis vérifiez votre abonnement.',[[urlButton('Rejoindre le canal',c.channel_url)],[cb('✅ Vérifier mon abonnement',`c:${cid}`)],home]);
 const link=await row(e.DB,'SELECT invite_link FROM links WHERE campaign_id=? AND owner_id=?',cid,u);
 const n=await counts(e,cid,u),v=n.valid||0;
 const b=[];if(link){b.push([urlButton('📤 Partager mon lien',`https://t.me/share/url?url=${encodeURIComponent(link.invite_link)}&text=${encodeURIComponent('Découvrez les ressources de MR X ACADEMY !')}`)]);b.push([cb('🔄 Actualiser',`check:${cid}`)]);}else b.push([cb('🔗 Créer mon lien personnel',`link:${cid}`)]);
 b.push([cb('🎁 Vérifier et obtenir la récompense',`claim:${cid}`)],home);
 return send(e,u,`🎁 ${c.title}\n\n${'🟩'.repeat(Math.min(v,c.target))}${'⬜'.repeat(Math.max(0,c.target-v))}\n${v}/${c.target} validées • ${n.pending||0} en attente\n\nInvitez de nouveaux abonnés réellement intéressés. Un compte ne compte qu’une fois par canal. Délai de validation : ${c.hold_seconds/3600} h. Aucun pari, dépôt ou achat obligatoire. Pas de spam.${link?'\n\nVotre lien personnel :\n'+link.invite_link:''}`,b);
}
async function makeLink(e,u,cid){
 const c=await campaign(e,cid);if(!c?.active||!c.product_active)return send(e,u,'Campagne indisponible.',[home]);
 if(!await getMember(e,c.channel_id,u))return showCampaign(e,u,cid);
 if(await entitlement(e,u,c.product_id))return showCampaign(e,u,cid);
 let link=await row(e.DB,'SELECT * FROM links WHERE campaign_id=? AND owner_id=?',cid,u);
 if(!link){
  const made=await tg(e,'createChatInviteLink',{chat_id:c.channel_id,name:`a-${cid.slice(0,12)}-${u.slice(-10)}`,creates_join_request:false});
  await run(e.DB,'INSERT OR IGNORE INTO links(campaign_id,owner_id,invite_link,channel_id,created_at) VALUES (?,?,?,?,?)',cid,u,made.invite_link,c.channel_id,now());
  link=await row(e.DB,'SELECT * FROM links WHERE campaign_id=? AND owner_id=?',cid,u);
  if(link.invite_link!==made.invite_link)await tg(e,'revokeChatInviteLink',{chat_id:c.channel_id,invite_link:made.invite_link});
 }
 return showCampaign(e,u,cid);
}
// An observed membership event is authoritative only for the exact channel and its own invite link.
// A previously observed member, even after leaving, cannot be credited again.
export async function membershipEvent(e,update){
 const ev=update.chat_member;if(!ev?.chat?.id||!ev.new_chat_member?.user)return;
 const channel=id(ev.chat.id),u=id(ev.new_chat_member.user.id),present=member(ev.new_chat_member),was=member(ev.old_chat_member),at=Number(ev.date),uid=Number(update.update_id);
 if(ev.new_chat_member.user.is_bot||!Number.isSafeInteger(at)||!Number.isSafeInteger(uid))return;
 const known=await row(e.DB,'SELECT 1 FROM campaigns WHERE channel_id=? LIMIT 1',channel);if(!known)return;
 const db=e.DB,ops=[];
 if(!was&&present&&ev.invite_link?.invite_link){
  ops.push(stmt(db,`INSERT OR IGNORE INTO referrals(channel_id,invitee_id,campaign_id,owner_id,joined_at,eligible_at,state)
  SELECT l.channel_id,?,l.campaign_id,l.owner_id,?,?+c.hold_seconds,'pending'
  FROM links l JOIN campaigns c ON c.id=l.campaign_id JOIN products p ON p.id=c.product_id
  WHERE l.invite_link=? AND l.channel_id=? AND c.channel_id=? AND c.active=1 AND p.active=1 AND l.owner_id<>?
  AND NOT EXISTS(SELECT 1 FROM memberships m WHERE m.channel_id=? AND m.user_id=?)`,u,at,at,ev.invite_link.invite_link,channel,channel,u,channel,u));
 }
 if(!present)ops.push(stmt(db,`UPDATE referrals SET state='rejected',reason='left_channel' WHERE channel_id=? AND invitee_id=? AND state IN('pending','valid') AND joined_at<=?
 AND NOT EXISTS(SELECT 1 FROM memberships m WHERE m.channel_id=? AND m.user_id=? AND (m.last_event>? OR (m.last_event=? AND m.last_update>=?)))`,channel,u,at,channel,u,at,at,uid));
 ops.push(stmt(db,`INSERT INTO memberships(channel_id,user_id,present,last_event,last_update) VALUES (?,?,?,?,?)
 ON CONFLICT(channel_id,user_id) DO UPDATE SET present=excluded.present,last_event=excluded.last_event,last_update=excluded.last_update
 WHERE excluded.last_event>memberships.last_event OR (excluded.last_event=memberships.last_event AND excluded.last_update>memberships.last_update)`,channel,u,present?1:0,at,uid));
 await db.batch(ops);
}
export async function validateDue(e,cid=null,owner=null,limit=20){
 const scope=cid?' AND campaign_id=? AND owner_id=?':'';
 const due=await all(e.DB,`SELECT channel_id,invitee_id FROM referrals WHERE state='pending' AND eligible_at<=?${scope} ORDER BY eligible_at LIMIT ?`,now(),...(cid?[cid,owner]:[]),limit);
 for(const r of due){
  try{const yes=await getMember(e,r.channel_id,r.invitee_id);await run(e.DB,"UPDATE referrals SET state=?,reason=? WHERE channel_id=? AND invitee_id=? AND state='pending'",yes?'valid':'rejected',yes?null:'not_member',r.channel_id,r.invitee_id);}
  catch(err){if(cid)throw err;console.warn('Membership check deferred',err.message);}
 }
 return due.length;
}
async function refresh(e,u,cid){await validateDue(e,cid,u,5);return showCampaign(e,u,cid);}
async function unlock(e,u,c){
 if(!c?.active||!c.product_active)return false;
 if(await entitlement(e,u,c.product_id))return false;
 if(!await getMember(e,c.channel_id,u))return false;
 const rs=await all(e.DB,"SELECT channel_id,invitee_id FROM referrals WHERE campaign_id=? AND owner_id=? AND state='valid' ORDER BY joined_at LIMIT ?",c.id,u,c.target);
 if(rs.length<c.target)return false;
 let good=0;
 for(const r of rs){if(await getMember(e,r.channel_id,r.invitee_id))good++;else await run(e.DB,"UPDATE referrals SET state='rejected',reason='not_member' WHERE channel_id=? AND invitee_id=? AND state='valid'",r.channel_id,r.invitee_id);}
 if(good<c.target)return false;
 const inList=rs.map(()=>'?').join(',');
 const result=await run(e.DB,`INSERT OR IGNORE INTO entitlements(user_id,product_id,source,created_at)
 SELECT ?,c.product_id,'referral',? FROM campaigns c JOIN products p ON p.id=c.product_id WHERE c.id=? AND c.active=1 AND p.active=1 AND c.target=?
 AND (SELECT COUNT(*) FROM referrals r WHERE r.campaign_id=c.id AND r.owner_id=? AND r.state='valid' AND r.invitee_id IN (${inList}))>=c.target`,u,now(),c.id,c.target,u,...rs.map(r=>r.invitee_id));
 return Boolean(result.meta.changes);
}
async function claim(e,u,cid){
 const c=await campaign(e,cid);if(!c?.active||!c.product_active)return send(e,u,'Campagne indisponible.',[home]);
 if(await entitlement(e,u,c.product_id))return sendPDF(e,u,c.product_id);
 await validateDue(e,cid,u,5);
 const fresh=await unlock(e,u,c);
 if(!await entitlement(e,u,c.product_id))return showCampaign(e,u,cid);
 if(fresh)await send(e,u,'🎉 Objectif atteint ! Votre formation est maintenant dans votre bibliothèque.');
 return sendPDF(e,u,c.product_id);
}
// Round-robin delivery scan avoids repeatedly selecting a participant who left the channel.
export async function autoReward(e){
 const last=await row(e.DB,"SELECT value FROM settings WHERE key='reward_cursor'");
 const query=`SELECT c.id, r.owner_id, c.id||':'||r.owner_id AS cursor FROM referrals r JOIN campaigns c ON c.id=r.campaign_id JOIN products p ON p.id=c.product_id
 WHERE r.state='valid' AND c.active=1 AND p.active=1 AND NOT EXISTS(SELECT 1 FROM entitlements t WHERE t.user_id=r.owner_id AND t.product_id=c.product_id)
 GROUP BY c.id,r.owner_id HAVING COUNT(*)>=c.target`;
 let next=await row(e.DB,`SELECT * FROM (${query}) WHERE cursor>? ORDER BY cursor LIMIT 1`,last?.value||'');
 if(!next)next=await row(e.DB,`SELECT * FROM (${query}) ORDER BY cursor LIMIT 1`);
 if(!next)return false;
 await run(e.DB,"INSERT INTO settings(key,value) VALUES ('reward_cursor',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",next.cursor);
 const c=await campaign(e,next.id);
 if(!await unlock(e,next.owner_id,c))return false;
 try{await send(e,next.owner_id,'🎉 Objectif atteint ! Votre formation est débloquée.');await sendPDF(e,next.owner_id,c.product_id);}catch(err){console.warn('Automatic delivery deferred; library access retained',err.message);}
 return true;
}
async function help(e,u){return send(e,u,'MR X ACADEMY — Assistance\n\n• Les invitations comptent uniquement les nouveaux abonnés attribués à votre lien.\n• Votre bibliothèque est liée à votre compte Telegram.\n• Un produit acquis reste disponible dans votre bibliothèque.\n• Aucun achat ni activité de jeu n’est requis pour le parrainage.\n• /privacy : données utilisées.\n• /id : identifiant utile au support.\n'+(e.SUPPORT_HANDLE?`\nContact : ${e.SUPPORT_HANDLE}`:''),[home]);}
async function adminCommand(e,u,cmd,arg,msg,statsOnly=false){
 if(!admins(e).has(u))return send(e,u,'Commande non autorisée.');
 if(cmd==='admin'){
  if(!statsOnly)return wizMenu(e,u);
  const s=await row(e.DB,`SELECT (SELECT COUNT(*) FROM users) users,(SELECT COUNT(*) FROM products) products,(SELECT COUNT(*) FROM referrals WHERE state='valid') valid,(SELECT COUNT(*) FROM referrals WHERE state='pending') pending,(SELECT COUNT(*) FROM entitlements WHERE source='referral') rewards,(SELECT COUNT(*) FROM entitlements WHERE source='purchase') purchases,(SELECT COUNT(*) FROM deliveries) deliveries`);
  return send(e,u,`ADMIN • MR X ACADEMY\nUtilisateurs : ${s.users}\nProduits : ${s.products}\nInvitations valides : ${s.valid}\nEn attente : ${s.pending}\nRécompenses : ${s.rewards}\nAchats validés : ${s.purchases}\nLivraisons uniques : ${s.deliveries}`,[[cb('⬅ Administration','aw:menu')]]);
 }
 if(cmd==='product'){
  const p=JSON.parse(arg);if(!slug(p.id)||typeof p.title!=='string'||!p.title.trim()||p.title.length>120||typeof p.category!=='string'||p.category.length>60||typeof p.description!=='string'||p.description.length>650||!Number.isSafeInteger(p.price_xof)||p.price_xof<0||p.price_xof>100000000)throw new Error('Invalid product');
  const old=await product(e,p.id);if(old&&old.price_xof!==p.price_xof&&old.active)throw new Error('Unpublish first');
  await run(e.DB,`INSERT INTO products(id,title,category,description,price_xof,filename) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,category=excluded.category,description=excluded.description,price_xof=excluded.price_xof`,p.id,p.title,p.category,p.description,p.price_xof,`${p.id}.pdf`);await audit(e,u,'product',p.id);return send(e,u,'Produit enregistré. Ajoutez le PDF puis /publish '+p.id);
 }
 if(cmd==='campaign'){
  const c=JSON.parse(arg);if(!slug(c.id)||!slug(c.product_id)||c.channel_id===String(e.STORAGE_CHANNEL_ID||'')||!validChannel(c.channel_id)||!validJoinURL(c.channel_url)||!Number.isInteger(c.target)||c.target<1||c.target>20||!Number.isInteger(c.hold_hours)||c.hold_hours<0||c.hold_hours>168)throw new Error('Invalid campaign');
  const p=await product(e,c.product_id);if(!p?.active||p.price_xof===0)throw new Error('Publish paid product first');
  const me=await tg(e,'getMe',{}),status=await tg(e,'getChatMember',{chat_id:c.channel_id,user_id:me.id});if(status.status!=='administrator'||!status.can_invite_users)throw new Error('Bot needs admin invite permission');
  const old=await campaign(e,c.id);if(old&&(old.product_id!==c.product_id||old.channel_id!==c.channel_id||old.target!==c.target||old.hold_seconds!==c.hold_hours*3600))throw new Error('Use new campaign ID for rule changes');
  await run(e.DB,`INSERT INTO campaigns(id,product_id,channel_id,channel_url,target,hold_seconds,active) VALUES (?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET channel_url=excluded.channel_url,active=1`,c.id,c.product_id,c.channel_id,c.channel_url,c.target,c.hold_hours*3600);await audit(e,u,'campaign',c.id);return send(e,u,'Campagne active : '+c.id);
 }
 if(cmd==='file'){
  if(!slug(arg)||!await product(e,arg)||msg.document?.mime_type!=='application/pdf'||(msg.document.file_size||0)>49*1024*1024)throw new Error('Attach PDF');
  await run(e.DB,'UPDATE products SET file_id=?,filename=?,object_key=NULL WHERE id=?',msg.document.file_id,msg.document.file_name||`${arg}.pdf`,arg);await audit(e,u,'file',arg);return send(e,u,'PDF enregistré.');
 }
 if(cmd==='cover'||cmd==='banner'){
  const pic=msg.photo?.at(-1);if(!pic)throw new Error('Attach photo');
  if(cmd==='banner')await run(e.DB,"INSERT INTO settings(key,value) VALUES ('welcome_file_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",pic.file_id);
  else{if(!slug(arg)||!await product(e,arg))throw new Error('Invalid product');await run(e.DB,'UPDATE products SET cover_file_id=?,cover_key=NULL WHERE id=?',pic.file_id,arg);}
  await audit(e,u,cmd,arg||'welcome');return send(e,u,'Image enregistrée.');
 }
 if(cmd==='publish'||cmd==='unpublish'){
  if(!slug(arg))throw new Error('Invalid product');const p=await product(e,arg);if(!p)throw new Error('Unknown product');
  if(cmd==='publish'&&!p.file_id)throw new Error('Missing PDF');
  await run(e.DB,'UPDATE products SET active=? WHERE id=?',cmd==='publish'?1:0,arg);await audit(e,u,cmd,arg);return send(e,u,'Statut modifié : '+arg);
 }
 if(cmd==='campaignoff'){
  if(!slug(arg))throw new Error('Invalid campaign');await run(e.DB,'UPDATE campaigns SET active=0 WHERE id=?',arg);await audit(e,u,cmd,arg);return send(e,u,'Campagne désactivée. Les droits acquis sont conservés.');
 }
 if(cmd==='grant'){
  const [who,pid]=arg.split(/\s+/);if(!telegramId(who)||!slug(pid)||!await product(e,pid)||!await row(e.DB,'SELECT id FROM users WHERE id=?',who))throw new Error('Invalid grant');
  await grant(e,who,pid,'purchase');await audit(e,u,'verified_manual_purchase',`${who}:${pid}`);return send(e,u,'Accès accordé après vérification manuelle de l’achat. Le client peut ouvrir sa bibliothèque.');
 }
}
// The private storage channel is explicitly allowlisted. Other channel posts are ignored.
async function storagePost(e,msg){
 if(!msg||msg.chat?.type!=='channel'||!validChannel(String(e.STORAGE_CHANNEL_ID||''))||id(msg.chat.id)!==String(e.STORAGE_CHANNEL_ID).trim())return;
 const actor=[...admins(e)][0];if(!actor||!telegramId(actor))return;
 const match=(msg.caption||'').match(/^\/(file|cover|banner)(?:@\w+)?(?:\s+([a-z0-9_-]{1,24}))?$/);
 if(!match)return;
 const cmd=match[1],arg=match[2]||'';
 if((cmd==='banner'&&arg)||(cmd!=='banner'&&!arg))return;
 try{await adminCommand(e,actor,cmd,arg,msg);}catch(err){console.warn('Storage import rejected',cmd,err.message);await send(e,actor,'Import du canal refusé : vérifiez le type de fichier et sa légende.');}
}

// Guided creation: private per-admin state in existing D1 settings, no new binding.
const wizardCategories=['Business','Finance','Sport','Intelligence artificielle','Marketing','Leadership','Autre'];
const wizKey=u=>'admin_wizard:'+u;
const wizSteps=['title','category','price','description','cover','pdf','review'];
const wizAction=(d,a)=>'aw:'+d.id+':'+d.step+':'+a;
const wizCancel=d=>[cb('❌ Annuler',wizAction(d,'cancel')),cb('⏸ Pause','aw:menu')];
const wizButtons=(d,extra=[])=>[...extra,...(d.step==='title'?[]:[[cb('⬅ Retour',wizAction(d,'back'))]]),wizCancel(d)];
async function wizRead(e,u){const r=await row(e.DB,'SELECT value FROM settings WHERE key=?',wizKey(u));return r?JSON.parse(r.value):null;}
const wizSave=(e,u,d)=>run(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',wizKey(u),JSON.stringify(d));
async function wizMenu(e,u){
 const d=await wizRead(e,u);
 return send(e,u,'⚙️ Administration • MR X ACADEMY\n\nChoisissez une action.',[
 [cb(d?'▶ Reprendre la création':'➕ Nouvelle formation',d?'aw:resume':'aw:new')],
 [cb('📚 Gérer les formations','aw:list:0')],[cb('📊 Statistiques','aw:stats')],home]);
}
async function wizPrompt(e,u,d){
 const n=wizSteps.indexOf(d.step)+1;
 const prefix='🎓 Nouvelle formation — étape '+n+'/7\n\n';
 const say=(t,b=[])=>send(e,u,prefix+t,wizButtons(d,b));
 switch(d.step){
 case 'title':return say('Quel est le titre de la formation ? Envoyez-le en message.');
 case 'category':return say('Choisissez une catégorie ou écrivez votre propre catégorie.',wizardCategories.map((c,i)=>[cb(c,wizAction(d,'cat'+i))]));
 case 'price':return say('Quel est le prix de la formation en FCFA ? Envoyez un montant entier, ou choisissez Gratuit.',[[cb('🆓 Gratuit',wizAction(d,'free'))]]);
 case 'description':return say('Envoyez une courte description (650 caractères maximum), ou passez cette étape.',[[cb('⏭ Sans description',wizAction(d,'skip'))]]);
 case 'cover':return say('Envoyez la photo de couverture dans cette conversation (en tant que photo Telegram).');
 case 'pdf':return say('Envoyez le fichier PDF comme document (49 Mio maximum).');
 case 'review':{
  const caption='✅ Aperçu avant publication\n\n'+d.title+'\n'+d.category+'\n'+(d.price===0?'Gratuit':d.price.toLocaleString('fr-FR')+' FCFA')+'\n\n'+(d.description||'Sans description')+'\n\n📎 '+d.filename;
  return photo(e,u,caption.slice(0,1000),wizButtons(d,[[cb('✅ Publier',wizAction(d,'publish'))],[cb('💾 Garder en brouillon',wizAction(d,'draft'))]]),null,d.cover);
 }
 }
}
async function wizList(e,u,page=0){
 const ps=await all(e.DB,'SELECT id,title,active,file_id FROM products ORDER BY title,id LIMIT 9 OFFSET ?',page*8);
 const buttons=ps.slice(0,8).map(p=>[cb((p.active?'🟢 ':'⚪ ')+p.title.slice(0,48),'aw:product:'+p.id)]);
 const nav=[];if(page>0)nav.push(cb('◀','aw:list:'+(page-1)));if(ps.length>8)nav.push(cb('▶','aw:list:'+(page+1)));if(nav.length)buttons.push(nav);
 return send(e,u,ps.length?'📚 Vos formations — choisissez un produit.':'Aucune formation.',[...buttons,[cb('⬅ Administration','aw:menu')]]);
}
async function wizProduct(e,u,pid){
 const p=await product(e,pid);if(!p)return wizList(e,u);
 const b=[];if(p.active)b.push([cb('Masquer du catalogue','aw:hide:'+pid)]);else if(p.file_id)b.push([cb('Publier','aw:show:'+pid)]);
 if(p.file_id)b.push([cb('📎 Tester le PDF','aw:test:'+pid)]);
 b.push([cb('⬅ Formations','aw:list:0')]);
 return photo(e,u,(p.title+'\n'+p.category+'\n'+p.price_xof+' FCFA\n'+(p.active?'Publié':'Brouillon')+'\n'+(p.file_id?'PDF enregistré':'PDF manquant')+'\n\n'+p.description).slice(0,1000),b,null,p.cover_file_id);
}
async function wizardCallback(e,u,action){
 if(!admins(e).has(u))return send(e,u,'Commande non autorisée.');
 if(action==='aw:menu')return wizMenu(e,u);
 if(action==='aw:stats')return adminCommand(e,u,'admin','',null,true);
 if(action==='aw:resume'){const d=await wizRead(e,u);return d?wizPrompt(e,u,d):wizMenu(e,u);}
 if(action==='aw:new'){
  const old=await wizRead(e,u);if(old)return wizPrompt(e,u,old);
  const d={id:'f-'+crypto.randomUUID().replace(/-/g,'').slice(0,20),step:'title'};await wizSave(e,u,d);return wizPrompt(e,u,d);
 }
 const v=action.split(':');
 if(v.length===3&&v[1]==='list'&&/^\d{1,3}$/.test(v[2]))return wizList(e,u,Number(v[2]));
 if(v.length===3&&slug(v[2])){
  const p=await product(e,v[2]);
  if(v[1]==='product')return wizProduct(e,u,v[2]);
  if(!p)return wizList(e,u);
  if(v[1]==='test'&&p.file_id)return tg(e,'sendDocument',{chat_id:u,document:p.file_id,caption:'Test administrateur : '+p.title,protect_content:true});
  if(v[1]==='hide'||v[1]==='show'){
   if(v[1]==='show'&&!p.file_id)return send(e,u,'PDF manquant.');
   await run(e.DB,'UPDATE products SET active=? WHERE id=?',v[1]==='show'?1:0,p.id);
   await audit(e,u,'wizard_'+v[1],p.id);return wizProduct(e,u,p.id);
  }
 }
 const d=await wizRead(e,u);
 if(!d||v.length!==4||v[1]!==d.id||v[2]!==d.step)return send(e,u,'Cette étape a expiré.',[[cb('Reprendre','aw:resume')],[cb('Administration','aw:menu')]]);
 const a=v[3];
 if(a==='cancel'){await run(e.DB,'DELETE FROM settings WHERE key=?',wizKey(u));return send(e,u,'Création annulée. Les fichiers déjà archivés restent dans le canal privé.',[[cb('➕ Nouvelle formation','aw:new')],[cb('Administration','aw:menu')]]);}
 if(a==='back'){const i=wizSteps.indexOf(d.step);if(i>0)d.step=wizSteps[i-1];await wizSave(e,u,d);return wizPrompt(e,u,d);}
 if(d.step==='category'&&/^cat[0-6]$/.test(a)){d.category=wizardCategories[Number(a.slice(3))];d.step='price';}
 else if(d.step==='price'&&a==='free'){d.price=0;d.step='description';}
 else if(d.step==='description'&&a==='skip'){d.description='';d.step='cover';}
 else if(d.step==='review'&&['publish','draft'].includes(a)){
  if(!d.title||!d.category||!Number.isSafeInteger(d.price)||d.price<0||!d.cover||!d.file||!d.filename)return send(e,u,'Brouillon incomplet.',[[cb('Reprendre','aw:resume')]]);
  const active=a==='publish'?1:0;
  await e.DB.batch([
   stmt(e.DB,'INSERT OR IGNORE INTO products(id,title,category,description,price_xof,active,filename,file_id,cover_file_id) VALUES (?,?,?,?,?,?,?,?,?)',d.id,d.title,d.category,d.description||'',d.price,active,d.filename,d.file,d.cover),
   stmt(e.DB,'DELETE FROM settings WHERE key=?',wizKey(u)),
   stmt(e.DB,'INSERT INTO audit(admin_id,action,target,created_at) VALUES (?,?,?,?)',u,'wizard_'+a,d.id,now())
  ]);
  return send(e,u,(active?'🎉 Formation publiée !':'💾 Formation enregistrée en brouillon.')+'\n'+d.title+'\nIdentifiant : '+d.id+(d.price>0?'\n\nPour ouvrir un accès Premium, configurez ensuite une campagne ou accordez un accès après achat vérifié.':''),[[cb('Voir la formation','aw:product:'+d.id)],[cb('➕ Nouvelle formation','aw:new')],[cb('Administration','aw:menu')]]);
 }else return wizPrompt(e,u,d);
 await wizSave(e,u,d);return wizPrompt(e,u,d);
}
async function wizardMessage(e,u,d,m){
 const t=String(m.text||'').trim();
 const invalid=(text)=>send(e,u,text,wizButtons(d));
 switch(d.step){
 case 'title':if(!t||t.length>120)return invalid('Envoyez un titre de 1 à 120 caractères.');d.title=t;d.step='category';break;
 case 'category':if(!t||t.length>60)return invalid('Envoyez une catégorie de 1 à 60 caractères.');d.category=t;d.step='price';break;
 case 'price':{const v=t.replace(/\s/g,'');if(!/^\d{1,9}$/.test(v)||Number(v)>100000000)return invalid('Envoyez un montant entier de 0 à 100 000 000 FCFA.');d.price=Number(v);d.step='description';break;}
 case 'description':if(!t||t.length>650)return invalid('Envoyez une description de 650 caractères maximum ou cliquez sur Sans description.');d.description=t==='0'?'':t;d.step='cover';break;
 case 'cover':{
  const pic=m.photo?.at(-1);if(!pic?.file_id)return invalid('Envoyez la couverture en tant que photo Telegram.');
  if(!validChannel(String(e.STORAGE_CHANNEL_ID||'')))return invalid('Le canal de stockage est mal configuré. Vérifiez STORAGE_CHANNEL_ID.');
  try{await tg(e,'sendPhoto',{chat_id:String(e.STORAGE_CHANNEL_ID),photo:pic.file_id,caption:'Archive Academy — couverture — '+d.id});}catch(err){return invalid('Archivage impossible. Vérifiez que le bot peut publier dans le canal privé, puis renvoyez la photo.');}
  d.cover=pic.file_id;d.step='pdf';break;
 }
 case 'pdf':{
  const f=m.document;if(!f?.file_id||f.mime_type!=='application/pdf'||(f.file_size||0)>49*1024*1024)return invalid('Envoyez un PDF de 49 Mio maximum comme document.');
  if(!validChannel(String(e.STORAGE_CHANNEL_ID||'')))return invalid('Le canal de stockage est mal configuré.');
  try{await tg(e,'sendDocument',{chat_id:String(e.STORAGE_CHANNEL_ID),document:f.file_id,caption:'Archive Academy — PDF — '+d.id});}catch(err){return invalid('Archivage impossible. Vérifiez le droit de publication du bot dans le canal privé puis renvoyez le PDF.');}
  d.file=f.file_id;d.filename=String(f.file_name||d.id+'.pdf').slice(0,200);d.step='review';break;
 }
 case 'review':return wizPrompt(e,u,d);
 default:return wizMenu(e,u);
 }
 await wizSave(e,u,d);return wizPrompt(e,u,d);
}

const adminCmds=new Set(['admin','product','campaign','file','cover','banner','publish','unpublish','grant','campaignoff']);
async function dispatch(e,update){
 if(update.chat_member)return membershipEvent(e,update);
 if(update.channel_post)return storagePost(e,update.channel_post);
 const q=update.callback_query,m=q?.message||update.message;if(!m||m.chat?.type!=='private')return;
 const from=q?.from||m.from;if(!from||from.is_bot||id(m.chat.id)!==id(from.id))return;
 const u=id(from.id);await touch(e,u);
 if(q){try{await tg(e,'answerCallbackQuery',{callback_query_id:q.id});}catch(err){if(err.status!==400)throw err;}}
 let action=q?.data||m.text||m.caption||'';
 if(q&&action.startsWith('aw:'))return wizardCallback(e,u,action);
 if(!q&&admins(e).has(u)&&!action.startsWith('/')){const d=await wizRead(e,u);if(d)return wizardMessage(e,u,d,m);if(m.forward_origin?.type==='channel')return send(e,u,`Canal : ${m.forward_origin.chat.title||'sans titre'}\nID : ${m.forward_origin.chat.id}`);}
 if(!q&&action==='/cancel'&&admins(e).has(u)){const d=await wizRead(e,u);if(d)return wizardCallback(e,u,wizAction(d,'cancel'));return wizMenu(e,u);}
 if(!q&&action.startsWith('/')){
  const match=action.match(/^\/([a-z_]+)(?:@\w+)?(?:\s+([\s\S]*))?$/);if(!match)return help(e,u);
  const cmd=match[1],arg=(match[2]||'').trim();
  if(adminCmds.has(cmd)){try{return await adminCommand(e,u,cmd,arg,m);}catch(err){console.warn('Admin command rejected',cmd,err.message);return send(e,u,'Commande refusée ou configuration incomplète. Consultez le README et vérifiez les paramètres.');}}
  if(cmd==='id')return send(e,u,`Votre identifiant : ${u}`);
  if(cmd==='privacy')return send(e,u,'Nous conservons votre identifiant Telegram, les invitations et droits d’accès nécessaires au fonctionnement. Aucun numéro de téléphone ni mot de passe demandé. Pour une demande d’accès ou de suppression, contactez l’assistance. Les invitations déjà comptabilisées peuvent nécessiter une conservation minimale antifraude.');
  action=cmd==='start'?(arg.startsWith('p_')?`p:${arg.slice(2)}`:arg.startsWith('c_')?`c:${arg.slice(2)}`:'home'):cmd;
 }
 if(action==='home')return welcome(e,u);
 if(action==='catalogue')return catalogue(e,u);
 if(action==='gratuit')return catalogue(e,u,'free');
 if(action==='premium')return catalogue(e,u,'premium');
 if(action==='bibliotheque')return library(e,u);
 if(action==='parrainage')return campaigns(e,u);
 if(action==='progression')return campaigns(e,u,true);
 if(action==='help')return help(e,u);
 let v=action.split(':');if(v[0]==='list'&&['all','free','premium'].includes(v[1])&&/^\d{1,3}$/.test(v[2]||''))return catalogue(e,u,v[1],Number(v[2]));
 if(v[0]==='lib'&&/^\d{1,3}$/.test(v[1]||''))return library(e,u,Number(v[1]));
 if(v.length===2&&slug(v[1])){
  if(v[0]==='p')return showProduct(e,u,v[1]);if(v[0]==='get')return sendPDF(e,u,v[1]);if(v[0]==='c')return showCampaign(e,u,v[1]);if(v[0]==='link')return makeLink(e,u,v[1]);if(v[0]==='check')return refresh(e,u,v[1]);if(v[0]==='claim')return claim(e,u,v[1]);
 }
 return help(e,u);
}
export async function handleWebhook(request,e){
 if(!e.WEBHOOK_SECRET||!e.BOT_TOKEN||!timingSafe(request.headers.get('X-Telegram-Bot-Api-Secret-Token'),e.WEBHOOK_SECRET))return new Response('Forbidden',{status:403});
 let update;try{update=await request.json();}catch{return new Response('Bad request',{status:400});}
 if(!Number.isSafeInteger(update.update_id))return new Response('Bad request',{status:400});
 const t=now(),uid=update.update_id;
 const lock=await run(e.DB,`INSERT INTO updates(id,state,lease_until,created_at) VALUES (?,'processing',?,?) ON CONFLICT(id) DO UPDATE SET state='processing',lease_until=excluded.lease_until WHERE updates.state='processing' AND updates.lease_until<=?`,uid,t+120,t,t);
 if(!lock.meta.changes){const s=await row(e.DB,'SELECT state FROM updates WHERE id=?',uid);return new Response(s?.state==='done'?'OK':'Retry',{status:s?.state==='done'?200:503});}
 try{await dispatch(e,update);await run(e.DB,"UPDATE updates SET state='done' WHERE id=?",uid);return new Response('OK');}
 catch(err){console.error('Update failed',uid,err.message);await run(e.DB,'UPDATE updates SET lease_until=0 WHERE id=?',uid);return new Response('Retry',{status:503});}
}
export default {async fetch(request,e){const p=new URL(request.url).pathname;if(p==='/health'&&request.method==='GET')return Response.json({service:'mr-x-academy',version:'1.2.0',telegram_configured:Boolean(e.BOT_TOKEN&&e.WEBHOOK_SECRET),storage_configured:validChannel(String(e.STORAGE_CHANNEL_ID||'')),admin_configured:admins(e).size>0});if(p==='/telegram/webhook'&&request.method==='POST')return handleWebhook(request,e);return new Response('Not found',{status:404});},async scheduled(_event,e,ctx){ctx.waitUntil((async()=>{if(!e.BOT_TOKEN)return;await validateDue(e,null,null,5);await autoReward(e);await run(e.DB,"DELETE FROM updates WHERE state='done' AND created_at<?",now()-7*86400);})());}};
export const internals={member,slug,validJoinURL,validChannel,sendPDF,claim,makeLink,dispatch,counts,wizRead,wizardCallback,wizardMessage};
