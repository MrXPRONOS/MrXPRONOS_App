import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
const allowedOrigins=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000","http://127.0.0.1:8000"]);
function cors(req:Request){
 const origin=req.headers.get("origin")||"";
 return {"Access-Control-Allow-Origin":allowedOrigins.has(origin)?origin:"https://mrxpronos.github.io",
  "Access-Control-Allow-Headers":"authorization,apikey,content-type,x-client-info",
  "Access-Control-Allow-Methods":"POST,OPTIONS","Vary":"Origin"};
}
function json(req:Request,data:unknown,status=200){
 return new Response(JSON.stringify(data),{status,headers:{"Content-Type":"application/json",...cors(req)}});
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:cors(req)});
 if(req.method!=="POST")return json(req,{error:"Method Not Allowed"},405);
 try{
  const url=Deno.env.get("SUPABASE_URL")||"";
  const anon=Deno.env.get("SUPABASE_ANON_KEY")||"";
  const key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")||"";
  if(!url||!anon||!key)throw Error("Configuration serveur manquante");
  const token=req.headers.get("authorization")||"";
  if(!token.toLowerCase().startsWith("bearer "))return json(req,{error:"Accès refusé"},401);
  const userClient=createClient(url,anon,{global:{headers:{Authorization:token}}});
  const {data:userResult,error:authError}=await userClient.auth.getUser();
  if(authError||!userResult.user)return json(req,{error:"Session expirée"},401);
  const {data:allowed,error:roleError}=await userClient.rpc("admin_can",{p_permission:"media"});
  if(roleError||allowed!==true)return json(req,{error:"Droits médiathèque insuffisants"},403);
  const body=await req.json().catch(()=>({}));
  const mediaId=String(body?.media_id||"");
  if(!/^[a-f0-9-]{36}$/i.test(mediaId))return json(req,{error:"Identifiant média invalide"},400);
  const srv=createClient(url,key);
  const {data:media,error:lookupError}=await srv.from("cms_media")
    .select("id,bucket_id,storage_path,thumbnail_path,mime_type").eq("id",mediaId).maybeSingle();
  if(lookupError)throw lookupError;
  if(!media)return json(req,{error:"Média introuvable"},404);
  if(media.bucket_id==="cms-media"){
    const pub=srv.storage.from("cms-media");
    return json(req,{success:true,url:pub.getPublicUrl(media.storage_path).data.publicUrl});
  }
  if(media.bucket_id!=="cms-drafts")return json(req,{error:"Bucket non autorisé"},400);
  const draft=srv.storage.from("cms-drafts"),published=srv.storage.from("cms-media");
  const copied:string[]=[];
  try{
    for(const item of [media.storage_path,...(media.thumbnail_path?[media.thumbnail_path]:[])]){
      const {data:blob,error:dlError}=await draft.download(item);
      if(dlError||!blob)throw Error("Téléchargement privé impossible: "+(dlError?.message||item));
      const mime=item===media.storage_path?media.mime_type:"image/webp";
      const {error:upError}=await published.upload(item,blob,{upsert:false,contentType:mime,cacheControl:"3600"});
      if(upError)throw Error("Publication refusée : "+upError.message);
      copied.push(item);
    }
    const {data:updated,error:editError}=await srv.from("cms_media").update({bucket_id:"cms-media"})
      .eq("id",mediaId).eq("bucket_id","cms-drafts").select("id").maybeSingle();
    if(editError||!updated)throw Error("Média modifié simultanément; publication annulée.");
  }catch(err){
    if(copied.length)await published.remove(copied).catch(()=>{});
    throw err;
  }
  // Removing the old private draft is best-effort and does not affect public delivery.
  await draft.remove([media.storage_path,...(media.thumbnail_path?[media.thumbnail_path]:[])]).catch(()=>{});
  const {error:auditError}=await srv.from("audit_log").insert({action:"cms_media_published",
    actor_user_id:userResult.user.id,details:{media_id:mediaId}});
  if(auditError)console.warn("cms_media_published audit failed");
  return json(req,{success:true,url:published.getPublicUrl(media.storage_path).data.publicUrl});
 }catch(err){return json(req,{error:String((err as Error)?.message||err)},500);}
});
