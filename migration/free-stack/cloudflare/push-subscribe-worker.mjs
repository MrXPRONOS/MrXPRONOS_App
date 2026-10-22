const allowed=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000"]);
const reply=(body,status=200,extra={})=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff",...extra}});
export default {async fetch(req,env) {
 const path=new URL(req.url).pathname;
 if(path==="/health")return reply({service:"push-subscribe",storage:env.DB?"configured":"unavailable"});
 if(path!=="/push-subscribe")return reply({error:"not_found"},404);
 const origin=req.headers.get("origin")||"";
 if(!allowed.has(origin))return reply({error:"origin_not_allowed"},403);
 const cors={"Access-Control-Allow-Origin":origin,"Access-Control-Allow-Headers":"content-type, authorization, apikey, x-client-info","Access-Control-Allow-Methods":"POST,OPTIONS","Access-Control-Max-Age":"86400","Vary":"Origin"};
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers:cors});
 if(req.method!=="POST")return reply({error:"method_not_allowed"},405,cors);
 if(!env.DB)return reply({error:"storage_unavailable"},503,cors);
 const size=Number(req.headers.get("content-length")||0);
 if(size>8192)return reply({error:"payload_too_large"},413,cors);
 let data;try{const raw=await req.text();if(raw.length>8192)return reply({error:"payload_too_large"},413,cors);data=JSON.parse(raw);}catch{return reply({error:"invalid_json"},400,cors);}
 const id=data?.user_id,sub=data?.subscription,endpoint=sub?.endpoint,keys=sub?.keys;
 if(typeof id!=="string"||id.length<1||id.length>256||typeof endpoint!=="string"||endpoint.length>2048||!keys||typeof keys.p256dh!=="string"||typeof keys.auth!=="string"||keys.p256dh.length<16||keys.p256dh.length>512||keys.auth.length<16||keys.auth.length>256)return reply({error:"invalid_subscription"},400,cors);
 try{const u=new URL(endpoint);if(u.protocol!=="https:"||!u.hostname||u.username||u.password)throw Error("invalid");}catch{return reply({error:"invalid_endpoint"},400,cors);}
 const now=new Date().toISOString();
 try{
 await env.DB.prepare("INSERT INTO push_subscriptions(user_id,endpoint,keys_json,created_at,updated_at) VALUES (?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,keys_json=excluded.keys_json,updated_at=excluded.updated_at").bind(id,endpoint,JSON.stringify({p256dh:keys.p256dh,auth:keys.auth}),now,now).run();
 return reply({success:true},200,cors);
 }catch{return reply({error:"storage_unavailable"},503,cors);}
}};