const now=()=>Math.floor(Date.now()/1000);
const id=x=>String(x);
const slug=s=>typeof s==='string' && /^[a-z0-9_-]{1,24}$/.test(s);
const row=(db,sql,...args)=>db.prepare(sql).bind(...args).first();
const run=(db,sql,...args)=>db.prepare(sql).bind(...args).run();
const all=async(db,sql,...args)=>(await db.prepare(sql).bind(...args).all()).results;
const stmt=(db,sql,...args)=>db.prepare(sql).bind(...args);
const cb=(text,callback_data)=>({text,callback_data});
const urlButton=(text,url)=>({text,url});
const menu=[[cb('📚 Catalogue','catalogue'),cb('🆓 Produits gratuits','gratuit')],[cb('🎁 Parrainage','parrainage'),cb('📊 Mes invitations','progression')],[cb('⭐ Produits Premium','premium')],[cb('📂 Ma bibliothèque','bibliotheque'),cb('❔ Assistance','help')]];
const home=[cb('🏠 Accueil','home')];
const member=m=>['member','administrator','creator'].includes(m?.status)||(m?.status==='restricted'&&m.is_member===true);
const validChannel=s=>typeof s==='string'&&/^-100\d+$/.test(s);
const validJoinURL=s=>typeof s==='string'&&/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]+|joinchat\/[A-Za-z0-9_-]+|[A-Za-z0-9_]{5,})$/.test(s);
const admins=e=>new Set(String(e.ADMIN_IDS||'').split(',').map(s=>s.trim()).filter(Boolean));
const telegramId=s=>typeof s==='string'&&/^\d{1,16}$/.test(s);
const timingSafe=(a,b)=>{if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let r=0;for(let i=0;i<a.length;i++)r|=a.charCodeAt(i)^b.charCodeAt(i);return r===0;};
export class TelegramError extends Error {constructor(method,status){super(`Telegram ${method}: ${status}`);this.status=status;}}

// Telegram entities use UTF-16 offsets (the native JavaScript string index).
// The original text is never parsed as markup; arbitrary titles/descriptions are safe.
export function formatTelegram(text,style='auto'){
 const entities=[];if(typeof text!=='string'||!text.trim())return entities;
 const add=(type,offset,length)=>{if(length>0&&offset>=0&&offset+length<=text.length&&!entities.some(x=>offset<x.offset+x.length&&x.offset<offset+length))entities.push({type,offset,length});};
 const lines=text.split('\n');let offset=0;let first=true;
 for(let i=0;i<lines.length;i++){
  const raw=lines[i],line=raw.trim(),at=offset+raw.indexOf(line);offset+=raw.length+1;
  if(!line)continue;
  const heading=first;first=false;
  if(/^https?:\/\/\S+$/.test(line)||/^[🟩⬜]+$/u.test(line))continue;
  if(/^(?:Votre identifiant|Identifiant(?: Telegram)?|ID|Canal) :\s*-?\d+$/.test(line)||/^Identifiant : [a-z0-9_-]+$/i.test(line)){
   const colon=line.indexOf(':');add('bold',at,colon+1);const value=line.slice(colon+1).trim();add('code',at+line.lastIndexOf(value),value.length);continue;
  }
  if(heading){
   // Preserve the complete title for product, welcome, caption and multi-line messages.
   let n=line.length;
   if(lines.length===1&&style==='auto'&&n>100){const end=line.search(/[.!?](?:\s|$)/);n=end>=0&&end<150?end+1:Math.min(n,80);if(n<line.length&&end<0){const space=line.lastIndexOf(' ',n);if(space>0)n=space;}}
   // Avoid splitting surrogate pairs.
   if(n<line.length&&/[\uD800-\uDBFF]/.test(line[n-1]))n--;
   add('bold',at,n);continue;
  }
  if(/^(?:Apprendre\. Appliquer\. Réussir\.|Invitez de nouveaux abonnés réellement intéressés\.|Conseil :|À savoir :|Important :|Les droits déjà acquis|Les fichiers déjà archivés)/i.test(line)){add('blockquote',at,line.length);continue;}
  if(/^(?:Votre lien personnel :|Lien du bot à partager dans le canal :|Choisissez une rubrique :|Conditions d’accès|Votre progression|Récapitulatif|Parrainage :|Boutique web :|Campagnes :)/i.test(line)){
   const colon=line.indexOf(':');add('underline',at,colon>=0?colon+1:line.length);continue;
  }
  if(/^(?:\d+\/\d+ validées|(?:💰 |🏷️ )?Prix :|(?:🆓 )?Gratuit$|✅ Dans votre bibliothèque|✅ Accès|📎 |🎁 Campagne :|🎁 Accès par parrainage|🎁 0 FCFA)/u.test(line)){add('bold',at,line.length);continue;}
  if(/^(?:Utilisateurs|Produits|Invitations valides|En attente|Récompenses|Achats validés|Livraisons uniques|Validées|Statut|Catégorie|Type|Délai de validation)\s*:/.test(line)){
   const n=line.indexOf(':')+1;add('bold',at,n);continue;
  }
  if(/^(?:• |📚 |📖 |⭐ |🎁 |📂 |🔒 |💡 |✓ |⚠️ )/u.test(line)&&style==='welcome'){add('bold',at,line.length);continue;}
  if(/^(?:Choisissez|Envoyez|Sélectionnez|Quel est|Quelle est|Combien|Durée minimale|Comment obtenir|Ajoutez d’abord|Vous pouvez|Actuel(?:le)? :|Sans description|Livre(?:s)? et formation|Livres, formations|Votre accès est conservé|Votre espace|Votre bibliothèque vous accompagne|Bonne lecture)/i.test(line)||style==='product'&&i===1){add('italic',at,line.length);continue;}
  if(style==='wizard'&&i>0&&line.length<=260){add('italic',at,line.length);continue;}
 }
 return entities.sort((a,b)=>a.offset-b.offset);
}

export async function tg(e,method,payload,style='auto'){
 const multipart=payload instanceof FormData;
 if(!multipart&&payload&&!payload.parse_mode){
  const key=method==='sendMessage'?'text':['sendPhoto','sendDocument','sendVideo','sendAudio','sendVoice','sendAnimation'].includes(method)?'caption':null;
  const entityKey=key==='text'?'entities':'caption_entities';
  if(key&&typeof payload[key]==='string'&&!payload[entityKey]){const entities=formatTelegram(payload[key],style);if(entities.length)payload={...payload,[entityKey]:entities};}
 }
 const res=await fetch(`https://api.telegram.org/bot${e.BOT_TOKEN}/${method}`,{method:'POST',headers:multipart?{}:{'Content-Type':'application/json'},body:multipart?payload:JSON.stringify(payload)});
 const j=await res.json();if(!res.ok||!j.ok)throw new TelegramError(method,j.error_code||res.status);return j.result;
}
const send=(e,chat,text,buttons,style='auto')=>tg(e,'sendMessage',{chat_id:chat,text, ...(buttons?{reply_markup:{inline_keyboard:buttons}}:{})},style);
const getMember=async(e,channel,user)=>member(await tg(e,'getChatMember',{chat_id:channel,user_id:Number(user)}));
const touch=(e,user)=>run(e.DB,'INSERT OR IGNORE INTO users(id,created_at) VALUES (?,?)',user,now());
const product=(e,p)=>row(e.DB,'SELECT * FROM products WHERE id=?',p);
const campaign=(e,c)=>row(e.DB,`SELECT c.*,p.title,p.active AS product_active FROM campaigns c JOIN products p ON p.id=c.product_id WHERE c.id=?`,c);
const entitlement=(e,u,p)=>row(e.DB,'SELECT * FROM entitlements WHERE user_id=? AND product_id=?',u,p);
const grant=(e,u,p,source)=>run(e.DB,'INSERT OR IGNORE INTO entitlements(user_id,product_id,source,created_at) VALUES (?,?,?,?)',u,p,source,now());
const audit=(e,u,action,target)=>run(e.DB,'INSERT INTO audit(admin_id,action,target,created_at) VALUES (?,?,?,?)',u,action,target,now());
async function photo(e,chat,caption,buttons,key,fileId,style='auto'){
 if(fileId){try{return await tg(e,'sendPhoto',{chat_id:chat,photo:fileId,caption,reply_markup:{inline_keyboard:buttons||[]}},style);}catch(err){if(err.status!==400)throw err;}}
 return send(e,chat,caption,buttons,style);
}
async function welcome(e,u){
 const s=await row(e.DB,"SELECT value FROM settings WHERE key='welcome_key'");const f=await row(e.DB,"SELECT value FROM settings WHERE key='welcome_file_id'");
 return photo(e,u,'🎓 Bienvenue dans MR X ACADEMY !\n\nVotre espace pour apprendre, développer vos compétences et passer à l’action.\n\nApprendre. Appliquer. Réussir.\n\n📚 Explorez nos livres et formations\n📖 Accédez aux ressources gratuites\n⭐ Découvrez nos contenus Premium\n🎁 Débloquez des formations par parrainage\n\nVotre bibliothèque vous accompagne partout, directement sur Telegram.\n\nChoisissez une rubrique :',admins(e).has(u)?[...menu,[cb('⚙️ Administration','aw:menu')]]:menu,s?.value,f?.value,'welcome');
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
 const buttons=[];if(access||p.price_xof===0)buttons.push([cb('📥 Accéder aux ressources',`get:${pid}`)]);
 if(!access&&p.price_xof>0)for(const c of cs)buttons.push([cb(`🎁 Obtenir gratuitement · ${c.target} abonnés`,`c:${c.id}`)]);
 buttons.push(home);
 const price=p.price_xof===0?'Gratuit':`${p.price_xof.toLocaleString('fr-FR')} FCFA`;const offers=cs.map(c=>`🎁 0 FCFA après ${c.target} nouveaux abonnés validés`).join('\n');
 const resources=await productAssets(e,p);const caption=(''+p.title+'\n'+p.category+' · '+resources.length+' ressource(s)'+'\n\n💰 Prix : '+price+'\n'+(!access&&p.price_xof>0&&cs.length?offers+'\n':'')+'\n'+p.description+(access?'\n\n✅ Dans votre bibliothèque.':'')).slice(0,1000);
 return photo(e,u,caption,buttons,p.cover_key,p.cover_file_id,'product');
}

