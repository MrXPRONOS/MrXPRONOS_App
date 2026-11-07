/**
 * Phase 5: two optional, copy-only A/B tests.
 * Assignment is server-side and stable per browser pseudonymous ID.
 * No browser/device fingerprint and no data about favorite teams is transmitted.
 */
const QUEUE="mx_ab_events_v1";
const MAX_EVENTS=24;
let clientPromise=null,flushing=false;
const experiments=new Map();

export const COPY={
  install_value_v1:{
    a:{
      title:"Votre football, en un seul geste.",
      body:"Accédez plus facilement aux pronostics du jour, aux analyses et aux résultats depuis l’icône Mr XPRONOS sur votre appareil."
    },
    b:{
      title:"Mr XPRONOS directement sur votre écran d’accueil.",
      body:"Ouvrez les sélections publiées, les analyses et les résultats depuis une icône sur votre téléphone ou votre ordinateur."
    }
  },
  favorites_guidance_v1:{
    a:{
      title:"Mes équipes et ligues",
      body:"Ajoutez vos équipes ou compétitions pour retrouver les sélections et les articles qui les concernent. Ces choix restent sur cet appareil."
    },
    b:{
      title:"Suivez vos équipes favorites.",
      body:"Choisissez une équipe ou une compétition pour retrouver plus vite les matchs et articles qui la concernent. Vos choix restent sur cet appareil."
    }
  }
};
function visitor(){
  try{
    const s=localStorage.getItem("mx_user_id")||"";
    return /^(MX|PL)-[a-zA-Z0-9._-]{6,120}$/.test(s)?s:null;
  }catch{return null;}
}
function uuid(){
  try{return crypto.randomUUID();}catch{return null;}
}
function pending(){
  try{
    const items=JSON.parse(sessionStorage.getItem(QUEUE)||"[]");
    const now=Date.now();
    return Array.isArray(items)?items.filter(e=>e&&
      /^[a-f0-9-]{36}$/i.test(e.event_id||"") &&
      ["exposure","conversion"].includes(e.kind) &&
      now>=Number(e.queued_at||0) && now-Number(e.queued_at||0)<8*86400000
    ).slice(-MAX_EVENTS):[];
  }catch{return [];}
}
function save(items){
  try{sessionStorage.setItem(QUEUE,JSON.stringify(items.slice(-MAX_EVENTS)));return true;}
  catch{return false;}
}
async function sdk(){
  if(!clientPromise)clientPromise=(async()=>{
    const c=await import("./config.js");
    if(!/^https:\/\//.test(c.supabaseUrl||"")||!c.supabaseAnonKey)
      throw Error("Supabase non disponible");
    const {createClient}=await import("https://esm.sh/@supabase/supabase-js@2.57.4");
    return createClient(c.supabaseUrl,c.supabaseAnonKey,{
      auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}
    });
  })().catch(e=>{clientPromise=null;throw e;});
  return clientPromise;
}
async function flush(){
  if(flushing||/^(localhost|127\.0\.0\.1)$/.test(location.hostname))return;
  flushing=true;
  try{
    const sb=await sdk();
    for(let i=0;i<MAX_EVENTS;i++){
      const arr=pending();
      if(!arr.length){save([]);break;}
      const entry=arr[0];
      const {data,error}=await sb.rpc("track_experiment_v1",{
        p_event_id:entry.event_id,p_experiment:entry.experiment,
        p_user_id:entry.user_id,p_variant:entry.variant,p_kind:entry.kind
      });
      if(error||data!==true)break;
      save(pending().filter(x=>x.event_id!==entry.event_id));
    }
  }catch{/* Retry after reconnection, without disrupting the site. */}
  finally{flushing=false;}
}
function addEvent(state,kind){
  const id=uuid();
  if(!id||!state||!["a","b"].includes(state.variant))return;
  const arr=pending();
  // One same-kind event per experiment per tab; server also deduplicates
  // by (experiment, visitor), including across tabs and devices with same ID.
  if(arr.some(e=>e.experiment===state.id&&e.kind===kind))return;
  arr.push({event_id:id,experiment:state.id,user_id:state.user_id,
    variant:state.variant,kind,queued_at:Date.now()});
  if(save(arr))void flush();
}
function isVisible(el){
  if(!el||el.hidden||document.hidden)return false;
  if(el.closest("[hidden]"))return false;
  const r=el.getBoundingClientRect(),w=window.innerWidth,h=window.innerHeight;
  if(r.width<=0||r.height<=0)return false;
  const x=Math.max(0,Math.min(r.right,w)-Math.max(r.left,0));
  const y=Math.max(0,Math.min(r.bottom,h)-Math.max(r.top,0));
  return x*y>=Math.min(r.width*r.height,Math.max(1,w*h))*0.22;
}
function expose(state){
  if(state.exposed||!isVisible(state.el))return false;
  state.exposed=true;
  addEvent(state,"exposure");
  return true;
}
function watchVisible(state){
  const el=state.el;
  if(typeof IntersectionObserver==="function"){
    const observer=new IntersectionObserver(entries=>{
      if(entries.some(e=>e.isIntersecting&&e.intersectionRatio>=0.22)){
        if(expose(state))observer.disconnect();
      }
    },{threshold:[0,0.22,0.5]});
    observer.observe(el);
  }else{
    const check=()=>{if(expose(state)){
      window.removeEventListener("scroll",check);
      window.removeEventListener("resize",check);
    }};
    window.addEventListener("scroll",check,{passive:true});
    window.addEventListener("resize",check);
    check();
  }
}
async function boot(id,el,apply,onGoal){
  if(!el||experiments.has(id)||/^(localhost|127\.0\.0\.1)$/.test(location.hostname))return;
  // Reserve the initialization once per page; fallback retains baseline copy.
  experiments.set(id,{disabled:true});
  void flush();
  const user_id=visitor();
  if(!user_id)return;
  try{
    const sb=await sdk();
    const {data,error}=await sb.rpc("experiment_variant_v1",{
      p_experiment:id,p_user_id:user_id
    });
    if(error||data?.enabled!==true||!["a","b"].includes(data?.variant))return;
    // Another module/page may have changed the element while awaiting the network.
    if(!el.isConnected)return;
    const state={id,user_id,variant:data.variant,el,exposed:false};
    experiments.set(id,state);
    apply(COPY[id][state.variant]);
    onGoal(()=>{expose(state);if(state.exposed)addEvent(state,"conversion");});
    watchVisible(state);
  }catch{/* Server flag off or network error => control UI, no exposure recorded. */}
}
export function startInstall(){
  const el=document.getElementById("mx-install-panel");
  if(!el)return;
  void boot("install_value_v1",el,copy=>{
    const title=document.getElementById("mx-install-panel-title");
    const body=el.querySelector(".mx-install-panel-copy > p");
    if(title)title.textContent=copy.title;
    if(body)body.textContent=copy.body;
  },goal=>{
    el.querySelector("[data-mx-install-trigger]")?.addEventListener("click",goal,{
      capture:true,passive:true
    });
  });
}
export function startFavorites(){
  const el=document.getElementById("daily-favorites");
  if(!el)return;
  void boot("favorites_guidance_v1",el,copy=>{
    const title=document.getElementById("favorites-title");
    const body=el.querySelector(":scope > p");
    if(title)title.textContent=copy.title;
    if(body)body.textContent=copy.body;
  },goal=>{
    window.addEventListener("mx-experiment-favorite-added",goal);
  });
}
