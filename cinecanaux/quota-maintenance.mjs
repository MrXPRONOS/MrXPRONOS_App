// CineRadar D1 quota maintenance: no D1 reads, writes or external services.
// Togo (Africa/Lome) observes UTC+0 year-round. Recovery is an *estimate*:
// Cloudflare can still be unavailable after 00:05 and must be probed again.
const D1_QUOTA_PATTERN=/(?:your account has exceeded.{0,150}(?:d1|daily row|free tier)|d1.{0,150}(?:free tier daily|daily row|daily read|daily write|quota|exceeded)|daily row (?:read|write|written) limit|row read limit)/i;
let localMaintenanceUntil=0;

export function isD1QuotaError(error){
 let current=error;
 for(let i=0;i<4&&current!=null;i++){
  const detail=typeof current==="string"?current:String(current.message||current);
  if(D1_QUOTA_PATTERN.test(detail))return true;
  const code=String(current.code||current.error_code||"");
  if(code==="7500"&&/(D1|row|daily|limit|quota|exceeded)/i.test(detail))return true;
  current=current.cause;
 }
 return false;
}
export function nextRecoveryUTC(now=new Date()){
 const when=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),0,5));
 if(now.getTime()>=when.getTime())when.setUTCDate(when.getUTCDate()+1);
 return when;
}
export function markD1Maintenance(error,now=new Date()){
 if(!isD1QuotaError(error))return false;
 localMaintenanceUntil=Math.max(localMaintenanceUntil,nextRecoveryUTC(now).getTime());
 return true;
}
export function d1MaintenanceActive(now=new Date()){
 return now.getTime()<localMaintenanceUntil;
}
export function maintenanceDetails(now=new Date()){
 const reopening=localMaintenanceUntil>now.getTime()?new Date(localMaintenanceUntil):nextRecoveryUTC(now);
 return {
  message:"🔧 CinéRadar est temporairement en maintenance en raison d’une limite technique. Reprise prévue à 00h05 (heure du Togo), sous réserve du rétablissement du service.",
  reopening_at:reopening.toISOString(),
  reopening_time:"00h05",
  timezone:"Africa/Lome",
  retry_after_seconds:Math.max(1,Math.ceil((reopening.getTime()-now.getTime())/1000))
 };
}
export function maintenanceResponse(request,{now=new Date()}={}){
 const details=maintenanceDetails(now);
 const url=new URL(request.url);
 const api=url.pathname.startsWith("/api/")||url.pathname.startsWith("/health");
 const headers={
  "cache-control":"no-store, max-age=0",
  "retry-after":String(details.retry_after_seconds),
  "x-content-type-options":"nosniff",
  "x-cineradar-maintenance":"d1-quota"
 };
 if(api){
  return Response.json({
   ok:false,maintenance:true,code:"D1_QUOTA_MAINTENANCE",
   message:details.message,reopening_at:details.reopening_at,
   timezone:details.timezone
  },{status:503,headers});
 }
 const date=new Intl.DateTimeFormat("fr-FR",{
  timeZone:"UTC",day:"numeric",month:"long",year:"numeric"
 }).format(new Date(details.reopening_at));
 const html=String.raw`<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0c1632"><meta name="robots" content="noindex">
<title>CinéRadar • Maintenance</title>
<style>
*{box-sizing:border-box}
html,body{min-height:100%;margin:0}
body{font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;color:#eaf2ff;
background:radial-gradient(circle at 50% 2%,#254785 0%,#142750 38%,#09152d 85%);
display:grid;place-items:center;padding:24px}
main{width:min(100%,540px);border:1px solid #385a91;border-radius:24px;
background:linear-gradient(155deg,#192e58,#101d37);padding:clamp(24px,6vw,44px);
text-align:center;box-shadow:0 20px 65px #02071399}
.logo{display:inline-grid;place-items:center;width:78px;height:78px;border-radius:20px;
background:#2b4e92;font-size:38px}
h1{font-size:clamp(26px,6vw,36px);margin:22px 0 10px;line-height:1.2}
p{color:#c2d4ee;margin:10px 0 20px}
.time{font-weight:800;color:#fff;font-size:clamp(34px,9vw,50px);line-height:1.1;margin:10px 0}
.date{color:#c3d7fb;font-size:15px;margin:4px 0 24px}
.small{font-size:13px;color:#9aafce;margin-top:22px}
button{background:#518af9;color:#fff;border:0;border-radius:14px;
font-size:15px;font-weight:700;padding:13px 24px;cursor:pointer}
button:focus-visible{outline:3px solid #f2be66;outline-offset:4px}
</style></head>
<body><main role="main"><div class="logo" aria-hidden="true">🎬</div>
<h1>CinéRadar est en maintenance</h1>
<p>Notre service rencontre une limite technique temporaire. Nous rétablissons l'accès au catalogue et à l'administration.</p>
<div>Réouverture prévue à</div><div class="time">00h05</div>
<div class="date">__DATE__ · Heure du Togo (UTC)</div>
<button type="button" onclick="location.reload()">Réessayer</button>
<div class="small">La reprise dépend de la disponibilité réelle du service. Merci de votre patience.</div>
</main></body></html>`.replace("__DATE__",date);
 return new Response(html,{status:503,headers:{
  ...headers,"content-type":"text/html; charset=utf-8",
  "content-security-policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"
 }});
}
export async function telegramMaintenanceReply(update,call,env,{now=new Date()}={}){
 const info=maintenanceDetails(now);
 const chat=update?.message?.chat||update?.callback_query?.message?.chat;
 const callbackId=update?.callback_query?.id;
 if(!chat||chat.type!=="private"||!Number.isSafeInteger(Number(chat.id))){
  // Do not silently discard channel posts that still require D1 ingestion.
  return new Response("Maintenance: retry later",{status:503,headers:{"cache-control":"no-store","retry-after":"60"}});
 }
 try{
  if(callbackId){
   const ack=await call(env,"answerCallbackQuery",{
    callback_query_id:callbackId,
    text:"CinéRadar est en maintenance. Retour prévu à 00h05 (heure du Togo).",
    show_alert:true
   });
   if(ack?.ok===true)return Response.json({ok:true,maintenance:true});
  }
  const sent=await call(env,"sendMessage",{
   chat_id:chat.id,
   text:info.message,
   disable_notification:true
  });
  if(sent?.ok===true)return Response.json({ok:true,maintenance:true});
 }catch{ /* Telegram failures must remain retryable, without leaking a token. */ }
 return new Response("Maintenance: Telegram delivery unavailable",{status:503,headers:{"cache-control":"no-store","retry-after":"60"}});
}
// Tests only. Does not persist or modify any Cloudflare resources.
export function resetMaintenanceForTests(){localMaintenanceUntil=0;}
