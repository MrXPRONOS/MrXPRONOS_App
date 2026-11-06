/**
 * Mesure des sessions V2 pour la route Aujourd'hui.
 * Réutilise les clés et la RPC de la phase 1 sans charger tout main.js.
 * Reprise des événements idempotents après interruption réseau.
 */
const SESSION_KEY="mx_analytics_session_v2";
const QUEUE_KEY="mx_analytics_events_v2";
const MAX_QUEUE=30;
let session=null,active=false,flushing=false,clientPromise=null,timer=null;

function readJSON(key){
  try{return JSON.parse(sessionStorage.getItem(key)||"null");}catch{return null;}
}
function writeJSON(key,value){
  try{sessionStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;}
}
function uuid(){
  return typeof crypto!=="undefined"&&typeof crypto.randomUUID==="function"
    ? crypto.randomUUID() : null;
}
function getVisitor(){
  let existing="";
  try{existing=localStorage.getItem("mx_user_id")||"";}catch{}
  if(/^(MX|PL)-[a-zA-Z0-9._-]{6,120}$/.test(existing))return existing;
  const id=uuid();
  if(!id)return null;
  try{localStorage.setItem("mx_user_id","MX-"+id);return"MX-"+id;}catch{return null;}
}
function sessionId(){
  const now=Date.now();
  const existing=readJSON(SESSION_KEY);
  if(existing&&/^[a-f0-9-]{36}$/i.test(String(existing.id))&&
    Number.isFinite(existing.last)&&now>=existing.last&&now-existing.last<30*60000){
    writeJSON(SESSION_KEY,{id:existing.id,last:now});
    return existing.id;
  }
  const id=uuid();
  if(!id)return null;
  writeJSON(SESSION_KEY,{id,last:now});
  return id;
}
function platform(){
  const ua=navigator.userAgent||"";
  if(/ipad|tablet/i.test(ua)||(/android/i.test(ua)&&!/mobile/i.test(ua)))return"tablet";
  if(/mobile|android|iphone|ipod/i.test(ua))return"mobile";
  return"desktop";
}
function standalone(){
  try{return matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;}
  catch{return false;}
}
function queue(kind){
  const id=uuid(),visitor=getVisitor(),sessionIdValue=sessionId();
  if(!id||!visitor||!sessionIdValue)return;
  const current=readJSON(QUEUE_KEY);
  const items=Array.isArray(current)?current:[];
  items.push({
    p_session_id:sessionIdValue,p_event_id:id,p_user_id:visitor,p_kind:kind,
    p_page:"/aujourdhui.html",p_device:platform(),
    p_display_mode:standalone()?"standalone":"browser"
  });
  writeJSON(QUEUE_KEY,items.slice(-MAX_QUEUE));
  void flush();
}
async function supabase(){
  if(!clientPromise){
    clientPromise=(async()=>{
      const config=await import("./config.js");
      const sdk=await import("https://esm.sh/@supabase/supabase-js@2");
      if(!config.supabaseUrl||!config.supabaseAnonKey)throw Error("config unavailable");
      return sdk.createClient(config.supabaseUrl,config.supabaseAnonKey,{
        auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}
      });
    })().catch(error=>{clientPromise=null;throw error;});
  }
  return clientPromise;
}
async function flush(){
  if(flushing)return;
  flushing=true;
  try{
    const sdk=await supabase();
    for(let n=0;n<MAX_QUEUE;n++){
      const current=readJSON(QUEUE_KEY);
      if(!Array.isArray(current)||!current.length)break;
      const item=current[0];
      if(!item||!item.p_event_id||!item.p_session_id||!item.p_user_id){
        writeJSON(QUEUE_KEY,current.slice(1));continue;
      }
      const {data,error}=await sdk.rpc("track_visitor_session_v2",item);
      if(error||data!==true)break;
      const latest=readJSON(QUEUE_KEY);
      if(!Array.isArray(latest))break;
      writeJSON(QUEUE_KEY,latest.filter(e=>e?.p_event_id!==item.p_event_id));
    }
  }catch{/* Retry on next page launch or online event. */}
  finally{flushing=false;}
}
export function start(){
  if(active)return;
  if(/^(localhost|127\.0\.0\.1)$/.test(location.hostname))return;
  active=true;
  void flush();
  queue("page_view");
  let engaged=false;
  let visibleSince=document.hidden?null:Date.now();
  const onVisibility=()=>{
    if(engaged)return;
    if(timer!==null)clearTimeout(timer);
    if(document.hidden){visibleSince=null;return;}
    visibleSince=Date.now();
    timer=setTimeout(()=>{
      if(!document.hidden&&Date.now()-visibleSince>=14500){
        engaged=true;queue("engaged");
        document.removeEventListener("visibilitychange",onVisibility);
      }
    },15000);
  };
  document.addEventListener("visibilitychange",onVisibility);
  if(!document.hidden)onVisibility();
  window.addEventListener("pageshow",event=>{if(event.persisted)queue("page_view");});
  window.addEventListener("online",()=>{void flush();});
}
