/* Mr XPRONOS — Premium dashboard, based on the approved visual reference.
 * Only authenticated, permission-checked reads; no invented KPIs.
 */
const icons={
 home:'<path d="m3 10 9-7 9 7v10H15v-7H9v7H3z"/>',
 trophy:'<path d="M8 21h8M12 17v4M7 4h10v6a5 5 0 0 1-10 0V4Z"/><path d="M7 6H4v3a4 4 0 0 0 4 4M17 6h3v3a4 4 0 0 1-4 4"/>',
 users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
 send:'<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
 zap:'<path d="m13 2-9 12h7l-1 8 10-12h-7z"/>',
 layers:'<path d="m12 2 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 17l9 5 9-5"/>',
 chart:'<path d="M5 20V12M12 20V4M19 20v-9"/>',
 pulse:'<path d="M3 12h5l3-8 4 16 3-8h3"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
 edit:'<path d="M13 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-8"/><path d="m14 8 6-6 2 2-6 6-4 1z"/>',
 arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
 database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 2 4 3 9 3s9-1 9-3V5M3 12c0 2 4 3 9 3s9-1 9-3"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-5 4-5 14 0 18M12 3c5 4 5 14 0 18"/>',
 bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z"/><path d="M10 21h4"/>',
 eye:'<path d="M2 12c2-4 6-7 10-7s8 3 10 7c-2 4-6 7-10 7s-8-3-10-7Z"/><circle cx="12" cy="12" r="3"/>',
 refresh:'<path d="M20 7a9 9 0 1 0 1 10M20 3v5h-5"/>',
 chevron:'<path d="m6 9 6 6 6-6"/>',
 check:'<path d="m4 12 5 5L20 6"/>'
};
const icon=(name,cls="")=>'<svg class="mxh-icon '+cls+'" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'+(icons[name]||icons.layers)+'</svg>';
const fmt=n=>Number.isFinite(Number(n))?Number(n).toLocaleString("fr-FR"):"—";
const get=(root,q)=>root.querySelector(q);
const set=(root,q,v)=>{const n=get(root,q);if(n)n.textContent=String(v)};
const div=(cls,text)=>{const n=document.createElement("div");n.className=cls;if(text!==undefined)n.textContent=text;return n};
const timeLabel=x=>{const t=new Date(x||"");return Number.isFinite(t.valueOf())?t.toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"}):"—"};
function markup(){
 const kpis=[
  ["users","Abonnements Push","mxh-subs","Abonnés enregistrés"],
  ["send","Notifications envoyées","mxh-sent","Campagnes récentes"],
  ["zap","Taux de livraison","mxh-rate","Campagnes récentes"],
  ["layers","Campagnes actives","mxh-active","Programmées / en cours"]
 ].map((item,i)=>'<article class="mxh-kpi '+(i%2?"mxh-blue":"mxh-gold")+'"><div class="mxh-kpi-label"><span class="mxh-kpi-icon">'+icon(item[0])+'</span><span>'+item[1]+'</span></div><strong id="'+item[2]+'">—</strong><small id="'+item[2]+'-hint">'+item[3]+'</small></article>').join("");
 const actions=[
  ["send","Nouvelle campagne","push","push_title"],
  ["edit","Rédiger un article","articles","a_title"],
  ["users","Gérer les abonnés","push","subs_search"],
  ["calendar","Programmer un Push","push","push_schedule_at"]
 ].map((a,i)=>'<button type="button" class="mxh-action '+(!i?"mxh-primary":"")+'" data-tab-target="'+a[2]+'" data-field="'+a[3]+'">'+icon(a[0])+'<span>'+a[1]+'</span>'+icon("arrow","mxh-action-arrow")+'</button>').join("");
 return '<div class="mxh-dashboard">'+
 '<div class="mxh-header-lights" aria-hidden="true"><i></i><i></i><i></i></div>'+
 '<div class="mxh-breadcrumb">'+icon("home")+'<span>Administration</span><span class="mxh-slash">/</span><b>Accueil</b></div>'+
 '<div class="mxh-hero"><div class="mxh-title"><span class="mxh-trophy">'+icon("trophy")+'</span><div><h2>Tableau de bord</h2><p>Vue d’ensemble de votre plateforme Mr XPRONOS.</p></div></div><label class="mxh-period">'+icon("calendar")+'<span id="mxh-period-text">7 derniers jours</span><select id="mxh-period" aria-label="Période des statistiques"><option value="7">7 derniers jours</option><option value="30">30 derniers jours</option></select>'+icon("chevron")+'</label></div>'+
 '<div class="mxh-kpi-grid">'+kpis+'</div>'+
 '<div class="mxh-content-grid">'+
 '<section class="mxh-panel mxh-visitors"><div class="mxh-panel-title"><span class="mxh-panel-icon">'+icon("chart")+'</span><div><h3>Visiteurs</h3><p>Évolution des visiteurs uniques sur la période.</p></div><span id="mxh-period-label" class="mxh-period-pill">7 jours</span></div><div id="mxh-graph" class="mxh-graph" role="img" aria-label="Graphique de visiteurs en chargement"></div><p id="mxh-graph-source" class="mxh-footnote">Source : Supabase</p></section>'+
 '<section class="mxh-panel mxh-services"><div class="mxh-panel-title"><span class="mxh-panel-icon">'+icon("pulse")+'</span><div><h3>État des services</h3><p>Disponibilité et fraîcheur des données.</p></div></div><div id="mxh-service-rows" class="mxh-service-rows"><p class="mxh-empty">Chargement…</p></div></section>'+
 '<section class="mxh-panel mxh-activity"><div class="mxh-panel-title"><span class="mxh-panel-icon">'+icon("clock")+'</span><div><h3>Activité récente</h3><p>Les dernières opérations administratives.</p></div><button type="button" id="mxh-audit" class="mxh-more">Voir tout</button></div><div id="mxh-activity-rows" class="mxh-activity-rows"><p class="mxh-empty">Chargement…</p></div></section>'+
 '<div class="mxh-right-stack"><section class="mxh-panel mxh-quick"><div class="mxh-panel-title"><span class="mxh-panel-icon">'+icon("zap")+'</span><div><h3>Actions rapides</h3><p>Accédez aux fonctionnalités principales.</p></div></div><div class="mxh-actions">'+actions+'</div></section>'+
 '<section class="mxh-panel mxh-performance"><div class="mxh-panel-title"><span class="mxh-panel-icon">'+icon("pulse")+'</span><div><h3>Performance en direct</h3><p>Dernier relevé disponible</p></div><span class="mxh-live-badge"><i></i>Données réelles</span></div><div class="mxh-performance-cards"><div>'+icon("eye")+'<strong id="mxh-visits">—</strong><small>Visites estimées</small></div><div>'+icon("send")+'<strong id="mxh-signals">—</strong><small>Signaux LIVE</small></div><div>'+icon("chart")+'<strong id="mxh-winrate">—</strong><small>Réussite vérifiée</small></div></div></section></div></div>'+
 '<div class="mxh-update"><span id="mxh-update-state" role="status">Synchronisation…</span><button type="button" id="mxh-refresh">'+icon("refresh")+'Actualiser</button></div>'+
 '<div class="mxh-links"><a target="_blank" rel="noopener noreferrer" href="statistiques-audience.html">Audience détaillée ↗</a><a target="_blank" rel="noopener noreferrer" href="admin-supervision.html">Supervision complète ↗</a></div>'+
 '<div class="mxh-bottom"><span><i class="mxh-dot"></i><b id="mxh-bottom-health">État des services : à vérifier</b></span><span>'+icon("users")+'<b id="mxh-bottom-subs">—</b> abonnements Push</span><span>'+icon("zap")+' Taux de livraison : <b id="mxh-bottom-rate">—</b></span><span>Mr XPRONOS · Admin</span></div>'+
 '</div>';
}
const serviceStatus=(value,threshold)=>{
 const t=Date.parse(value||"");
 if(!Number.isFinite(t))return ["Non vérifié","unknown"];
 return Date.now()-t>threshold*60000?["En retard","late"]:["À jour","good"];
};
function showServices(root,data){
 const items=[
  ["globe","Collecte LIVE",data?.health?.live_scrape_last,5],
  ["layers","Fusion des données",data?.health?.live_merged_last,5],
  ["send","Signaux LIVE",data?.health?.latest_live_prediction,180],
  ["database","Actualités football",data?.health?.last_actu_foot_run,120]
 ];
 const region=get(root,"#mxh-service-rows");region.replaceChildren();let late=0,unknown=0;
 for(const [glyph,label,time,threshold] of items){
  const [status,tone]=serviceStatus(time,threshold);
  late+=tone==="late"?1:0;unknown+=tone==="unknown"?1:0;
  const row=div("mxh-service-row");
  row.innerHTML='<div class="mxh-service-name">'+icon(glyph)+'<span></span></div><span class="mxh-pill mxh-'+tone+'"><i></i><span></span></span>';
  row.querySelector(".mxh-service-name span").textContent=label;
  row.querySelector(".mxh-pill span").textContent=status;
  row.title=time?"Dernière trace : "+new Date(time).toLocaleString("fr-FR"):"Dernière trace indisponible";
  region.append(row);
 }
 set(root,"#mxh-bottom-health",late?late+" service(s) en retard":unknown?"Services partiellement non vérifiés":"Services à jour");
}
const escapeSvg=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll('"',"&quot;");
function makeGraph(root,audience,days){
 const node=get(root,"#mxh-graph");
 const daily=Array.isArray(audience?.daily)?audience.daily.filter(d=>d&&typeof d.day==="string").slice(-days):[];
 if(!daily.length){
  node.replaceChildren(div("mxh-empty","Aucune série de visiteurs disponible pour ce graphique."));
  node.setAttribute("aria-label","Série de visiteurs indisponible");
 }else{
  const values=daily.map(d=>Math.max(0,Number(d.visitors)||0));
  const topValue=Math.max(4,Math.ceil(Math.max(...values)/4)*4);
  const w=640,h=245,L=58,R=21,T=20,B=41,plotH=h-T-B,plotW=w-L-R,n=daily.length;
  const points=values.map((value,i)=>({x:L+(n===1?plotW/2:i*plotW/(n-1)),y:T+plotH-value/topValue*plotH,value}));
  const grids=Array.from({length:5},(_,i)=>{const yy=T+i*plotH/4;
   return '<line x1="'+L+'" y1="'+yy+'" x2="'+(w-R)+'" y2="'+yy+'" stroke="#3b5369" opacity=".45"/><text x="'+(L-12)+'" y="'+(yy+4)+'" font-size="12" text-anchor="end" fill="#aebcc9">'+escapeSvg(fmt(topValue*(4-i)/4))+'</text>'}).join("");
  const path=points.map((p,i)=>(i?"L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)).join(" ");
  const area=path+"L"+points.at(-1).x+" "+(T+plotH)+" L"+points[0].x+" "+(T+plotH)+"Z";
  const labels=daily.map((d,i)=>{
   if(days===30&&i%5!==0&&i!==n-1)return "";
   const date=new Date(d.day+"T12:00:00");
   const label=Number.isFinite(date.valueOf())?date.toLocaleDateString("fr-FR",days===7?{weekday:"short"}:{day:"numeric",month:"short"}):d.day.slice(5);
   return '<text x="'+points[i].x+'" y="'+(h-9)+'" text-anchor="middle" font-size="12" fill="#afbbca">'+escapeSvg(label)+'</text>';
  }).join("");
  const dots=points.map(p=>'<circle cx="'+p.x+'" cy="'+p.y+'" r="3.5" stroke="#f3b44f" stroke-width="2" fill="#fff0bb"/>').join("");
  const last=points.at(-1),bx=Math.max(L,Math.min(w-153,last.x-76)),by=Math.max(3,last.y-42);
  node.innerHTML='<svg viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><defs><linearGradient id="mxh-fill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#f7bd53" stop-opacity=".37"/><stop offset="1" stop-color="#f7bd53" stop-opacity="0"/></linearGradient></defs>'+grids+'<path d="'+area+'" fill="url(#mxh-fill)"/><path d="'+path+'" fill="none" stroke="#d9a54f" stroke-width="8" opacity=".24"/><path d="'+path+'" fill="none" stroke="#ffd277" stroke-width="3" stroke-linejoin="round"/>'+dots+labels+'<rect x="'+bx+'" y="'+by+'" width="145" height="28" rx="8" fill="#152537" stroke="#dbb26c"/><text x="'+(bx+72.5)+'" y="'+(by+18)+'" text-anchor="middle" font-size="12" fill="#f9e6bd" font-weight="700">'+escapeSvg(fmt(last.value))+' visiteurs</text></svg>';
  node.setAttribute("aria-label","Visiteurs uniques : "+daily.map(d=>d.day+" : "+fmt(d.visitors)).join("; "));
 }
 set(root,"#mxh-period-label",days+" jours");
 set(root,"#mxh-graph-source","Source : Supabase · "+days+" jours · "+daily.length+" points de mesure");
}
function showCampaigns(root,data){
 const campaigns=Array.isArray(data)?data:[];
 const active=campaigns.filter(c=>["scheduled","queued","pending","in_progress","processing","running"].includes(String(c.status||"").toLowerCase())).length;
 let successes=0,failures=0,known=false;
 for(const c of campaigns){
  const s=c.summary;if(!s||typeof s!=="object")continue;
  const ok=Number(s.sent??s.sent_count??s.delivered),ko=Number(s.failed??s.failed_count);
  if(Number.isFinite(ok)){known=true;successes+=Math.max(0,ok)}
  if(Number.isFinite(ko))failures+=Math.max(0,ko);
 }
 const rate=known&&successes+failures>0?(100*successes/(successes+failures)).toFixed(1).replace(".",",")+" %":"—";
 set(root,"#mxh-sent",known?fmt(successes):"—");
 set(root,"#mxh-rate",rate);set(root,"#mxh-bottom-rate",rate);
 set(root,"#mxh-active",fmt(active));
 set(root,"#mxh-sent-hint",known?"D'après les campagnes consultées":"Aucun bilan d’envoi disponible");
 set(root,"#mxh-rate-hint",rate==="—"?"Livraisons non renseignées":"Envois réussis / tentatives suivies");
 set(root,"#mxh-active-hint",campaigns.length?campaigns.length+" campagnes récentes":"Aucune campagne enregistrée");
}
function showActivity(root,data,readable){
 const region=get(root,"#mxh-activity-rows");region.replaceChildren();
 get(root,"#mxh-audit").hidden=!readable;
 if(!Array.isArray(data)||!data.length){region.append(div("mxh-empty",data===null?"Journal non accessible ou indisponible.":"Aucune activité enregistrée."));return}
 const names={vip_reset:"Accès VIP créé ou renouvelé",vip_revoke:"Accès VIP révoqué",cms_publish:"Contenu publié",cms_save:"Contenu enregistré",cms_restore:"Contenu restauré",push_send:"Notification envoyée",push_schedule:"Campagne programmée",admin_role_change:"Droits administrateur modifiés"};
 for(const item of data.slice(0,5)){
  const label=names[item.action]||String(item.action||"Action enregistrée").replaceAll("_"," ");
  const glyph=/vip|role/.test(item.action||"")?"users":/push/.test(item.action||"")?"send":/cms/.test(item.action||"")?"edit":"clock";
  const row=div("mxh-activity-row");
  row.innerHTML='<span class="mxh-activity-icon">'+icon(glyph)+'</span><div><strong></strong><small>Journal d’audit · activité enregistrée</small></div><time></time>';
  row.querySelector("strong").textContent=label;
  row.querySelector("time").textContent=timeLabel(item.created_at);
  region.append(row);
 }
}
async function openAction(navigate,tab,focus){
 await navigate(tab);
 const field=document.getElementById(focus);
 if(!field)return;
 if(focus==="a_title"){
  const toggle=document.querySelector("#tab-articles .admin-cms-editor-toggle");
  if(toggle&&toggle.getAttribute("aria-expanded")==="false")toggle.click();
 }
 if(focus==="subs_search")document.querySelector("#subs_list")?.closest(".card")?.scrollIntoView({behavior:"smooth",block:"start"});
 else field.scrollIntoView({behavior:"smooth",block:"center"});
 field.focus({preventScroll:true});
}
function ensureHomeShortcuts(navigate,permissions){
 const list=[
  {id:"mxh-subs-nav",group:"pilotage",label:"Abonnés",glyph:"users",field:"subs_search"},
  {id:"mxh-campaign-nav",group:"communication",label:"Campagnes",glyph:"calendar",field:"push_history"}
 ];
 for(const shortcut of list){
  if(document.getElementById(shortcut.id)||!permissions.push)continue;
  const parent=document.querySelector('.sidebar-nav .nav-group[data-group="'+shortcut.group+'"]');
  if(!parent)continue;
  const button=document.createElement("button");
  button.id=shortcut.id;button.type="button";button.className="nav-item mxh-shortcut";
  button.setAttribute("aria-label",shortcut.label);
  button.innerHTML=icon(shortcut.glyph)+"<span></span>";
  button.querySelector("span").textContent=shortcut.label;
  button.addEventListener("click",()=>void openAction(navigate,"push",shortcut.field));
  parent.append(button);
 }
}

/* Reorder real nav nodes only while Accueil is open.
 * CSS display:contents across multiple groups makes Playwright/mobile
 * hit targets overlap after switching tabs. Moving nodes retains all handlers.
 */
let homeNavRestore=null;
function setHomeNavigation(enabled){
 const nav=document.querySelector(".sidebar-nav");if(!nav)return;
 if(!enabled){
  homeNavRestore?.();
  homeNavRestore=null;
  return;
 }
 if(homeNavRestore)return;
 const selectors=[
  '[data-tab="overview"]','a[href="statistiques-audience.html"]',
  '#mxh-subs-nav','[data-tab="push"]','#mxh-campaign-nav',
  '[data-tab="pronostics"]','[data-tab="articles"]',
  '[data-tab="vip"]','[data-tab="users"]'
 ];
 const menu=document.createElement("div");menu.className="mxh-home-menu";
 menu.setAttribute("role","group");menu.setAttribute("aria-label","Navigation principale");
 const slots=[];
 const move=(selector,target)=>{
  const node=nav.querySelector(selector);
  if(!node||!node.parentNode||node.closest(".mxh-home-menu"))return;
  const placeholder=document.createComment("restore admin menu");
  node.before(placeholder);target.appendChild(node);slots.push([placeholder,node]);
 };
 for(const selector of selectors)move(selector,menu);
 const extra=[
  {title:"Contenus & publication",items:['[data-tab="conseils"]','[data-tab="bonus"]','[data-tab="infos"]','[data-tab="media"]']},
  {title:"Paramètres & outils",items:['[data-tab="health"]','[data-tab="incidents"]','[data-tab="audit"]']}
 ];
 for(const group of extra){
  const details=document.createElement("details");
  details.className="mxh-menu-details";
  const summary=document.createElement("summary");
  summary.textContent=group.title;
  details.appendChild(summary);
  const wrap=document.createElement("div");
  wrap.className="mxh-menu-children";
  for(const selector of group.items)move(selector,wrap);
  if(wrap.children.length){details.append(wrap);menu.append(details)}
 }
 nav.prepend(menu);
 homeNavRestore=()=>{
  for(const [placeholder,node] of slots)if(placeholder.isConnected)placeholder.replaceWith(node);
  menu.remove();
 };
}
let homeNavListenerBound=false;
function bindHomeNavigation(){
 if(!homeNavListenerBound){
  window.addEventListener("mx:admin-tab",e=>{
   setHomeNavigation(e.detail?.name==="overview");
  });
  homeNavListenerBound=true;
 }
 setHomeNavigation(document.getElementById("app")?.classList.contains("mx-home-active"));
}
export function mountAdminHome(root,{navigate,permissions,refresh}){
 root.innerHTML=markup();
 ensureHomeShortcuts(navigate,permissions);
 bindHomeNavigation();
 const period=get(root,"#mxh-period");
 const reload=()=>{set(root,"#mxh-period-text",period.value==="30"?"30 derniers jours":"7 derniers jours");refresh(Number(period.value))};
 period.addEventListener("change",reload);
 get(root,"#mxh-refresh").addEventListener("click",reload);
 get(root,"#mxh-audit").addEventListener("click",()=>navigate("audit"));
 for(const button of root.querySelectorAll(".mxh-action")){
  const tab=button.dataset.tabTarget,focus=button.dataset.field;
  const requirement=tab==="articles"?"cms":"push";
  if(!permissions[requirement])button.hidden=true;
  else button.addEventListener("click",()=>void openAction(navigate,tab,focus));
 }
 return {
  loading(){get(root,"#mxh-refresh").disabled=true;set(root,"#mxh-update-state","Actualisation des données…")},
  render({snapshot,audience,campaigns,activity,days,errors}){
   const push=snapshot?.push||{},live=snapshot?.live||{},analytics=snapshot?.analytics||{};
   const resolved=Number(live.wins||0)+Number(live.losses||0);
   const subscriptions=snapshot?fmt(push.subscriptions??0):"—";
   set(root,"#mxh-subs",subscriptions);
   set(root,"#mxh-bottom-subs",subscriptions);
   set(root,"#mxh-subs-hint",snapshot?"Abonnements Push enregistrés":"Source indisponible");
   set(root,"#mxh-visits",snapshot?fmt(analytics.visits??0):"—");
   set(root,"#mxh-signals",snapshot?fmt(live.total??0):"—");
   set(root,"#mxh-winrate",snapshot&&resolved?(100*Number(live.wins||0)/resolved).toFixed(1).replace(".",",")+" %":"—");
   showCampaigns(root,campaigns);showServices(root,snapshot||{});makeGraph(root,audience,days);
   showActivity(root,activity,!!permissions.read);
   period.value=String(days);
   set(root,"#mxh-period-text",days===30?"30 derniers jours":"7 derniers jours");
   set(root,"#mxh-update-state","Mis à jour à "+new Date().toLocaleTimeString("fr-FR",{hour:"2-digit",minute:"2-digit"})+(errors.length?" · Données indisponibles : "+errors.join(", "):""));
   get(root,"#mxh-refresh").disabled=false;
  },
  error(err){get(root,"#mxh-refresh").disabled=false;set(root,"#mxh-update-state","Erreur : "+String(err))}
 };
}
