// Ciné Radar — adapter de livraison vers le compte Cloudflare 44.
// Fonctionne uniquement avec un flag explicite. Ne rejoue pas un envoi ambigu.
import {guardTelegramMethod} from './telegram-global-quota.mjs';
const endpoint='https://cine-radar-delivery44.ananiolivier44.workers.dev/internal/v1/copy';
const enc=new TextEncoder();
async function hmac(secret,time,body){
 const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
 const signature=await crypto.subtle.sign('HMAC',key,enc.encode(time+'.'+body));
 return Array.from(new Uint8Array(signature),x=>x.toString(16).padStart(2,'0')).join('');
}
export function delivery44Enabled(env){return env?.CINE_DELIVERY44_ENABLED==='1';}
export async function remoteCopyMessage(env,requestId,payload){
 if(!/^classic:[0-9]+$/.test(String(requestId))||!env?.TELEGRAM_TOKEN||
   !env?.CINE_BRIDGE_SECRET)return {ok:false,error_code:503,uncertain:true};
 // Le quota reste arbitré dans D1 sur le compte 52, partagé avec les autres envois.
 const quota=await guardTelegramMethod(env,'copyMessage',payload);
 if(quota&&!quota.allowed)return {ok:false,error_code:429,retry_after:quota.retryAfter,quotaDeferred:true};
 const body=JSON.stringify({request_id:requestId,method:'copyMessage',bot_token:env.TELEGRAM_TOKEN,payload});
 const time=String(Date.now());
 let response;
 try{
  response=await fetch(endpoint,{
    method:'POST',
    headers:{'content-type':'application/json','x-cine-time':time,'x-cine-signature':await hmac(env.CINE_BRIDGE_SECRET,time,body)},
    body,
    signal:AbortSignal.timeout(16000)
  });
 }catch{return {ok:false,error_code:502,uncertain:true};}
 let data;try{data=await response.json()}catch{return {ok:false,error_code:502,uncertain:true};}
 if(response.ok&&data?.ok&&Number.isSafeInteger(data?.result?.message_id))
   return {ok:true,result:data.result};
 if(data?.error_code===429)return {ok:false,error_code:429,retry_after:Number(data.retry_after||1)};
 return {ok:false,error_code:Number(data?.error_code||response.status),uncertain:true};
}
