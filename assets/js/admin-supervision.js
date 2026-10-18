import {supabaseUrl,supabaseAnonKey} from "./config.js";
const $=id=>document.getElementById(id);
const sb=window.supabase.createClient(supabaseUrl,supabaseAnonKey);
let channel=null, refreshTimer=null, pending=false, lastRealtime=0;
let chartRows=[], chartMode="visits";
const format=n=>Number(n||0).toLocaleString("fr-FR");
const date=s=>s?new Date(s).toLocaleString("fr-FR",{timeZone:"UTC",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"} )+" UTC":"–";
const output=(id,value)=>{if($(id))$(id).textContent=value};
const safe=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function notice(message){$("error").innerHTML=message?'<div class="notice error">'+safe(message)+'</div>':""}
function connection(status){output("socket-state",status);$("socket-dot").className="status-dot "+(status==="En direct"?"good":"bad")}
function windowStart(){
 const n=Number($("period").value);const d=new Date();
 if(n===1){d.setUTCHours(0,0,0,0)}else d.setTime(Date.now()-n*86400000);
 return d.toISOString();
}
async function query(client){
 const t=performance.now();const {data,error}=await client;
 if(error)throw error;return {data,ms:Math.round(performance.now()-t)};
}
async function aggregate(table,types,start){
 const entries=await Promise.all(types.map(async type=>{
 const {count,error}=await sb.from(table).select("id",{count:"exact",head:true}).eq("event_type",type).gte("created_at",start);
 if(error)throw error;return [type,count||0];
 }));
 return Object.fromEntries(entries);
}
async function fetchSnapshot(){
 if(pending||document.hidden)return;
 pending=true;$("refresh").disabled=true;
 const started=performance.now();
 try{
  const {data,error}=await sb.rpc("admin_monitor_snapshot",{p_days:Number($("period").value)});
  if(error)throw error;
  const x=data||{},a=x.analytics||{},l=x.live||{},t=x.telegram||{},h=x.health||{};
  chartRows=Array.isArray(x.daily)?x.daily:[];renderActivityChart();
  const show=(id,n)=>output(id,format(n));
  show("visits",a.visits);show("clicks",a.click_pronostic);
  output("analytics-audit","Événements bruts : "+format(x.analytics_raw_visits)+" visites · "+format(x.analytics_excluded_suspected_ci)+" événements de tous types exclus des périodes suspectes de tests CI. Le résultat restant est une estimation, non une preuve de visiteurs humains.");
  // "share" may mirror platform-specific shares; never sum these as independent actions.
  show("shares",a.share_generic);show("signals",l.total);
  const settled=Number(l.wins||0)+Number(l.losses||0);
  output("winrate",settled?((100*Number(l.wins||0)/settled).toFixed(1)+" %"):"–");
  show("telegram",t.total);
  show("unique",a.unique_visitors);show("pageviews",a.page_views);
  show("pushcount",x.push?.subscriptions);
  output("last-signal",format(l.pending)+" en attente · "+format(l.validated)+" validés");
  renderQuality(l);
  renderTable("crons",x.crons||[],[
   r=>safe(r.name)+" <small class='muted'>"+safe(r.origin)+"</small>",
   r=>safe(date(r.last_run)),
   r=>{const age=r.last_run?(Date.now()-Date.parse(r.last_run))/60000:Infinity;return "<span class='"+(r.ok&&age<180?"good-txt":"bad-txt")+"'>"+(r.ok?"OK":"Échec")+" · "+(Number.isFinite(age)?Math.floor(age)+" min":"?")+"</span>"}
  ]);
  renderTable("marketrows",x.live_markets||[],[r=>safe(r.name),r=>format(r.total),r=>percent(r.wins,r.losses)]);
  renderTable("tierrows",x.live_tiers||[],[r=>safe(r.name),r=>format(r.total),r=>percent(r.wins,r.losses)]);
  renderTable("prematchrows",x.prematch||[],[r=>safe(r.name),r=>format(r.total),r=>percent(r.wins,r.losses)]);
  renderTable("sourcesrows",x.attribution||[],[r=>safe(r.source),r=>format(r.views),r=>format(r.interactions)]);
  renderTable("vitalsrows",x.web_vitals||[],[
   r=>safe(r.metric)+" / "+safe(r.device),r=>format(r.sample_count),
   r=>r.metric==="CLS"?Number(r.p75).toFixed(3):format(Math.round(Number(r.p75)))+" ms"
  ]);
  const freshness=[["Scraping live",h.live_scrape_last,5],["Fusion de données",h.live_merged_last,5],["Dernier signal",h.latest_live_prediction,180],["Actualités football",h.last_actu_foot_run,120]];
  renderTable("freshrows",freshness.map(([name,at,limit])=>({name,at,limit})),[
    r=>safe(r.name),r=>safe(date(r.at)),r=>{if(!r.at)return "<span class='bad-txt'>Non disponible</span>";const age=Math.round((Date.now()-Date.parse(r.at))/60000);return "<span class='"+(age>r.limit?"bad-txt":"good-txt")+"'>"+age+" min</span>"}
  ]);
  output("freshness",h.live_merged_last?date(h.live_merged_last):"Aucune donnée");
  output("health-extra",format(h.blocked_signals)+" signaux bloqués · "+format(h.actu_foot_errors)+" erreurs actualités");
  void refreshGitHubRuns();
  void refreshClientErrors();
  output("latency",format(Math.round(performance.now()-started))+" ms");
  output("updated","Mis à jour à "+new Date().toLocaleTimeString("fr-FR",{timeZone:"UTC"})+" UTC");
  notice("");
 }catch(e){notice("Supervision indisponible : "+(e?.message||String(e)));}finally{pending=false;$("refresh").disabled=false}
}
function percent(w,l){const n=Number(w||0)+Number(l||0);return n?(100*Number(w||0)/n).toFixed(1)+" %":"–"}
function renderTable(id,rows,columns){
 const target=$(id);if(!target)return;
 target.innerHTML=rows.length?rows.map(r=>"<tr>"+columns.map(fn=>"<td>"+fn(r)+"</td>").join("")+"</tr>").join(""):"<tr><td colspan='"+columns.length+"' class='muted'>Aucune donnée disponible</td></tr>";
}
async function authenticate(){
 const {data}=await sb.auth.getUser();
 if(!data?.user)return false;
 const {data:allowed,error}=await sb.rpc("is_admin");
 return !error&&allowed===true;
}
async function establishSession(){
 const ok=await authenticate();
 $("checking").style.display="none";$("dashboard").style.display=ok?"block":"none";$("auth-form").style.display=ok?"none":"block";$("logout").hidden=!ok;
 if(ok){await startDashboard()}else stopDashboard();
}
function stopDashboard(){
 if(channel){sb.removeChannel(channel);channel=null}
 if(refreshTimer){clearInterval(refreshTimer);refreshTimer=null}
}
async function startDashboard(){
 stopDashboard();connection("Connexion en cours");
 channel=sb.channel("online-users",{config:{presence:{key:"dashboard-supervision-"+Math.random().toString(36).slice(2)}}});
 channel.on("presence",{event:"sync"},()=>{
  const states=channel.presenceState();
  output("online",format(Object.keys(states).filter(k=>!k.startsWith("dashboard-")).length));
  lastRealtime=Date.now();
 });
 channel.subscribe(status=>{
  if(status==="SUBSCRIBED"){connection("En direct");channel.track({online_at:new Date().toISOString(),admin_dashboard:true});}
  else if(["CHANNEL_ERROR","TIMED_OUT","CLOSED"].includes(status))connection("Repli 60 s");
 });
 await fetchSnapshot();
 refreshTimer=setInterval(()=>{
  if(document.hidden)return;
  void fetchSnapshot();
  if(Date.now()-lastRealtime>120000&&channel?.state!=="joined")connection("Repli 60 s");
 },60000);
}
$("period").addEventListener("change",()=>void fetchSnapshot());
$("refresh").addEventListener("click",()=>void fetchSnapshot());
$("login").addEventListener("click",async()=>{
 const btn=$("login");btn.disabled=true;output("auth-error","");
 const {error}=await sb.auth.signInWithPassword({email:$("email").value.trim(),password:$("password").value});
 btn.disabled=false;
 if(error){output("auth-error",error.message);return}
 await establishSession();
});
$("logout").addEventListener("click",async()=>{stopDashboard();await sb.auth.signOut();location.reload()});
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&$("dashboard").style.display==="block")void fetchSnapshot()});
await establishSession();

