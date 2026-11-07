// Read-only cron-job.org integration. No provider key or target URL query in responses.
// cron-job.org default API quota is 100 requests/day: cache lists for 30 minutes.
import {createClient} from "https://esm.sh/@supabase/supabase-js@2";
const projectOrigin="https://mrxpronos.github.io";
const allowedOrigin=new Set([projectOrigin,"http://localhost:3000","http://127.0.0.1:8000"]);
const responseHeaders=(req:Request)=>({
 "Access-Control-Allow-Origin":allowedOrigin.has(req.headers.get("origin")||"")?req.headers.get("origin")!:projectOrigin,
 "Access-Control-Allow-Headers":"authorization,apikey,content-type,x-client-info",
 "Access-Control-Allow-Methods":"POST,OPTIONS","Content-Type":"application/json","Vary":"Origin"
});
const reply=(req:Request,x:unknown,status=200)=>new Response(JSON.stringify(x),{status,headers:responseHeaders(req)});
const safeTarget=(raw:string)=>{
 try{
  const url=new URL(raw);
  if(url.protocol!=="https:"&&url.protocol!=="http:")return "autre";
  // Never return credentials or query/fragment: dispatch URLs may contain tokens.
  return url.hostname.toLowerCase()+url.pathname;
 }catch{return "inconnu";}
};
function sanitizeJob(job:any){
 const minutes=Array.isArray(job.schedule?.minutes)?job.schedule.minutes.map(Number):[];
 const hours=Array.isArray(job.schedule?.hours)?job.schedule.hours.map(Number):[];
 const schedule={timezone:String(job.schedule?.timezone||"UTC").slice(0,80),
  minutes:minutes.filter(Number.isFinite).slice(0,60),
  hours:hours.filter(Number.isFinite).slice(0,24),
  wdays:Array.isArray(job.schedule?.wdays)?job.schedule.wdays.map(Number).slice(0,7):[]};
 return {
  id:Number(job.jobId),title:String(job.title||"Tâche").slice(0,120),
  enabled:job.enabled===true,last_status:Number(job.lastStatus||0),
  last_execution:Number(job.lastExecution||0),next_execution:Number(job.nextExecution||0),
  last_duration_ms:Number(job.lastDuration||0),schedule,
  endpoint:safeTarget(String(job.url||""))
 };
}
Deno.serve(async req=>{
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:responseHeaders(req)});
 if(req.method!=="POST")return reply(req,{error:"Method not allowed"},405);
 const url=Deno.env.get("SUPABASE_URL")||"",
       anon=Deno.env.get("SUPABASE_ANON_KEY")||"",
       key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
 if(!url||!anon||!key)return reply(req,{error:"Configuration Supabase absente"},500);
 const bearer=req.headers.get("authorization")||"";
 if(!bearer.toLowerCase().startsWith("bearer "))return reply(req,{error:"Session obligatoire"},401);
 const user=createClient(url,anon,{global:{headers:{Authorization:bearer}}});
 const {data:{user:actor},error:authError}=await user.auth.getUser();
 if(authError||!actor)return reply(req,{error:"Session expirée"},401);
 const {data:allowed,error:roleError}=await user.rpc("admin_can",{p_permission:"read"});
 if(roleError||allowed!==true)return reply(req,{error:"Accès admin requis"},403);
 let body:any={};
 try{body=await req.json()}catch{return reply(req,{error:"JSON invalide"},400)}
 const op=String(body?.operation||"jobs");
 if(!["jobs","history"].includes(op))return reply(req,{error:"Opération inconnue"},400);
 const service=createClient(url,key);
 const providerKey=Deno.env.get("CRON_JOB_ORG_API_KEY")||"";
 const {data:cached,error:dbError}=await service.from("admin_cron_snapshot")
  .select("fetched_at,status,jobs,last_error").eq("id",1).maybeSingle();
 if(dbError)return reply(req,{error:"Cache de supervision indisponible"},503);
 if(!providerKey)return reply(req,{configured:false,status:"unconfigured",jobs:[],last_error:"Clé cron-job.org non configurée"});
 const source=async(path:string)=>{
  const ctl=new AbortController();const timeout=setTimeout(()=>ctl.abort(),9000);
  try{
   const res=await fetch("https://api.cron-job.org"+path,{
    method:"GET",signal:ctl.signal,headers:{"Authorization":"Bearer "+providerKey,
     "Accept":"application/json"}});
   if(!res.ok)throw Error("cron-job.org HTTP "+res.status);
   return await res.json();
  }finally{clearTimeout(timeout)}
 };
 if(op==="history"){
  const id=Number(body.job_id);
  if(!Number.isSafeInteger(id)||id<=0)return reply(req,{error:"Identifiant de tâche invalide"},400);
  if(!Array.isArray(cached?.jobs)||!cached.jobs.some((j:any)=>j.id===id))
   return reply(req,{error:"Tâche absente du registre connu"},404);
  try{
   const data=await source("/jobs/"+id+"/history");
   const history=(Array.isArray(data.history)?data.history:[]).slice(0,20).map((h:any)=>({
     planned:Number(h.datePlanned||0),executed:Number(h.date||0),duration_ms:Number(h.duration||0),
     status:String(h.statusText||"").slice(0,80),http_status:Number(h.httpStatus||0),
     jitter_ms:Number(h.jitter||0)
   }));
   return reply(req,{configured:true,id,history});
  }catch(e){return reply(req,{error:"Historique cron-job.org indisponible : "+String((e as Error).message||e)},502)}
 }
 const age=Date.now()-Date.parse(cached?.fetched_at||"");
 if(cached?.status==="ok"&&Array.isArray(cached?.jobs)&&age>=0&&age<30*60*1000)
  return reply(req,{configured:true,cached:true,status:"ok",fetched_at:cached.fetched_at,jobs:cached.jobs});
 try{
  const provider=await source("/jobs");
  const jobs=(Array.isArray(provider.jobs)?provider.jobs:[]).map(sanitizeJob)
   .filter((j:any)=>Number.isSafeInteger(j.id)&&j.id>0);
  const stamp=new Date().toISOString();
  await service.from("admin_cron_snapshot").upsert({
    id:1,fetched_at:stamp,status:"ok",jobs,last_error:null,updated_at:stamp
  },{onConflict:"id"});
  return reply(req,{configured:true,cached:false,status:"ok",fetched_at:stamp,jobs,
    partial:provider.someFailed===true});
 }catch(e){
  const reason=String((e as Error)?.message||e).slice(0,160);
  // Do not erase the last known good snapshot on transient API failure.
  return reply(req,{configured:true,status:"error",cached:true,
   stale:true,fetched_at:cached?.fetched_at||null,jobs:cached?.jobs||[],error:reason});
 }
});
