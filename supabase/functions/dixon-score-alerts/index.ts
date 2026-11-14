import {createClient} from "https://esm.sh/@supabase/supabase-js@2";
import * as webpush from "npm:web-push@3.6.7";
const ORIGIN="https://mrxpronos.github.io", BASE=ORIGIN+"/MrXPRONOS_App";
function headers(req:Request){const o=req.headers.get("origin")||"";return {"Access-Control-Allow-Origin":o===ORIGIN?o:ORIGIN,"Access-Control-Allow-Headers":"content-type,authorization,apikey","Access-Control-Allow-Methods":"POST,OPTIONS","Vary":"Origin","Cache-Control":"no-store"};}
function respond(req:Request,data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{...headers(req),"Content-Type":"application/json"}});}
async function hash(v:string){const x=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(v));return Array.from(new Uint8Array(x),v=>v.toString(16).padStart(2,"0")).join("");}
function keyObj(k:any){if(typeof k==="string"){try{k=JSON.parse(k)}catch{return null}}return k&&typeof k==="object"?k:null;}
function tomorrow(){const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Africa/Lome",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date());const f=Object.fromEntries(parts.map(p=>[p.type,p.value]));const d=new Date(f.year+"-"+f.month+"-"+f.day+"T12:00:00Z");d.setUTCDate(d.getUTCDate()+1);return d.toISOString().slice(0,10);}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:headers(req)});
 if(req.method!=="POST")return respond(req,{error:"POST required"},405);
 const origin=req.headers.get("origin");if(origin&&origin!==ORIGIN&&!/^http:\/\/(?:localhost|127\.0\.0\.1):3000$/.test(origin))return respond(req,{error:"Origin denied"},403);
 const url=Deno.env.get("SUPABASE_URL"),service=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
 if(!url||!service)return respond(req,{error:"Backend unavailable"},503);
 const db=createClient(url,service,{auth:{persistSession:false}});
 let body:any;try{body=await req.json()}catch{return respond(req,{error:"Invalid JSON"},400)}
 const action=String(body?.action||"");
 try{
   if(["enable","disable","status"].includes(action)){
     const sub=body.subscription,endpoint=sub?.endpoint,keys=keyObj(sub?.keys);
     if(typeof endpoint!=="string"||!endpoint.startsWith("https://")||endpoint.length>2048||
        typeof keys?.p256dh!=="string"||keys.p256dh.length>300||
        typeof keys?.auth!=="string"||keys.auth.length>300)return respond(req,{error:"Invalid push subscription"},400);
     const {data:stored,error:lookupErr}=await db.from("push_subscriptions").select("keys").eq("endpoint",endpoint).maybeSingle();
     if(lookupErr)return respond(req,{error:"Subscription lookup unavailable"},503);
     const storedKeys=keyObj(stored?.keys);
     if(!storedKeys||keys.p256dh!==storedKeys.p256dh||keys.auth!==storedKeys.auth)return respond(req,{error:"Unknown subscription"},403);
     const id=await hash(endpoint);
     if(action==="status"){
       const {data,error}=await db.from("dixon_score_push_optins").select("enabled").eq("endpoint_digest",id).maybeSingle();
       return error?respond(req,{error:"Status unavailable"},503):respond(req,{success:true,enabled:data?.enabled===true});
     }
     const enabled=action==="enable";
     const {error}=await db.from("dixon_score_push_optins").upsert({endpoint_digest:id,enabled,updated_at:new Date().toISOString()},{onConflict:"endpoint_digest"});
     return error?respond(req,{error:"Could not save preference"},503):respond(req,{success:true,enabled});
   }
   if(action!=="publish")return respond(req,{error:"Unknown action"},400);
   const cron=Deno.env.get("CRON_SECRET");
   if(!cron||req.headers.get("authorization")!=="Bearer "+cron)return respond(req,{error:"Unauthorized"},401);
   const day=String(body?.date||""),sha=String(body?.video_sha256||""),count=body?.count;
   if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||day!==tomorrow()||!/^[a-f0-9]{64}$/.test(sha)||!Number.isInteger(count)||count<1||count>10)
     return respond(req,{error:"Invalid next-day video manifest"},400);
   const proof=await fetch(BASE+"/dixon-scores-daily/"+day+".json?proof="+Date.now(),{cache:"no-store"});
   if(!proof.ok)return respond(req,{error:"Published scores unavailable"},409);
   const receipt=await proof.json();
   if(receipt.schema_version!=="mrx-dixon-coles-video-scores-v1"||
      receipt.origin!=="verified_social_video_render"||receipt.status!=="published"||
      receipt.date!==day||receipt.video_sha256!==sha||receipt.count!==count||
      !Array.isArray(receipt.matches)||receipt.matches.length!==count)
       return respond(req,{error:"Published video scores do not match"},409);
   const {error:claimed}=await db.from("dixon_score_push_dispatches").insert({match_date:day,video_sha256:sha,total_count:count});
   if(claimed){if(claimed.code==="23505")return respond(req,{success:true,already_claimed:true});return respond(req,{error:"Notification claim unavailable"},503);}
   const pub=Deno.env.get("VAPID_PUBLIC_KEY"),priv=Deno.env.get("VAPID_PRIVATE_KEY");
   const subject=Deno.env.get("VAPID_SUBJECT")||(Deno.env.get("VAPID_EMAIL")?"mailto:"+Deno.env.get("VAPID_EMAIL"):"");
   if(!pub||!priv||!subject)return respond(req,{error:"VAPID configuration missing"},503);
   webpush.setVapidDetails(subject,pub,priv);
   const {data:optins,error:err}=await db.from("dixon_score_push_optins").select("endpoint_digest").eq("enabled",true).limit(50000);
   if(err)return respond(req,{error:"Push opt-ins unavailable"},503);
   const wanted=new Set((optins||[]).map(row=>row.endpoint_digest));
   let sent=0,failed=0;
   for(let pg=0;pg<50&&wanted.size;pg++){
     const {data:subs,error:e}=await db.from("push_subscriptions").select("id,endpoint,keys").order("id",{ascending:true}).range(pg*1000,pg*1000+999);
     if(e)throw e;
     for(const sub of subs||[]){
       if(typeof sub.endpoint!=="string"||!wanted.has(await hash(sub.endpoint)))continue;
       const keys=keyObj(sub.keys);if(!keys?.p256dh||!keys?.auth)continue;
       try{
         await webpush.sendNotification({endpoint:sub.endpoint,keys},JSON.stringify({
           title:"⚽ Nouveaux scores exacts Mr XPRONOS",
           body:count+" pronostic(s) Dixon-Coles pour demain sont disponibles.",
           url:BASE+"/scores-exacts.html?day=tomorrow",tag:"dixon-score-"+day
         }));
         sent++;
       }catch(e){
         failed++;
         if([404,410].includes(Number((e as any)?.statusCode||0))){
           await db.from("dixon_score_push_optins").update({enabled:false,updated_at:new Date().toISOString()}).eq("endpoint_digest",await hash(sub.endpoint));
         }
       }
     }
     if((subs||[]).length<1000)break;
   }
   await db.from("dixon_score_push_dispatches").update({finished_at:new Date().toISOString(),delivered:sent}).eq("match_date",day).eq("video_sha256",sha);
   return respond(req,{success:true,date:day,sent,failed,opted_in:wanted.size});
 }catch(err){console.error("Dixon push:",String(err));return respond(req,{error:"Notification delivery failed"},500);}
});