// Public GitHub Actions endpoint; read-only, cached client-side for 5 minutes.
let githubLastFetch=0;
async function refreshGitHubRuns(){
 if(!$("githubrows")||Date.now()-githubLastFetch<300000)return;
 githubLastFetch=Date.now();
 try{
  const c=new AbortController();
  const timeout=setTimeout(()=>c.abort(),7000);
  let response;
  try{
   response=await fetch("https://api.github.com/repos/MrXPRONOS/MrXPRONOS_App/actions/runs?per_page=50",{
    signal:c.signal,headers:{"Accept":"application/vnd.github+json"}
   });
  }finally{clearTimeout(timeout)}
  if(!response.ok)throw Error("GitHub API : HTTP "+response.status);
  const json=await response.json();
  const runs=(json.workflow_runs||[]).filter(r=>r.head_branch==="main");
  // Only surface probable duplicates, not definitive evidence.
  const groups=new Map();
  for(const r of runs){
   const k=r.path||r.name;
   const old=groups.get(k)||[];old.push(r);groups.set(k,old);
  }
  const suspects=[...groups.entries()].filter(([k,rs])=>
   rs.some((r,i)=>rs.some((s,j)=>i!==j && Math.abs(Date.parse(r.created_at)-Date.parse(s.created_at))<90000))
  ).map(([k])=>k);
  output("github-alerts",suspects.length?suspects.length+" workflows potentiellement lancés en double (fenêtre 90 s)":"Aucun doublon proche détecté parmi les 50 dernières exécutions");
  renderTable("githubrows",runs.slice(0,14),[
   r=>'<a target="_blank" rel="noopener noreferrer" href="'+safe(r.html_url)+'">'+safe(r.name)+'</a>',
   r=>safe(date(r.created_at)),
   r=>'<span class="'+(r.conclusion==="success"?"good-txt":r.conclusion==="failure"?"bad-txt":"muted")+'">'+safe(r.conclusion||r.status)+'</span>'
  ]);
 }catch(e){
  output("github-alerts","Impossible de vérifier les exécutions GitHub pour le moment");
  $("githubrows").innerHTML="<tr><td colspan='3' class='muted'>"+safe(e.message)+"</td></tr>";
 }
}

