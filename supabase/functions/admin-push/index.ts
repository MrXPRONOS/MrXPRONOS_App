// Mr XPRONOS admin Push: durable queue, server idempotency and scheduled dispatch.
// This endpoint does not expose CRON_SECRET or the service key to the browser.
import {createClient} from "https://esm.sh/@supabase/supabase-js@2";
const origins=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000","http://127.0.0.1:8000"]);
function headers(req:Request){
  const origin=req.headers.get("origin")||"";
  return {"Access-Control-Allow-Origin":origins.has(origin)?origin:"https://mrxpronos.github.io",
    "Access-Control-Allow-Headers":"authorization,apikey,content-type,x-client-info",
    "Access-Control-Allow-Methods":"POST,OPTIONS","Vary":"Origin"};
}
function json(req:Request,value:unknown,status=200){
  return new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json",...headers(req)}});
}
type Campaign={id:string;request_id:string;title:string;body:string;url:string|null;tag:string|null;recipient_user_id:string|null;status:string;scheduled_at:string};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function summarize(data:any){
 const rows=Array.isArray(data?.results)?data.results:[];
 const counts={sent:0,failed:0,expired:0,skipped:0,total:rows.length};
 for(const row of rows){
  if(row.status==="sent")counts.sent++;
  else if(row.status==="failed")counts.failed++;
  else if(row.status==="deleted_410")counts.expired++;
  else counts.skipped++;
 }
 return counts;
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:headers(req)});
 if(req.method!=="POST")return json(req,{error:"Method Not Allowed"},405);
 const url=Deno.env.get("SUPABASE_URL")||"";
 const anon=Deno.env.get("SUPABASE_ANON_KEY")||"";
 const secret=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
 const cronSecret=Deno.env.get("CRON_SECRET")||"";
 if(!url||!anon||!secret||!cronSecret)return json(req,{error:"Configuration manquante"},500);
 const service=createClient(url,secret);
 const authorization=req.headers.get("authorization")||"";
 let body:any;
 try{body=await req.json();}catch{return json(req,{error:"JSON invalide"},400);}
 const operation=String(body?.operation||"send");
 const isCron=authorization===`Bearer ${cronSecret}`;
 let actorId:string|null=null;
 if(operation==="dispatch"){
  if(!isCron)return json(req,{error:"Dispatch réservé au planificateur"},403);
 }else{
  if(!authorization.toLowerCase().startsWith("bearer "))return json(req,{error:"Session requise"},401);
  const userClient=createClient(url,anon,{global:{headers:{Authorization:authorization}}});
  const {data:userData,error:authErr}=await userClient.auth.getUser();
  if(authErr||!userData?.user)return json(req,{error:"Session expirée"},401);
  const {data:authorized,error:roleErr}=await userClient.rpc("admin_can",{p_permission:"push"});
  if(roleErr||authorized!==true)return json(req,{error:"Droit de communication requis"},403);
  actorId=userData.user.id;
 }
 async function deliver(c:Campaign){
  // Conditional UPDATE acquires the queued message once. Retries never
  // automatically resend a message whose delivery outcome is unknown.
  const {data:claimed,error:claimErr}=await service.from("admin_push_campaigns")
    .update({status:"processing",started_at:new Date().toISOString(),attempt_count:1})
    .eq("id",c.id).eq("status","queued").select("*").maybeSingle();
  if(claimErr)throw claimErr;
  if(!claimed)return {id:c.id,status:"already_claimed"};
  try{
   const res=await fetch(url+"/functions/v1/push-notifications",{
    method:"POST",headers:{"Content-Type":"application/json","Authorization":`Bearer ${cronSecret}`},
    body:JSON.stringify({title:claimed.title,body:claimed.body,
     user_id:claimed.recipient_user_id||null,url:claimed.url||null,tag:claimed.tag||null})
   });
   const payload=await res.json().catch(()=>({}));
   if(!res.ok)throw Error(String(payload?.error||"Envoi Push refusé"));
   const summary=summarize(payload);
   const {error:doneErr}=await service.from("admin_push_campaigns")
     .update({status:"sent",summary,completed_at:new Date().toISOString(),updated_at:new Date().toISOString()})
     .eq("id",c.id).eq("status","processing");
   if(doneErr)throw doneErr;
   try{
     await service.from("audit_log").insert({action:"admin_push_sent",
       actor_user_id:claimed.created_by,details:{campaign_id:c.id,...summary}});
   }catch{ /* Audit failure must never cause a notification to be resent. */ }
   return {id:c.id,status:"sent",summary};
  }catch(e){
   const reason=String((e as Error)?.message||e).slice(0,500);
   await service.from("admin_push_campaigns")
     .update({status:"failed",error:reason,updated_at:new Date().toISOString(),completed_at:new Date().toISOString()})
     .eq("id",c.id).eq("status","processing");
   return {id:c.id,status:"failed",error:reason};
  }
 }
 try{
  if(operation==="dispatch"){
   const {data,error}=await service.from("admin_push_campaigns").select("*")
     .eq("status","queued").lte("scheduled_at",new Date().toISOString())
     .order("scheduled_at",{ascending:true}).limit(12);
   if(error)throw error;
   const results=[];
   for(const item of data||[])results.push(await deliver(item));
   return json(req,{success:true,processed:results.length,results});
  }
  if(operation==="history"){
   const {data,error}=await service.from("admin_push_campaigns")
     .select("id,request_id,status,scheduled_at,title,recipient_user_id,summary,error,created_at")
     .order("created_at",{ascending:false}).limit(100);
   if(error)throw error;
   return json(req,{success:true,campaigns:data||[]});
  }
  if(operation==="cancel"){
   if(!uuid.test(String(body.id||"")))return json(req,{error:"ID invalide"},400);
   const {data,error}=await service.from("admin_push_campaigns")
     .update({status:"cancelled",updated_at:new Date().toISOString()})
     .eq("id",body.id).eq("status","queued").select("id").maybeSingle();
   if(error)throw error;
   return data?json(req,{success:true,status:"cancelled"}):json(req,{error:"La campagne est déjà traitée"},409);
  }
  if(operation!=="send"&&operation!=="schedule")return json(req,{error:"Opération inconnue"},400);
  const title=String(body?.title||"").trim(),message=String(body?.body||"").trim();
  if(title.length<1||title.length>110||message.length<1||message.length>700)
    return json(req,{error:"Titre ou message invalide"},400);
  const audience=String(body?.audience||"");
  const userId=audience==="user"?String(body?.user_id||"").trim():"";
  if(!["user","all"].includes(audience)||(audience==="user"&&!userId))
    return json(req,{error:"Audience explicite requise"},400);
  if(userId.length>120)return json(req,{error:"Identifiant trop long"},400);
  const requestId=String(body.request_id||"");
  if(!uuid.test(requestId))return json(req,{error:"Clé d'idempotence UUID requise"},400);
  const clickUrl=String(body.url||"").trim();
  if(clickUrl){
   try{const parsed=new URL(clickUrl);if(parsed.protocol!=="https:"||parsed.hostname!=="mrxpronos.github.io")
    return json(req,{error:"Lien de notification non autorisé"},400);}
   catch{return json(req,{error:"URL invalide"},400);}
  }
  const tag=String(body.tag||"").slice(0,100);
  const scheduled=operation==="schedule"?new Date(String(body.scheduled_at||"")):new Date();
  if(!Number.isFinite(scheduled.getTime()))return json(req,{error:"Date de programmation invalide"},400);
  const delta=scheduled.getTime()-Date.now();
  if(operation==="schedule"&&(delta<60000||delta>90*24*3600*1000))
    return json(req,{error:"Programmer entre 1 minute et 90 jours dans le futur"},400);
  const {data:existing}=await service.from("admin_push_campaigns")
    .select("id,status,summary,scheduled_at").eq("request_id",requestId).maybeSingle();
  if(existing)return json(req,{success:true,reused:true,...existing});
  const {data:created,error:insertErr}=await service.from("admin_push_campaigns").insert({
    request_id:requestId,created_by:actorId,title,body:message,url:clickUrl||null,
    recipient_user_id:userId||null,tag:tag||null,scheduled_at:scheduled.toISOString(),status:"queued"
  }).select("*").single();
  if(insertErr){
    if(insertErr.code==="23505"){
      const {data:same}=await service.from("admin_push_campaigns")
        .select("id,status,summary,scheduled_at").eq("request_id",requestId).maybeSingle();
      if(same)return json(req,{success:true,reused:true,...same});
    }
    throw insertErr;
  }
  if(operation==="schedule")return json(req,{
    success:true,id:created.id,request_id:requestId,status:"queued",scheduled_at:created.scheduled_at
  });
  return json(req,{success:true,...await deliver(created)});
 }catch(e){return json(req,{error:String((e as Error)?.message||e)},500);}
});
