// Private GitHub Actions OIDC -> least-privilege Neon PostgreSQL connection broker.
// NO password in source control. NEON_DATABASE_URL is an encrypted Cloudflare secret.
// Only explicit workflow refs on main or the migration branch may access it.
const WORKFLOWS = new Set([
  "bsd-v2-telegram-hourly.yml","bsd-v2-telegram-wins.yml",
  "bsd-v2-bluesky.yml","shorts-coupons-production.yml",
  "shorts-coupons-production-validation.yml","accumulator-photo-production.yml",
  "football-production.yml","api-football-scheduled-fixtures.yml",
  "enrich-live-market-statistics.yml","telegram-channel-monitor-daily.yml",
  "telegram-foot-discovery.yml","editorial-analytics.yml",
  "neon-migration-adapters-tests.yml","clean-cache.yml"
]);
const REFS = new Set([
 "refs/heads/main","refs/heads/migration/neon-cloudflare-adaptation-20261023"
]);
const fail = (status) => new Response(JSON.stringify({error:"Access denied"}), {
 status,headers:{"Content-Type":"application/json","Cache-Control":"no-store",
 "X-Content-Type-Options":"nosniff"}
});
const decode = part => Uint8Array.from(
 atob(part.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(part.length/4)*4,"=")),
 x=>x.charCodeAt(0));
const decoded = part => JSON.parse(new TextDecoder().decode(decode(part)));
async function verifyOIDC(auth) {
 try {
  const token=auth.replace(/^Bearer /,"");
  const parts=token.split(".");
  if(parts.length!==3)return false;
  const header=decoded(parts[0]),claims=decoded(parts[1]);
  if(header.alg!=="RS256"||typeof header.kid!=="string"||!header.kid)return false;
  const now=Math.floor(Date.now()/1000);
  if(claims.iss!=="https://token.actions.githubusercontent.com"||
     claims.aud!=="mrxpronos-neon-ci"||
     claims.repository!=="MrXPRONOS/MrXPRONOS_App"||
     !REFS.has(claims.ref)||
     !Number.isFinite(claims.iat)||claims.iat>now+45||claims.iat<now-900||
     !Number.isFinite(claims.exp)||claims.exp<now||claims.exp>now+1000||
     (claims.nbf!==undefined&&(!Number.isFinite(claims.nbf)||claims.nbf>now)))return false;
  const name=String(claims.workflow_ref||"");
  const prefix="MrXPRONOS/MrXPRONOS_App/.github/workflows/";
  if(!name.startsWith(prefix)||!name.endsWith("@"+claims.ref))return false;
  const relative=name.slice(prefix.length,-("@"+claims.ref).length);
  if(!WORKFLOWS.has(relative))return false;
  const keys=await fetch("https://token.actions.githubusercontent.com/.well-known/jwks",
                        {cf:{cacheTtl:600,cacheEverything:true}});
  if(!keys.ok)return false;
  const jwk=(await keys.json()).keys?.find(k=>k.kid===header.kid&&k.kty==="RSA");
  if(!jwk)return false;
  const key=await crypto.subtle.importKey("jwk",jwk,
    {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  return crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,decode(parts[2]),
                             new TextEncoder().encode(parts[0]+"."+parts[1]));
 }catch(_){return false;}
}
export default {
 async fetch(request,env) {
  const u=new URL(request.url);
  if(u.pathname!=="/neon-dsn"||request.method!=="GET")return fail(404);
  if(request.headers.has("Origin"))return fail(403);
  const auth=request.headers.get("Authorization")||"";
  if(!/^Bearer [A-Za-z0-9_\-.]+$/.test(auth)||!(await verifyOIDC(auth)))return fail(403);
  const dsn=env.NEON_DATABASE_URL;
  if(!dsn||!/^postgres(ql)?:\/\/mrxpronos_ci:/.test(dsn)||
     !dsn.includes(".neon.tech")||!dsn.includes("/mrxpronos"))
    return fail(503);
  return new Response(JSON.stringify({database_url:dsn}),{
    status:200,headers:{"Content-Type":"application/json",
    "Cache-Control":"private, no-store, max-age=0",
    "Pragma":"no-cache","X-Content-Type-Options":"nosniff"}
  });
 }
};
