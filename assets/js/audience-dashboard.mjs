/**
 * Mr XPRONOS: administration de l'audience, uniquement des agrégats.
 * Aucune donnée individuelle n'est demandée par ce client.
 */
import { supabaseUrl,supabaseAnonKey } from "./config.js";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.57.4";
const sb=createClient(supabaseUrl,supabaseAnonKey);
const $=id=>document.getElementById(id);
const num=n=>Number(n||0).toLocaleString("fr-FR");
const percent=(numerator,denominator)=>Number(denominator)>0
  ? (100*Number(numerator||0)/Number(denominator)).toLocaleString("fr-FR",
    {maximumFractionDigits:1,minimumFractionDigits:1})+" %":"—";
const string=v=>String(v??"");
const stat=(id,n)=>{$(id).textContent=num(n);};
const label=(id,v)=>{$(id).textContent=string(v);};
let authorised=false,busy=false,current=null,currentPwa=null,chartKey="visitors",selected="audience";
const stages=[
  ["cta_visible","ins-visible"],["cta_click","ins-clicks"],["prompt_accepted","ins-accepted"],
  ["appinstalled","ins-installed"],["standalone_open","ins-standalone"],["guide_open","ins-guides"]
];
function setStatus(text,isError=false){
  const e=$("status");e.textContent=text;e.classList.toggle("error",isError);
}
function emptyRow(count,text){
  const tr=document.createElement("tr"),td=document.createElement("td");
  td.colSpan=count;td.textContent=text;tr.append(td);return tr;
}
function table(id,rows,cols){
  const t=$(id);t.replaceChildren();
  if(!rows.length){t.append(emptyRow(cols.length,"Aucune mesure disponible sur la période"));return;}
  const frag=document.createDocumentFragment();
  rows.forEach(row=>{
    const tr=document.createElement("tr");
    cols.forEach(field=>{
      const td=document.createElement("td");
      const value=typeof field==="function"?field(row):row[field];
      td.textContent=typeof value==="number"?num(value):string(value??"—");
      tr.append(td);
    });
    frag.append(tr);
  });
  t.append(frag);
}
function showChart(rows){
  const chart=$("traffic-chart");chart.replaceChildren();
  const filtered=(Array.isArray(rows)?rows:[]).map(r=>({
    day:string(r.day),value:Math.max(0,Number(r[chartKey]||0))
  })).filter(r=>Number.isFinite(r.value));
  if(!filtered.length){
    const text=document.createElement("p");
    text.className="bar-empty";text.textContent="Aucune mesure disponible";chart.append(text);
    chart.setAttribute("aria-label","Aucune donnée");return;
  }
  const max=Math.max(1,...filtered.map(r=>r.value));
  const frag=document.createDocumentFragment();
  filtered.forEach(row=>{
    const outer=document.createElement("div");
    outer.className="bar";outer.tabIndex=0;
    const desc=row.day+" : "+num(row.value);
    outer.title=desc;outer.setAttribute("aria-label",desc);
    const bar=document.createElement("span");
    bar.style.height=(row.value?Math.max(2,100*row.value/max):1)+"%";
    outer.append(bar);frag.append(outer);
  });
  chart.append(frag);
  chart.setAttribute("aria-label",filtered.length+" jours UTC, indicateur "+chartKey);
  document.querySelectorAll("[data-chart]").forEach(b=>
    b.setAttribute("aria-pressed",String(b.dataset.chart===chartKey)));
}
function renderAudience(d) {
  const s=d.summary||{},daily=Array.isArray(d.daily)?d.daily:[];
  for(const [id,key] of [
    ["kpi-dau","dau"],["kpi-wau","wau"],["kpi-mau","mau"],
    ["kpi-visitors","visitors_period"],["kpi-sessions","sessions"],
    ["kpi-pageviews","page_views"],["kpi-engaged","engaged_sessions"],
    ["kpi-standalone","standalone_sessions"]
  ])stat(id,s[key]);
  label("kpi-engaged-detail",percent(s.engaged_sessions,s.sessions)+
    " des sessions · 15 s visibles ou davantage");
  table("daily-rows",daily,["day","visitors","sessions","page_views","engaged_sessions"]);
  table("page-rows",Array.isArray(d.pages)?d.pages:[],["page","views"]);
  showChart(daily);
}
function renderRetention(d) {
  const c=d.cohorts||{},s=d.summary||{};
  for(const [key,id] of [["j1","ret-j1"],["j7","ret-j7"],["j30","ret-j30"]]){
    const v=c[key]||{};
    label(id,percent(v.returned,v.eligible));
    const days=key.slice(1);
    label(id+"-detail",Number(v.eligible)>0
      ? num(v.returned)+" retours / "+num(v.eligible)+" navigateurs mûrs"
      : "Aucune cohorte arrivée à maturité pour J+"+days);
  }
  stat("ret-returning",s.returning_visitor_ids);
}
function renderInstall(d,pwa) {
  const e=d.install_funnel||{};
  for(const [event,id] of stages)stat(id,e[event]);
  label("ins-rate",Number(e.cta_visible)>0
    ? percent(e.cta_click,e.cta_visible)+" de navigateurs ayant vu le CTA l'ont activé*"
    : "Taux de clics indisponible faute de CTA vu");
  const platforms=Array.isArray(pwa?.platforms)?pwa.platforms:[];
  table("platform-rows",platforms,["platform","cta_visible","cta_click","standalone_open"]);
  const surfaces=Array.isArray(pwa?.surfaces)?pwa.surfaces:[];
  table("surface-rows",surfaces,["surface","cta_visible","cta_click"]);
}
function renderAcquisition(d){
  const sources=Array.isArray(d.acquisition)?d.acquisition:[];
  const campaigns=Array.isArray(d.campaigns)?d.campaigns:[];
  table("source-rows",sources,["channel","visitors","cta_clicks","standalone_open"]);
  table("campaign-rows",campaigns,["campaign","channel","visitors"]);
}
function renderQuality(d) {
  const s=d.summary||{},q=d.quality||{},days=Number(d.period_days||0);
  label("quality-sessions",num(s.sessions)+" sessions V2 et "+
    num(q.session_events)+" événements de session mesurés");
  label("quality-gaps",num(q.days_without_telemetry)+" jour(s) sans événement V2 sur "+
    num(days)+" jour(s) observés (absence de mesure ≠ absence de trafic)");
  label("quality-legacy",num(q.legacy_raw_visits)+" visites dans l'ancien journal"+
    " (non fusionnées avec les nouvelles sessions)");
  label("quality-suspects",num(q.legacy_high_rate_minutes)+" minute(s) à débit suspect"+
    " · "+num(q.legacy_historic_ci_window_visits)+" anciennes visites dans la fenêtre de test CI identifiée");
  label("quality-attribution",num(q.acquisition_visitor_ids)+" navigateurs enregistrés"+
    " avec un premier contact dans la période · "+
    num(q.installation_events)+" événements d'installation bruts");
  const sparse=Number(s.sessions||0)===0;
  $("data-note").textContent=sparse
    ? "Aucune session V2 enregistrée sur cette période. Les anciens journaux ne sont pas convertis : les taux de fidélisation ne peuvent pas être extrapolés."
    : "Du "+d.start_day+" au "+d.end_day+
      " (UTC). Visiteurs = identifiants pseudonymisés, pas personnes physiques. Les données anciennes et les pics suspects sont signalés séparément.";
}
function renderAll(d,pwa){
  renderAudience(d);renderRetention(d);renderInstall(d,pwa);
  renderAcquisition(d);renderQuality(d);
}
async function isAdmin(){
  const user=await sb.auth.getUser();
  if(user.error||!user.data?.user)return false;
  const result=await sb.rpc("is_admin");
  return !result.error&&result.data===true;
}
async function refreshAuth(){
  try{authorised=await isAdmin();}
  catch{authorised=false;}
  $("auth-form").hidden=authorised;
  $("dashboard").hidden=!authorised;
  $("logout").hidden=!authorised;
  if(authorised){setStatus("Accès administrateur autorisé.");await refresh();}
  else{
    current=null;currentPwa=null;
    setStatus("Identifiez-vous avec un compte administrateur autorisé.");
  }
}
async function refresh(){
  if(!authorised||busy)return;
  busy=true;$("refresh").disabled=true;$("export").disabled=true;
  setStatus("Chargement des agrégats…");
  try{
    const days=Number($("period").value);
    if(![1,7,30,90].includes(days))throw Error("Période invalide");
    // Les deux RPC imposent is_admin côté serveur. Aucun accès direct aux tables.
    const [main,pwa]=await Promise.all([
      sb.rpc("admin_audience_dashboard_v1",{p_days:days}),
      sb.rpc("admin_pwa_install_funnel_v2",{p_days:days})
    ]);
    if(main.error)throw main.error;
    if(pwa.error)throw pwa.error;
    current=main.data||{};currentPwa=pwa.data||{};
    renderAll(current,currentPwa);
    setStatus("Actualisé le "+new Date().toLocaleString("fr-FR")+
      " · Fenêtre UTC : "+current.start_day+" → "+current.end_day);
  }catch(error){
    setStatus("Mesures indisponibles : "+string(error?.message||error),true);
  }finally{
    busy=false;$("refresh").disabled=false;
    $("export").disabled=!current;
  }
}
function switchTab(id,focus=false) {
  if(!["audience","retention","installation","acquisition"].includes(id))return;
  selected=id;
  document.querySelectorAll("[data-tab]").forEach(b=>{
    const active=b.dataset.tab===id;
    b.setAttribute("aria-selected",String(active));b.tabIndex=active?0:-1;
    if(active&&focus)b.focus();
  });
  for(const tab of ["audience","retention","installation","acquisition"]){
    $("panel-"+tab).hidden=tab!==id;
  }
}
function csvCell(value){
  const s=string(value);
  // Prevent spreadsheet formula injection when exporting untrusted campaign slugs.
  const safe=/^[=+\-@\t\r]/.test(s)?"'"+s:s;
  return '"'+safe.replace(/"/g,'""')+'"';
}
function exportAggregates(){
  if(!current||!authorised)return;
  const d=current,s=d.summary||{},c=d.cohorts||{},q=d.quality||{};
  const rows=[["section","key","value","period_start","period_end"]];
  function add(section,key,value){rows.push([section,key,value??"",d.start_day,d.end_day]);}
  Object.entries(s).forEach(([k,v])=>add("audience",k,v));
  for(const [k,v] of Object.entries(c)){
    add("cohort",k+"_eligible",v.eligible);
    add("cohort",k+"_returned",v.returned);
  }
  Object.entries(d.install_funnel||{}).forEach(([k,v])=>add("install",k,v));
  Object.entries(q).forEach(([k,v])=>add("quality",k,v));
  (d.daily||[]).forEach(v=>{
    for(const key of ["visitors","sessions","page_views","engaged_sessions","standalone_sessions"])
      add("daily_"+v.day,key,v[key]);
  });
  (d.acquisition||[]).forEach(v=>{
    for(const key of ["visitors","cta_clicks","appinstalled","standalone_open"])
      add("channel_"+v.channel,key,v[key]);
  });
  (d.campaigns||[]).forEach(v=>add("campaign_"+v.channel,v.campaign,v.visitors));
  const text="\uFEFF"+rows.map(r=>r.map(csvCell).join(",")).join("\r\n")+"\r\n";
  const blob=new Blob([text],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;a.download="mrxpronos-audience-"+d.end_day+"-"+d.period_days+"j.csv";
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
}
$("auth-form").addEventListener("submit",async event=>{
  event.preventDefault();
  const b=$("login");b.disabled=true;setStatus("Connexion en cours…");
  try{
    const {error}=await sb.auth.signInWithPassword({
      email:$("email").value.trim(),password:$("password").value
    });
    if(error)throw error;
    await refreshAuth();
    if(!authorised){
      await sb.auth.signOut();
      setStatus("Ce compte ne dispose pas des droits administrateur.",true);
    }
  }catch(error){setStatus("Connexion refusée : "+string(error?.message||error),true);}
  finally{b.disabled=false;}
});
$("logout").addEventListener("click",async()=>{
  await sb.auth.signOut();current=null;currentPwa=null;authorised=false;
  await refreshAuth();
});
$("refresh").addEventListener("click",()=>{void refresh();});
$("period").addEventListener("change",()=>{void refresh();});
$("export").addEventListener("click",exportAggregates);
document.querySelectorAll("[data-chart]").forEach(b=>
  b.addEventListener("click",()=>{chartKey=b.dataset.chart;if(current)showChart(current.daily);}));
document.querySelectorAll("[data-tab]").forEach(b=>{
  b.addEventListener("click",()=>switchTab(b.dataset.tab));
  b.addEventListener("keydown",event=>{
    if(!["ArrowRight","ArrowLeft","Home","End"].includes(event.key))return;
    const all=["audience","retention","installation","acquisition"];
    let i=all.indexOf(selected);
    if(event.key==="Home")i=0;
    else if(event.key==="End")i=all.length-1;
    else i=(i+(event.key==="ArrowRight"?1:-1)+all.length)%all.length;
    event.preventDefault();switchTab(all[i],true);
  });
});
switchTab("audience");
void refreshAuth();
