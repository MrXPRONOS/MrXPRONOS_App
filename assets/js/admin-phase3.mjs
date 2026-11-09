/* Mr XPRONOS — Administration Phase 3: supervision, audit, dialogs.
   No client-side secrets, no hidden business calls. Supabase RPC/RLS remain authoritative. */
const make=(tag,cls,text)=>{
 const e=document.createElement(tag);
 if(cls)e.className=cls;
 if(text!==undefined)e.textContent=String(text);
 return e;
};
const pad=n=>String(n).padStart(2,"0");
const FR=new Intl.NumberFormat("fr-FR");
const number=x=>FR.format(Math.max(0,Number(x)||0));
const shortTime=x=>{if(!x)return "—";const d=new Date(x);return Number.isFinite(d.valueOf())?d.toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"short"}):"—"};
const isoDay=d=>d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());
const ageMinutes=x=>{const t=Date.parse(x||"");return Number.isFinite(t)?Math.max(0,(Date.now()-t)/60000):null};
const badge=(label,tone="neutral")=>make("span","mx3-badge mx3-"+tone,label);
const safe=(text,max=1000)=>String(text??"").slice(0,max);
const host=document.createElement("div");host.className="mx3-toast-stack";host.setAttribute("aria-live","polite");
export function initAdminFeedback(){
 if(!document.body.contains(host))document.body.append(host);
}
export function adminToast(message,kind="info"){
 initAdminFeedback();
 const toast=make("div","mx3-toast mx3-"+(["success","error","warning"].includes(kind)?kind:"info"));
 toast.setAttribute("role",kind==="error"?"alert":"status");
 const text=make("span","mx3-toast-text",message);
 const close=make("button","mx3-toast-close","×");close.type="button";
 close.setAttribute("aria-label","Fermer le message");close.addEventListener("click",()=>toast.remove());
 toast.append(text,close);host.append(toast);
 while(host.children.length>4)host.firstElementChild.remove();
 setTimeout(()=>toast.remove(),kind==="error"?10000:5500);
}
function decisionDialog({message,title="Confirmation",kind="confirm",phrase="",danger=false}){
 return new Promise(resolve=>{
  initAdminFeedback();
  const before=document.activeElement;
  const overlay=make("div","mx3-dialog-backdrop");
  const dialog=make("section","mx3-dialog");
  dialog.setAttribute("role","dialog");dialog.setAttribute("aria-modal","true");
  dialog.setAttribute("aria-label",title);
  const icon=make("span","mx3-dialog-icon",danger?"!":"✓");
  const heading=make("h2","mx3-dialog-title",title);
  const content=make("p","mx3-dialog-message",message);
  const actions=make("div","mx3-dialog-actions");
  const cancel=make("button","mx3-dialog-cancel","Annuler");
  const yes=make("button","mx3-dialog-accept",kind==="notice"?"Fermer":danger?"Confirmer l'action":"Confirmer");
  cancel.type=yes.type="button";yes.dataset.adminDialogConfirm="true";
  let input=null;
  if(kind==="prompt"||phrase){
   const label=make("label","mx3-dialog-label",phrase?"Saisis exactement « "+phrase+" » pour confirmer":"Saisis la confirmation");
   input=make("input","mx3-dialog-input");
   input.type="text";input.autocomplete="off";input.setAttribute("aria-label",label.textContent);
   label.append(input);dialog.append(icon,heading,content,label);
   if(phrase){yes.disabled=true;input.addEventListener("input",()=>{yes.disabled=input.value!==phrase})}
  }else dialog.append(icon,heading,content);
  if(kind==="notice")cancel.hidden=true;
  actions.append(cancel,yes);dialog.append(actions);overlay.append(dialog);
  const finish=value=>{document.removeEventListener("keydown",key);overlay.remove();
   if(before?.isConnected)before.focus();resolve(value)};
  cancel.addEventListener("click",()=>finish(kind==="prompt"?null:false));
  yes.addEventListener("click",()=>finish(kind==="prompt"?(input?.value||""):true));
  overlay.addEventListener("click",event=>{if(event.target===overlay)finish(kind==="prompt"?null:false)});
  const key=event=>{
   if(!overlay.isConnected)return;
   if(event.key==="Escape"){event.preventDefault();finish(kind==="prompt"?null:false);return}
   if(event.key!=="Tab")return;
   const items=[...dialog.querySelectorAll('button:not([disabled]):not([hidden]),input:not([disabled])')];
   if(!items.length)return;
   const start=items[0],end=items[items.length-1];
   if(event.shiftKey&&document.activeElement===start){event.preventDefault();end.focus()}
   else if(!event.shiftKey&&document.activeElement===end){event.preventDefault();start.focus()}
  };
  document.addEventListener("keydown",key);
  document.body.append(overlay);
  (input||(cancel.hidden?yes:cancel)).focus();
 });
}
export function adminConfirm(message,options={}){return decisionDialog({message,title:options.title||"Confirmer l'action",kind:"confirm",danger:!!options.danger,phrase:options.phrase||""})}
export function adminPrompt(message){return decisionDialog({message,title:"Confirmation explicite",kind:"prompt",danger:true})}
export function adminNotice(message,title="Information"){return decisionDialog({message,title,kind:"notice"})}

