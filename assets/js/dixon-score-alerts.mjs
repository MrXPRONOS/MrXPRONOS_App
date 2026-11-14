/** Mr XPRONOS — opt-in notifications only for new Dixon-Coles exact scores.
 * No automatic permission request and no bulk notification signup. */
import {supabaseUrl} from "./config.js";
const button=document.getElementById("mx-scores-enable-alerts");
const notice=document.getElementById("mx-scores-notice");
const endpoint=supabaseUrl+"/functions/v1/dixon-score-alerts";
let pending=false,enabled=false;
function message(text){if(notice){notice.hidden=false;notice.textContent=String(text);}}
function standalone(){try{return matchMedia("(display-mode: standalone)").matches||navigator.standalone===true}catch{return navigator.standalone===true}}
function supported(){
 const ios=/iPhone|iPad|iPod/i.test(navigator.userAgent)||navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1;
 return "Notification" in window && "serviceWorker" in navigator && "PushManager" in window && (!ios||standalone());
}
function updateButton(){
 if(!button)return;
 button.classList.toggle("mx-scores-bell-enabled",enabled);
 button.setAttribute("aria-pressed",String(enabled));
 button.setAttribute("aria-label",enabled?"Désactiver les notifications de nouveaux scores exacts":"Activer les notifications de nouveaux scores exacts");
 button.disabled=pending;
 button.title=enabled?"Notifications scores exacts activées":"Activer les notifications des nouveaux scores";
}
function userId(){
 const key="mx_user_id";
 let id="";
 try{id=localStorage.getItem(key)||""}catch{}
 if(/^(MX|PL)-[A-Za-z0-9._-]{6,120}$/.test(id))return id;
 id="MX-"+crypto.randomUUID();
 try{localStorage.setItem(key,id)}catch{throw Error("Stockage local indisponible")}
 return id;
}
function base64Key(raw){
 const normalized=(raw+"=".repeat((4-raw.length%4)%4)).replace(/-/g,"+").replace(/_/g,"/");
 return Uint8Array.from(atob(normalized),c=>c.charCodeAt(0));
}
async function service(){
 return await Promise.race([
   navigator.serviceWorker.ready,
   new Promise((_,reject)=>setTimeout(()=>reject(Error("Service Worker indisponible")),7500))
 ]);
}
async function send(action,subscription){
 const res=await fetch(endpoint,{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,subscription:subscription.toJSON()})});
 const payload=await res.json().catch(()=>({}));
 if(!res.ok||payload?.success!==true)throw Error(payload?.error||"Enregistrement impossible");
 return payload;
}
async function attachToServer(subscription){
 const res=await fetch(supabaseUrl+"/functions/v1/push-subscribe",{
  method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({user_id:userId(),subscription:subscription.toJSON()})
 });
 if(!res.ok)throw Error("Impossible d'enregistrer cet appareil");
}
async function getOrCreateSubscription(){
 const reg=await service();
 let subscription=await reg.pushManager.getSubscription();
 if(!subscription){
   const key=await fetch(supabaseUrl+"/functions/v1/vapid-public-key",{cache:"no-store"});
   if(!key.ok)throw Error("Clé de notifications indisponible");
   const raw=(await key.text()).trim();
   if(!raw)throw Error("Clé de notifications vide");
   subscription=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:base64Key(raw)});
 }
 await attachToServer(subscription);
 return subscription;
}
async function onClick(){
 if(pending)return;
 if(!supported()){
  message("Sur iPhone, installe d’abord Mr XPRONOS sur l’écran d’accueil et ouvre l’application. Sur Android, utilise un navigateur compatible avec les notifications.");
  return;
 }
 if(Notification.permission==="denied"){message("Les notifications sont bloquées dans les réglages de ce navigateur.");return;}
 // Request directly on the user gesture, before asynchronous network operations.
 const permission=Notification.permission==="default"?await Notification.requestPermission():Notification.permission;
 if(permission!=="granted"){message("Notifications non autorisées. Aucun abonnement enregistré.");return;}
 pending=true;updateButton();
 try{
  const subscription=await getOrCreateSubscription();
  const response=await send(enabled?"disable":"enable",subscription);
  enabled=response.enabled===true;
  message(enabled?"Notifications activées : tu recevras une alerte lorsque les nouveaux scores Dixon-Coles seront publiés.":"Notifications des scores exacts désactivées sur cet appareil.");
 }catch(e){message("Activation non confirmée : "+String(e?.message||e));}
 finally{pending=false;updateButton();}
}
async function sync(){
 if(!button||!supported()||Notification.permission!=="granted"){updateButton();return;}
 try{
  const reg=await service();
  const sub=await reg.pushManager.getSubscription();
  if(sub)enabled=(await send("status",sub)).enabled===true;
 }catch{/* no fake confirmation */}
 updateButton();
}
button?.addEventListener("click",()=>void onClick());
updateButton();
void sync();
