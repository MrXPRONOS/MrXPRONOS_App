// Mr XPRONOS: same-refresh Neon -> Cloudflare -> Telegram instant alerts.
// All Telegram credentials are Cloudflare SECRET bindings (never in code).
// Share the existing D1 telegram_sent table with the GitHub legacy sender.
const MODEL = "neon-live-value-v2.3-playability-espn";
const SITE = "https://mrxpronos.github.io/MrXPRONOS_App/live.html";
const KIND = "live_neon_signal";
const json=(o,s=200)=>new Response(JSON.stringify(o),{status:s,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
function asBytes(hex){
 if(!/^[0-9a-f]{64}$/i.test(hex||""))return null;
 return Uint8Array.from(hex.match(/../g),x=>parseInt(x,16));
}
async function verify(req,raw,key){
 const timestamp=req.headers.get("x-mrx-timestamp")||"";
 const signature=req.headers.get("x-mrx-signature")||"";
 if(!/^\d{10,13}$/.test(timestamp)||!key)return false;
 const time=Number(timestamp);
 if(!Number.isSafeInteger(time)||Math.abs(Date.now()-time)>90000)return false;
 const sig=asBytes(signature);
 if(!sig)return false;
 try{
  const k=await crypto.subtle.importKey("raw",new TextEncoder().encode(key),{name:"HMAC",hash:"SHA-256"},false,["verify"]);
  return await crypto.subtle.verify("HMAC",k,sig,new TextEncoder().encode(timestamp+"."+raw));
 }catch{return false}
}
function good(row){
 if(!row||typeof row!=="object")return false;
 if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(row.id||""))return false;
 if(row.model_version!==MODEL||row.pricing_mode!=="model_only")return false;
 if(!["total_shots","total_corners","total_fouls"].includes(row.type))return false;
 if(!["quality","value","high_value"].includes(row.signal_tier))return false;
 if(typeof row.home_team!=="string"||!row.home_team.trim()||row.home_team.length>160||
    typeof row.away_team!=="string"||!row.away_team.trim()||row.away_team.length>160)return false;
 const age=Date.now()-Date.parse(row.created_at);
 if(!Number.isFinite(age)||age < -30000||age>900000)return false;
 const p=Number(row.probability), threshold=Number(row.threshold), current=Number(row.signal_value), reliability=Number(row.reliability),quality=Number(row.data_quality_score);
 return p>=.3&&p<=.95&&Number.isFinite(threshold)&&Number.isFinite(current)&&threshold-current>=2&&reliability>=68&&quality>=67;
}
function clean(str,max=130){return String(str||"").replace(/[<>&]/g,"").slice(0,max)}
function message(row){
 const label={total_shots:"Tirs",total_corners:"Corners",total_fouls:"Fautes"}[row.type];
 const prob=Math.round(Number(row.probability)*100);
 const min=Math.max(0,Math.min(130,Math.trunc(Number(row.minute)||0)));
 return [
  "🔥 NOUVEAU PRONOSTIC LIVE",
  "⚽ "+clean(row.home_team)+" vs "+clean(row.away_team),
  "⏱ Minute : "+min+"'",
  "🎯 "+label+" : Over "+Number(row.threshold),
  "📊 Au signal : "+Number(row.signal_value),
  "🧠 Probabilité estimée (modèle) : "+prob+"%",
  "Cote bookmaker non disponible. Estimation non garantie.",
  "18+ • Joue responsablement."
 ].join("\n");
}
async function send(env,chat,row){
 const token=env.TELEGRAM_BOT_TOKEN;
 const url="https://api.telegram.org/bot"+token+"/sendMessage";
 let resp,body;
 try{
  resp=await fetch(url,{method:"POST",headers:{"content-type":"application/json"},
   body:JSON.stringify({chat_id:chat,text:message(row),disable_web_page_preview:true,
    reply_markup:{inline_keyboard:[[{text:"⚽ Plus d'opportunités LIVE",url:SITE}]]}}),
   signal:AbortSignal.timeout(10000)});
  body=await resp.json();
 }catch(e){return {status:"unknown",reason:String(e?.name||"network_error").slice(0,30)}}
 if(!resp.ok||body?.ok!==true)return {status:"rejected",reason:"telegram_http_"+resp.status};
 if(!Number.isSafeInteger(body.result?.message_id))return {status:"unknown",reason:"unconfirmed_message_id"};
 return {status:"sent",message_id:body.result.message_id};
}
async function dispatchOne(env,row){
 const date=new Date(row.created_at).toISOString().slice(0,10);
 const destinations=[["primary",env.TELEGRAM_CHAT_ID],["secondary",env.TELEGRAM_CHAT_ID_SECONDARY]]
 .filter(([_,v])=>!!String(v||"").trim());
 const seen=new Set(),res=[];
 for(const [slot,chat] of destinations){
  if(seen.has(String(chat)))continue;
  seen.add(String(chat));
  const ref=row.id+":"+slot;
  // A unique D1 ledger constraint gives cross-run/channel deduplication.
  const claimed=await env.DB.prepare(
   "INSERT OR IGNORE INTO telegram_sent(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,settlement_status,claim_owner) "+
   "VALUES(?,?,?,?,?,0,'reserved','notstarted','neon-instant')"
  ).bind(crypto.randomUUID(),KIND,ref,date,new Date().toISOString()).run();
  if((claimed.meta?.changes||0)!==1){
   const prior=await env.DB.prepare(
    "SELECT delivery_status FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=?"
   ).bind(KIND,ref,date).first();
   res.push({destination:slot,status:prior?.delivery_status==="sent"?"sent":"unresolved"});
   continue;
  }
  const result=await send(env,chat,row);
  if(result.status==="sent"){
   const marked=await env.DB.prepare(
    "UPDATE telegram_sent SET delivery_status='sent',telegram_message_id=?,published_at=? "+
    "WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved'"
   ).bind(result.message_id,new Date().toISOString(),KIND,ref,date).run();
   res.push({destination:slot,status:marked.meta?.changes===1?"sent":"unresolved"});
  }else if(result.status==="rejected"){
   // Definitive API rejection: safe to retry at next refresh, no message posted.
   await env.DB.prepare(
    "DELETE FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=? AND delivery_status='reserved' AND claim_owner='neon-instant'"
   ).bind(KIND,ref,date).run();
   res.push({destination:slot,status:"rejected"});
  }else{
   // Network ambiguity: retain claim to avoid accidentally double-posting.
   res.push({destination:slot,status:"unresolved"});
  }
 }
 return {prediction_id:row.id,deliveries:res,
  all_sent:res.length===destinations.length&&res.every(x=>x.status==="sent")};
}
export default {
 async fetch(req,env){
  const url=new URL(req.url);
  if(url.pathname==="/health"&&req.method==="GET")return json({
   service:"mrxpronos-neon-live-telegram-instant",
   ready:!!(env.DB&&env.NEON_DELIVERY_HMAC_KEY&&env.TELEGRAM_BOT_TOKEN&&env.TELEGRAM_CHAT_ID&&env.TELEGRAM_CHAT_ID_SECONDARY),
   mode:"post-commit",
   live_send:false
  });
  if(url.pathname!=="/deliver")return json({error:"not_found"},404);
  if(req.method!=="POST")return json({error:"method_not_allowed"},405);
  if(!env.DB||!env.NEON_DELIVERY_HMAC_KEY||!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID||!env.TELEGRAM_CHAT_ID_SECONDARY)
   return json({error:"not_configured"},503);
  if(Number(req.headers.get("content-length")||0)>16000)return json({error:"too_large"},413);
  const raw=await req.text();
  if(raw.length>16000)return json({error:"too_large"},413);
  if(!await verify(req,raw,env.NEON_DELIVERY_HMAC_KEY))return json({error:"unauthorized"},401);
  let data;try{data=JSON.parse(raw)}catch{return json({error:"invalid_json"},400)}
  if(!data||!Array.isArray(data.signals)||data.signals.length>4)return json({error:"invalid_payload"},400);
  if(data.signals.some(x=>!good(x)))return json({error:"invalid_signal"},422);
  const result=[];
  for(const s of data.signals)result.push(await dispatchOne(env,s));
  return json({ok:true,results:result,telegram_sent:result.reduce((n,p)=>n+p.deliveries.filter(d=>d.status==="sent").length,0),
   all_sent:result.every(x=>x.all_sent)});
 }
};
