// Privacy-preserving, Cloudflare D1-backed protection for public statistics writes.
// IP addresses are never stored: only a rotating, secret-peppered minute hash.
// Missing Cloudflare proxy headers / D1 rollout gaps intentionally fail open to
// preserve the Mini App; authentication for owner/admin routes remains separate.
const enc=new TextEncoder();
const toHex=buf=>Array.from(new Uint8Array(buf),x=>x.toString(16).padStart(2,'0')).join('');

export async function allowPublicEvent(env,request,category,{cap=35,now=Date.now()}={}){
 const addr=String(request.headers.get('cf-connecting-ip')||'');
 if(!addr||addr.length>90||!/^[a-z0-9:.]+$/i.test(addr))return true;
 if(!env.DB||!env.TELEGRAM_WEBHOOK_SECRET)return true;
 if(!/^[a-z_]{3,40}$/.test(String(category)))throw Error('invalid_public_event_category');
 const safeCap=Math.max(10,Math.min(120,Number(cap)||35));
 const bucket=Math.floor(now/60000);
 const digest=await crypto.subtle.digest('SHA-256',enc.encode(
  'cine-public-event:v1:'+env.TELEGRAM_WEBHOOK_SECRET+':'+category+':'+bucket+':'+addr
 ));
 try{
  const result=await env.DB.prepare(
   "INSERT INTO cine_public_event_buckets(bucket_hash,hits,expires_at) "+
   "VALUES(?,1,datetime('now','+2 hours')) "+
   "ON CONFLICT(bucket_hash) DO UPDATE SET hits=hits+1 WHERE hits<?"
  ).bind(toHex(digest),safeCap).run();
  return Number(result.meta?.changes||0)===1;
 }catch(e){
  console.warn('cine_public_event_limit_unavailable',String(e?.name||'error'));
  return true;
 }
}
export function publicRateLimited(){
 return Response.json({error:'Trop de requêtes. Réessaie dans une minute.'},
  {status:429,headers:{'retry-after':'60','cache-control':'no-store'}});
}
export async function purgeOldPublicEventBuckets(env){
 if(!env.DB)return {purged:0};
 try{
  const r=await env.DB.prepare(
   "DELETE FROM cine_public_event_buckets WHERE bucket_hash IN "+
   "(SELECT bucket_hash FROM cine_public_event_buckets WHERE expires_at<CURRENT_TIMESTAMP LIMIT 2000)"
  ).run();
  return {purged:Number(r.meta?.changes||0)};
 }catch(e){
  console.warn('cine_public_event_limit_cleanup_unavailable',String(e?.name||'error'));
  return {purged:0,unavailable:true};
 }
}