// V1.4: ordered resource manifest. Legacy PDF products remain readable without migration.
const assetKey=p=>'product_assets:'+p;
const assetMethods={document:'sendDocument',video:'sendVideo',audio:'sendAudio',voice:'sendVoice',photo:'sendPhoto',animation:'sendAnimation'};
const assetIcons={document:'📄',video:'🎬',audio:'🎧',voice:'🎙',photo:'🖼',animation:'🎞',link:'🔗'};
const assetURL=s=>{try{const u=new URL(s);return s.length<=1000&&u.protocol==='https:'&&!u.username&&!u.password&&u.hostname.includes('.')&&u.hostname!=='localhost';}catch{return false;}};
function readAsset(m){
 for(const kind of ['animation','video','audio','voice','document','photo']){
  const f=kind==='photo'?m.photo?.at(-1):m[kind];if(!f?.file_id)continue;
  const name=String(f.file_name||f.title||m.caption||({video:'Vidéo',audio:'Audio',voice:'Audio vocal',photo:'Image',animation:'Animation',document:'Document'}[kind])).trim().slice(0,120);
  return {kind,id:f.file_id,name:name||'Ressource',...(f.file_unique_id?{unique:f.file_unique_id}:{}),size:f.file_size||0};
 }
 const t=String(m.text||'').trim();if(assetURL(t))return {kind:'link',url:t,name:'Lien externe'};
 return null;
}
const legacyAssets=(p)=>p?.file_id?[{kind:'document',id:p.file_id,name:p.filename||'Document'}]:[];
async function productAssets(e,p){
 const r=await row(e.DB,'SELECT value FROM settings WHERE key=?',assetKey(p.id));
 if(!r)return legacyAssets(p);
 const a=JSON.parse(r.value);if(!Array.isArray(a))throw Error('Invalid resource manifest');return a;
}
const draftAssets=d=>Array.isArray(d.assets)?d.assets:(d.file?[{kind:'document',id:d.file,name:d.filename||'Document'}]:[]);
function setDraftAssets(d,a){d.assets=a;d.file=a.find(x=>x.kind!=='link')?.id||null;d.filename=a[0]?.name||'Ressources';}
async function sendAsset(e,chat,a,caption,protect=false){
 if(a.kind==='link')return tg(e,'sendMessage',{chat_id:chat,text:caption+'\n\n'+a.url,protect_content:protect,link_preview_options:{is_disabled:true}});
 const method=assetMethods[a.kind];if(!method||!a.id)throw Error('Invalid asset');
 return tg(e,method,{chat_id:chat,[a.kind]:a.id,caption:caption.slice(0,1000),protect_content:protect});
}
async function resourceAccess(e,u,p){
 let access=await entitlement(e,u,p.id);
 if(!access&&p.active&&p.price_xof===0){await grant(e,u,p.id,'free');access=await entitlement(e,u,p.id);}
 return !!access;
}
async function resourceMenu(e,u,p,a,page=0){
 const start=page*8;
 const b=a.slice(start,start+8).map((x,j)=>[cb((assetIcons[x.kind]||'📎')+' '+(start+j+1)+'. '+x.name.slice(0,40),'asset:'+p.id+':'+(start+j))]);
 const nav=[];if(page>0)nav.push(cb('◀','assets:'+p.id+':'+(page-1)));if(start+8<a.length)nav.push(cb('▶','assets:'+p.id+':'+(page+1)));if(nav.length)b.push(nav);
 b.push([cb('📂 Ma bibliothèque','bibliotheque')],home);
 return send(e,u,'📂 '+p.title+'\n\n'+a.length+' ressources disponibles.\nChoisissez un fichier ou un lien :',b);
}
async function deliverResource(e,u,p,a,index){
 const x=a[index];if(!x)return send(e,u,'Ressource introuvable.',[[cb('Voir les ressources','get:'+p.id)]]);
 try{await sendAsset(e,u,x,'📥 '+p.title+'\n'+(index+1)+'/'+a.length+' — '+x.name,p.price_xof>0);}
 catch(err){if(err.status!==400)throw err;return send(e,u,'Ressource temporairement indisponible. Votre accès est conservé.',[[cb('Voir les ressources','get:'+p.id)]]);}
 await run(e.DB,'INSERT OR IGNORE INTO deliveries(user_id,product_id,delivered_at) VALUES (?,?,?)',u,p.id,now());
}
async function resourceAction(e,u,pid,index,menuOnly=false){
 const p=await product(e,pid);if(!p)return send(e,u,'Produit introuvable.',[home]);
 if(!await resourceAccess(e,u,p))return send(e,u,'🔒 Ce produit n’est pas encore débloqué.',[[cb('Voir le produit','p:'+pid)],home]);
 const a=await productAssets(e,p);if(!a.length)return send(e,u,'Aucune ressource disponible. Votre accès est conservé.',[home]);
 return menuOnly?resourceMenu(e,u,p,a,index):deliverResource(e,u,p,a,index);
}

