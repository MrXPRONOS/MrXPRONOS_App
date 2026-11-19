// Owner-only Telegram announcements. Anonymous analytics remain separate from delivery IDs.
const response=(body,status=200)=>Response.json(body,{status,headers:{"cache-control":"no-store"}});
const validId=x=>Number.isSafeInteger(Number(x))&&Number(x)>0?Number(x):null;
export async function ensureBroadcastTables(env){
 const sql=[
  "CREATE TABLE IF NOT EXISTS cine_broadcast_subscribers (chat_id INTEGER PRIMARY KEY, active INTEGER NOT NULL DEFAULT 1, blocked INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)",
  "CREATE TABLE IF NOT EXISTS cine_broadcast_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL, text_html TEXT NOT NULL, photo_id TEXT NOT NULL DEFAULT '', button_text TEXT NOT NULL DEFAULT '', button_url TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft', recipients INTEGER NOT NULL DEFAULT 0, delivered INTEGER NOT NULL DEFAULT 0, failed INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, lease_until TEXT)",
  "CREATE TABLE IF NOT EXISTS cine_broadcast_receipts (job_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', retry_at TEXT, PRIMARY KEY(job_id,chat_id))"
 ];
 for(const query of sql)await env.DB.prepare(query).run();
}
export async function trackBroadcastSubscriber(env,update){
 const msg=update?.message,chat=msg?.chat?.id;
 if(msg?.chat?.type!=="private"||!validId(chat)||chat!==msg.from?.id)return;
 const text=String(msg.text||"").trim();
 const start=/^\/start(?:@[A-Za-z0-9_]+)?(?:\s|$)/i.test(text);
 const stop=/^\/stop(?:@[A-Za-z0-9_]+)?\s*$/i.test(text);
 if(!start&&!stop)return;
 await ensureBroadcastTables(env);
 if(start)await env.DB.prepare("INSERT INTO cine_broadcast_subscribers(chat_id,active,blocked) VALUES(?,1,0) ON CONFLICT(chat_id) DO UPDATE SET active=1,blocked=0,updated_at=CURRENT_TIMESTAMP").bind(chat).run();
 else{
  await env.DB.prepare("INSERT INTO cine_broadcast_subscribers(chat_id,active,blocked) VALUES(?,0,0) ON CONFLICT(chat_id) DO UPDATE SET active=0,updated_at=CURRENT_TIMESTAMP").bind(chat).run();
  await env.DB.prepare("UPDATE cine_broadcast_receipts SET state='skipped',last_error='opted_out' WHERE chat_id=? AND state IN ('pending','failed')").bind(chat).run();
 }
}
const LINK_TAGS=new Set(["b","i","u","s","code","blockquote"]);
export function validateBroadcastText(value,photo){
 const text=String(value||"").trim();
 if(!text||text.length>(photo?1000:3900))throw Error(photo?"Texte avec image : 1 000 caractères maximum.":"Texte : 3 900 caractères maximum.");
 const stack=[],tags=/<[^>]*>/g;let tag,last=0;
 while((tag=tags.exec(text))){
  const before=text.slice(last,tag.index);
  if(/[<>]/.test(before))throw Error("Format HTML incorrect.");
  const m=/^<(\/?)(b|i|u|s|code|blockquote)>$/.exec(tag[0]);
  if(!m||!LINK_TAGS.has(m[2]))throw Error("Format autorisé : gras, italique, souligné, barré, code et citation.");
  if(m[1]){if(stack.pop()!==m[2])throw Error("Balises de formatage mal fermées.");}
  else stack.push(m[2]);
  last=tags.lastIndex;
 }
 if(/[<>]/.test(text.slice(last))||stack.length)throw Error("Format HTML incomplet.");
 return text.replace(/&(?!(?:amp|lt|gt|quot);)/g,"&amp;");
}
function safeUrl(value){
 const text=String(value||"").trim();if(!text)return "";
 if(text.length>500)throw Error("Lien trop long.");
 let url;try{url=new URL(text);}catch{throw Error("Le lien doit commencer par https://.");}
 const h=url.hostname.toLowerCase();
 if(url.protocol!=="https:"||url.username||url.password||!h.includes(".")||h.endsWith(".local")||h==="localhost"||h==="169.254.169.254"||/^(10|127|192|172)\.\d+\.\d+\.\d+$/.test(h))throw Error("Le bouton doit avoir une URL HTTPS publique.");
 return url.toString();
}
function validateDraft(body){
 const photo_id=String(body.photo_id||"").trim();
 if(photo_id&&!/^[A-Za-z0-9_-]{20,512}$/.test(photo_id))throw Error("Image incorrecte : importe-la à nouveau.");
 const text_html=validateBroadcastText(body.text_html,Boolean(photo_id));
 const button_text=String(body.button_text||"").trim(),button_url=safeUrl(body.button_url);
 if(Boolean(button_text)!==Boolean(button_url))throw Error("Saisis le texte ET le lien du bouton.");
 if(button_text.length>64)throw Error("Texte du bouton trop long.");
 return {text_html,photo_id,button_text,button_url};
}
const markup=draft=>draft.button_text?{inline_keyboard:[[{text:draft.button_text,url:draft.button_url,style:"primary"}]]}:undefined;
async function send(env,chat,draft){
 const data={chat_id:chat,parse_mode:"HTML",reply_markup:markup(draft)};
 let method="sendMessage";
 if(draft.photo_id){method="sendPhoto";data.photo=draft.photo_id;data.caption=draft.text_html;}
 else{data.text=draft.text_html;data.link_preview_options={is_disabled:true};}
 const r=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data),signal:AbortSignal.timeout(6500)});
 return r.json();
}
export async function uploadAnnouncementImage(env,request,owner){
 if(Number(request.headers.get("content-length")||0)>2500000)return response({error:"Fichier limité à 2 Mo."},413);
 let form;try{form=await request.formData();}catch{return response({error:"Téléversement invalide."},400)}
 const photo=form.get("photo");
 if(!photo||typeof photo.arrayBuffer!=="function"||photo.size>2000000||photo.size<200||!["image/jpeg","image/png","image/webp"].includes(photo.type))return response({error:"Utilise une image JPEG, PNG ou WebP de 2 Mo maximum."},400);
 const bytes=new Uint8Array(await photo.arrayBuffer());
 const png=bytes[0]===137&&bytes[1]===80&&bytes[2]===78&&bytes[3]===71;
 const jpg=bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
 const webp=String.fromCharCode(...bytes.slice(0,4))==="RIFF"&&String.fromCharCode(...bytes.slice(8,12))==="WEBP";
 if(!(photo.type==="image/png"&&png||photo.type==="image/jpeg"&&jpg||photo.type==="image/webp"&&webp))return response({error:"Type de fichier incorrect."},400);
 const formData=new FormData();
 formData.append("chat_id",String(owner));
 formData.append("photo",new Blob([bytes],{type:photo.type}),"cineradar-image."+({"image/png":"png","image/jpeg":"jpg","image/webp":"webp"}[photo.type]));
 formData.append("caption","🖼️ Aperçu privé de l'image. Aucun utilisateur du bot ne l'a reçue.");
 let result;
 try{const r=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/sendPhoto",{method:"POST",body:formData,signal:AbortSignal.timeout(14000)});result=await r.json();}
 catch{return response({error:"Impossible de téléverser l'image vers Telegram."},502)}
 const photo_id=Array.isArray(result?.result?.photo)?result.result.photo.at(-1)?.file_id:null;
 return result?.ok&&photo_id?response({ok:true,photo_id}):response({error:"Telegram a refusé l'image."},502);
}
export async function broadcastAdminAPI(env,request,owner){
 await ensureBroadcastTables(env);
 const path=new URL(request.url).pathname;
 if(path==="/api/admin/broadcast-image"&&request.method==="POST")return uploadAnnouncementImage(env,request,owner);
 if(path==="/api/admin/broadcasts"&&request.method==="GET"){
  const [users,jobs]=await Promise.all([
   env.DB.prepare("SELECT COUNT(*) total,COALESCE(SUM(CASE WHEN active=1 AND blocked=0 THEN 1 ELSE 0 END),0) active FROM cine_broadcast_subscribers").first(),
   env.DB.prepare("SELECT id,status,recipients,delivered,failed,blocked,created_at,button_text,CASE WHEN photo_id<>'' THEN 1 ELSE 0 END has_photo FROM cine_broadcast_jobs ORDER BY id DESC LIMIT 15").all()
  ]);
  return response({subscribers:{total:Number(users?.total||0),active:Number(users?.active||0)},jobs:jobs.results||[]});
 }
 if(request.method!=="POST")return response({error:"Méthode non autorisée."},405);
 if(Number(request.headers.get("content-length")||0)>8000)return response({error:"Message trop volumineux."},413);
 let data;try{const text=await request.text();if(text.length>8000)throw Error();data=JSON.parse(text);}catch{return response({error:"JSON invalide."},400)}
 if(path==="/api/admin/broadcasts"){
  let draft;try{draft=validateDraft(data);}catch(e){return response({error:e.message},400)}
  const r=await env.DB.prepare("INSERT INTO cine_broadcast_jobs(owner_id,text_html,photo_id,button_text,button_url) VALUES(?,?,?,?,?)").bind(owner,draft.text_html,draft.photo_id,draft.button_text,draft.button_url).run();
  return response({ok:true,id:r.meta?.last_row_id,status:"draft"},201);
 }
 const match=/^\/api\/admin\/broadcasts\/(\d+)\/(preview|start|cancel)$/.exec(path);
 if(!match)return response({error:"Route inconnue."},404);
 const id=Number(match[1]),op=match[2];
 const row=await env.DB.prepare("SELECT * FROM cine_broadcast_jobs WHERE id=?").bind(id).first();
 if(!row)return response({error:"Annonce introuvable."},404);
 if(op==="preview"){
  if(row.status!=="draft")return response({error:"Prévisualisation réservée aux brouillons."},409);
  try{const result=await send(env,owner,row);return result.ok?response({ok:true}):response({error:"Telegram a refusé l'aperçu."},502);}
  catch{return response({error:"Aperçu indisponible."},502)}
 }
 if(op==="cancel"){
  if(!["draft","preparing","sending"].includes(row.status))return response({error:"Annonce déjà terminée."},409);
  await env.DB.prepare("UPDATE cine_broadcast_jobs SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('draft','preparing','sending')").bind(id).run();
  return response({ok:true,status:"cancelled"});
 }
 if(row.status!=="draft")return response({error:"Cette annonce a déjà été lancée."},409);
 const claimed=await env.DB.prepare("UPDATE cine_broadcast_jobs SET status='preparing' WHERE id=? AND status='draft'").bind(id).run();
 if(!Number(claimed.meta?.changes||0))return response({error:"Envoi déjà démarré."},409);
 try{
  await env.DB.prepare("INSERT OR IGNORE INTO cine_broadcast_receipts(job_id,chat_id) SELECT ?,chat_id FROM cine_broadcast_subscribers WHERE active=1 AND blocked=0").bind(id).run();
  const c=await env.DB.prepare("SELECT COUNT(*) n FROM cine_broadcast_receipts WHERE job_id=?").bind(id).first();
  const recipients=Number(c?.n||0);
  await env.DB.prepare("UPDATE cine_broadcast_jobs SET status=?,recipients=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='preparing'").bind(recipients?"sending":"completed",recipients,id).run();
  return response({ok:true,status:recipients?"sending":"completed",recipients});
 }catch{
  await env.DB.prepare("UPDATE cine_broadcast_jobs SET status='draft' WHERE id=? AND status='preparing'").bind(id).run().catch(()=>{});
  return response({error:"Impossible de préparer les destinataires."},503);
 }
}
export async function deliverBroadcastBatch(env){
 await ensureBroadcastTables(env);
 const job=await env.DB.prepare("SELECT * FROM cine_broadcast_jobs WHERE status='sending' AND (lease_until IS NULL OR lease_until<datetime('now')) ORDER BY id LIMIT 1").first();
 if(!job)return {processed:0};
 const claim=await env.DB.prepare("UPDATE cine_broadcast_jobs SET lease_until=datetime('now','+45 seconds') WHERE id=? AND status='sending' AND (lease_until IS NULL OR lease_until<datetime('now'))").bind(job.id).run();
 if(!Number(claim.meta?.changes||0))return {processed:0};
 let processed=0;
 try{
  const r=await env.DB.prepare("SELECT r.chat_id FROM cine_broadcast_receipts r JOIN cine_broadcast_subscribers u ON u.chat_id=r.chat_id WHERE r.job_id=? AND r.state IN ('pending','failed') AND r.attempts<3 AND (r.retry_at IS NULL OR r.retry_at<=CURRENT_TIMESTAMP) AND u.active=1 AND u.blocked=0 ORDER BY r.chat_id LIMIT 12").bind(job.id).all();
  const rows=r.results||[];
  for(let i=0;i<rows.length;i+=3){
   await Promise.all(rows.slice(i,i+3).map(async row=>{
    const state=await env.DB.prepare("SELECT status FROM cine_broadcast_jobs WHERE id=?").bind(job.id).first();
    if(state?.status!=="sending")return;
    let answer;try{answer=await send(env,row.chat_id,job);}catch{answer={ok:false,error_code:0,description:"network"}}
    const code=Number(answer?.error_code||0),blocked=code===403||code===400&&/blocked|chat not found|user is deactivated/i.test(String(answer?.description||""));
    const status=answer?.ok?"sent":blocked?"blocked":"failed";
    await env.DB.prepare("UPDATE cine_broadcast_receipts SET state=?,attempts=attempts+1,last_error=?,retry_at=CASE WHEN ?='failed' THEN datetime('now','+5 minutes') ELSE NULL END WHERE job_id=? AND chat_id=? AND state IN ('pending','failed')").bind(status,answer?.ok?"":blocked?"unavailable":String(code||"network"),status,job.id,row.chat_id).run();
    if(blocked){
     await env.DB.prepare("UPDATE cine_broadcast_subscribers SET active=0,blocked=1,updated_at=CURRENT_TIMESTAMP WHERE chat_id=?").bind(row.chat_id).run();
     await env.DB.prepare("UPDATE cine_broadcast_receipts SET state='skipped',last_error='unavailable' WHERE chat_id=? AND state IN ('pending','failed')").bind(row.chat_id).run();
    }
    processed++;
   }));
  }
  const counts=await env.DB.prepare("SELECT SUM(state='sent') sent,SUM(state='blocked' OR state='skipped') blocked,SUM(state='failed' AND attempts>=3) failed,SUM(state='pending' OR (state='failed' AND attempts<3)) remaining FROM cine_broadcast_receipts WHERE job_id=?").bind(job.id).first();
  const remaining=Number(counts?.remaining||0);
  await env.DB.prepare("UPDATE cine_broadcast_jobs SET delivered=?,blocked=?,failed=?,status=CASE WHEN status='sending' AND ?=0 THEN 'completed' ELSE status END,lease_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?").bind(Number(counts?.sent||0),Number(counts?.blocked||0),Number(counts?.failed||0),remaining,job.id).run();
  return {processed,remaining};
 }finally{
  await env.DB.prepare("UPDATE cine_broadcast_jobs SET lease_until=NULL WHERE id=?").bind(job.id).run().catch(()=>{});
 }
}
