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
// Public copy must never expose infrastructure or diagnostic details.
const STANDBY_URL="https://mrxpronos.github.io/MrXPRONOS_App/cineradar-secours/";
export function maintenanceDetails(now=new Date(),{mode="quota"}={}){
 const quota=mode==="quota";
 const reopening=quota?(localMaintenanceUntil>now.getTime()?new Date(localMaintenanceUntil):nextRecoveryUTC(now)):null;
 const intro="<b>🎬 CinéRadar est en maintenance</b>\n\n<i>Nous revenons très bientôt. Merci de votre patience et de votre confiance.</i>\n\n<blockquote>✨ Notre équipe prépare le retour de CinéRadar.</blockquote>\n\n";
 const schedule=quota?"<b>🕛 Retour prévu :</b> 00h05 (heure du Togo).\n<i>La reprise dépend de la disponibilité du service.</i>":"<b>🕘 Retour :</b> dès que possible.\n<i>La disponibilité est vérifiée automatiquement.</i>";
 return {
  message:intro+schedule+'\n\n<a href="'+STANDBY_URL+'">🔗 Suivre la maintenance</a>',
  plain_message:"CinéRadar est en maintenance. Nous revenons très bientôt.",
  reopening_at:reopening?reopening.toISOString():null,
  reopening_time:quota?"00h05":null,
  timezone:"Africa/Lome",
  retry_after_seconds:quota?Math.max(1,Math.ceil((reopening.getTime()-now.getTime())/1000)):60
 };
}
export function maintenanceResponse(request,{now=new Date(),mode="quota"}={}){
 const details=maintenanceDetails(now,{mode});
 const url=new URL(request.url);
 const api=url.pathname.startsWith("/api/")||url.pathname.startsWith("/health");
 const headers={
  "cache-control":"no-store, max-age=0",
  "retry-after":String(details.retry_after_seconds),
  "x-content-type-options":"nosniff",
  "x-cineradar-maintenance":"active"
 };
 if(url.pathname==="/health")headers["access-control-allow-origin"]="https://mrxpronos.github.io";
 if(api){
  return Response.json({
   ok:false,maintenance:true,code:"SERVICE_MAINTENANCE",
   message:details.plain_message,reopening_at:details.reopening_at,
   timezone:details.timezone
  },{status:503,headers});
 }
 const date=details.reopening_at?new Intl.DateTimeFormat("fr-FR",{
  timeZone:"UTC",day:"numeric",month:"long",year:"numeric"
 }).format(new Date(details.reopening_at)):"";
 const html=String.raw`<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080d1d"><meta name="robots" content="noindex">
<title>CinéRadar • Maintenance</title>
<style>
:root{color-scheme:dark;--text:#f7f8ff;--muted:#aeb8d0;--accent:#ffb862}
*{box-sizing:border-box}html,body{margin:0;min-height:100%}
body{display:grid;place-items:center;min-height:100svh;padding:24px;font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--text);background:radial-gradient(ellipse at 12% 4%,#253f70 0%,transparent 45%),radial-gradient(ellipse at 94% 93%,#40233c 0%,transparent 48%),#080d1d}
body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.17;background-image:linear-gradient(#ffffff10 1px,transparent 1px),linear-gradient(90deg,#ffffff10 1px,transparent 1px);background-size:44px 44px}
main{position:relative;width:min(100%,540px);padding:clamp(26px,6vw,49px);text-align:center;border:1px solid #53648c66;border-radius:28px;background:linear-gradient(145deg,#202e4eea,#10182dee 70%);box-shadow:0 35px 90px #0008;overflow:hidden}
main:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#6aaaff,var(--accent),#ff858b)}
.brand{display:flex;align-items:center;justify-content:center;gap:9px;font-size:13px;font-weight:850;letter-spacing:.22em;text-transform:uppercase;color:#e8eeff}.brand span{color:var(--accent)}
.mark{display:grid;place-items:center;width:91px;height:91px;margin:29px auto 22px;border-radius:25px;background:linear-gradient(145deg,#334f83,#1b2c50);box-shadow:inset 0 1px #ffffff29,0 18px 40px #0005;font-size:41px}
.pill{display:inline-flex;gap:8px;align-items:center;margin:0 auto 12px;padding:5px 13px;border:1px solid #ffbf7255;border-radius:100px;background:#ffb86213;color:#ffd49f;font-size:12px;font-weight:750;letter-spacing:.07em;text-transform:uppercase}
.pill:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
h1{font-size:clamp(27px,6.5vw,38px);line-height:1.18;letter-spacing:-.04em;margin:12px 0 15px}
.lead{max-width:360px;margin:0 auto 28px;color:var(--muted)}
.schedule{padding:20px 16px;border:1px solid #ffffff21;border-radius:18px;background:#ffffff08}
.overline{color:#c0cbe0;font-size:12px;font-weight:750;letter-spacing:.11em;text-transform:uppercase}
.time{font-size:clamp(37px,10vw,53px);font-weight:850;line-height:1.2;letter-spacing:-.04em;color:#fff}
small{display:block;color:#a6b9d6}
#recovery-status{min-height:44px;margin:20px 0 8px;color:#d4ddf1;font-size:14px}
.loader{display:inline-block;width:9px;height:9px;margin-right:8px;border-radius:50%;background:#7fc6ff;box-shadow:0 0 0 4px #7fc6ff1a;animation:pulse 1.7s ease-in-out infinite}
button{width:100%;border:0;border-radius:14px;padding:15px 20px;font:800 15px system-ui;cursor:pointer;color:#101b30;background:linear-gradient(120deg,#ffe0a7,#ffb862);box-shadow:0 8px 30px #ffb86223}
button:hover{filter:brightness(1.07)}button:focus-visible{outline:3px solid #7fc6ff;outline-offset:4px}
.note{margin:20px 0 0;color:#9daccc;font-size:13px}
@keyframes pulse{50%{opacity:.35;transform:scale(.75)}}@media(prefers-reduced-motion:reduce){.loader{animation:none}}
@media(max-width:380px){main{padding:25px 20px}.brand{letter-spacing:.12em}}
</style></head>
<body><main role="main">
<div class="brand">🎞️ CINÉ<span>RADAR</span></div>
<div class="mark" aria-hidden="true">🎬</div>
<div class="pill">Maintenance en cours</div>
<h1>CinéRadar est en maintenance</h1>
<p class="lead">Nous revenons très bientôt. Merci de votre patience et de votre confiance.</p>
<div class="schedule"><div class="overline">Retour prévu à</div><div class="time">00h05</div><small>__DATE__ · Heure du Togo · sous réserve de disponibilité</small></div>
<div id="recovery-status" role="status" aria-live="polite"><span class="loader" aria-hidden="true"></span>Vérification automatique de la disponibilité…</div>
<button type="button" onclick="location.reload()">↻ Vérifier maintenant</button>
<p class="note">Cette page se rouvrira automatiquement dès le retour de CinéRadar.</p>
<script>
(function(){
 const status=document.getElementById("recovery-status");
 const recoverAt=new Date("__REOPENING__").getTime();
 const delay=Math.max(0,recoverAt-Date.now()+2000);
 async function check(){
  try{
   const response=await fetch("/health?recovery="+Date.now(),{cache:"no-store",signal:AbortSignal.timeout(10000)});
   if(response.ok){
    const result=await response.json();
    if(result.service==="cine-radar"&&result.database===true){
     status.textContent="CinéRadar est de retour. Ouverture automatique…";
     location.replace("/app");
     return;
    }
   }
  }catch{}
  status.textContent="La maintenance se poursuit. Nouvelle vérification automatique dans une minute.";
 }
 setTimeout(function(){check();setInterval(check,60000)},Math.min(delay,2147480000));
})();
</script>
</main></body></html>`.replace("__DATE__",date).replace("__REOPENING__",details.reopening_at||now.toISOString());
 const page=details.reopening_at?html:html.replace(
  '<div class="schedule"><div class="overline">Retour prévu à</div><div class="time">00h05</div><small> · Heure du Togo · sous réserve de disponibilité</small></div>',
  '<div class="schedule"><div class="overline">Retour du service</div><div class="time">Dès que possible</div><small>Vérification automatique de la disponibilité</small></div>'
 );
 return new Response(page,{status:503,headers:{
  ...headers,"content-type":"text/html; charset=utf-8",
  "content-security-policy":"default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org"
 }});
}
export async function telegramMaintenanceReply(update,call,env,{now=new Date(),mode="quota"}={}){
 const info=maintenanceDetails(now,{mode});
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
    text:mode==="quota"?"CinéRadar est en maintenance. Retour prévu à 00h05 (heure du Togo).":"CinéRadar est en maintenance. Retour dès que possible.",
    show_alert:true
   });
   if(ack?.ok===true)return Response.json({ok:true,maintenance:true});
  }
  const sent=await call(env,"sendMessage",{
   chat_id:chat.id,
   text:info.message,
   parse_mode:"HTML",
   disable_web_page_preview:true,
   disable_notification:true
  });
  if(sent?.ok===true)return Response.json({ok:true,maintenance:true});
 }catch{ /* Telegram failures must remain retryable, without leaking a token. */ }
 return new Response("Maintenance: Telegram delivery unavailable",{status:503,headers:{"cache-control":"no-store","retry-after":"60"}});
}
// Tests only. Does not persist or modify any Cloudflare resources.
export function resetMaintenanceForTests(){localMaintenanceUntil=0;}