async function sendPDF(e,u,pid){
 const p=await product(e,pid);if(!p)return send(e,u,'Produit introuvable.',[home]);
 if(!await resourceAccess(e,u,p))return send(e,u,'🔒 Ce produit n’est pas encore débloqué.',[[cb('Voir le produit','p:'+pid)],home]);
 const assets=await productAssets(e,p);if(!assets.length)return send(e,u,'Aucune ressource disponible. Votre accès est conservé.',[home]);
 return assets.length===1?deliverResource(e,u,p,assets,0):resourceMenu(e,u,p,assets);
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
const basicSteps=['title','category','price','description','cover','pdf'];
const premiumSteps=d=>d.price>0?['shop','access',...(d.access==='new'?['channeltype','channel','target','hold']:[])]:[];
const wizSteps=d=>[...basicSteps,...premiumSteps(d),'review'];
const afterPDF=d=>d.price>0?'shop':'review';
const shopKey=p=>'product_shop:'+p;
const shopURL=s=>{try{const u=new URL(s);return s.length<=500&&u.protocol==='https:'&&!u.username&&!u.password&&u.hostname.includes('.')&&!['localhost','127.0.0.1'].includes(u.hostname);}catch{return false;}};
const channelReq=d=>parseInt(d.session.slice(0,7),16)+1;
async function channelDetails(e,chatRef,kind){
 const chat=await tg(e,'getChat',{chat_id:chatRef});
 const cid=id(chat.id);
 if(chat.type!=='channel'||!validChannel(cid)||cid===String(e.STORAGE_CHANNEL_ID||'').trim())throw new Error('Canal non autorisé');
 if(kind==='public'&&!chat.username||kind==='private'&&chat.username)throw new Error('Type de canal différent');
 const me=await tg(e,'getMe',{}),status=await tg(e,'getChatMember',{chat_id:cid,user_id:me.id});
 if(status.status!=='administrator'||!status.can_invite_users)throw new Error('Le bot doit être administrateur avec le droit d’inviter');
 return {id:cid,title:String(chat.title||'Canal').slice(0,100),username:chat.username||''};
}
async function channelPicker(e,u,d){
 await tg(e,'sendMessage',{chat_id:u,text:'Sélectionnez le canal '+(d.kind==='private'?'privé':'public')+' dans Telegram. Ajoutez d’abord le bot comme administrateur, droit Inviter des utilisateurs.',reply_markup:{keyboard:[[{text:'📢 Sélectionner un canal',request_chat:{request_id:channelReq(d),chat_is_channel:true,chat_has_username:d.kind==='public',bot_is_member:true,request_title:true,request_username:true}}]],resize_keyboard:true,one_time_keyboard:true}});
}
async function closePicker(e,u){await tg(e,'sendMessage',{chat_id:u,text:'Sélection du canal terminée.',reply_markup:{remove_keyboard:true}});}
async function premiumChannel(e,u,d,m){
 const t=String(m.text||'').trim();
 let ref=null;
 if(m.chat_shared&&m.chat_shared.request_id===channelReq(d))ref=id(m.chat_shared.chat_id);
 else if(m.forward_origin?.type==='channel')ref=id(m.forward_origin.chat.id);
 else if(validChannel(t))ref=t;
 else if(/^https:\/\/t\.me\/c\/\d+\/\d+\/?$/.test(t))ref='-100'+t.split('/')[4];
 else if(/^@[A-Za-z0-9_]{5,}$/.test(t))ref=t;
 else if(/^https:\/\/t\.me\/[A-Za-z0-9_]{5,}\/?$/.test(t))ref='@'+t.split('/')[3];
 if(!ref)return send(e,u,'Un lien privé t.me/+… seul ne permet pas au bot de retrouver le canal. Utilisez le bouton Sélectionner un canal, transférez une publication ou envoyez son ID -100… / lien t.me/c/…',wizButtons(d,[[cb('📢 Sélectionner un canal',wizAction(d,'picker'))]]));
 let ch;try{ch=await channelDetails(e,ref,d.kind);}catch{return send(e,u,'Canal inaccessible ou incorrect. Vérifiez le type de canal, ajoutez le bot comme administrateur avec le droit d’inviter et ne choisissez pas le canal de stockage.',wizButtons(d,[[cb('📢 Sélectionner un canal',wizAction(d,'picker'))]]));}
 d.channel=ch;delete d.campaignId;delete d.joinLink;delete d.joinChannel;d.step='target';await wizSave(e,u,d);await closePicker(e,u);return wizPrompt(e,u,d);
}

const wizAction=(d,a)=>'aw:'+d.session+':'+d.step+':'+a;
const wizCancel=d=>[cb('❌ Annuler',wizAction(d,'cancel')),cb('⏸ Pause','aw:menu')];
const wizButtons=(d,extra=[])=>[...extra,...((d.step==='title'&&d.title)||(d.step==='category'&&d.category)||(d.step==='price'&&Number.isSafeInteger(d.price))||(d.step==='description'&&typeof d.description==='string')||(d.step==='cover'&&d.cover)||(d.step==='pdf'&&draftAssets(d).length)?[[cb('✓ Conserver la valeur actuelle',wizAction(d,'keep'))]]:[]),...(d.step==='title'?[]:[[cb('⬅ Retour',wizAction(d,'back'))]]),wizCancel(d)];
async function wizRead(e,u){const r=await row(e.DB,'SELECT value FROM settings WHERE key=?',wizKey(u));return r?JSON.parse(r.value):null;}
const wizSave=(e,u,d)=>run(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',wizKey(u),JSON.stringify(d));
async function wizMenu(e,u){
 const d=await wizRead(e,u);if(d&&!d.paused){d.paused=true;await wizSave(e,u,d);}
 return send(e,u,'⚙️ Administration • MR X ACADEMY\n\nChoisissez une action.',[
 [cb(d?'▶ Reprendre la création':'➕ Nouvelle formation',d?'aw:resume':'aw:new')],
 [cb('📚 Gérer les formations','aw:list:0')],[cb('📣 Promouvoir les produits','ad:menu')],[cb('📊 Statistiques','aw:stats')],home]);
}
async function wizPrompt(e,u,d){
 const steps=wizSteps(d),n=steps.indexOf(d.step)+1;
 const prefix='🎓 '+(d.edit?'Modifier la formation':'Nouvelle formation')+' — étape '+n+'/'+steps.length+'\n\n';
 const say=(t,b=[])=>send(e,u,prefix+t,wizButtons(d,b),'wizard');
 switch(d.step){
 case 'title':return say('Quel est le titre de la formation ? Envoyez-le en message.'+(d.title?'\nActuel : '+d.title:''));
 case 'category':return say('Choisissez une catégorie ou écrivez votre propre catégorie.'+(d.category?'\nActuelle : '+d.category:''),wizardCategories.map((c,i)=>[cb(c,wizAction(d,'cat'+i))]));
 case 'price':return say('Quel est le prix de la formation en FCFA ? Envoyez un montant entier, ou choisissez Gratuit.'+(Number.isSafeInteger(d.price)?'\nActuel : '+d.price+' FCFA':''),[[cb('🆓 Gratuit',wizAction(d,'free'))]]);
 case 'description':return say('Envoyez une courte description (650 caractères maximum), ou passez cette étape.',[[cb('⏭ Sans description',wizAction(d,'skip'))]]);
 case 'cover':return say('Envoyez la photo de couverture dans cette conversation (en tant que photo Telegram).');
 case 'pdf':{const a=draftAssets(d);return say('Envoyez les ressources une par une : documents (PDF, ZIP, RAR, etc.), vidéos, audios, images ou liens HTTPS.\n\n'+a.length+' / 100 ressources enregistrées.\n'+a.slice(-5).map((x,i)=> (assetIcons[x.kind]||'📎')+' '+x.name).join('\n')+'\n\nCliquez sur Terminer lorsque tout est ajouté.',[...(a.length?[[cb('✅ Terminer les ressources',wizAction(d,'done_assets'))],[cb('↩ Retirer la dernière',wizAction(d,'remove_asset'))],[cb('🗑 Vider la liste',wizAction(d,'clear_assets'))]]:[])]);}
 case 'shop':return say('Envoyez le lien HTTPS de la fiche de vente sur votre boutique web indépendante (Ficsell, etc.) ou passez cette étape. Il sera conservé pour votre administration et futur catalogue web, pas utilisé comme paiement dans Telegram.'+(d.shop?'\nActuel : '+d.shop:''),[[cb('⏭ Sans lien',wizAction(d,'skip'))],...(d.shop?[[cb('✓ Conserver le lien',wizAction(d,'keep_shop'))]]:[])]);
 case 'access':return say('Comment obtenir ce livre Premium ? Vous pouvez conserver les campagnes existantes ou créer une nouvelle campagne de parrainage. Une nouvelle campagne ne supprime pas les anciennes. Les achats web vérifiés restent accordés manuellement.',[[cb('🎁 Créer une campagne',wizAction(d,'new_campaign'))],[cb('✓ Pas de nouvelle campagne',wizAction(d,'keep_campaign'))]]);
 case 'channeltype':return say('Quel type de canal souhaitez-vous développer ?',[[cb('🌐 Canal public',wizAction(d,'public'))],[cb('🔒 Canal privé',wizAction(d,'private'))]]);
 case 'channel':return say('Ajoutez le bot comme administrateur du canal cible avec le droit Inviter. Sélectionnez ensuite le canal dans Telegram, transférez une publication, ou envoyez @username / lien public / ID -100… / lien t.me/c/… . Le canal de stockage est interdit.',[[cb('📢 Sélectionner le canal',wizAction(d,'picker'))]]);
 case 'target':return say('Combien de nouveaux abonnés validés sont nécessaires ? Envoyez un nombre de 1 à 20.',[[cb('5',wizAction(d,'n5')),cb('10',wizAction(d,'n10')),cb('15',wizAction(d,'n15')),cb('20',wizAction(d,'n20'))]]);
 case 'hold':return say('Durée minimale d’abonnement avant validation ? Envoyez un nombre entier d’heures de 0 à 168.',[[cb('24 h (recommandé)',wizAction(d,'h24')),cb('0 h (test)',wizAction(d,'h0'))]]);
 case 'review':{
  const caption='✅ Aperçu avant publication\n\n'+d.title+'\n'+d.category+'\n💰 Prix : '+(d.price===0?'Gratuit':d.price.toLocaleString('fr-FR')+' FCFA')+'\n\n'+(d.description||'Sans description')+'\n\n📎 '+draftAssets(d).length+' ressource(s) : '+draftAssets(d).slice(0,3).map(x=>x.name).join(', ')+(d.price>0?'\n\nBoutique web : '+(d.shop?'lien enregistré':'aucun lien')+'\nParrainage : '+(d.access==='new'?d.target+' nouveaux abonnés • '+d.hold+' h • '+d.channel.title+' ('+d.kind+')':'pas de nouvelle campagne'):'');
  return photo(e,u,caption.slice(0,1000),wizButtons(d,[[cb('✅ Publier',wizAction(d,'publish'))],[cb('💾 Garder en brouillon',wizAction(d,'draft'))]]),null,d.cover,'wizard');
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
 const cs=await all(e.DB,'SELECT id,channel_id,target,hold_seconds,active FROM campaigns WHERE product_id=? ORDER BY id',pid);
 const shop=await row(e.DB,'SELECT value FROM settings WHERE key=?',shopKey(pid));const assets=await productAssets(e,p);
 const b=[[cb('✏️ Compléter / modifier','aw:edit:'+pid)]];if(cs.length)b.push([cb('🎁 Gérer les campagnes','aw:campaigns:'+pid)]);if(p.active)b.push([cb('Masquer du catalogue','aw:hide:'+pid)]);else if(assets.length)b.push([cb('Publier','aw:show:'+pid)]);
 if(assets.length)b.push([cb('📎 Tester les ressources','aw:test:'+pid)]);if(p.active)b.push([cb('📣 Promouvoir ce produit','ad:item:'+pid)]);
 b.push([cb('⬅ Formations','aw:list:0')]);
 return photo(e,u,(p.title+'\n'+p.category+'\n'+p.price_xof+' FCFA\n'+(p.active?'Publié':'Brouillon')+'\n'+(assets.length?assets.length+' ressource(s) enregistrée(s)':'Aucune ressource')+'\nBoutique web : '+(shop?.value||'non configurée')+'\nCampagnes : '+(cs.length?cs.map(c=>c.id+' · '+c.target+' invitations · '+(c.active?'active':'arrêtée')).join('\n'):'aucune')+'\n\n'+p.description).slice(0,1000),b,null,p.cover_file_id);
}
async function wizardCallback(e,u,action){
 if(!admins(e).has(u))return send(e,u,'Commande non autorisée.');
 if(action==='aw:menu')return wizMenu(e,u);
 if(action==='aw:stats')return adminCommand(e,u,'admin','',null,true);
 if(action==='aw:resume'){const d=await wizRead(e,u);if(!d)return wizMenu(e,u);d.paused=false;await wizSave(e,u,d);return wizPrompt(e,u,d);}
 if(action==='aw:new'){
  const old=await wizRead(e,u);if(old){old.paused=false;await wizSave(e,u,old);return wizPrompt(e,u,old);}
  const d={id:'f-'+crypto.randomUUID().replace(/-/g,'').slice(0,20),session:crypto.randomUUID().replace(/-/g,'').slice(0,16),step:'title'};await wizSave(e,u,d);return wizPrompt(e,u,d);
 }
 const v=action.split(':');
 if(v.length===3&&v[1]==='list'&&/^\d{1,3}$/.test(v[2]))return wizList(e,u,Number(v[2]));
 if(v.length===3&&slug(v[2])){
  if(v[1]==='campaigns'){
   const cs=await all(e.DB,'SELECT id,target,hold_seconds,active FROM campaigns WHERE product_id=? ORDER BY id LIMIT 30',v[2]);
   return send(e,u,'🎁 Campagnes de parrainage', [...cs.map(c=>[cb((c.active?'🟢 ':'⚪ ')+c.target+' invitations · '+c.hold_seconds/3600+' h · '+c.id.slice(-8),'aw:camp:'+c.id)]),[cb('⬅ Formation','aw:product:'+v[2])]]);
  }
  if(['camp','stop','stopconfirm'].includes(v[1])){
   const c=await campaign(e,v[2]);if(!c)return wizMenu(e,u);
   if(v[1]==='stop')return send(e,u,'Arrêter cette campagne ? Les droits déjà acquis restent disponibles, mais les invitations en cours ne permettront plus de débloquer le livre.',[[cb('Confirmer l’arrêt','aw:stopconfirm:'+c.id)],[cb('Retour','aw:camp:'+c.id)]]);
   if(v[1]==='stopconfirm'){await run(e.DB,'UPDATE campaigns SET active=0 WHERE id=?',c.id);await audit(e,u,'wizard_campaignoff',c.id);return send(e,u,'Campagne arrêtée.',[[cb('⬅ Formation','aw:product:'+c.product_id)]]);}
   const me=await tg(e,'getMe',{}),link=me.username?'https://t.me/'+me.username+'?start=c_'+c.id:'';
   const total=await row(e.DB,"SELECT SUM(CASE WHEN state='valid' THEN 1 ELSE 0 END) valid,SUM(CASE WHEN state='pending' THEN 1 ELSE 0 END) pending FROM referrals WHERE campaign_id=?",c.id);
   return send(e,u,'🎁 '+c.title+'\n'+c.target+' nouveaux abonnés · '+c.hold_seconds/3600+' h\nCanal : '+c.channel_id+'\nStatut : '+(c.active?'active':'arrêtée')+'\nValidées : '+(total?.valid||0)+' · En attente : '+(total?.pending||0)+'\n\nLien du bot à partager dans le canal :\n'+link,[[...(c.active?[cb('Arrêter','aw:stop:'+c.id)]:[]),cb('⬅ Formation','aw:product:'+c.product_id)]]);
  }
  const p=await product(e,v[2]);
  if(v[1]==='product')return wizProduct(e,u,v[2]);
  if(!p)return wizList(e,u);
  if(v[1]==='edit'){
   const old=await wizRead(e,u);if(old)return send(e,u,'Une création est déjà en cours.',[[cb('Reprendre','aw:resume')],[cb('Administration','aw:menu')]]);
   const shop=await row(e.DB,'SELECT value FROM settings WHERE key=?',shopKey(p.id));const d={id:p.id,session:crypto.randomUUID().replace(/-/g,'').slice(0,16),step:'title',edit:true,title:p.title,category:p.category,price:p.price_xof,description:p.description,cover:p.cover_file_id,file:p.file_id,filename:p.filename,assets:await productAssets(e,p),shop:shop?.value||''};await wizSave(e,u,d);return wizPrompt(e,u,d);
  }
  if(v[1]==='test'){const a=await productAssets(e,p);if(!a.length)return send(e,u,'Aucune ressource.');return send(e,u,'📎 Test administrateur — '+p.title,a.slice(0,100).map((x,j)=>[cb((assetIcons[x.kind]||'📎')+' '+x.name.slice(0,45),'atest:'+p.id+':'+j)]));}
  if(v[1]==='hide'||v[1]==='show'){
   if(v[1]==='show'&&!(await productAssets(e,p)).length)return send(e,u,'Ressource manquante.');
   await run(e.DB,'UPDATE products SET active=? WHERE id=?',v[1]==='show'?1:0,p.id);
   await audit(e,u,'wizard_'+v[1],p.id);return wizProduct(e,u,p.id);
  }
 }
 const d=await wizRead(e,u);
 if(!d||d.paused||v.length!==4||v[1]!==d.session||v[2]!==d.step)return send(e,u,'Cette étape a expiré.',[[cb('Reprendre','aw:resume')],[cb('Administration','aw:menu')]]);
 const a=v[3];
 if(a==='cancel'){if(d.step==='channel')await closePicker(e,u);await run(e.DB,'DELETE FROM settings WHERE key=?',wizKey(u));return send(e,u,'Création annulée. Les fichiers déjà archivés restent dans le canal privé.',[[cb('➕ Nouvelle formation','aw:new')],[cb('Administration','aw:menu')]]);}
 if(a==='back'){if(d.step==='channel')await closePicker(e,u);const steps=wizSteps(d),i=steps.indexOf(d.step);if(i>0)d.step=steps[i-1];await wizSave(e,u,d);return wizPrompt(e,u,d);}
 if(d.step==='pdf'&&['done_assets','keep','remove_asset','clear_assets'].includes(a)){const list=draftAssets(d);if(a==='clear_assets'){setDraftAssets(d,[]);}else if(a==='remove_asset'){setDraftAssets(d,list.slice(0,-1));}else if(list.length){setDraftAssets(d,list);d.step=afterPDF(d);}else return wizPrompt(e,u,d);
 }else if(a==='keep'&&basicSteps.includes(d.step)){
  const field={title:'title',category:'category',price:'price',description:'description',cover:'cover',pdf:'file'}[d.step];if(d[field]===undefined||d[field]===null||(['title','category','cover','pdf'].includes(d.step)&&!d[field]))return wizPrompt(e,u,d);d.step=d.step==='pdf'?afterPDF(d):basicSteps[basicSteps.indexOf(d.step)+1];
 }else if(d.step==='category'&&/^cat[0-6]$/.test(a)){d.category=wizardCategories[Number(a.slice(3))];d.step='price';}
 else if(d.step==='price'&&a==='free'){d.price=0;d.step='description';}
 else if(d.step==='description'&&a==='skip'){d.description='';d.step='cover';}
 else if(d.step==='shop'&&['skip','keep_shop'].includes(a)){if(a==='skip')d.shop='';d.step='access';}
 else if(d.step==='access'&&['new_campaign','keep_campaign'].includes(a)){d.access=a==='new_campaign'?'new':'keep';if(d.access==='new'){delete d.campaignId;delete d.joinLink;delete d.joinChannel;}d.step=d.access==='new'?'channeltype':'review';}
 else if(d.step==='channeltype'&&['public','private'].includes(a)){d.kind=a;d.channel=null;delete d.campaignId;delete d.joinLink;delete d.joinChannel;d.step='channel';}
 else if(d.step==='channel'&&a==='picker')return channelPicker(e,u,d);
 else if(d.step==='target'&&/^n(5|10|15|20)$/.test(a)){d.target=Number(a.slice(1));delete d.campaignId;d.step='hold';}
 else if(d.step==='hold'&&/^h(0|24)$/.test(a)){d.hold=Number(a.slice(1));delete d.campaignId;d.step='review';}
 else if(d.step==='review'&&['publish','draft'].includes(a)){
  if(!d.title||!d.category||!Number.isSafeInteger(d.price)||d.price<0||!d.cover||!draftAssets(d).length||!d.filename)return send(e,u,'Brouillon incomplet.',[[cb('Reprendre','aw:resume')]]);
  const active=a==='publish'?1:0;
  const existing=d.edit?await product(e,d.id):null;
  if(d.edit&&!existing)return send(e,u,'Produit introuvable.',[[cb('Administration','aw:menu')]]);
  if(existing&&existing.price_xof!==d.price&&existing.active)return send(e,u,'Masquez d’abord ce produit pour modifier son prix, puis reprenez le brouillon.',[[cb('Administration','aw:menu')]]);
  const write=d.edit?stmt(e.DB,'UPDATE products SET title=?,category=?,description=?,price_xof=?,active=?,filename=?,file_id=?,cover_file_id=?,object_key=NULL,cover_key=NULL WHERE id=?',d.title,d.category,d.description||'',d.price,active,d.filename,d.file,d.cover,d.id):stmt(e.DB,'INSERT OR IGNORE INTO products(id,title,category,description,price_xof,active,filename,file_id,cover_file_id) VALUES (?,?,?,?,?,?,?,?,?)',d.id,d.title,d.category,d.description||'',d.price,active,d.filename,d.file,d.cover);
  const extra=[stmt(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',assetKey(d.id),JSON.stringify(draftAssets(d)))];
  if(d.price>0){
   extra.push(stmt(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',shopKey(d.id),d.shop||''));
   if(d.access==='new'){
    if(!d.channel||!Number.isInteger(d.target)||d.target<1||d.target>20||!Number.isInteger(d.hold)||d.hold<0||d.hold>168)return send(e,u,'Conditions de parrainage incomplètes.',[[cb('Reprendre','aw:resume')]]);
    let ch;try{ch=await channelDetails(e,d.channel.id,d.kind);}catch{return send(e,u,'Le bot n’a plus les droits nécessaires sur ce canal. Rétablissez-les puis réessayez.',wizButtons(d,[[cb('Réessayer',wizAction(d,a))]]));}
    const same=await row(e.DB,'SELECT id FROM campaigns WHERE product_id=? AND channel_id=? AND target=? AND hold_seconds=? AND active=1 LIMIT 1',d.id,ch.id,d.target,d.hold*3600);
    if(same)d.campaignId=same.id;
    else{
     d.campaignId=d.campaignId||'c-'+crypto.randomUUID().replace(/-/g,'').slice(0,20);
     let join=ch.username?'https://t.me/'+ch.username:null;
     if(!join){
      if(d.joinLink&&d.joinChannel===ch.id)join=d.joinLink;
      else{try{const made=await tg(e,'createChatInviteLink',{chat_id:ch.id,name:'academy-entry-'+d.campaignId.slice(-8),creates_join_request:false});join=made.invite_link;}catch{return send(e,u,'Création du lien privé impossible. Vérifiez les droits d’invitation.',wizButtons(d,[[cb('Réessayer',wizAction(d,a))]]));}
      if(!validJoinURL(join))return send(e,u,'Telegram n’a pas fourni de lien valide.',wizButtons(d));d.joinLink=join;d.joinChannel=ch.id;}
     }
     await wizSave(e,u,d);
     extra.push(stmt(e.DB,'INSERT OR IGNORE INTO campaigns(id,product_id,channel_id,channel_url,target,hold_seconds,active) VALUES (?,?,?,?,?,?,1)',d.campaignId,d.id,ch.id,join,d.target,d.hold*3600));
    }
   }
  }else{extra.push(stmt(e.DB,'DELETE FROM settings WHERE key=?',shopKey(d.id)));extra.push(stmt(e.DB,'UPDATE campaigns SET active=0 WHERE product_id=?',d.id));}
  await e.DB.batch([
   write,...extra,
   stmt(e.DB,'DELETE FROM settings WHERE key=?',wizKey(u)),
   stmt(e.DB,'INSERT INTO audit(admin_id,action,target,created_at) VALUES (?,?,?,?)',u,'wizard_'+a,d.id,now())
  ]);
  return send(e,u,(active?'🎉 Formation publiée !':'💾 Formation enregistrée en brouillon.')+'\n'+d.title+'\nIdentifiant : '+d.id+(d.price>0?(d.campaignId?'\n\n🎁 Campagne : '+d.campaignId+'\n'+d.target+' abonnés • '+d.hold+' h. '+(active?'Les utilisateurs peuvent y participer.':'Elle sera disponible à la publication.'):'\n\nAccès Premium : campagnes existantes ou accès accordé après achat web vérifié.'):''),[[cb('Voir la formation','aw:product:'+d.id)],[cb('➕ Nouvelle formation','aw:new')],[cb('Administration','aw:menu')]]);
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
  const list=draftAssets(d),a=readAsset(m);
  if(!a)return invalid('Envoyez un document, une vidéo, un audio, une image ou un lien HTTPS.');
  if(list.length>=100)return invalid('Limite de 100 ressources par produit. Cliquez sur Terminer.');
  if(list.some(x=>a.unique&&x.unique===a.unique||a.id&&x.id===a.id||a.url&&x.url===a.url))return invalid('Ressource déjà enregistrée. Envoyez la suivante ou terminez.');
  if(!validChannel(String(e.STORAGE_CHANNEL_ID||'')))return invalid('Le canal de stockage est mal configuré.');
  try{await sendAsset(e,String(e.STORAGE_CHANNEL_ID),a,'Archive Academy — '+d.id+' — '+(list.length+1)+' — '+a.name,true);}catch(err){return invalid('Archivage impossible. Vérifiez les droits du bot et réessayez.');}
  setDraftAssets(d,[...list,a]);break;
 }
 case 'shop':if(t==='0'){d.shop='';}else if(!shopURL(t))return invalid('Envoyez un lien HTTPS valide ou 0.');else d.shop=t;d.step='access';break;
 case 'channel':return premiumChannel(e,u,d,m);
 case 'target':if(!/^\d{1,2}$/.test(t)||Number(t)<1||Number(t)>20)return invalid('Nombre de nouveaux abonnés : de 1 à 20.');d.target=Number(t);delete d.campaignId;d.step='hold';break;
 case 'hold':if(!/^\d{1,3}$/.test(t)||Number(t)>168)return invalid('Durée de 0 à 168 heures.');d.hold=Number(t);delete d.campaignId;d.step='review';break;
 case 'review':return wizPrompt(e,u,d);
 default:return wizMenu(e,u);
 }
 await wizSave(e,u,d);return wizPrompt(e,u,d);
}

const adminCmds=new Set(['admin','product','campaign','file','cover','banner','publish','unpublish','grant','campaignoff']);

// Administrator-only channel promotion. The Premium PDF is never sent to the channel.
const promoKey=u=>'academy_promo:'+u;
const promoRead=async(e,u)=>{const r=await row(e.DB,'SELECT value FROM settings WHERE key=?',promoKey(u));return r?JSON.parse(r.value):null;};
const promoSave=(e,u,d)=>run(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',promoKey(u),JSON.stringify(d));
const promoClear=(e,u)=>run(e.DB,'DELETE FROM settings WHERE key=?',promoKey(u));
const promoValid=(link,username)=>typeof link==='string'&&/^[A-Za-z0-9_]{5,}$/.test(username)&&new RegExp('^https://t\\.me/'+username+'/[1-9][0-9]*$','i').test(link);
async function promoCampaign(e,cid){
 const c=await campaign(e,cid);if(!c?.active||!c.product_active||c.product_id!=='masterclass')return null;
 const p=await product(e,c.product_id);if(!p?.active||p.price_xof<=0||!p.file_id)return null;
 const ch=await channelDetails(e,c.channel_id,'public');
 return ch.username&&/^[A-Za-z0-9_]{5,}$/.test(ch.username)?{c,p,ch}:null;
}

async function genericPromoProduct(e,pid){
 const p=await product(e,pid);if(!p?.active||!(await productAssets(e,p)).length)return null;return p;
}
async function promoProducts(e,u,page=0){
 const ps=await all(e.DB,'SELECT id,title FROM products WHERE active=1 ORDER BY title,id LIMIT 9 OFFSET ?',page*8);
 const b=ps.slice(0,8).map(p=>[cb(p.title.slice(0,50),'ad:item:'+p.id)]);
 const nav=[];if(page>0)nav.push(cb('◀','ad:page:'+(page-1)));if(ps.length>8)nav.push(cb('▶','ad:page:'+(page+1)));if(nav.length)b.push(nav);
 return send(e,u,'📣 Sélectionnez le produit à promouvoir.',[...b,[cb('⬅ Promotion','ad:menu')]]);
}
async function promoDestination(e,ref){
 const chat=await tg(e,'getChat',{chat_id:ref}),cid=id(chat.id);
 if(chat.type!=='channel'||!validChannel(cid)||cid===String(e.STORAGE_CHANNEL_ID||'').trim())throw Error('Invalid destination');
 const me=await tg(e,'getMe',{}),rights=await tg(e,'getChatMember',{chat_id:cid,user_id:me.id});
 if(rights.status!=='administrator'||!rights.can_post_messages)throw Error('Posting permission required');
 return {id:cid,username:chat.username||'',title:String(chat.title||'Canal').slice(0,100)};
}
function promoDestinationRef(m,d){
 const t=String(m.text||'').trim();if(m.chat_shared&&m.chat_shared.request_id===parseInt(d.nonce.slice(0,7),16)+1)return id(m.chat_shared.chat_id);
 if(m.forward_origin?.type==='channel')return id(m.forward_origin.chat.id);
 if(validChannel(t)||/^@[A-Za-z0-9_]{5,}$/.test(t))return t;
 if(/^https:\/\/t\.me\/c\/\d+\/\d+\/?$/.test(t))return '-100'+t.split('/')[4];
 if(/^https:\/\/t\.me\/[A-Za-z0-9_]{5,}(?:\/\d+)?\/?$/.test(t))return '@'+t.split('/')[3];
 return null;
}
async function genericPromoPreview(e,u,d){
 const p=await genericPromoProduct(e,d.pid);if(!p){await send(e,u,'Produit indisponible.',[[cb('Annuler','ad:cancel')]]);return null;}
 const me=await tg(e,'getMe',{});if(!/^[A-Za-z0-9_]{5,}$/.test(me.username||''))return null;
 const url='https://t.me/'+me.username+'?start=p_'+p.id;
 const cs=await all(e.DB,'SELECT id,target,hold_seconds FROM campaigns WHERE product_id=? AND active=1 ORDER BY target,id LIMIT 10',p.id);
 const access=p.price_xof===0?'🆓 Gratuit':'💰 Prix : '+p.price_xof.toLocaleString('fr-FR')+' FCFA'+(cs.length?'\n🎁 0 FCFA après '+cs[0].target+' nouveaux abonnés validés ('+cs[0].hold_seconds/3600+' h).':'');
 const caption=(p.title+'\n\n'+access+'\n\n'+(d.message??p.description??'')+'\n\n📦 '+(await productAssets(e,p)).length+' ressource(s) disponibles.').slice(0,1000);
 const buttons=[[urlButton(p.price_xof===0?'📥 Recevoir gratuitement':cs.length?'🎁 Découvrir / obtenir gratuitement':'📚 Voir le produit',url)]];
 return {p,caption,buttons,url};
}
async function genericPromoShow(e,u,d){
 if(d.step==='destination')return send(e,u,'📢 Où souhaitez-vous publier ?\n\nChoisissez un canal public ou privé dont le bot est administrateur, ou créez une annonce à partager ailleurs.',[[cb('📢 Sélectionner le canal','ad:pick:'+d.nonce)],[cb('🔗 Partager ailleurs','ad:external:'+d.nonce)],[cb('Annuler','ad:cancel')]]);
 if(d.step==='message')return send(e,u,'✍️ Envoyez le texte publicitaire, ou utilisez la description du produit.',[[cb('Utiliser la description','ad:default:'+d.nonce)],[cb('Annuler','ad:cancel')]]);
 if(d.step==='art')return send(e,u,'🖼 Envoyez une affiche, ou utilisez la couverture actuelle.',[[cb('Utiliser la couverture','ad:cover:'+d.nonce)],[cb('Sans image','ad:plain:'+d.nonce)],[cb('Annuler','ad:cancel')]]);
 if(d.step==='posting')return send(e,u,'Publication précédente à vérifier dans le canal. Aucun renvoi automatique.',[[cb('Annuler','ad:cancel')]]);
 if(d.step==='review'){
  const p=await genericPromoPreview(e,u,d);if(!p)return;
  const b=[...p.buttons,...(d.dest?[[cb('✅ Publier dans le canal','ad:publish:'+d.nonce)]]:[]),[cb('Terminer','ad:cancel')]];
  await photo(e,u,p.caption,b,null,d.cover,'product');
  return send(e,u,'Aperçu — '+(d.dest?d.dest.title:'partage externe')+'\n\nLien direct à partager :\n'+p.url);
 }
}
async function genericPromoAction(e,u,d,a){
 if(!admins(e).has(u))return send(e,u,'Commande non autorisée.');
 if(d.step==='destination'&&a==='pick')return tg(e,'sendMessage',{chat_id:u,text:'Sélectionnez un canal dans Telegram, transférez une publication ou envoyez son @nom / ID -100…',reply_markup:{keyboard:[[{text:'📢 Sélectionner un canal',request_chat:{request_id:parseInt(d.nonce.slice(0,7),16)+1,chat_is_channel:true,bot_is_member:true,request_title:true}}]],resize_keyboard:true,one_time_keyboard:true}});
 if(d.step==='destination'&&a==='external'){d.dest=null;d.step='message';await closePicker(e,u);}
 else if(d.step==='message'&&a==='default'){delete d.message;d.step='art';}
 else if(d.step==='art'&&['cover','plain'].includes(a)){const p=await genericPromoProduct(e,d.pid);if(!p)return send(e,u,'Produit indisponible.');d.cover=a==='cover'?p.cover_file_id:null;d.step='review';}
 else if(d.step==='review'&&a==='publish'&&d.dest){
  const p=await genericPromoPreview(e,u,d);if(!p)return;
  let dest;try{dest=await promoDestination(e,d.dest.id);}catch{return send(e,u,'Vérifiez le droit de publication du bot.',[[cb('Reprendre','ad:resume')]]);}
  const old=JSON.stringify(d);d.step='posting';
  const lock=await run(e.DB,'UPDATE settings SET value=? WHERE key=? AND value=?',JSON.stringify(d),promoKey(u),old);if(!lock.meta.changes)return send(e,u,'Publication déjà traitée.');
  let m;try{m=d.cover?await tg(e,'sendPhoto',{chat_id:dest.id,photo:d.cover,caption:p.caption,reply_markup:{inline_keyboard:p.buttons}},'product'):await send(e,dest.id,p.caption,p.buttons,'product');}
  catch(err){if(err instanceof TelegramError&&[400,403].includes(err.status)){d.step='review';await promoSave(e,u,d);return send(e,u,'Publication refusée. Vérifiez les droits ou l’image.',[[cb('Reprendre','ad:resume')]]);}return send(e,u,'Résultat incertain : vérifiez le canal avant de recommencer.');}
  const link=dest.username?'https://t.me/'+dest.username+'/'+m.message_id:'https://t.me/c/'+dest.id.slice(4)+'/'+m.message_id;
  await audit(e,u,'promotion_publish',d.pid+':'+m.message_id);await promoClear(e,u);
  return send(e,u,'✅ Publication envoyée.\n\n'+link,[[urlButton('Voir la publication',link)],[cb('Administration','aw:menu')]]);
 }else return genericPromoShow(e,u,d);
 await promoSave(e,u,d);return genericPromoShow(e,u,d);
}
async function genericPromoMessage(e,u,d,m){
 if(d.step==='destination'){
  const ref=promoDestinationRef(m,d);if(!ref)return send(e,u,'Sélectionnez le canal, transférez une publication ou envoyez son identifiant. Un lien d’invitation privé seul ne suffit pas.',[[cb('Sélectionner','ad:pick:'+d.nonce)],[cb('Annuler','ad:cancel')]]);
  try{d.dest=await promoDestination(e,ref);}catch{return send(e,u,'Canal inaccessible, stockage interdit ou droit de publication manquant.',[[cb('Réessayer','ad:pick:'+d.nonce)],[cb('Annuler','ad:cancel')]]);}
  d.step='message';await closePicker(e,u);
 }else if(d.step==='message'){const t=String(m.text||'').trim();if(!t||t.length>650)return send(e,u,'Envoyez un texte de 1 à 650 caractères.');d.message=t;d.step='art';}
 else if(d.step==='art'){const f=m.photo?.at(-1)?.file_id;if(!f)return send(e,u,'Envoyez une photo ou choisissez la couverture.',[[cb('Utiliser la couverture','ad:cover:'+d.nonce)]]);d.cover=f;d.step='review';}
 else return genericPromoShow(e,u,d);
 await promoSave(e,u,d);return genericPromoShow(e,u,d);
}

async function promoMenu(e,u){
 const w=await wizRead(e,u);if(w&&!w.paused){w.paused=true;await wizSave(e,u,w);}
 const cs=await all(e.DB,"SELECT id,target FROM campaigns WHERE product_id='masterclass' AND active=1 ORDER BY id LIMIT 20");
 const d=await promoRead(e,u);
 return send(e,u,'📣 Promouvoir les produits\n\nChoisissez un produit numérique à promouvoir ou préparez l’ancienne annonce combinée des livres. Aucun envoi sans confirmation.',[...(d?[[cb('▶ Reprendre la promotion','ad:resume')],[cb('❌ Annuler la promotion','ad:cancel')]]:[[cb('📦 Choisir un produit','ad:page:0')],...cs.map(c=>[cb('📚 Annonce Fondamentaux + Masterclass · '+c.target,'ad:new:'+c.id)])]),[cb('⬅ Administration','aw:menu')]]);
}
async function promoPreview(e,u,d){
 let x;try{x=await promoCampaign(e,d.cid);}catch{}if(!x||!promoValid(d.link,x.ch.username)){await send(e,u,'Canal ou campagne indisponible. Recommencez la promotion.',[[cb('Annuler','ad:cancel')]]);return null;}
 const me=await tg(e,'getMe',{});if(!/^[A-Za-z0-9_]{5,}$/.test(me.username||'')){await send(e,u,'Nom du bot indisponible.');return null;}
 const botURL='https://t.me/'+me.username+'?start=p_'+x.p.id;
 const price=x.p.price_xof.toLocaleString('fr-FR');
 const caption='📚 L’ART DE PARIER — Les Fondamentaux\n\n200 pages pour comprendre les cotes, les probabilités et les risques des paris sportifs.\n\n🎁 PDF gratuit dans notre canal Telegram.\n\n⭐ Masterclass Expert : 492 pages, 5 volumes.\n💰 Prix : '+price+' FCFA\n🎁 0 FCFA après '+x.c.target+' nouveaux abonnés validés ('+x.c.hold_seconds/3600+' h).\n\nImportant : 18+. Contenu pédagogique. Aucun pari, dépôt ou achat nécessaire. Aucun gain garanti.';
 return {x,caption,buttons:[[urlButton('📥 Recevoir le PDF gratuit',d.link)],[urlButton('🎁 Obtenir la Masterclass gratuitement',botURL)]],botURL};
}
async function promoShow(e,u,d){
 if(d.pid)return genericPromoShow(e,u,d);
 if(d.step==='link')return send(e,u,'📎 Étape 1 — PDF gratuit\n\nTransférez la publication contenant Les Fondamentaux depuis le canal de coupons, ou collez son lien public exact (t.me/nom/123). Ne transférez pas la Masterclass.',[[cb('Annuler','ad:cancel')]]);
 if(d.step==='cover')return send(e,u,'🖼 Étape 2 — Affiche\n\nEnvoyez une photo de couverture des Fondamentaux ou choisissez un message sans image.',[[cb('Sans image','ad:noimage:'+d.nonce)],[cb('Annuler','ad:cancel')]]);
 if(d.step==='posting')return send(e,u,'Publication précédente à vérifier dans le canal. Pour éviter les doublons, aucun nouvel envoi automatique.',[[cb('Annuler','ad:cancel')]]);
 if(d.step==='review'){
  const p=await promoPreview(e,u,d);if(!p)return;
  await photo(e,u,p.caption,[...p.buttons,[cb('✅ Publier dans le canal','ad:post:'+d.nonce)],[cb('Annuler','ad:cancel')]],null,d.cover,'product');
  return send(e,u,'Aperçu uniquement — destination : @'+p.x.ch.username+'\n\nLien à utiliser dans vos publicités externes :\n'+d.link+'\n\nLien direct vers la Masterclass :\n'+p.botURL);
 }
}
async function promoAction(e,u,action){
 if(!admins(e).has(u))return send(e,u,'Commande non autorisée.');
 if(action==='ad:menu')return promoMenu(e,u);
 if(action==='ad:cancel'){await promoClear(e,u);return wizMenu(e,u);}
 if(action==='ad:resume'){const d=await promoRead(e,u);if(!d)return promoMenu(e,u);delete d.paused;await promoSave(e,u,d);return promoShow(e,u,d);}
 const [,a,v]=action.split(':');
 if(a==='page'&&/^\d{1,3}$/.test(v||''))return promoProducts(e,u,Number(v));
 if(a==='item'&&slug(v)){if(await promoRead(e,u))return promoMenu(e,u);if(!await genericPromoProduct(e,v))return send(e,u,'Produit non publié ou sans ressources.');const w=await wizRead(e,u);if(w&&!w.paused){w.paused=true;await wizSave(e,u,w);}const d={pid:v,nonce:crypto.randomUUID().replace(/-/g,'').slice(0,16),step:'destination'};await promoSave(e,u,d);return genericPromoShow(e,u,d);}
 if(a==='new'&&slug(v)){
  if(await promoRead(e,u))return promoMenu(e,u);
  let x;try{x=await promoCampaign(e,v);}catch{}if(!x)return send(e,u,'Cette campagne doit être active, avec un canal public accessible au bot.');
  const d={cid:v,nonce:crypto.randomUUID().replace(/-/g,'').slice(0,16),step:'link'};await promoSave(e,u,d);return promoShow(e,u,d);
 }
 const d=await promoRead(e,u);
 if(!d||d.paused||v!==d.nonce)return send(e,u,'Cette action a expiré.',[[cb('Promotion','ad:menu')]]);
 if(d.pid)return genericPromoAction(e,u,d,a);
 if(a==='noimage'&&d.step==='cover'){d.step='review';await promoSave(e,u,d);return promoShow(e,u,d);}
 if(a==='post'&&d.step==='review'){
  const p=await promoPreview(e,u,d);if(!p)return;
  const me=await tg(e,'getMe',{}),rights=await tg(e,'getChatMember',{chat_id:p.x.ch.id,user_id:me.id});
  if(rights.status!=='administrator'||!rights.can_post_messages)return send(e,u,'Le bot doit avoir le droit de publier dans le canal. Corrigez ses droits puis reprenez l’aperçu.',[[cb('Reprendre','ad:resume')]]);
  const old=JSON.stringify(d);d.step='posting';
  const lock=await run(e.DB,'UPDATE settings SET value=? WHERE key=? AND value=?',JSON.stringify(d),promoKey(u),old);
  if(!lock.meta.changes)return send(e,u,'Publication déjà traitée ou modifiée.');
  let m;
  try{m=d.cover?await tg(e,'sendPhoto',{chat_id:p.x.ch.id,photo:d.cover,caption:p.caption,reply_markup:{inline_keyboard:p.buttons}},'product'):await send(e,p.x.ch.id,p.caption,p.buttons,'product');}
  catch(err){if(err instanceof TelegramError&&err.status===400){d.step='review';await promoSave(e,u,d);return send(e,u,'Telegram a refusé la publication. Vérifiez l’image et les droits.',[[cb('Reprendre','ad:resume')]]);}return send(e,u,'Résultat incertain : vérifiez le canal avant de republier.',[[cb('Promotion','ad:menu')]]);}
  const link='https://t.me/'+p.x.ch.username+'/'+m.message_id;
  await audit(e,u,'promotion_publish',d.cid+':'+m.message_id);await promoClear(e,u);
  return send(e,u,'✅ Publication envoyée dans le canal.\n\n'+link,[[urlButton('Voir la publication',link)],[cb('Administration','aw:menu')]]);
 }
 return promoShow(e,u,d);
}
async function promoMessage(e,u,d,m){
 if(d.pid)return genericPromoMessage(e,u,d,m);
 let x;try{x=await promoCampaign(e,d.cid);}catch{}if(!x)return send(e,u,'Campagne indisponible.',[[cb('Annuler','ad:cancel')]]);
 if(d.step==='link'){
  const origin=m.forward_origin;let link=String(m.text||'').trim();
  if(origin?.type==='channel'&&id(origin.chat.id)===x.ch.id&&m.document?.mime_type==='application/pdf'&&Number.isSafeInteger(origin.message_id)&&origin.message_id>0)link='https://t.me/'+x.ch.username+'/'+origin.message_id;
  if(!promoValid(link,x.ch.username))return send(e,u,'Lien invalide. Transférez le PDF gratuit depuis @'+x.ch.username+' ou collez son lien exact.',[[cb('Annuler','ad:cancel')]]);
  d.link=link;d.step='cover';await promoSave(e,u,d);return promoShow(e,u,d);
 }
 if(d.step==='cover'){const f=m.photo?.at(-1)?.file_id;if(!f)return send(e,u,'Envoyez une photo ou choisissez Sans image.',[[cb('Sans image','ad:noimage:'+d.nonce)],[cb('Annuler','ad:cancel')]]);d.cover=f;d.step='review';await promoSave(e,u,d);return promoShow(e,u,d);}
 return promoShow(e,u,d);
}

async function dispatch(e,update){
 if(update.chat_member)return membershipEvent(e,update);
 if(update.channel_post)return storagePost(e,update.channel_post);
 const q=update.callback_query,m=q?.message||update.message;if(!m||m.chat?.type!=='private')return;
 const from=q?.from||m.from;if(!from||from.is_bot||id(m.chat.id)!==id(from.id))return;
 const u=id(from.id);await touch(e,u);
 if(q){try{await tg(e,'answerCallbackQuery',{callback_query_id:q.id});}catch(err){if(err.status!==400)throw err;}}
 let action=q?.data||m.text||m.caption||'';
 if(q&&action.startsWith('ad:'))return promoAction(e,u,action);
 if(q&&action.startsWith('aw:')){if(admins(e).has(u)){const ad=await promoRead(e,u);if(ad&&!ad.paused){ad.paused=true;await promoSave(e,u,ad);}}return wizardCallback(e,u,action);}
 if(!q&&admins(e).has(u)&&!action.startsWith('/')){const ad=await promoRead(e,u);if(ad&&!ad.paused)return promoMessage(e,u,ad,m);const d=await wizRead(e,u);if(d&&!d.paused)return wizardMessage(e,u,d,m);if(m.forward_origin?.type==='channel')return send(e,u,`Canal : ${m.forward_origin.chat.title||'sans titre'}\nID : ${m.forward_origin.chat.id}`);}
 if(!q&&action==='/cancel'&&admins(e).has(u)){if(await promoRead(e,u))return promoAction(e,u,'ad:cancel');const d=await wizRead(e,u);if(d){d.paused=false;await wizSave(e,u,d);return wizardCallback(e,u,wizAction(d,'cancel'));}return wizMenu(e,u);}
 if(!q&&action.startsWith('/')){
  const match=action.match(/^\/([a-z_]+)(?:@\w+)?(?:\s+([\s\S]*))?$/);if(!match)return help(e,u);
  const cmd=match[1],arg=(match[2]||'').trim();
  if(adminCmds.has(cmd)){try{if(cmd==='admin'&&admins(e).has(u)){const ad=await promoRead(e,u);if(ad&&!ad.paused){ad.paused=true;await promoSave(e,u,ad);}}return await adminCommand(e,u,cmd,arg,m);}catch(err){console.warn('Admin command rejected',cmd,err.message);return send(e,u,'Commande refusée ou configuration incomplète. Consultez le README et vérifiez les paramètres.');}}
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
 if(v.length===3&&slug(v[1])&&/^\d{1,3}$/.test(v[2])){if(v[0]==='asset'||v[0]==='assets')return resourceAction(e,u,v[1],Number(v[2]),v[0]==='assets');if(v[0]==='atest'&&admins(e).has(u)){const p=await product(e,v[1]);if(!p)return;const a=(await productAssets(e,p))[Number(v[2])];if(a)return sendAsset(e,u,a,'Test administrateur — '+a.name,true);}}
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

// Temporary capability-based importer. No token, PDF or cover is stored in GitHub.
// The capability hash, expiry and exact file manifest are provisioned in D1.
const IMPORT_KEY='academy_import_v1';
const importSlots={
 'fondamentaux-cover':{pid:'fondamentaux',kind:'photo',name:'Les_Fondamentaux_Couverture.jpg',mime:'image/jpeg'},
 'fondamentaux-pdf':{pid:'fondamentaux',kind:'document',name:'L_Art_de_Parier_Les_Fondamentaux.pdf',mime:'application/pdf'},
 'masterclass-cover':{pid:'masterclass',kind:'photo',name:'Masterclass_Expert_Couverture.jpg',mime:'image/jpeg'},
 'masterclass-pdf':{pid:'masterclass',kind:'document',name:'L_Art_de_Parier_Masterclass_Expert.pdf',mime:'application/pdf'},
 'welcome':{kind:'photo',name:'MR_X_ACADEMY_Bienvenue.jpg',mime:'image/jpeg'}
};
const importCors={'Access-Control-Allow-Origin':'null','Access-Control-Allow-Methods':'POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, X-Academy-Import-Key','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
const importResponse=(data,status=200)=>Response.json(data,{status,headers:importCors});
const hexDigest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('');
async function importReadBody(request,limit){
 const length=request.headers.get('Content-Length');
 if(length!==null&&(!/^\d+$/.test(length)||Number(length)>limit))throw Error('size');
 if(!request.body)throw Error('body');
 const reader=request.body.getReader();const parts=[];let total=0;
 try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>limit){await reader.cancel();throw Error('size');}parts.push(value);}}
 finally{reader.releaseLock();}
 const data=new Uint8Array(total);let pos=0;for(const p of parts){data.set(p,pos);pos+=p.byteLength;}return data;
}
async function importState(e){const r=await row(e.DB,'SELECT value FROM settings WHERE key=?',IMPORT_KEY);if(!r)return null;try{return JSON.parse(r.value);}catch{return null;}}
async function importDone(e){const rows=await all(e.DB,"SELECT key FROM settings WHERE key LIKE 'academy_import_asset:%'");return rows.map(r=>r.key.slice('academy_import_asset:'.length)).filter(s=>Object.hasOwn(importSlots,s));}
async function importExisting(e,s){
 if(!s.pid)return row(e.DB,"SELECT value FROM settings WHERE key='welcome_file_id'");
 const p=await product(e,s.pid);return p&&(s.kind==='photo'?p.cover_file_id:p.file_id);
}
function importChannelRef(s){
 const t=String(s||'').trim();if(!t)return '';
 if(validChannel(t)||/^@[A-Za-z0-9_]{5,}$/.test(t))return t;
 if(/^https:\/\/t\.me\/c\/\d+\/\d+\/?$/.test(t))return '-100'+t.split('/')[4];
 if(/^https:\/\/t\.me\/[A-Za-z0-9_]{5,}\/?$/.test(t))return '@'+t.split('/')[3];
 throw Error('Canal invalide. Utilisez @nom, ID -100… ou lien t.me/c/…');
}
async function handleAcademyImport(request,e,p){
 if(request.method==='OPTIONS')return new Response(null,{status:204,headers:importCors});
 if(request.method!=='POST')return importResponse({ok:false,error:'Méthode refusée.'},405);
 const key=request.headers.get('X-Academy-Import-Key')||'';
 const cfg=await importState(e);
 if(!cfg||!Number.isSafeInteger(cfg.expires)||cfg.expires<now()||!/^[-_A-Za-z0-9]{43}$/.test(key)||!timingSafe(await hexDigest(new TextEncoder().encode(key)),cfg.hash))return importResponse({ok:false,error:'Clé invalide, consommée ou expirée.'},403);
 if(!validChannel(String(e.STORAGE_CHANNEL_ID||''))||!e.BOT_TOKEN)return importResponse({ok:false,error:'Stockage Telegram non configuré.'},409);
 const slot=p.slice('/academy-import/'.length);
 if(slot==='status')return importResponse({ok:true,done:await importDone(e)});
 const lockKey='academy_import_lock';
 const lock=await run(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE CAST(settings.value AS INTEGER)<?',lockKey,String(now()+300),now());
 if(!lock.meta.changes)return importResponse({ok:false,error:'Import déjà en cours. Réessayez dans un instant.'},409);
 try{
  if(slot==='finish'){
   const done=await importDone(e);
   if(!Object.keys(importSlots).every(s=>done.includes(s)))return importResponse({ok:false,error:'Tous les fichiers ne sont pas encore enregistrés.'},409);
   let body;try{body=JSON.parse(new TextDecoder().decode(await importReadBody(request,1024)));}catch{return importResponse({ok:false,error:'Données invalides.'},400);}
   let ref;try{ref=importChannelRef(body.channel);}catch(err){return importResponse({ok:false,error:err.message},400);}
   const extra=[];let premium=false;
   const found=await product(e,'fondamentaux'),master=await product(e,'masterclass');
   if(!found?.file_id||!found?.cover_file_id||!master?.file_id||!master?.cover_file_id)return importResponse({ok:false,error:'Fichiers introuvables dans le catalogue.'},409);
   if(ref){
    let ch;try{ch=await channelDetails(e,ref,null);}catch{return importResponse({ok:false,error:'Canal inaccessible. Ajoutez le bot comme administrateur avec le droit d’inviter. Le canal de stockage est interdit.'},409);}
    const same=await row(e.DB,'SELECT id FROM campaigns WHERE product_id=? AND channel_id=? AND target=? AND hold_seconds=? AND active=1 LIMIT 1','masterclass',ch.id,10,86400);
    if(!same){
     const cid='c-'+crypto.randomUUID().replace(/-/g,'').slice(0,20);let join=ch.username?'https://t.me/'+ch.username:null;
     if(!join){const made=await tg(e,'createChatInviteLink',{chat_id:ch.id,name:'academy-masterclass',creates_join_request:false});join=made.invite_link;}
     if(!validJoinURL(join))return importResponse({ok:false,error:'Lien d’entrée Telegram invalide.'},409);
     extra.push(stmt(e.DB,'INSERT INTO campaigns(id,product_id,channel_id,channel_url,target,hold_seconds,active) VALUES (?,?,?,?,?,?,1)',cid,'masterclass',ch.id,join,10,86400));
    }
    premium=true;
   }else{
    const existing=await row(e.DB,'SELECT id FROM campaigns WHERE product_id=? AND target=10 AND hold_seconds=86400 AND active=1 LIMIT 1','masterclass');premium=!!existing;
   }
   await e.DB.batch([stmt(e.DB,'UPDATE products SET active=1 WHERE id=?','fondamentaux'),...(premium?[stmt(e.DB,'UPDATE products SET active=1 WHERE id=?','masterclass')]:[]),...extra,stmt(e.DB,'DELETE FROM settings WHERE key=?',IMPORT_KEY)]);
   return importResponse({ok:true,freePublished:true,premiumPublished:premium});
  }
  const s=Object.hasOwn(importSlots,slot)?importSlots[slot]:null;const expected=cfg.files?.[slot];
  if(!s||!expected||!Number.isSafeInteger(expected.size)||expected.size<1||expected.size>20*1024*1024)return importResponse({ok:false,error:'Fichier non autorisé.'},400);
  if((await importDone(e)).includes(slot))return importResponse({ok:true,already:true});
  if(await importExisting(e,s))return importResponse({ok:false,error:'Cette ressource a déjà été enregistrée autrement. Aucun remplacement automatique.'},409);
  let bytes;try{bytes=await importReadBody(request,expected.size);}catch{return importResponse({ok:false,error:'Taille du fichier invalide.'},400);}
  if(bytes.byteLength!==expected.size||!timingSafe(await hexDigest(bytes),expected.sha256))return importResponse({ok:false,error:'Le fichier ne correspond pas à la version originale.'},400);
  const f=new FormData();f.append('chat_id',String(e.STORAGE_CHANNEL_ID));f.append(s.kind,new Blob([bytes],{type:s.mime}),s.name);f.append('caption','Archive MR X ACADEMY — '+s.name);
  const result=await tg(e,s.kind==='photo'?'sendPhoto':'sendDocument',f);
  const fileId=s.kind==='photo'?result.photo?.at(-1)?.file_id:result.document?.file_id;
  if(!fileId)throw Error('missing file_id');
  const write=s.pid?stmt(e.DB,s.kind==='photo'?'UPDATE products SET cover_file_id=?,cover_key=NULL WHERE id=? AND cover_file_id IS NULL':'UPDATE products SET file_id=?,object_key=NULL WHERE id=? AND file_id IS NULL',fileId,s.pid):stmt(e.DB,"INSERT OR IGNORE INTO settings(key,value) VALUES ('welcome_file_id',?)",fileId);
  const q=await e.DB.batch([write,stmt(e.DB,'INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO NOTHING','academy_import_asset:'+slot,String(now()))]);
  if(!q[0].meta.changes){await run(e.DB,'DELETE FROM settings WHERE key=?','academy_import_asset:'+slot);return importResponse({ok:false,error:'Ressource modifiée pendant l’import. Vérifiez dans le bot.'},409);}
  return importResponse({ok:true,slot});
 }catch(err){console.error('Academy import failed',slot,err.status||err.name);return importResponse({ok:false,error:'Import Telegram impossible. Vérifiez les droits de publication du bot dans le canal privé et réessayez.'},502);}
 finally{await run(e.DB,'DELETE FROM settings WHERE key=?',lockKey);}
}

export default {async fetch(request,e){const p=new URL(request.url).pathname;if(p.startsWith('/academy-import/'))return handleAcademyImport(request,e,p);if(p==='/health'&&request.method==='GET')return Response.json({service:'mr-x-academy',version:'1.4.0',telegram_configured:Boolean(e.BOT_TOKEN&&e.WEBHOOK_SECRET),storage_configured:validChannel(String(e.STORAGE_CHANNEL_ID||'')),admin_configured:admins(e).size>0});if(p==='/telegram/webhook'&&request.method==='POST')return handleWebhook(request,e);return new Response('Not found',{status:404});},async scheduled(_event,e,ctx){ctx.waitUntil((async()=>{if(!e.BOT_TOKEN)return;await validateDue(e,null,null,5);await autoReward(e);await run(e.DB,"DELETE FROM updates WHERE state='done' AND created_at<?",now()-7*86400);})());}};
export const internals={member,slug,validJoinURL,validChannel,sendPDF,claim,makeLink,dispatch,counts,wizRead,wizardCallback,wizardMessage,channelDetails,premiumChannel,promoValid,promoAction,promoMessage,promoPreview,promoRead,showProduct,readAsset,productAssets,sendAsset,resourceAction,genericPromoPreview,genericPromoAction};
