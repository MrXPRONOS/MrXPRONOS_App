/**
 * Mr XPRONOS V2 encrypted Cloudflare backup receiver.
 * No API key, shared secret or recoverable decryption key is embedded.
 * Authenticate short-lived GitHub Actions OIDC JWT by issuer JWKS + signature
 * AND exact repository/workflow/ref/audience claims. Accept ciphertext only.
 */
const AUDIENCE = "mrxpronos-actufoot-v2-backup";
const ISSUER = "https://token.actions.githubusercontent.com";
const REPO = "MrXPRONOS/MrXPRONOS_App";
const WORKFLOW = REPO + "/.github/workflows/actu-foot-v2-backup.yml@refs/heads/main";
const RECOVERY_WORKFLOW = REPO + "/.github/workflows/actu-foot-v2-recovery-drill.yml@refs/heads/main";
const COLLECTIONS = ["audit", "live_events", "matches", "news", "publications", "settings", "statistics"];
const MAX_BODY = 14500000;
const MAX_FILE = 2200000;

function fail(status) {
  return new Response(JSON.stringify({ok:false}), {status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
}
function b64url(s) {
  const base=s.replace(/-/g,"+").replace(/_/g,"/");
  return Uint8Array.from(atob(base.padEnd(Math.ceil(base.length/4)*4,"=")), c=>c.charCodeAt(0));
}
function readJson(bytes) { return JSON.parse(new TextDecoder().decode(bytes)); }
async function authenticate(header, expectedWorkflow = WORKFLOW) {
  if(!header || !header.startsWith("Bearer ") || header.length>10000) throw new Error("auth");
  const jwt=header.slice(7);
  const segments=jwt.split(".");
  if(segments.length!==3) throw new Error("segments");
  const hdr=readJson(b64url(segments[0])), claims=readJson(b64url(segments[1]));
  if(hdr.alg!=="RS256" || !hdr.kid || typeof hdr.kid!=="string") throw new Error("alg");
  const now=Math.floor(Date.now()/1000);
  if(claims.iss!==ISSUER || claims.aud!==AUDIENCE || claims.repository!==REPO
     || claims.repository_id!=="1169480535" || claims.repository_owner_id!=="256667374"
     || claims.workflow_ref!==expectedWorkflow || claims.ref!=="refs/heads/main"
     || !["schedule","workflow_dispatch","push"].includes(claims.event_name)
     || typeof claims.exp!=="number" || claims.exp<now-30 || claims.exp>now+900
     || typeof claims.iat!=="number" || claims.iat>now+60 || claims.iat<now-900
     || (claims.nbf!==undefined && (typeof claims.nbf!=="number" || claims.nbf>now+60))
     || !/^\d+$/.test(String(claims.run_id||""))
     || !/^\d+$/.test(String(claims.run_attempt||""))
     || !/^[0-9a-f]{40}$/.test(String(claims.sha||""))) {
    throw new Error("claims");
  }
  const response=await fetch("https://token.actions.githubusercontent.com/.well-known/jwks",{
    cf:{cacheTtl:300,cacheEverything:true}
  });
  if(!response.ok) throw new Error("jwks");
  const keys=(await response.json()).keys||[];
  const jwk=keys.find(k=>k.kid===hdr.kid && k.kty==="RSA" && k.use==="sig");
  if(!jwk) throw new Error("kid");
  const key=await crypto.subtle.importKey("jwk",jwk,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  const valid=await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,b64url(segments[2]),
    new TextEncoder().encode(segments[0]+"."+segments[1]));
  if(!valid) throw new Error("signature");
  return claims;
}
async function digestHex(data) {
  const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(data));
  return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,"0")).join("");
}
export default {
 async fetch(request, env) {
   const pathname = new URL(request.url).pathname;
   if(request.method==="POST" && pathname==="/v2/recover") {
     let claims;
     try {claims=await authenticate(request.headers.get("Authorization"), RECOVERY_WORKFLOW);} catch(e){return fail(401);}
     let requestBody;
     try {requestBody=await request.json();}catch(e){return fail(400);}
     if(!requestBody || !/^\d{5,16}$/.test(String(requestBody.run||"")) || !/^\d{1,4}$/.test(String(requestBody.attempt||""))) return fail(400);
     const prefix="snapshots/"+requestBody.run+"/"+requestBody.attempt;
     const names=[...COLLECTIONS.map(c=>c+".aes.json"),"manifest.json","provenance.json"];
     const values=await Promise.all(names.map(n=>env.BACKUPS.get(prefix+"/"+n)));
     if(values.some(v=>v===null)) return fail(404);
     const provenance=JSON.parse(values[values.length-1]);
     if(provenance.repository!==REPO || provenance.workflow!==WORKFLOW || provenance.run!==String(requestBody.run) || provenance.attempt!==String(requestBody.attempt)) return fail(409);
     const files=Object.fromEntries(COLLECTIONS.map((c,i)=>[c,values[i]]));
     return new Response(JSON.stringify({ok:true,files,manifest:values[COLLECTIONS.length],provenance}),{headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
   }
   if(request.method==="GET" && new URL(request.url).pathname==="/health") return new Response("healthy", {headers:{"Cache-Control":"no-store"}});
   if(request.method!=="POST" || new URL(request.url).pathname!=="/v2/backup") return fail(404);
   const size=Number(request.headers.get("Content-Length")||0);
   if(size>MAX_BODY) return fail(413);
   let claims;
   try {claims=await authenticate(request.headers.get("Authorization"));} catch(e){return fail(401);}
   let body;
   try {
     const payload=await request.text();
     if(payload.length>MAX_BODY) return fail(413);
     body=JSON.parse(payload);
     if(!body || typeof body!=="object" || !body.files || !body.manifest) return fail(400);
     const provided=Object.keys(body.files).sort();
     if(JSON.stringify(provided)!==JSON.stringify(COLLECTIONS)) return fail(400);
     const manifest=JSON.parse(body.manifest);
     if(manifest.format!=="actufoot-v2-backup-v2"
        || JSON.stringify(Object.keys(manifest.collections||{}).sort())!==JSON.stringify(COLLECTIONS)) return fail(400);
     for(const name of COLLECTIONS){
       const raw=body.files[name];
       if(typeof raw!=="string" || raw.length>MAX_FILE) return fail(413);
       const header=JSON.parse(raw);
       if(header.format!=="mrxp.actufoot.v2.aes256gcm" || header.collection!==name
          || !header.ciphertext_b64 || !header.nonce_b64) return fail(400);
       const expected=manifest.collections[name].sha256;
       if(await digestHex(raw)!==expected) return fail(400);
     }
   }catch(e){return fail(400);}
   const prefix="snapshots/"+claims.run_id+"/"+claims.run_attempt;
   if(await env.BACKUPS.get(prefix+"/manifest.json")!==null) return fail(409);
   try {
     for(const name of COLLECTIONS){
       await env.BACKUPS.put(prefix+"/"+name+".aes.json",body.files[name]);
     }
     // Completion marker written LAST to exclude partly uploaded sets.
     await env.BACKUPS.put(prefix+"/manifest.json",body.manifest);
     const proof={repository:REPO,workflow:WORKFLOW,run:claims.run_id,
       attempt:claims.run_attempt,commit:claims.sha,uploaded_at:new Date().toISOString()};
     await env.BACKUPS.put(prefix+"/provenance.json",JSON.stringify(proof));
   }catch(e){return fail(503);}
   return new Response(JSON.stringify({ok:true,count:COLLECTIONS.length,run:claims.run_id}),
     {status:201,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
 }
};
