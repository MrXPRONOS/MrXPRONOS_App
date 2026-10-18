import {supabaseUrl,supabaseAnonKey} from "./config.js";
const $=id=>document.getElementById(id);
const sb=window.supabase.createClient(supabaseUrl,supabaseAnonKey);
let channel=null, refreshTimer=null, pending=false, lastRealtime=0;
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
 pending=true;$("refresh").disabled=true;const since=windowStart();const t=performance.now();
 try{
  // No large analytics event arrays: server-side counts only.
  const [analytics,signalCounts,telegram,crons,liveData]=await Promise.all([
   aggregate("analytics",["visit","click_pronostic","share","share_whatsapp","share_telegram"],since),
   Promise.all(["success","failure"].map(async outcome=>{
    const {count,error}=await sb.from("live_predictions").select("id",{count:"exact",head:true}).gte("created_at",since).eq("validated",true).eq("outcome",outcome);
    if(error)throw error;return count||0;
   })).then(async r=>{
    const {count,error}=await sb.from("live_predictions").select("id",{count:"exact",head:true}).gte("created_at",since);
    if(error)throw error;return {wins:r[0],losses:r[1],all:count||0};
   }),
   sb.from("telegram_sent").select("id",{count:"exact",head:true}).gte("sent_at",since),
   sb.from("cron_runs").select("name,last_run_at,last_ok").order("last_run_at",{ascending:false}).limit(20),
   sb.from("matches_live_scrape").select("updated_at").order("updated_at",{ascending:false}).limit(1)
  ]);
  for(const res of [telegram,crons,liveData])if(res.error)throw res.error;
  output("visits",format(analytics.visit));output("clicks",format(analytics.click_pronostic));
  output("shares",format(analytics.share+analytics.share_whatsapp+analytics.share_telegram));
  output("signals",format(signalCounts.all));output("telegram",format(telegram.count));
  const settled=signalCounts.wins+signalCounts.losses;
  output("winrate",settled?((100*signalCounts.wins/settled).toFixed(1)+" %"):"–");
  $("quality").innerHTML="<p>Gagnants validés : <strong>"+format(signalCounts.wins)+"</strong></p><p>Perdants validés : <strong>"+format(signalCounts.losses)+"</strong></p><p>Non classés : <strong>"+format(Math.max(0,signalCounts.all-settled))+"</strong></p>";
  $("crons").innerHTML=(crons.data||[]).map(c=>"<tr><td>"+safe(c.name)+"</td><td>"+safe(date(c.last_run_at))+"</td><td class='"+(c.last_ok?"good-txt":"bad-txt")+"'>"+(c.last_ok?"OK":"Échec")+"</td></tr>").join("")||"<tr><td colspan='3'>Aucune exécution disponible</td></tr>";
  const last=liveData.data?.[0]?.updated_at;
  if(last){const age=Math.round((Date.now()-Date.parse(last))/60000);output("freshness",date(last)+" · "+age+" min");}else output("freshness","Aucune donnée disponible");
  output("latency",format(Math.round(performance.now()-t))+" ms");output("updated","Mis à jour à "+new Date().toLocaleTimeString("fr-FR",{timeZone:"UTC"})+" UTC");
  notice("");
 }catch(e){notice("Certaines statistiques sont indisponibles : "+(e?.message||String(e)));}
 finally{pending=false;$("refresh").disabled=false}
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
