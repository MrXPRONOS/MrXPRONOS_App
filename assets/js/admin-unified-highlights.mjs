// Unified admin summary. Data are read on demand and always labelled with their
// source/refresh time; the specialist pages remain available for detailed investigations.
export async function loadAdminHighlights(sb){
 const calls=[
  ["audience",()=>sb.rpc("admin_audience_dashboard_v1",{p_days:7})],
  ["pwa",()=>sb.rpc("admin_pwa_install_funnel_v2",{p_days:7})],
  ["errors",()=>sb.rpc("admin_client_error_summary",{p_days:7})],
  ["incidents",()=>sb.from("admin_incidents").select("status,severity,created_at")
    .in("status",["open","acknowledged"]).limit(200)],
  ["campaigns",()=>sb.from("admin_push_campaigns")
    .select("status,summary").order("created_at",{ascending:false}).limit(50)]
 ];
 const settled=await Promise.allSettled(calls.map(async ([name,call])=>{
  const {data,error}=await call();
  if(error)throw error;
  return {name,data};
 }));
 const result={};
 for(let i=0;i<calls.length;i++){
  const outcome=settled[i];
  result[calls[i][0]]=outcome.status==="fulfilled"?outcome.value.data:null;
 }
 return result;
}
export function createAdminHighlightWidget(root){
 if(!root)return null;
 root.replaceChildren();
 const section=document.createElement("section");section.className="admin-unified-summary";
 const heading=document.createElement("h3");heading.textContent="Audience, installation et incidents · 7 jours";
 const metrics=document.createElement("div");metrics.className="admin-overview-kpis";
 const chart=document.createElement("div");chart.className="admin-unified-chart";
 chart.setAttribute("role","img");chart.setAttribute("aria-label","Visiteurs uniques par jour");
 const caption=document.createElement("p");caption.className="muted";caption.setAttribute("role","status");
 section.append(heading,metrics,chart,caption);root.append(section);
 const fmt=value=>Number.isFinite(Number(value))?Number(value).toLocaleString("fr-FR"):"—";
 function metric(label,value){
  const box=document.createElement("div");box.className="admin-kpi";
  const val=document.createElement("strong");val.textContent=value;
  const name=document.createElement("small");name.textContent=label;
  box.append(val,name);metrics.append(box);
 }
 function draw(data){
  metrics.replaceChildren();chart.replaceChildren();
  const a=data.audience||{},summary=a.summary||{},
    e=data.pwa?.events||{},errs=data.errors||{},
    incidents=Array.isArray(data.incidents)?data.incidents:[],
    campaigns=Array.isArray(data.campaigns)?data.campaigns:[];
  metric("Visiteurs uniques",fmt(summary.visitors_period));
  metric("Sessions engagées",fmt(summary.engaged_sessions));
  metric("Clics d'installation",fmt(e.cta_click));
  metric("Ouvertures installées",fmt(e.standalone_open));
  metric("Erreurs navigateur",fmt(errs.total));
  metric("Incidents à traiter",fmt(data.incidents?incidents.length:null));
  const failures=campaigns.filter(x=>x.status==="failed").length;
  metric("Campagnes Push en échec",fmt(data.campaigns?failures:null));
  const daily=Array.isArray(a.daily)?a.daily:[];
  const max=Math.max(1,...daily.map(d=>Math.max(0,Number(d.visitors||0))));
  for(const d of daily.slice(-7)){
   const block=document.createElement("div");block.className="admin-unified-day";
   const meter=document.createElement("div");meter.className="admin-unified-bar";
   const v=Math.max(0,Number(d.visitors||0));
   meter.style.height=(v?Math.max(4,Math.round(90*v/max)):1)+"px";
   const label=document.createElement("small");
   label.textContent=String(d.day||"").slice(5);
   block.title=String(d.day||"")+" : "+fmt(v)+" visiteurs";
   block.append(meter,label);chart.append(block);
  }
  const missing=Object.keys(data).filter(k=>data[k]===null);
  caption.textContent="Actualisé "+new Date().toLocaleTimeString("fr-FR")+
   " · Sources : Supabase (données estimées et déclaratives)"+
   (missing.length?" · Indisponibles : "+missing.join(", "):"");
 }
 return {draw};
}
