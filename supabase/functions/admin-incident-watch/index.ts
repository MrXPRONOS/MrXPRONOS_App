// Cron/GitHub/Push health watchdog. Runs only from the signed workflow on main.
// Creates actionable incidents, resolves observed recoveries, escalates recurring issues.
import {createClient} from "https://esm.sh/@supabase/supabase-js@2";
import {createRemoteJWKSet,jwtVerify} from "https://esm.sh/jose@5.9.6";
const jwks=createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));
const idPath="MrXPRONOS/MrXPRONOS_App/.github/workflows/admin-incident-watch.yml@refs/heads/main";
const fallbackOrigin="https://mrxpronos.github.io";
const send=(data:unknown,status=200)=>new Response(JSON.stringify(data),{
 status,headers:{"Content-Type":"application/json","Cache-Control":"no-store",
 "Access-Control-Allow-Origin":fallbackOrigin}});
type Observation={key:string;source:string;summary:string;severity:"low"|"medium"|"high";
  evidence:string;action:string;detail?:Record<string,unknown>;repeated?:number};
const ageMin=(stamp:unknown)=>{const n=Date.parse(String(stamp||""));return Number.isFinite(n)?(Date.now()-n)/60000:null;};
const safeName=(v:unknown)=>String(v||"").replace(/[\r\n<>]/g,"").slice(0,120);
const statusOf=(r:any)=>String(r?.conclusion||r?.status||"");
const sanitizeRun=(r:any)=>({
 id:Number(r?.id||0),name:safeName(r?.name),path:safeName(r?.path),
 event:safeName(r?.event),head_sha:safeName(r?.head_sha),
 created_at:String(r?.created_at||""),status:String(r?.status||""),
 conclusion:String(r?.conclusion||""),run_attempt:Number(r?.run_attempt||1),
 html_url:/^https:\/\/github\.com\/MrXPRONOS\/MrXPRONOS_App\/actions\/runs\/\d+$/.test(String(r?.html_url||""))
   ?r.html_url:null
});
const identicalSchedule=(job:any)=>JSON.stringify({
 endpoint_fingerprint:job.endpoint_fingerprint||job.endpoint,
 h:job.schedule?.hours,m:job.schedule?.minutes,
 w:job.schedule?.wdays,tz:job.schedule?.timezone
});
function workflowHint(raw:string){
 try{
  const url=new URL(raw);
  if(url.hostname.toLowerCase()!=="api.github.com")return null;
  const match=url.pathname.match(/^\/repos\/MrXPRONOS\/MrXPRONOS_App\/actions\/workflows\/([\w.-]+)\/dispatches\/?$/);
  return match?match[1]:null;
 }catch{return null;}
}
async function targetFingerprint(raw:string,secret:string){
 const enc=new TextEncoder();
 const key=await crypto.subtle.importKey("raw",enc.encode(secret),
  {name:"HMAC",hash:"SHA-256"},false,["sign"]);
 const bytes=await crypto.subtle.sign("HMAC",key,enc.encode(raw));
 return Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,"0")).join("");
}
Deno.serve(async req=>{
 if(req.method!=="POST")return send({error:"POST only"},405);
 const bearer=req.headers.get("authorization")||"";
 try{
  if(!bearer.toLowerCase().startsWith("bearer "))return send({error:"Workflow JWT required"},401);
  const {payload}=await jwtVerify(bearer.slice(7),jwks,{
   issuer:"https://token.actions.githubusercontent.com",audience:"mrxpronos-admin-watch"
  });
  if(payload.repository!=="MrXPRONOS/MrXPRONOS_App" ||
     payload.ref!=="refs/heads/main" ||
     payload.workflow_ref!==idPath ||
     !["schedule","workflow_dispatch"].includes(String(payload.event_name||"")))
    return send({error:"Workflow identity denied"},403);
 }catch{return send({error:"Unverified GitHub workflow"},403)}
 const url=Deno.env.get("SUPABASE_URL")||"",
       key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
 if(!url||!key)return send({error:"Backend unavailable"},500);
 const sb=createClient(url,key);
 let body:any={};
 try{body=await req.json()}catch{return send({error:"Invalid JSON"},400)}
 const runs=(Array.isArray(body?.runs)?body.runs:[]).slice(0,120).map(sanitizeRun)
  .filter((x:any)=>x.id>0&&x.name&&Date.parse(x.created_at));
 const now=new Date().toISOString();
 const observations:Observation[]=[];const recovered=new Set<string>();
 const sourceFlags:Record<string,string>={github:runs.length?"ok":"no_runs"};
 // GitHub: only warn when the most recent TWO finished executions of a
 // workflow failed, not simply because two jobs ran near each other.
 const groups=new Map<string,typeof runs>();
 for(const run of runs){
  const key=run.path||run.name;
  if(!groups.has(key))groups.set(key,[]);
  groups.get(key)!.push(run);
 }
 for(const [name,entries] of groups){
  // Never let this monitor treat its own alert-triggered failed run as a new
  // incident; otherwise it could create an infinite escalation feedback loop.
  if(name.includes("admin-incident-watch.yml")||entries.some((r:any)=>r.name==="Admin incidents — automatic monitoring"))continue;
  const recent=entries.filter((x:any)=>x.status==="completed").sort(
    (a:any,b:any)=>Date.parse(b.created_at)-Date.parse(a.created_at));
  if(!recent.length)continue;
  const issueKey="github:"+name.slice(0,160);
  if(recent[0].conclusion==="success"){recovered.add(issueKey);continue;}
  if(recent.length>=2&&recent[0].conclusion==="failure"&&recent[1].conclusion==="failure"){
   observations.push({key:issueKey,source:"cron",severity:"high",
    summary:"GitHub : échecs répétés de "+recent[0].name,evidence:String(recent[0].id),
    repeated:2,action:"Ouvrir les dernières exécutions GitHub et corriger le workflow avant toute relance.",
    detail:{provider:"GitHub Actions",last_run:recent[0].created_at,
      latest_run_url:recent[0].html_url,previous_run_id:recent[1].id}});
  }
 }
 // Duplicate launches require matching workflow, event and SHA. Never claim
 // certainty when external cron-job.org execution cannot be correlated.
 for(const [name,entries] of groups){
  if(name.includes("admin-incident-watch.yml")||entries.some((r:any)=>r.name==="Admin incidents — automatic monitoring"))continue;
  for(let i=0;i<entries.length;i++)for(let j=i+1;j<entries.length;j++){
   const a=entries[i],b=entries[j];
   if(a.id===b.id||a.event!==b.event||a.head_sha!==b.head_sha||
     a.run_attempt!==b.run_attempt||Math.abs(Date.parse(a.created_at)-Date.parse(b.created_at))>90000)
    continue;
   const ids=[a.id,b.id].sort((x,y)=>x-y);
   observations.push({key:"github-duplicate:"+ids.join("-"),source:"cron",
    severity:"medium",summary:"Déclenchements GitHub rapprochés : "+a.name,
    evidence:ids.join("-"),action:"Comparer les deux exécutions et leur déclencheur avant de désactiver une tâche.",
    detail:{provider:"GitHub Actions",workflow:name,run_ids:ids,certainty:"possible"}});
  }
 }
 const [
  {data:crons,error:cronsError},
  {data:failedPush,error:pushError},
  {data:cronSnapshot,error:cronError}
 ]=await Promise.all([
  sb.from("cron_runs").select("name,last_run_at,last_ok,meta").limit(200),
  sb.from("admin_push_campaigns").select("id,status,error,completed_at,summary")
   .in("status",["failed","sent"])
   .gte("completed_at",new Date(Date.now()-24*3600000).toISOString()).limit(200),
  sb.from("admin_cron_snapshot").select("status,jobs,fetched_at").eq("id",1).maybeSingle()
 ]);
 if(cronsError||pushError||cronError)return send({
  error:"Watchdog database read failed"},503);
 sourceFlags.supabase="ok";
 let cronObserved=cronSnapshot;
 const apiKey=Deno.env.get("CRON_JOB_ORG_API_KEY")||"";
 if(apiKey&&(!cronObserved?.fetched_at||(ageMin(cronObserved.fetched_at)??Infinity)>=30)){
  const ctl=new AbortController();const timer=setTimeout(()=>ctl.abort(),9000);
  try{
   const res=await fetch("https://api.cron-job.org/jobs",{
    method:"GET",signal:ctl.signal,
    headers:{"Authorization":"Bearer "+apiKey,"Accept":"application/json"}
   });
   if(!res.ok)throw Error("API HTTP "+res.status);
   const provider=await res.json();
   const cleaned=(await Promise.all((Array.isArray(provider.jobs)?provider.jobs:[])
    .map(async(job:any)=>{
     const raw=String(job.url||"");
     let endpoint="inconnu";
     try{endpoint=new URL(raw).hostname.toLowerCase();}catch{}
     return {id:Number(job.jobId),title:safeName(job.title),enabled:job.enabled===true,
      endpoint,endpoint_fingerprint:await targetFingerprint(raw,apiKey),
      workflow_hint:workflowHint(raw),
      last_status:Number(job.lastStatus||0),
      last_execution:Number(job.lastExecution||0),next_execution:Number(job.nextExecution||0),
      schedule:{timezone:String(job.schedule?.timezone||"UTC"),
       hours:Array.isArray(job.schedule?.hours)?job.schedule.hours.slice(0,24):[],
       minutes:Array.isArray(job.schedule?.minutes)?job.schedule.minutes.slice(0,60):[],
       wdays:Array.isArray(job.schedule?.wdays)?job.schedule.wdays.slice(0,7):[]}};
    }))).filter((j:any)=>Number.isSafeInteger(j.id)&&j.id>0);
   await sb.from("admin_cron_snapshot").upsert({
    id:1,status:"ok",fetched_at:now,jobs:cleaned,last_error:null,updated_at:now
   },{onConflict:"id"});
   cronObserved={status:"ok",fetched_at:now,jobs:cleaned};
  }catch(error){
   sourceFlags.cron_job_org="fetch_error";
  }finally{clearTimeout(timer)}
 }
 if(!apiKey)sourceFlags.cron_job_org="not_configured";
 for(const entry of crons||[]){
  const key="cron-run:"+safeName(entry.name);
  const stamp=entry.last_run_at,minutes=ageMin(stamp);
  const expected=Number(entry.meta?.expected_interval_minutes||0);
  if(entry.last_ok===false && minutes!=null && minutes<1440)
   observations.push({key,source:"cron",severity:"high",
    summary:"Dernière exécution échouée : "+safeName(entry.name),evidence:String(stamp),
    action:"Consulter les journaux de la tâche et sa dernière exécution.",
    detail:{provider:"Supabase cron_runs",last_run:stamp}});
  else if(expected>0&&minutes!=null&&minutes>Math.max(expected*2,15))
   observations.push({key,source:"cron",severity:"medium",
    summary:"Tâche en retard : "+safeName(entry.name),evidence:Math.floor(minutes/Math.max(expected,30)).toString(),
    action:"Vérifier l'activation du cron et la dernière exécution réelle.",
    detail:{provider:"Supabase cron_runs",last_run:stamp,expected_interval_minutes:expected}});
  else if(entry.last_ok===true)recovered.add(key);
 }
 for(const entry of failedPush||[]){
  const errors=Number(entry.summary?.failed||0);
  if(entry.status!=="failed"&&errors<=0)continue;
  observations.push({key:"push:"+entry.id,source:"push",
   severity:entry.status==="failed"?"medium":"low",
   summary:entry.status==="failed"?"Campagne Push en échec":"Campagne Push : erreurs partielles d'appareils",
   evidence:String(entry.id)+"|"+errors,
   action:"Examiner les erreurs par appareil ; ne pas renvoyer si la livraison est incertaine.",
   detail:{campaign_id:entry.id,provider:"Supabase Push",device_failures:errors}});
 }
 if(apiKey&&cronObserved?.status==="ok"&&Array.isArray(cronObserved.jobs)&&
    (ageMin(cronObserved.fetched_at)??Infinity)<180){
  sourceFlags.cron_job_org="ok";
  const jobGroups=new Map();
  for(const job of cronObserved.jobs){
   if(!job.enabled)continue;
   const key="cron-job-org:"+String(job.id);
   if(job.last_status===1){recovered.add(key);}
   else if(job.last_status>=2&&job.last_status<=9)
    observations.push({key,source:"cron",severity:"medium",
      summary:"cron-job.org en échec : "+safeName(job.title),
      evidence:String(job.last_execution),action:"Vérifier le statut HTTP et l'historique de cette tâche.",
      detail:{provider:"cron-job.org",job_id:job.id,last_execution:job.last_execution,
        last_status:job.last_status}});
   const fingerprint=identicalSchedule(job);
   if(!jobGroups.has(fingerprint))jobGroups.set(fingerprint,[]);
   jobGroups.get(fingerprint).push(job);
  }
  // Cross-provider correlation: known cron-job.org dispatch endpoints
  // targeting a specific GitHub Actions workflow, plus >=2 runs around the
  // same cron execution with different trigger origins. This is probabilistic,
  // never auto-disable tasks based on it.
  for(const job of cronObserved.jobs){
   if(!job.enabled||!job.workflow_hint||!Number(job.last_execution))continue;
   const runsNear=runs.filter((run:any)=>{
    const basename=String(run.path||"").split("/").at(-1);
    return basename===job.workflow_hint &&
      Math.abs(Date.parse(run.created_at)-Number(job.last_execution)*1000)<180000;
   });
   const sources=new Set(runsNear.map((r:any)=>r.event));
   if(runsNear.length>=2 && sources.size>=2){
    const ids=runsNear.map((r:any)=>r.id).sort((a:number,b:number)=>a-b);
    observations.push({
     key:"cross-provider:"+job.id+":"+ids.join("-"),source:"cron",severity:"medium",
     summary:"cron-job.org + GitHub : double déclenchement possible",
     evidence:ids.join("-"),
     action:"Comparer l'horaire du cron externe, le schedule GitHub et les journaux ; désactiver uniquement le déclencheur réellement redondant.",
     detail:{provider:"cron-job.org / GitHub Actions",job_id:job.id,
      workflow_hint:job.workflow_hint,run_ids:ids,certainty:"possible_not_proven"}
    });
   }
  }
  for(const jobs of jobGroups.values()){
   if(jobs.length<2)continue;
   const ids=jobs.map((x:any)=>x.id).sort((a:number,b:number)=>a-b);
   observations.push({key:"cron-config:"+ids.join("-"),source:"cron",
    severity:"medium",summary:"Configuration cron-job.org identique",
    evidence:ids.join("-"),action:"Vérifier si les tâches sont volontairement redondantes.",
    detail:{provider:"cron-job.org",job_ids:ids,certainty:"configuration_same_not_proven_duplicate"}});
  }
 }else{sourceFlags.cron_job_org=sourceFlags.cron_job_org||
    cronObserved?.status||"not_connected";}
 let escalations=0,changes=0;
 for(const observation of observations.slice(0,100)){
  const {data:prior,error:readError}=await sb.from("admin_incidents")
    .select("id,status,detail,failure_count,escalation_level,detected_at")
    .eq("external_key",observation.key).maybeSingle();
  if(readError)continue;
  const changed=prior?.detail?.observation_id!==observation.evidence;
  const reopened=prior?.status==="resolved"&&changed;
  const repeat=prior&&!reopened
    ? (changed?Math.max(prior.failure_count||0,observation.repeated||1)+1:prior.failure_count||1)
    : (observation.repeated||1);
  const level=(repeat>=2&&observation.severity==="high")?1:prior?.escalation_level||0;
  const escalated=level>0&&!(prior?.escalation_level>0);
  const row={external_key:observation.key,source:observation.source,
   summary:observation.summary,severity:repeat>=2?"high":observation.severity,
   status:!prior||reopened?"open":prior.status,
   detail:{...(observation.detail||{}),observation_id:observation.evidence,
     action:observation.action},
   last_seen_at:now,detected_at:!prior||reopened?now:prior.detected_at,
   failure_count:repeat,escalation_level:level,
   ...(escalated?{escalated_at:now}:{}),
   updated_at:now};
  const {error:writeError}=await sb.from("admin_incidents").upsert(
    {...row,...(prior?.id?{id:prior.id}:{})},{onConflict:"external_key"});
  if(!writeError){changes++;if(escalated)escalations++;}
 }
 // Resolve only when healthy evidence for the same source is observed.
 for(const key of recovered){
  const {data:prior}=await sb.from("admin_incidents").select("id,status")
    .eq("external_key",key).maybeSingle();
  if(prior?.id&&prior.status!=="resolved")
   await sb.from("admin_incidents").update({status:"resolved",resolved_at:now,updated_at:now})
    .eq("id",prior.id).neq("status","resolved");
 }
 const {error:stateError}=await sb.from("admin_monitor_state").upsert({
  id:1,last_scan_at:now,last_result:escalations?"degraded":"ok",
  findings:observations.length,escalations,sources:sourceFlags,updated_at:now
 },{onConflict:"id"});
 if(stateError)return send({error:"Failed to record watchdog status"},503);
 // GitHub action fails on true high severity escalations to trigger standard
 // Actions failure notifications if the repository owner has enabled them.
 return send({success:true,observations:observations.length,changes,escalations,
  degraded_sources:Object.entries(sourceFlags).filter(([k,v])=>v!=="ok").map(([k,v])=>({source:k,status:v}))});
});
