// Ciné Radar — adapter de livraison vers le compte Cloudflare 44.
// Fonctionne uniquement avec un flag explicite. Ne rejoue pas un envoi ambigu.
import {guardTelegramMethod} from './telegram-global-quota.mjs';
const endpoint='https://cine-radar-delivery44.ananiolivier44.workers.dev/internal/v1/copy';
const enc=new TextEncoder();
async function signBody(privateDerBase64,time,body) {
 const der=Uint8Array.from(atob(privateDerBase64), c=>c.charCodeAt(0));
 const key=await crypto.subtle.importKey('pkcs8',der,{name:'ECDSA',namedCurve:'P-256'},false,['sign']);
 const signed=await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},key,enc.encode(time+'.'+body));
 return Array.from(new Uint8Array(signed), x=>x.toString(16).padStart(2,'0')).join('');
}
export function delivery44Enabled(env){return env?.CINE_DELIVERY44_ENABLED==='1';}
export async function remoteCopyMessage(env,requestId,payload){
 if(!/^(classic|library|franchise|series):[0-9]+(?::[0-9]+)?$/.test(String(requestId))||!env?.TELEGRAM_TOKEN||
   !env?.CINE_DELIVERY44_PRIVATE_KEY)return {ok:false,error_code:503,uncertain:true};
 // Le quota reste arbitré dans D1 sur le compte 52, partagé avec les autres envois.
 const quota=await guardTelegramMethod(env,'copyMessage',payload);
 if(quota&&!quota.allowed)return {ok:false,code:429,retry:quota.retryAfter,error_code:429,retry_after:quota.retryAfter,quotaDeferred:true};
 const body=JSON.stringify({request_id:requestId,method:'copyMessage',bot_token:env.TELEGRAM_TOKEN,payload});
 const time=String(Date.now());
 let response;
 try{
  response=await fetch(endpoint,{
    method:'POST',
    headers:{'content-type':'application/json','x-cine-time':time,'x-cine-signature':await signBody(env.CINE_DELIVERY44_PRIVATE_KEY,time,body)},
    body,
    signal:AbortSignal.timeout(16000)
  });
 }catch{return {ok:false,error_code:502,uncertain:true};}
 let data;try{data=await response.json()}catch{return {ok:false,error_code:502,uncertain:true};}
 if(response.ok&&data?.ok&&Number.isSafeInteger(data?.result?.message_id))
   return {ok:true,result:data.result};
 if(data?.error_code===429)return {ok:false,code:429,retry:Number(data.retry_after||1),error_code:429,retry_after:Number(data.retry_after||1)};
 return {ok:false,error_code:Number(data?.error_code||response.status),uncertain:true};
}
