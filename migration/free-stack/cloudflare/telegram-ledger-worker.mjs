const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "mrxpronos-telegram-ledger";
const REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED = new Set([
  REPO + "/.github/workflows/neon-telegram-ledger-smoke.yml@refs/heads/main",
  REPO + "/.github/workflows/bsd-v2-telegram-hourly.yml@refs/heads/main",
]);
const json = (data, status = 200) => new Response(JSON.stringify(data), {
 status, headers: {"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}
});
function decode(input) {
 const b64 = input.replace(/-/g,"+").replace(/_/g,"/");
 const text = atob(b64+"=".repeat((4-b64.length%4)%4));
 return Uint8Array.from(text, c=>c.charCodeAt(0));
}
const asText = bytes => new TextDecoder().decode(bytes);
async function verifyGithub(req) {
 const auth = req.headers.get("authorization") || "";
 if (!auth.startsWith("Bearer ") || auth.length > 15000) throw Error("auth");
 const parts = auth.slice(7).split(".");
 if(parts.length!==3) throw Error("jwt");
 const header = JSON.parse(asText(decode(parts[0])));
 const claims = JSON.parse(asText(decode(parts[1])));
 if(header.alg!=="RS256" || typeof header.kid!=="string") throw Error("algorithm");
 const now = Math.floor(Date.now()/1000);
 if(claims.iss!==ISSUER || claims.aud!==AUDIENCE || claims.repository!==REPO || claims.ref!=="refs/heads/main") throw Error("claims");
 if(!ALLOWED.has(claims.workflow_ref)) throw Error("workflow");
 if(!Number.isSafeInteger(claims.exp) || claims.exp <= now || claims.exp>now+900 || !Number.isSafeInteger(claims.iat) || claims.iat>now+60 || claims.iat<now-900) throw Error("expiry");
 if(typeof claims.run_id!=="string" || !/^\d{4,25}$/.test(claims.run_id)) throw Error("run");
 const jwksResponse = await fetch("https://token.actions.githubusercontent.com/.well-known/jwks", {cf:{cacheTtl:300,cacheEverything:true}});
 if(!jwksResponse.ok) throw Error("jwks");
 const jwks = await jwksResponse.json();
 const keyData = jwks.keys?.find(k=>k.kid===header.kid && k.kty==="RSA");
 if(!keyData) throw Error("key");
 const key = await crypto.subtle.importKey("jwk", keyData, {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
 const content = new TextEncoder().encode(parts[0]+"."+parts[1]);
 const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, decode(parts[2]),content);
 if(!valid)throw Error("signature");
 return claims;
}
function validBody(x) {
 if(!x || !["bsd_v2_hourly","bsd_v2_combo_hourly"].includes(x.kind))return false;
 if(typeof x.ref_id!=="string" || x.ref_id.length<1||x.ref_id.length>350)return false;
 if(typeof x.ref_date!=="string" || !/^\d{4}-\d{2}-\d{2}$/.test(x.ref_date))return false;
 return true;
}
export default {
 async fetch(req, env){
  const path = new URL(req.url).pathname;
  if(path==="/health" && req.method==="GET")return json({service:"telegram-ledger",ready:!!env.DB});
  if(!["/claim","/mark","/release"].includes(path))return json({error:"not_found"},404);
  if(req.method!=="POST")return json({error:"method_not_allowed"},405);
  if(!env.DB)return json({error:"storage_unavailable"},503);
  let claims; try {claims=await verifyGithub(req);}catch(e){return json({error:"unauthorized"},401);}
  const len=Number(req.headers.get("content-length")||0);
  if(len>4096)return json({error:"payload_too_large"},413);
  let x;try{const txt=await req.text();if(txt.length>4096)return json({error:"payload_too_large"},413);x=JSON.parse(txt);}catch{return json({error:"bad_json"},400);}
  if(!validBody(x))return json({error:"invalid_payload"},400);
  const owner=claims.run_id;
  try{
   if(path==="/claim"){
    const n=new Date().toISOString();
    const r=await env.DB.prepare("INSERT OR IGNORE INTO telegram_sent(id,kind,ref_id,ref_date,sent_at,validation_sent,delivery_status,settlement_status,claim_owner) VALUES(?,?,?,?,?,0,'reserved','notstarted',?)")
      .bind(crypto.randomUUID(),x.kind,x.ref_id,x.ref_date,n,owner).run();
    return json({claimed:(r.meta?.changes||0)===1});
   }
   if(path==="/release"){
    const r=await env.DB.prepare("DELETE FROM telegram_sent WHERE kind=? AND ref_id=? AND ref_date=? AND claim_owner=? AND delivery_status='reserved'")
     .bind(x.kind,x.ref_id,x.ref_date,owner).run();
    return json({released:(r.meta?.changes||0)===1});
   }
   const mid=x.telegram_message_id;
   if(!Number.isSafeInteger(mid) || mid<1 || mid>9007199254740991)return json({error:"message_id_required"},400);
   const r=await env.DB.prepare("UPDATE telegram_sent SET delivery_status='sent',telegram_message_id=?,published_at=? WHERE kind=? AND ref_id=? AND ref_date=? AND claim_owner=? AND delivery_status='reserved'")
     .bind(mid,new Date().toISOString(),x.kind,x.ref_id,x.ref_date,owner).run();
   return json({marked:(r.meta?.changes||0)===1});
  }catch(e){return json({error:"storage_error"},503);}
 }
};