const json=(x,status=200)=>new Response(JSON.stringify(x),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}});
const encoder=new TextEncoder();
function base64url(s){let t=s.replace(/-/g,"+").replace(/_/g,"/");t+="=".repeat((4-t.length%4)%4);return Uint8Array.from(atob(t),c=>c.charCodeAt(0));}
function safeEqual(a,b){let d=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)d|=(a[i]||0)^(b[i]||0);return d===0;}
async function hmac(secret,bytes){const key=await crypto.subtle.importKey("raw",encoder.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return new Uint8Array(await crypto.subtle.sign("HMAC",key,bytes));}
async function verify(signed,secret){const p=signed.split(".");if(p.length!==2||p.some(t=>!t||t.length>12000))return null;try{const sig=base64url(p[0]),expected=await hmac(secret,encoder.encode(p[1]));if(!safeEqual(sig,expected))return null;const obj=JSON.parse(new TextDecoder().decode(base64url(p[1])));const id=obj.user_id;if(obj.algorithm!=="HMAC-SHA256"||!["number","string"].includes(typeof id)||!/^\d{1,40}$/.test(String(id)))return null;return String(id);}catch{return null;}}
const hex=b=>[...b].map(x=>x.toString(16).padStart(2,"0")).join("");
export default {async fetch(req,env){
 const path=new URL(req.url).pathname;
 const kind=path.endsWith("/threads-uninstall")?"uninstall":path.endsWith("/threads-data-deletion")?"deletion":null;
 if(!kind)return json({error:"not_found"},404);
 if(!env.DB)return json({error:"not_configured"},503);
 if(req.method==="GET"&&kind==="deletion"){
  const code=new URL(req.url).searchParams.get("code")||"";
  if(!/^[0-9a-f-]{36}$/i.test(code))return json({error:"invalid_confirmation"},400);
  try{const row=await env.DB.prepare("SELECT status,created_at,completed_at FROM privacy_requests WHERE confirmation_code=? AND request_type='deletion'").bind(code).first();return row?json(row):json({error:"not_found"},404)}
  catch{return json({error:"service_unavailable"},503)}
 }
 if(req.method!=="POST")return json({error:"method_not_allowed"},405);
 if(!env.THREADS_APP_SECRET)return json({error:"not_configured"},503);
 const l=Number(req.headers.get("content-length")||0);if(l>20000)return json({error:"payload_too_large"},413);
 const raw=await req.text();if(raw.length>20000)return json({error:"payload_too_large"},413);
 const signed=new URLSearchParams(raw).get("signed_request");if(!signed)return json({error:"missing_signed_request"},400);
 const id=await verify(signed,env.THREADS_APP_SECRET);if(!id)return json({error:"invalid_signature"},403);
 const digest=hex(await hmac(env.THREADS_APP_SECRET,encoder.encode("mrxpronos:threads:user:"+id)));
 const code=crypto.randomUUID(),now=new Date().toISOString();
 try{
  await env.DB.prepare("INSERT INTO privacy_requests (request_type,subject_hmac,confirmation_code,status,created_at,last_seen_at) VALUES (?,?,?,'pending',?,?) ON CONFLICT(request_type,subject_hmac) DO UPDATE SET last_seen_at=excluded.last_seen_at").bind(kind,digest,code,now,now).run();
  const row=await env.DB.prepare("SELECT confirmation_code FROM privacy_requests WHERE request_type=? AND subject_hmac=?").bind(kind,digest).first();
  if(!row)return json({error:"recording_failed"},503);
  if(kind==="deletion"){const url=new URL(req.url);url.pathname="/threads-data-deletion";url.search="code="+encodeURIComponent(row.confirmation_code);return json({url:url.toString(),confirmation_code:row.confirmation_code});}
  return json({received:true});
 }catch{return json({error:"recording_failed"},503)}
}};