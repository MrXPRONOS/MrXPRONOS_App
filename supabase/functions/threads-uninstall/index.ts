const KIND = "uninstall";
const encoder = new TextEncoder();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status, headers: {"content-type":"application/json; charset=utf-8", "cache-control":"no-store"}});
function fromB64url(input: string): Uint8Array {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
  const decoded = atob(padded);
  return Uint8Array.from(decoded, c => c.charCodeAt(0));
}
function safeEq(a: Uint8Array,b: Uint8Array):boolean {
  let diff = a.length ^ b.length;
  for(let i=0;i<Math.max(a.length,b.length);i++) diff |= (a[i]||0) ^ (b[i]||0);
  return diff === 0;
}
async function hmac(secret:string,data:Uint8Array):Promise<Uint8Array>{
  const key = await crypto.subtle.importKey("raw",encoder.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC",key,data));
}
async function verifiedSubject(signed:string,secret:string):Promise<string|null>{
  const pieces=signed.split(".");
  if(pieces.length!==2||pieces.some(x=>!x||x.length>12000))return null;
  try {
    const signature=fromB64url(pieces[0]); const payload=fromB64url(pieces[1]);
    const expected=await hmac(secret,encoder.encode(pieces[1]));
    if(!safeEq(signature,expected))return null;
    const parsed=JSON.parse(new TextDecoder().decode(payload));
    if(parsed.algorithm!=="HMAC-SHA256")return null;
    const id=parsed.user_id;
    if((typeof id!=="string"&&typeof id!=="number")||!/^\d{1,40}$/.test(String(id)))return null;
    return String(id);
  }catch{return null;}
}
function hex(value:Uint8Array):string{return Array.from(value,v=>v.toString(16).padStart(2,"0")).join("");}
Deno.serve(async req=>{
  if(req.method==="GET" && KIND==="deletion"){
    const url=new URL(req.url); const code=url.searchParams.get("code")||"";
    if(!/^[0-9a-f-]{36}$/i.test(code))return json({error:"invalid_confirmation"},400);
    const base=Deno.env.get("SUPABASE_URL"), key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if(!base||!key)return json({error:"service_unavailable"},503);
    const query=new URL(base+"/rest/v1/threads_privacy_requests");
    query.searchParams.set("select","status,created_at,completed_at");
    query.searchParams.set("confirmation_code","eq."+code);
    query.searchParams.set("request_type","eq.deletion");
    try {
      const r=await fetch(query,{headers:{apikey:key,Authorization:"Bearer "+key}});
      if(!r.ok)return json({error:"service_unavailable"},503);
      const found=await r.json();
      if(!found.length)return json({error:"not_found"},404);
      return json({status:found[0].status,created_at:found[0].created_at,completed_at:found[0].completed_at});
    }catch{return json({error:"service_unavailable"},503);}
  }
  if(req.method!=="POST")return json({error:"method_not_allowed"},405);
  const secret=Deno.env.get("THREADS_APP_SECRET");
  const base=Deno.env.get("SUPABASE_URL"),key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!secret||!base||!key)return json({error:"not_configured"},503);
  const length=Number(req.headers.get("content-length")||"0");
  if(length>20000)return json({error:"payload_too_large"},413);
  const raw=await req.text();
  if(raw.length>20000)return json({error:"payload_too_large"},413);
  const signed=new URLSearchParams(raw).get("signed_request");
  if(!signed)return json({error:"missing_signed_request"},400);
  const subject=await verifiedSubject(signed,secret);
  if(!subject)return json({error:"invalid_signature"},403);
  // Domain-separated, irreversible user identifier, no raw user IDs in DB or logs.
  const digest=hex(await hmac(secret,encoder.encode("mrxpronos:threads:user:"+subject)));
  const now=new Date().toISOString();
  const upsert=new URL(base+"/rest/v1/threads_privacy_requests");
  upsert.searchParams.set("on_conflict","request_type,subject_hmac");
  upsert.searchParams.set("select","confirmation_code,status");
  const reply=await fetch(upsert,{
    method:"POST",
    headers:{"content-type":"application/json",apikey:key,Authorization:"Bearer "+key,
      Prefer:"resolution=merge-duplicates,return=representation"},
    body:JSON.stringify({request_type:KIND,subject_hmac:digest,last_seen_at:now}),
  }).catch(()=>null);
  if(!reply||!reply.ok)return json({error:"recording_failed"},503);
  const rows=await reply.json().catch(()=>[]);
  if(!rows.length||!rows[0].confirmation_code)return json({error:"recording_failed"},503);
  // No false claims: credentials and any related tokens require separate verified cleanup.
  if(KIND==="deletion"){
    return json({url:base+"/functions/v1/threads-data-deletion?code="+encodeURIComponent(rows[0].confirmation_code),confirmation_code:rows[0].confirmation_code});
  }
  return json({received:true});
});