async function refreshClientErrors(){
 try{
  const {data,error}=await sb.rpc("admin_client_error_summary",{p_days:Number($("period").value)});
  if(error)throw error;
  output("errors-total",format(data.total));
  output("errors-detail","Script : "+format(data.script)+" · Promesses : "+format(data.promise)+" · Ressources : "+format(data.resource));
 }catch(e){output("errors-detail","Données indisponibles : "+e.message)}
}


// Accessible, lightweight activity chart: native HTML/CSS only, no heavy chart dependency.
function renderActivityChart(){
 const chart=$("traffic-chart");
 if(!chart)return;
 const kind=chartMode==="clicks"?"clicks":"visits";
 const rows=chartRows.map(r=>({day:String(r.day||""),value:Math.max(0,Number(r[kind]||0))})).filter(r=>Number.isFinite(r.value));
 const top=Math.max(1,...rows.map(r=>r.value));
 chart.innerHTML=rows.length?rows.map(r=>{
  const h=r.value?Math.max(3,(r.value/top)*96):1.5;
  const label=r.day.slice(5).replace("-","/");
  return '<div class="chart-column'+(rows.length===1?" single":"")+'" title="'+safe(r.day)+": "+format(r.value)+'" aria-label="'+safe(r.day)+": "+format(r.value)+'"><div class="chart-bar'+(kind==="clicks"?" clicks":"")+'" style="--bar-size:'+h+'%"></div><span class="chart-axis">'+safe(label)+'</span></div>';
 }).join(""):'<div class="chart-empty">Aucune donnée sur cette période</div>';
 const total=rows.reduce((sum,r)=>sum+r.value,0);
 output("chart-caption",(kind==="clicks"?"Clics":"Visites")+" sur la période : "+format(total)+" · "+rows.length+" jour(s) mesuré(s)");
 chart.setAttribute("aria-label",(kind==="clicks"?"Clics":"Visites")+" par jour ; total "+format(total));
 for(const [id,val] of [["chart-visits","visits"],["chart-clicks","clicks"]]){
  $(id)?.setAttribute("aria-pressed",String(kind===val));
 }
}
$("chart-visits")?.addEventListener("click",()=>{chartMode="visits";renderActivityChart()});
$("chart-clicks")?.addEventListener("click",()=>{chartMode="clicks";renderActivityChart()});

function renderQuality(l){
 const won=Number(l.wins||0),lost=Number(l.losses||0),total=won+lost;
 const percentValue=total?Math.max(0,Math.min(100,(won/total)*100)):0;
 const panel=$("quality");if(!panel)return;
 panel.innerHTML='<div class="quality-summary"><div><strong>'+ (total?percentValue.toFixed(1)+" %":"—")+'</strong><br><span>Réussite sur résultats validés</span></div><span>'+format(total)+' résultats</span></div>'+
 '<div class="quality-progress" role="progressbar" aria-label="Réussite" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+Math.round(percentValue)+'"><span style="width:'+percentValue+'%"></span></div>'+
 '<div class="quality-mini"><div><strong class="good-txt">'+format(won)+'</strong><small>Gagnants</small></div><div><strong class="bad-txt">'+format(lost)+'</strong><small>Perdants</small></div></div>';
}

// Interface density preference is session-only; no persistence, analytics or network side effects.
$("compact-view")?.addEventListener("click",()=>{
 const grid=document.querySelector(".metric-grid");
 if(!grid)return;
 const compact=grid.classList.toggle("is-compact");
 $("compact-view").setAttribute("aria-pressed",String(compact));
 $("compact-view").textContent=compact?"▤ Vue détaillée":"▦ Vue compacte";
});
