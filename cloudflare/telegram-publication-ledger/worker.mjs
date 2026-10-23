const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "mrxpronos-telegram-ledger";
const REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED = new Set([
  REPO + "/.github/workflows/neon-telegram-ledger-smoke.yml@refs/heads/main",
  REPO + "/.github/workflows/bsd-v2-telegram-hourly.yml@refs/heads/main",
  REPO + "/.github/workflows/neon-live-telegram.yml@refs/heads/main",
  REPO + "/.github/workflows/shorts-coupons-production.yml@refs/heads/main",
  REPO + "/.github/workflows/shorts-coupons-production-validation.yml@refs/heads/main",
  REPO + "/.github/workflows/accumulator-photo-production.yml@refs/heads/main",
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
 if(!x || !["bsd_v2_hourly","bsd_v2_combo_hourly","live_neon_signal"].includes(x.kind))return false;
 if(typeof x.ref_id!=="string" || x.ref_id.length<1||x.ref_id.length>350)return false;
 if(typeof x.ref_date!=="string" || !/^\d{4}-\d{2}-\d{2}$/.test(x.ref_date))return false;
 return true;
}

const REST_TABLE = "/rest/v1/telegram_sent";
const SAFE_FIELDS = new Set(["id","kind","ref_id","ref_date","sent_at","validation_sent",
 "selection_snapshot","delivery_status","telegram_message_id","published_at",
 "settlement_status","settlement_claimed_at","validated_at","validation_message_id","validation_details"]);
const FILTER_FIELDS = new Set(["id","kind","ref_id","ref_date","validation_sent"]);
function buildWhere(url, forcedFilters) {
 const clauses=[], args=[];
 for(const [name, raw] of [...url.searchParams, ...(forcedFilters||[])]) {
  if(!FILTER_FIELDS.has(name))continue;
  const match=/^(eq|gte|lte)\.(.*)$/s.exec(String(raw));
  if(!match || (match[1]!=="eq" && name!=="ref_date"))throw Error("invalid_filter");
  clauses.push(name+" "+({eq:"=",gte:">=",lte:"<="}[match[1]])+" ?");
  args.push(name==="validation_sent"?(match[2]==="true"?1:match[2]==="false"?0:null):match[2]);
  if(args[args.length-1]===null)throw Error("invalid_boolean");
 }
 return {sql:clauses.length?" WHERE "+clauses.join(" AND "):"",args};
}
async function handleRest(req,env) {
 const url=new URL(req.url);
 const q=url.searchParams;
 try {
  if(req.method==="GET"){
   const {sql,args}=buildWhere(url);
   const requested=(q.get("select")||"id,kind,ref_id,ref_date,validation_sent").split(",");
   if(requested.length>15 || !requested.every(x=>SAFE_FIELDS.has(x)))return json({error:"invalid_select"},400);
   const rawLimit=q.get("limit")||"500",limit=Number(rawLimit);
   if(!Number.isInteger(limit)||limit<1||limit>1000)return json({error:"invalid_limit"},400);
   const order=q.get("order")||"ref_date.asc,id.asc";
   const orderParts=order.split(",").map(x=>x.split("."));
   if(orderParts.length>3||!orderParts.every(x=>x.length===2 && ["id","ref_date","sent_at"].includes(x[0]) && ["asc","desc"].includes(x[1])))return json({error:"invalid_order"},400);
   const orderSQL=orderParts.map(x=>x[0]+" "+x[1].toUpperCase()).join(", ");
   const data=await env.DB.prepare("SELECT "+requested.join(",")+" FROM telegram_sent"+sql+" ORDER BY "+orderSQL+" LIMIT ?").bind(...args,limit).all();
   return json((data.results||[]).map(row=>({...row,validation_sent:row.validation_sent===1})));
  }
  if(req.method==="POST"){
   const txt=await req.text();
   if(txt.length>40000)return json({error:"too_large"},413);
   const row=JSON.parse(txt);
   if(!row||Array.isArray(row)||typeof row!=="object")return json({error:"invalid_row"},400);
   const kind=row.kind, ref_id=row.ref_id, ref_date=row.ref_date;
   if(typeof kind!=="string" || !/^[a-z][a-z0-9_]{0,79}$/.test(kind))return json({error:"invalid_kind"},400);
   if(typeof ref_id!=="string" || !ref_id.length || ref_id.length>1800)return json({error:"invalid_ref"},400);
   if(typeof ref_date!=="string"|| !/^\d{4}-\d{2}-\d{2}$/.test(ref_date))return json({error:"invalid_date"},400);
   const id=crypto.randomUUID();
   const snapshot=row.selection_snapshot==null?null:JSON.stringify(row.selection_snapshot);
   const result=await env.DB.prepare("INSERT OR IGNORE INTO telegram_sent (id,kind,ref_id,ref_date,sent_at,validation_sent,selection_snapshot,delivery_status,settlement_status) VALUES (?,?,?,?,?,?,?,?,?)")
    .bind(id,kind,ref_id,ref_date,new Date().toISOString(),row.validation_sent?1:0,snapshot,row.delivery_status||"legacy",row.settlement_status||"pending").run();
   return json((result.meta?.changes||0)===1?[{id,kind,ref_id,ref_date,validation_sent:!!row.validation_sent}]:[]);
  }
  if(req.method==="DELETE"){
   const {sql,args}=buildWhere(url);
   if(!q.has("kind")||!q.has("ref_id")||!q.has("ref_date"))return json({error:"narrow_delete_required"},400);
   await env.DB.prepare("DELETE FROM telegram_sent"+sql).bind(...args).run();
   return json([]);
  }
  if(req.method==="PATCH"){
   const {sql,args}=buildWhere(url);
   if(!q.has("id")||!q.has("kind"))return json({error:"narrow_update_required"},400);
   const row=JSON.parse(await req.text());
   if(Object.keys(row).length!==1||typeof row.validation_sent!=="boolean")return json({error:"unsupported_patch"},400);
   await env.DB.prepare("UPDATE telegram_sent SET validation_sent=?"+sql).bind(row.validation_sent?1:0,...args).run();
   return json([]);
  }
  return json({error:"method_not_allowed"},405);
 } catch(e){
  if(["invalid_filter","invalid_boolean"].includes(e.message))return json({error:e.message},400);
  return json({error:"ledger_unavailable"},503);
 }
}

export default {
 async fetch(req, env){
  const path = new URL(req.url).pathname;
  if(path==="/health" && req.method==="GET")return json({service:"telegram-ledger",ready:!!env.DB});
  if(path===REST_TABLE) {
    if(!env.DB)return json({error:"storage_unavailable"},503);
    try {await verifyGithub(req);}catch(e){return json({error:"unauthorized"},401);}
    return handleRest(req,env);
  }
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