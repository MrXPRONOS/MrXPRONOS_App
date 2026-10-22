// Free Pronos — centre d'assistance isolé, anti-spam et sans fuite des IDs admin.
const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const one=async(env,sql,...args)=>env.DB.prepare(sql).bind(...args).first();
const all=async(env,sql,...args)=>(await env.DB.prepare(sql).bind(...args).all()).results||[];
const run=async(env,sql,...args)=>env.DB.prepare(sql).bind(...args).run();
const admins=env=>String(env.CF_BOT_ADMIN_IDS||'').split(',').map(x=>Number(x.trim())).filter(x=>Number.isSafeInteger(x)&&x>0);
export function supportGuide(){
 return '💬 <b>FREE PRONOS · ASSISTANCE</b>\n\n'+
   '<blockquote>Un souci avec tes XP, une mission ou un coupon ? Notre équipe peut te répondre ici.</blockquote>\n\n'+
   '✉️ <b>Écris ton message après la commande :</b>\n'+
   '<code>/support Je souhaite comprendre mon solde XP.</code>\n\n'+
   '📮 <b>Consulte mes demandes :</b> /mytickets\n'+
   '🔒 <i>Évite de communiquer ton mot de passe ou tes informations bancaires. Maximum 3 tickets ouverts.</i>';
}
export async function createTicket(env,uid,content){
 const message=String(content||'').trim().slice(0,800);
 if(message.length<12)return {status:'invalid'};
 const u=await one(env,'SELECT adult_confirmed,required_verified FROM users WHERE id=?',uid);
 if(!u?.adult_confirmed)return {status:'locked'};
 const cutoff=new Date(Date.now()-600000).toISOString();
 const q=await one(env,
   "SELECT count(*) AS open,(SELECT count(*) FROM support_tickets WHERE user_id=? AND created_at>?) AS recent FROM support_tickets WHERE user_id=? AND status='open'",
   uid,cutoff,uid);
 if(Number(q.open)>=3||Number(q.recent)>=1)return {status:'rate_limited'};
 const ticket=await one(env,'INSERT INTO support_tickets(user_id,message) VALUES(?,?) RETURNING id',uid,message);
 return {status:'ok',id:ticket.id,message};
}
export async function informAdmins(env,ticket,telegram){
 for(const uid of admins(env)){
   try{
     await telegram(env,'sendMessage',{
       chat_id:uid,
       text:'📨 <b>NOUVEAU TICKET FREE PRONOS</b>\n\n'+
         '🆔 Ticket : <b>#'+ticket.id+'</b>\n'+
         '👤 Utilisateur : <code>'+ticket.uid+'</code>\n'+
         '<blockquote>'+escape(ticket.message)+'</blockquote>\n\n'+
         '✍️ <b>Pour répondre :</b>\n<code>/replyticket '+ticket.id+' Votre réponse ici</code>',
       parse_mode:'HTML'
     });
   }catch(err){console.warn('Support notification unavailable',String(err).slice(0,100))}
 }
}
export async function ticketsForUser(env,uid){
 return all(env,'SELECT id,message,status,admin_reply,created_at,replied_at FROM support_tickets WHERE user_id=? ORDER BY id DESC LIMIT 8',uid);
}
export async function pendingTickets(env){
 return all(env,"SELECT id,user_id,message,created_at FROM support_tickets WHERE status='open' ORDER BY id ASC LIMIT 20");
}
export async function replyToTicket(env,adminId,id,text,telegram){
 if(!admins(env).includes(adminId))return {status:'denied'};
 const ticketId=Number(id),answer=String(text||'').trim().slice(0,1200);
 if(!Number.isSafeInteger(ticketId)||ticketId<1||answer.length<3)return {status:'invalid'};
 const ticket=await one(env,'SELECT id,user_id,status FROM support_tickets WHERE id=?',ticketId);
 if(!ticket)return {status:'missing'};
 if(ticket.status!=='open')return {status:'closed'};
 try{
   await telegram(env,'sendMessage',{
     chat_id:ticket.user_id,
     text:'💬 <b>FREE PRONOS · RÉPONSE DE L’ÉQUIPE</b>\n\n📮 Ticket #'+ticket.id+
       '\n<blockquote>'+escape(answer)+'</blockquote>\n\n<i>Tu peux ouvrir une nouvelle demande avec /support si nécessaire.</i>',
     parse_mode:'HTML'
   });
 }catch(err){console.warn('Support reply send failure',String(err).slice(0,100));return {status:'delivery_failed'}}
 await run(env,"UPDATE support_tickets SET status='replied',admin_reply=?,replied_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND status='open'",answer,ticketId);
 return {status:'ok'};
}
export async function closeUserTicket(env,uid,id){
 const ticketId=Number(id);
 if(!Number.isSafeInteger(ticketId)||ticketId<1)return false;
 const result=await run(env,"UPDATE support_tickets SET status='closed' WHERE id=? AND user_id=? AND status<>'closed'",ticketId,uid);
 return !!result.meta?.changes;
}
export function ticketSummary(rows){
 if(!rows.length)return '📭 <b>AUCUNE DEMANDE</b>\n\n<i>Pour contacter l’équipe, utilise /support suivi de ton message.</i>';
 return '📮 <b>MES DEMANDES FREE PRONOS</b>\n\n'+rows.map(x=>
   '🆔 <b>#'+x.id+'</b> '+(x.status==='open'?'⏳ En attente':x.status==='replied'?'✅ Répondu':'🔒 Fermé')+
   '\n<i>'+escape(x.message.slice(0,90))+'</i>'+
   (x.admin_reply?'\n💬 <b>Réponse :</b> '+escape(x.admin_reply.slice(0,200)):'')
 ).join('\n\n');
}
