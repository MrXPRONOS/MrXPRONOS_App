/**
 * Acquisition sans empreinte digitale ni URL de provenance brute.
 * Le navigateur ne transmet que le canal connu et un slug de campagne limité.
 * 1 événement par ouverture d'onglet ; rediffusion avec le même UUID en cas d'échec.
 */
const QUEUE_KEY="mx_acquisition_pending_v1";
const TAB_KEY="mx_acquisition_tab_v1";
const MAX=12;
const CHANNELS=new Set([
  "direct","google","organic_search","facebook","instagram","whatsapp",
  "telegram","youtube","tiktok","pinterest","linkedin","referral","other","unknown"
]);
let active=false,flushing=false,clientPromise=null;
export function channelOf(source) {
  const name=String(source||"").trim().toLowerCase().replace(/^www\./,"");
  if(!name)return null;
  const rules=[
    [/^(google|google\.|g\.co|goo\.gl|googleads|adwords)/,"google"],
    [/^(bing|bing\.|yahoo|yahoo\.|duckduckgo|duckduckgo\.|baidu)/,"organic_search"],
    [/^(facebook|facebook\.|fb|fb\.|m\.facebook|meta|l\.facebook)/,"facebook"],
    [/^(instagram|instagram\.|ig|l\.instagram)/,"instagram"],
    [/^(whatsapp|whatsapp\.|wa\.me|api\.whatsapp)/,"whatsapp"],
    [/^(telegram|telegram\.|t\.me|telegram\.me)/,"telegram"],
    [/^(youtube|youtube\.|youtu\.be|yt)/,"youtube"],
    [/^(tiktok|tiktok\.|vm\.tiktok|tt)/,"tiktok"],
    [/^(pinterest|pinterest\.|pin\.it)/,"pinterest"],
    [/^(linkedin|linkedin\.|lnkd\.in)/,"linkedin"]
  ];
  for(const [re,channel] of rules)if(re.test(name))return channel;
  if(name==="organic"||name==="seo"||name==="search")return"organic_search";
  if(name==="direct"||name==="none")return"direct";
  if(name==="referral"||name==="referent")return"referral";
  return null;
}
export function classifyLanding(locationHref,referrer="") {
  let page;
  try{page=new URL(locationHref);}catch{return{channel:"unknown",campaign:null};}
  const params=page.searchParams;
  const utm=params.get("utm_source")||params.get("source")||"";
  const fromUtm=channelOf(utm);
  const medium=String(params.get("utm_medium")||"").trim().toLowerCase();
  const campaign=String(params.get("utm_campaign")||"").trim().toLowerCase()
    .replace(/[^a-z0-9_.-]/g,"_").replace(/^[_\-.]+/,"").slice(0,48);
  let channel=fromUtm;
  if(!channel) {
    try{
      if(referrer){
        const prev=new URL(referrer);
        if(prev.origin!==page.origin)channel=channelOf(prev.hostname)||"referral";
      }
    }catch{/* Invalid referrer: no URL transmitted. */}
  }
  if(!channel && ["organic","seo"].includes(medium))channel="organic_search";
  if(!channel && utm)channel="other";
  if(!channel)channel="direct";
  return {channel:CHANNELS.has(channel)?channel:"other",
    campaign:/^[a-z0-9][a-z0-9_.-]{0,47}$/.test(campaign)?campaign:null};
}
function readQueue() {
  try{
    const data=JSON.parse(sessionStorage.getItem(QUEUE_KEY)||"[]");
    return Array.isArray(data)?data.filter(x=>x&&typeof x.event_id==="string").slice(-MAX):[];
  }catch{return[];}
}
function writeQueue(items) {
  try{sessionStorage.setItem(QUEUE_KEY,JSON.stringify(items.slice(-MAX)));return true;}
  catch{return false;}
}
function visitorId() {
  let id="";
  try{id=localStorage.getItem("mx_user_id")||"";}catch{}
  if(/^(MX|PL)-[A-Za-z0-9._-]{6,120}$/.test(id))return id;
  if(typeof crypto==="undefined"||typeof crypto.randomUUID!=="function")return null;
  id="MX-"+crypto.randomUUID();
  try{localStorage.setItem("mx_user_id",id);}catch{return null;}
  return id;
}
async function client() {
  if(!clientPromise)clientPromise=(async()=>{
    const cfg=await import("./config.js");
    if(!cfg.supabaseAnonKey||!/^https:\/\//.test(cfg.supabaseUrl||""))
      throw Error("Configuration Supabase manquante");
    const {createClient}=await import("https://esm.sh/@supabase/supabase-js@2.57.4");
    return createClient(cfg.supabaseUrl,cfg.supabaseAnonKey,{
      auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}
    });
  })().catch(e=>{clientPromise=null;throw e;});
  return clientPromise;
}
export async function flush() {
  if(flushing||/^(localhost|127\.0\.0\.1)$/.test(location.hostname))return;
  flushing=true;
  try{
    const items=readQueue();if(!items.length)return;
    const id=visitorId();if(!id)return;
    const sb=await client();
    for(let n=0;n<MAX;n++){
      const queue=readQueue();if(!queue.length)break;
      const item=queue[0];
      const {data,error}=await sb.rpc("track_acquisition_v1",{
        p_event_id:item.event_id,p_user_id:id,
        p_channel:item.channel,p_campaign:item.campaign
      });
      if(error||data!==true)break;
      writeQueue(readQueue().filter(entry=>entry.event_id!==item.event_id));
    }
  }catch{/* Non-bloquant ; même UUID renvoyé lors de la prochaine tentative. */}
  finally{flushing=false;}
}
export function start() {
  if(active||/^(localhost|127\.0\.0\.1)$/.test(location.hostname))return;
  active=true;
  // Retry in this tab, even if a new route is loaded.
  void flush();
  let stored=false;
  try{stored=sessionStorage.getItem(TAB_KEY)==="1";}catch{}
  if(!stored&&typeof crypto!=="undefined"&&typeof crypto.randomUUID==="function"){
    const landing=classifyLanding(location.href,document.referrer);
    const queued=readQueue();
    queued.push({event_id:crypto.randomUUID(),...landing});
    if(writeQueue(queued)){
      try{sessionStorage.setItem(TAB_KEY,"1");}catch{}
      void flush();
    }
  }
  window.addEventListener("online",()=>{void flush();});
  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden)void flush();
  });
}
