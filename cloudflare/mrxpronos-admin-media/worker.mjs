// Signature Version 4 implemented with the Workers Web Crypto API.
// Keep S3 credentials private; they are never sent to browsers.
const utf8 = value => new TextEncoder().encode(value);
const hex = b => [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("");
async function digest(b) {return hex(await crypto.subtle.digest("SHA-256",b));}
async function hmac(key,message){
  const secret=await crypto.subtle.importKey("raw",typeof key==="string"?utf8(key):key,
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC",secret,utf8(message)));
}
async function signedStorageFetch(env,url,method,body=null,mime=null){
  const date=new Date().toISOString().replace(/[:-]|\.\d{3}/g,"");
  const ymd=date.slice(0,8),region=env.NEON_S3_REGION||"eu-central-1";
  const scope=ymd+"/"+region+"/s3/aws4_request";
  const parsed=new URL(url),payload=body===null?new Uint8Array():new Uint8Array(body);
  const payloadHash=await digest(payload);
  const fields={"host":parsed.host,"x-amz-content-sha256":payloadHash,"x-amz-date":date};
  if(mime)fields["content-type"]=mime;
  const keys=Object.keys(fields).sort();
  const canonicalHeaders=keys.map(x=>x+":"+fields[x].trim()+"\n").join("");
  const signedHeaders=keys.join(";");
  const canonical=[method,parsed.pathname,parsed.search.slice(1),canonicalHeaders,signedHeaders,payloadHash].join("\n");
  const stringToSign=["AWS4-HMAC-SHA256",date,scope,await digest(utf8(canonical))].join("\n");
  let key=await hmac("AWS4"+env.NEON_S3_SECRET_ACCESS_KEY,ymd);
  key=await hmac(key,region);key=await hmac(key,"s3");key=await hmac(key,"aws4_request");
  const signature=hex(await hmac(key,stringToSign));
  const headers={
    "x-amz-content-sha256":payloadHash,"x-amz-date":date,
    "Authorization":"AWS4-HMAC-SHA256 Credential="+env.NEON_S3_ACCESS_KEY_ID+"/"+scope+
     ", SignedHeaders="+signedHeaders+", Signature="+signature
  };
  if(mime)headers["content-type"]=mime;
  return fetch(url,{method,headers,...(body===null?{}:{body})});
}

const ORIGIN = "https://mrxpronos.github.io";
const FORMATS = {
  "image/jpeg": ["jpg", 15_728_640],
  "image/png": ["png", 15_728_640],
  "image/webp": ["webp", 15_728_640],
  "image/gif": ["gif", 15_728_640],
  "video/mp4": ["mp4", 31_457_280],
  "video/webm": ["webm", 31_457_280],
};
const json = (data,status=200,origin=ORIGIN)=>new Response(JSON.stringify(data),{
  status,headers:{"Content-Type":"application/json","Access-Control-Allow-Origin":origin,
  "Cache-Control":"no-store","Vary":"Origin",
  "Access-Control-Allow-Headers":"Authorization,Content-Type",
  "Access-Control-Allow-Methods":"OPTIONS,POST,DELETE"}
});
function signatureOk(mime,b) {
  const ascii=(n,k)=>String.fromCharCode(...b.slice(n,n+k));
  if(mime==="image/jpeg")return b[0]===255&&b[1]===216&&b[2]===255;
  if(mime==="image/png")return b[0]===137&&ascii(1,3)==="PNG";
  if(mime==="image/webp")return ascii(0,4)==="RIFF"&&ascii(8,4)==="WEBP";
  if(mime==="image/gif")return ["GIF87a","GIF89a"].includes(ascii(0,6));
  if(mime==="video/mp4")return ascii(4,4)==="ftyp";
  if(mime==="video/webm")return b[0]===26&&b[1]===69&&b[2]===223&&b[3]===163;
  return false;
}
function configured(env) {
  return !!(env.NEON_DATA_API_URL?.startsWith("https://")&&
    env.NEON_S3_ENDPOINT?.startsWith("https://")&&
    env.NEON_S3_ACCESS_KEY_ID&&env.NEON_S3_SECRET_ACCESS_KEY);
}
const decodeSegment = text => {
  const raw=atob(text.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(text.length/4)*4,"="));
  return Uint8Array.from(raw,c=>c.charCodeAt(0));
};
async function verifyGithubOIDC(token) {
  try{
    const jwt=token.replace(/^Bearer /,"");
    const parts=jwt.split(".");
    if(parts.length!==3)return false;
    const head=JSON.parse(new TextDecoder().decode(decodeSegment(parts[0])));
    const claims=JSON.parse(new TextDecoder().decode(decodeSegment(parts[1])));
    if(head.alg!=="RS256"||!head.kid)return false;
    const now=Math.floor(Date.now()/1000);
    if(claims.iss!=="https://token.actions.githubusercontent.com"||
       claims.aud!=="mrxpronos-media"||
       claims.repository!=="MrXPRONOS/MrXPRONOS_App"||
       ![ "refs/heads/main",
          "refs/heads/migration/neon-cloudflare-adaptation-20261023" ].includes(claims.ref)||
       !Number.isFinite(claims.exp)||claims.exp<=now||
       !Number.isFinite(claims.iat)||claims.iat>now+60||
       !Number.isFinite(claims.nbf)||claims.nbf>now)return false;
    const allowed=["shorts-coupons-production.yml",
      "shorts-coupons-production-validation.yml","accumulator-photo-production.yml"];
    const ref=String(claims.workflow_ref||"");
    if(!allowed.some(name=>ref==="MrXPRONOS/MrXPRONOS_App/.github/workflows/"+name+"@"+claims.ref))
      return false;
    const r=await fetch("https://token.actions.githubusercontent.com/.well-known/jwks",{
      cf:{cacheTtl:600,cacheEverything:true}});
    if(!r.ok)return false;
    const jwk=(await r.json()).keys.find(x=>x.kid===head.kid&&x.kty==="RSA");
    if(!jwk)return false;
    const key=await crypto.subtle.importKey("jwk",jwk,
      {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
    return crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,decodeSegment(parts[2]),
      utf8(parts[0]+"."+parts[1]));
  }catch(_){return false}
}
async function verifyAdmin(token,env) {
  const r=await fetch(env.NEON_DATA_API_URL.replace(/\/$/,"")+"/rpc/is_admin",{
    method:"POST",headers:{"Authorization":token,"Content-Type":"application/json"},
    body:"{}",redirect:"error"});
  if(!r.ok)return false;
  return (await r.json())===true;
}
function objectUrl(env,key) {
  const bucket=env.NEON_S3_BUCKET||"videos";
  return env.NEON_S3_ENDPOINT.replace(/\/$/,"")+"/"+bucket+"/"+key.split("/").map(encodeURIComponent).join("/");
}
function publicUrl(env,key) {
  const base=env.NEON_PUBLIC_MEDIA_BASE_URL?.trim() ||
    env.NEON_S3_ENDPOINT.replace(/\/$/,"")+"/"+(env.NEON_S3_BUCKET||"videos");
  return base.replace(/\/$/,"")+"/"+key.split("/").map(encodeURIComponent).join("/");
}
export default {
  async fetch(request,env) {
    const origin=request.headers.get("Origin");
    if(origin!==ORIGIN&&origin!==null)return json({error:"Origine interdite"},403);
    if(request.method==="OPTIONS")return origin===ORIGIN?json({ok:true}):json({error:"Origine interdite"},403);
    if(!configured(env))return json({error:"Stockage Neon non configuré"},503);
    const bearer=request.headers.get("Authorization")||"";
    if(!/^Bearer [A-Za-z0-9_.-]+$/.test(bearer))return json({error:"Session requise"},401);
    // Browser: signed-in Neon administrator. GitHub: short-lived OIDC with exact workflow_ref.
    const fromGithub=origin===null;
    if(fromGithub ? !(await verifyGithubOIDC(bearer)) : !(await verifyAdmin(bearer,env)))
      return json({error:"Accès refusé"},403);
    const pathname=new URL(request.url).pathname;
    try {
      if(request.method==="POST"&&pathname==="/upload") {
        const mime=(request.headers.get("Content-Type")||"").split(";")[0].trim().toLowerCase();
        const format=FORMATS[mime];
        if(!format)return json({error:"Format média refusé"},415);
        const declared=Number(request.headers.get("Content-Length")||"0");
        if(declared>format[1])return json({error:"Taille excessive"},413);
        const buffer=await request.arrayBuffer();
        if(!buffer.byteLength||buffer.byteLength>format[1]||!signatureOk(mime,new Uint8Array(buffer).slice(0,16)))
          return json({error:"Média invalide"},422);
        const key=(fromGithub ? (mime==="video/mp4"?"shorts/":"accumulator/") : "cms/")+
          crypto.randomUUID()+"."+format[0];
        const upstream=await signedStorageFetch(env,objectUrl(env,key),"PUT",buffer,mime);
        if(!upstream.ok)return json({error:"Écriture Neon refusée"},502);
        // Public-readable bucket is a prerequisite; never claim a URL without checking.
        const link=publicUrl(env,key);
        const probe=await fetch(link,{method:"GET",headers:{"Range":"bytes=0-0"}});
        if(!probe.ok)return json({error:"Média stocké mais URL publique non accessible"},502);
        return json({key,url:link,size:buffer.byteLength,mime},201);
      }
      if(!fromGithub&&request.method==="DELETE"&&pathname==="/object") {
        const key=new URL(request.url).searchParams.get("key")||"";
        if(!/^cms\/[0-9a-f-]{36}\.(jpg|png|webp|gif|mp4|webm)$/.test(key))
          return json({error:"Clé invalide"},400);
        const upstream=await signedStorageFetch(env,objectUrl(env,key),"DELETE");
        if(!upstream.ok&&upstream.status!==404)return json({error:"Suppression refusée"},502);
        return json({deleted:true});
      }
      return json({error:"Action inconnue"},404);
    } catch (_) {return json({error:"Service média temporairement indisponible"},502);}
  }
};
