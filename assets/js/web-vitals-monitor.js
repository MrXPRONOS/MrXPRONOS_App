// Privacy-conscious anonymous sampled Core Web Vitals (no IP, user ID or query params).
// The existing RLS permits INSERT only; browsers cannot SELECT telemetry.
import {supabaseUrl,supabaseAnonKey} from "./config.js";
const page=location.pathname.replace(/^\/MrXPRONOS_App/i,"").slice(0,140)||"/";
if(/^\/[a-zA-Z0-9/_.-]+$/.test(page)&&Math.random()<0.12){
  const device=/iPad|Tablet/i.test(navigator.userAgent)?"tablet":/iPhone|Android|Mobile/i.test(navigator.userAgent)?"mobile":"desktop";
  const client=window.supabase?.createClient?.(supabaseUrl,supabaseAnonKey);
  if(client){
    const sent=new Set();
    const record=async({name,value})=>{
      if(!["LCP","INP","CLS"].includes(name)||!Number.isFinite(value)||value<0||value>60000)return;
      // report each metric once per page load to minimize requests and duplication
      if(sent.has(name))return;sent.add(name);
      try{await client.from("admin_web_vitals").insert({metric:name,value:Math.round(value*1000)/1000,page,device})}catch{}
    };
    // Lazy loading; no impact on critical rendering.
    const begin=()=>{
      import("https://unpkg.com/web-vitals@5/dist/web-vitals.attribution.js").then(({onCLS,onINP,onLCP})=>{
        onCLS(record,{reportAllChanges:false});onINP(record,{reportAllChanges:false});onLCP(record,{reportAllChanges:false});
      }).catch(()=>{});
    };
    if(document.readyState==="complete")begin();else addEventListener("load",begin,{once:true});
  }
}
