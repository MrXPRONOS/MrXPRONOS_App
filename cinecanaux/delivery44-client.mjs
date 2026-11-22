// Ciné Radar — adapter de livraison vers le compte Cloudflare 44.
// Fonctionne uniquement avec un flag explicite. Ne rejoue pas un envoi ambigu.
import {guardTelegramMethod,noteTelegramFloodWait} from './telegram-global-quota.mjs';
const endpoint='https://cine-radar-delivery44.ananiolivier44.workers.dev/internal/v1/copy';
const enc=new TextEncoder();
async function signBody(privateDerBase64,time,body) {
 const der=Uint8Array.from(atob(privateDerBase64), c=>c.charCodeAt(0));
 const key=await crypto.subtle.importKey('pkcs8',der,{name:'ECDSA',namedCurve:'P-256'},false,['sign']);
 const signed=await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},key,enc.encode(time+'.'+body));
 return Array.from(new Uint8Array(signed), x=>x.toString(16).padStart(2,'0')).join('');
}
export function delivery44Enabled(env){return env?.CINE_DELIVERY44_ENABLED==='1' && typeof env?.CINE_DELIVERY44_PRIVATE_KEY === 'string' && env.CINE_DELIVERY44_PRIVATE_KEY.length > 100;}
async function safeLocalFallback(env,payload,status) {
 console.warn('cine_delivery44_pre_send_rejected',status);
 try {
  const response=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/copyMessage',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify(payload),signal:AbortSignal.timeout(14000)
  });
  const data=await response.json();
  const error_code=Number(data?.error_code||response.status);
  const retry_after=Number(data?.parameters?.retry_after||0);
  if(error_code===429)await noteTelegramFloodWait(env,retry_after||30);
  return {ok:response.ok&&data?.ok===true,result:data?.result,
   error_code,code:error_code,retry_after,retry:retry_after};
 }catch{return {ok:false,error_code:502,uncertain:true};}
}
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
 // These gateway errors happen before Telegram is contacted by Worker 44.
 // It is safe to fall back to the original engine in these cases only.
 if([400,401,403,404,405,413,503].includes(response.status))
  return safeLocalFallback(env,payload,response.status);
 let data;try{data=await response.json()}catch{return {ok:false,error_code:502,uncertain:true};}
 if(response.ok&&data?.ok&&Number.isSafeInteger(data?.result?.message_id))
   return {ok:true,result:data.result};
 if(data?.error_code===429)return {ok:false,code:429,retry:Number(data.retry_after||1),error_code:429,retry_after:Number(data.retry_after||1)};
 return {ok:false,error_code:Number(data?.error_code||response.status),uncertain:true};
}
