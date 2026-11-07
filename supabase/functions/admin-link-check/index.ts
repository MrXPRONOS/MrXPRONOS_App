// Authenticated CMS link diagnostics. HEAD only (GET range fallback), bounded
// cardinality and timeouts. Reject loopback/private targets to avoid SSRF.
import {createClient} from "https://esm.sh/@supabase/supabase-js@2";
const origins=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:8000"]);
const cors=(r:Request)=>{
 const v=r.headers.get("origin")||"";
 return {"Access-Control-Allow-Origin":origins.has(v)?v:"https://mrxpronos.github.io",
  "Access-Control-Allow-Headers":"authorization,apikey,content-type,x-client-info",
  "Access-Control-Allow-Methods":"POST,OPTIONS","Vary":"Origin","Content-Type":"application/json"};
};
const response=(r:Request,data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:cors(r)});
const ipLike=(hostname:string)=>/^(\d+[.]\d+[.]\d+[.]\d+|\[[0-9a-f:]+\]|0x[\da-f]+|\d+)$/i.test(hostname);
const isPublicIpv4=(ip:string)=>{
 const parts=ip.split(".").map(Number);
 if(parts.length!==4||parts.some(n=>!Number.isInteger(n)||n<0||n>255))return false;
 const [a,b]=parts;
 return !(a===0||a===10||a===127||a>=224||a===169&&b===254||
   a===172&&b>=16&&b<=31||a===192&&b===168||a===100&&b>=64&&b<=127||
   a===192&&b===0||a===198&&b===18||a===198&&b===19);
};
const publicUrl=async(url:URL)=>{
 const host=url.hostname.toLowerCase();
 if(url.protocol!=="https:"||url.username||url.password||url.port||
   !host.includes(".")||host.endsWith(".local")||host.endsWith(".internal")||
   host.endsWith(".localhost")||ipLike(host))return false;
 let a:string[]=[],aaaa:string[]=[];
 try{a=await Deno.resolveDns(host,"A");}catch{}
 try{aaaa=await Deno.resolveDns(host,"AAAA");}catch{}
 if(!a.length&&!aaaa.length)return false;
 if(a.some(ip=>!isPublicIpv4(ip)))return false;
 if(aaaa.some(ip=>!ip.includes(":")||ip==="::1"||ip.startsWith("fe80:")||
   ip.startsWith("fc")||ip.startsWith("fd")||ip.startsWith("::ffff:")||
   ip.toLowerCase().startsWith("2001:db8")))return false;
 return true;
};
async function check(raw:string){
 let url:URL;
 try{url=new URL(raw)}catch{return {url:raw,status:"invalid"}}
 if(!await publicUrl(url))return {url:raw,status:"unsafe_or_unresolvable"};
 if(url.hostname==="mrxpronos.github.io")
  return {url:raw,status:"internal_not_yet_published"};
 const ctl=new AbortController(),timeout=setTimeout(()=>ctl.abort(),6500);
 try{
  let res=await fetch(url,{method:"HEAD",redirect:"manual",signal:ctl.signal});
  if(res.status===405||res.status===501){
   res=await fetch(url,{method:"GET",redirect:"manual",signal:ctl.signal,
     headers:{"Range":"bytes=0-0"}});
  }
  try{await res.body?.cancel()}catch{}
  if(res.status===404||res.status===410)return {url:raw,status:"broken",http_status:res.status};
  if(res.status>=200&&res.status<300)return {url:raw,status:"ok",http_status:res.status};
  return {url:raw,status:"warning",http_status:res.status};
 }catch(err){return {url:raw,status:"warning",message:String((err as Error)?.name||"network")};}
 finally{clearTimeout(timeout)}
}
Deno.serve(async(req)=>{
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:cors(req)});
 if(req.method!=="POST")return response(req,{error:"POST only"},405);
 const base=Deno.env.get("SUPABASE_URL")||"",
       anon=Deno.env.get("SUPABASE_ANON_KEY")||"";
 if(!base||!anon)return response(req,{error:"Service non configuré"},500);
 const bearer=req.headers.get("authorization")||"";
 if(!bearer.toLowerCase().startsWith("bearer "))return response(req,{error:"Connexion requise"},401);
 const sb=createClient(base,anon,{global:{headers:{Authorization:bearer}}});
 const {data:{user},error:authErr}=await sb.auth.getUser();
 if(authErr||!user)return response(req,{error:"Session expirée"},401);
 const {data:allowed,error:roleErr}=await sb.rpc("admin_can",{p_permission:"cms"});
 if(roleErr||allowed!==true)return response(req,{error:"Droits éditeur requis"},403);
 const body=await req.json().catch(()=>({}));
 const urls=Array.isArray(body?.urls)?body.urls:[];
 if(urls.length>12||urls.some(u=>typeof u!=="string"||u.length>1800))
  return response(req,{error:"Maximum 12 liens par contrôle, 1800 caractères par lien"},400);
 // Run in batches of three; each request can only fetch a bounded set of URLs.
 const results=[];
 for(let i=0;i<urls.length;i+=3){
  const chunk=await Promise.all(urls.slice(i,i+3).map(check));
  results.push(...chunk);
 }
 return response(req,{success:true,results});
});