/** Overview uses the existing real snapshot and the separate real daily-visitors chart.
 * Never convert incomparable visitor counts to one combined percentage. */
export function enhanceAdminOverview(root,snapshot){
 if(!root)return;
 let strip=root.querySelector(".mx3-service-overview");
 if(!strip){strip=make("section","mx3-service-overview");strip.setAttribute("aria-label","État des services");const health=root.querySelector(".admin-overview-health");health?.after(strip)}
 const services=[
  ["Récupération LIVE",snapshot?.health?.live_scrape_last,5],
  ["Fusion LIVE",snapshot?.health?.live_merged_last,5],
  ["Signaux LIVE",snapshot?.health?.latest_live_prediction,180],
  ["Actualités",snapshot?.health?.last_actu_foot_run,120]
 ];
 const items=make("div","mx3-service-items");
 let alerts=0;
 for(const [label,last,maxMinutes] of services){
  const mins=ageMinutes(last),isUnknown=mins===null,late=mins!==null&&mins>maxMinutes;
  if(late)alerts++;
  const state=isUnknown?"Inconnu":late?"En retard":"À jour";
  const tone=isUnknown?"neutral":late?"warning":"success";
  const block=make("div","mx3-service-item");
  const left=make("div","mx3-service-title");
  left.append(make("strong","",label),make("small","",last?"Dernière trace : "+shortTime(last):"Aucune trace disponible"));
  block.append(left,badge(state,tone));items.append(block);
 }
 const heading=make("h3","mx3-panel-title","Surveillance de la production");
 const note=make("p","mx3-panel-note",alerts?alerts+" service(s) présentent un retard selon leur seuil de fraîcheur.":"États basés sur les dernières traces reçues. Une absence d'activité ne prouve pas une panne.");
 strip.replaceChildren(heading,note,items);
}
const cronState=item=>{
 if(item.last_ok===false)return "error";
 const ago=ageMinutes(item.last_run_at),expected=Number(item.meta?.expected_interval_minutes||0);
 if(item.last_ok===true&&ago!==null&&expected>0&&ago>expected*2)return "warning";
 if(item.last_ok===true)return "success";
 return "unknown";
};
const ghState=item=>{
 if(["failure","timed_out","startup_failure"].includes(item.conclusion))return "error";
 if(["cancelled","skipped","neutral","action_required","stale"].includes(item.conclusion))return "warning";
 if(item.conclusion==="success")return "success";
 if(item.status==="queued"||item.status==="in_progress"||item.status==="waiting")return "progress";
 return "unknown";
};
const friendly={success:"Réussie",error:"Échec",warning:"Attention",progress:"En cours",unknown:"Non vérifié"};
const mkStat=(label,value,tone)=>{
 const el=make("div","mx3-stat");
 el.append(make("span","mx3-stat-label",label),make("strong","mx3-stat-number "+(tone?"mx3-tone-"+tone:""),number(value)));
 return el;
};
export function enhanceHealthDashboard(root,{cron=[],runs=null,ghError=null}={}){
 if(!root)return;
 let panel=root.querySelector(".mx3-health-dashboard");
 const base=root.querySelector(":scope > .card");
 if(!base)return;
 if(!panel){panel=make("section","card mx3-health-dashboard");root.prepend(panel)}
 const stateCounts={success:0,error:0,warning:0,progress:0,unknown:0};
 const cronData=(Array.isArray(cron)?cron:[]).map(x=>({name:x.name,kind:"Supabase",state:cronState(x),time:x.last_run_at}));
 const latestGithub=new Map();
 for(const run of (Array.isArray(runs)?runs:[])){
  const name=String(run?.name||"Workflow sans nom");
  if(!latestGithub.has(name) || Date.parse(run.created_at||"")>Date.parse(latestGithub.get(name).created_at||""))
   latestGithub.set(name,run);
 }
 const githubData=[...latestGithub.values()].map(x=>({name:x.name,kind:"GitHub Actions",state:ghState(x),time:x.created_at}));
 const data=[...cronData,...githubData];
 for(const entry of data)stateCounts[entry.state]++;
 const head=make("div","mx3-heading");
 head.append(make("h3","","État des automatisations"),make("span","mx3-subtitle","Dernier état observé · "+new Date().toLocaleString("fr-FR")));
 const stats=make("div","mx3-stats");
 stats.append(
  mkStat("Réussies",stateCounts.success,"success"),
  mkStat("En échec",stateCounts.error,"error"),
  mkStat("En retard / attention",stateCounts.warning,"warning"),
  mkStat("En cours",stateCounts.progress),
  mkStat("Inconnues",stateCounts.unknown)
 );
 const bar=make("div","mx3-health-bar");
 const denom=Math.max(1,data.length);
 for(const tone of ["success","error","warning","progress","unknown"]){
  const chunk=make("div","mx3-segment mx3-segment-"+tone);
  chunk.style.width=stateCounts[tone]/denom*100+"%";
  chunk.title=friendly[tone]+": "+stateCounts[tone];
  if(!stateCounts[tone])chunk.hidden=true;
  bar.append(chunk);
 }
 bar.setAttribute("role","img");bar.setAttribute("aria-label","Répartition des états des "+data.length+" exécutions ou tâches observées");
 const filterArea=make("div","mx3-health-filters");
 const query=make("input");query.type="search";query.placeholder="Rechercher un workflow ou une tâche";query.setAttribute("aria-label","Rechercher une automatisation");
 const dropdown=make("select");dropdown.setAttribute("aria-label","Filtrer par état");
 for(const [id,name] of [["all","Tous les états"],["error","Échecs"],["warning","Retards / attention"],["success","Réussies"],["progress","En cours"],["unknown","Non vérifiés"]]){
  const option=make("option","",name);option.value=id;dropdown.append(option);
 }
 const list=make("div","mx3-automation-list");
 const note=make("p","mx3-panel-note");
 const draw=()=>{
  list.replaceChildren();const q=query.value.trim().toLocaleLowerCase("fr");
  const filtered=data.filter(x=>(dropdown.value==="all"||x.state===dropdown.value)
   &&(x.name||"").toLocaleLowerCase("fr").includes(q));
  for(const entry of filtered.slice(0,50)){
   const row=make("div","mx3-automation");
   const name=make("div","mx3-automation-name");
   name.append(make("strong","",entry.name||"Sans nom"),make("small","",entry.kind+" · "+(entry.time?shortTime(entry.time):"Date inconnue")));
   row.append(name,badge(friendly[entry.state],entry.state==="error"?"error":entry.state==="warning"?"warning":entry.state==="success"?"success":"neutral"));
   list.append(row);
  }
  if(!filtered.length)list.append(make("p","mx3-empty","Aucune automatisation dans cette sélection."));
  const warns=[];
  if(!Array.isArray(runs))warns.push(ghError?"Source GitHub indisponible : "+safe(ghError,120):"GitHub Actions : données non chargées");
  note.textContent=filtered.length+" résultat(s) parmi "+data.length+" traces chargées · affichage limité à 50."+(warns.length?" "+warns.join(" · "):"")
   +" Les exécutions GitHub correspondent à un échantillon, pas à tout l'historique.";
 };
 query.addEventListener("input",draw);dropdown.addEventListener("change",draw);
 filterArea.append(query,dropdown);
 panel.replaceChildren(head,stats,bar,filterArea,list,note);draw();
}
function createBars(series,aria){
 const root=make("div","mx3-mini-chart");root.setAttribute("role","img");root.setAttribute("aria-label",aria);
 const highest=Math.max(1,...series.map(s=>s.total));
 for(const item of series){
  const group=make("div","mx3-mini-chart-group");
  const value=make("span","mx3-mini-chart-value",item.total?number(item.total):"0");
  const column=make("div","mx3-mini-chart-bar");
  column.style.height=Math.max(3,Math.round(item.total/highest*88))+"px";
  column.title=item.label+": "+number(item.total);
  group.append(value,column,make("small","",item.label));root.append(group);
 }
 return root;
}
export async function renderAuditWorkbench(sb,root){
 if(!root)return;
 root.replaceChildren();
 const panel=make("section","card mx3-audit-workbench");
 const head=make("div","admin-section-heading");
 const title=make("h3","","Journal d’audit");
 const reload=make("button","btn btn-secondary","↻ Actualiser");
 reload.type="button";
 const csv=make("button","btn btn-secondary","Exporter le filtre en CSV");
 csv.type="button";
 const controls=make("div","mx3-audit-actions");
 controls.append(reload,csv);head.append(title,controls);
 const intro=make("p","mx3-panel-note","Historique des opérations administratives · chaque détail est consultable sans afficher toutes les données techniques d’un coup.");
 const stats=make("div","mx3-stats");
 const timeline=make("section","mx3-audit-timeline");
 const filters=make("div","mx3-audit-filters");
 const search=make("input");search.type="search";search.placeholder="Action, identifiant ou détail…";search.setAttribute("aria-label","Rechercher dans le journal");
 const kind=make("select");kind.setAttribute("aria-label","Type d’action");
 const date=make("select");date.setAttribute("aria-label","Période");
 for(const [val,label] of [["all","Toutes les dates chargées"],["1","Dernières 24 h"],["7","7 jours"],["30","30 jours"],["90","90 jours"]]){
  const option=make("option","",label);option.value=val;date.append(option);
 }
 const state=make("p","mx3-panel-note");state.setAttribute("role","status");state.setAttribute("aria-live","polite");
 const viewport=make("div","admin-pronostics-table-scroll");
 const table=make("table","mx2-responsive-table mx3-audit-table");
 const headers=["Date","Administrateur","Action","Détails"];
 const thead=make("thead"),tr=make("tr");
 for(const h of headers)tr.append(make("th","",h));
 thead.append(tr);
 const tbody=make("tbody");table.append(thead,tbody);viewport.append(table);
 const more=make("button","btn btn-secondary","Charger 100 événements supplémentaires");
 more.type="button";
 filters.append(search,kind,date);panel.append(head,intro,stats,timeline,filters,state,viewport,more);root.append(panel);
 let rows=[],offset=0,done=false,busy=false;
 const render=()=>{
  const old=kind.value||"all";
  const allActions=[...new Set(rows.map(x=>String(x.action||"").trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"fr"));
  kind.replaceChildren();
  const all=make("option","","Toutes les actions");all.value="all";kind.append(all);
  for(const action of allActions){const op=make("option","",action);op.value=action;kind.append(op)}
  kind.value=allActions.includes(old)?old:"all";
  const q=search.value.trim().toLocaleLowerCase("fr"),now=Date.now(),period=Number(date.value);
  const shown=rows.filter(row=>{
   const ts=Date.parse(row.created_at||"");
   return (!q||[row.action,row.actor_user_id,JSON.stringify(row.details||{})].some(x=>String(x||"").toLocaleLowerCase("fr").includes(q)))
    &&(kind.value==="all"||row.action===kind.value)
    &&(date.value==="all"||(Number.isFinite(ts)&&ts>=now-period*86400000));
  });
  tbody.replaceChildren();
  for(const row of shown){
   const tr=make("tr");
   const cell=(val,label)=>{const td=make("td","",val);td.dataset.label=label;tr.append(td);return td};
   cell(shortTime(row.created_at),"Date");
   cell(row.actor_user_id||"Système","Administrateur");
   const action=cell("","Action");
   action.append(badge(row.action||"Action",/error|fail|revoke|delete/i.test(row.action||"")?"warning":"neutral"));
   const details=cell("","Détails");
   const reveal=make("details","mx3-audit-details");
   const summary=make("summary","","Voir les détails");
   const pre=make("pre","",JSON.stringify(row.details||{},null,2));
   reveal.append(summary,pre);details.append(reveal);tbody.append(tr);
  }
  if(!shown.length){const row=make("tr");const cell=make("td","mx3-empty","Aucun événement pour ce filtre.");cell.colSpan=4;row.append(cell);tbody.append(row)}
  const unique=new Set(shown.map(x=>x.actor_user_id||"system"));
  const lastDay=shown.filter(x=>ageMinutes(x.created_at)!==null&&ageMinutes(x.created_at)<=1440).length;
  stats.replaceChildren(mkStat("Événements affichés",shown.length),mkStat("Administrateurs distincts",unique.size),mkStat("Dernières 24 h",lastDay));
  const series=[];for(let i=6;i>=0;i--){
   const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-i);
   const day=isoDay(d);
   series.push({label:pad(d.getDate())+"/"+pad(d.getMonth()+1),total:shown.filter(x=>x.created_at&&isoDay(new Date(x.created_at))===day).length});
  }
  const caption=make("p","mx3-panel-note","Événements par jour · 7 derniers jours parmi les entrées chargées (historique partiel).");
  timeline.replaceChildren(caption,createBars(series,"Répartition des événements d’audit par jour sur les sept derniers jours."));
  state.textContent=shown.length+" événement(s) affiché(s) parmi "+rows.length+" chargé(s). "+(done?"Fin des résultats.":"Charger la suite pour consulter l’historique plus ancien.");
  more.hidden=done;csv.disabled=!shown.length;
  return shown;
 };
 const load=async(reset=false)=>{
  if(busy)return;
  if(reset){rows=[];offset=0;done=false}
  if(done)return;
  busy=true;more.disabled=true;reload.disabled=true;
  state.textContent="Chargement de l’historique…";
  try{
   const {data,error}=await sb.from("audit_log").select("created_at,action,details,actor_user_id")
    .order("created_at",{ascending:false}).range(offset,offset+99);
   if(error)throw error;
   rows.push(...data||[]);offset+=(data||[]).length;done=(data||[]).length<100;
   render();
  }catch(err){state.textContent="Impossible de lire l’historique : "+safe(err?.message||err);
   adminToast(state.textContent,"error");
  }finally{busy=false;more.disabled=false;reload.disabled=false}
 };
 for(const input of [search,kind,date])input.addEventListener(input.tagName==="INPUT"?"input":"change",render);
 more.addEventListener("click",()=>void load());
 reload.addEventListener("click",()=>void load(true));
 csv.addEventListener("click",()=>{
  const records=render();if(!records.length)return;
  const escapeCsv=x=>{
   let val=String(x??"");if(/^[\s]*[=+\-@]/.test(val))val="'"+val;
   return '"'+val.replaceAll('"','""')+'"';
  };
  const lines=[["Date","Administrateur","Action","Détails"].map(escapeCsv).join(","),
   ...records.map(r=>[r.created_at,r.actor_user_id,r.action,JSON.stringify(r.details||{})].map(escapeCsv).join(","))];
  const blob=new Blob(["\ufeff"+lines.join("\r\n")],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob);const a=make("a");
  a.href=url;a.download="mrxpronos-audit-"+isoDay(new Date())+".csv";
  a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
  adminToast(records.length+" événement(s) exporté(s) avec les filtres actifs.","success");
 });
 await load();
}
