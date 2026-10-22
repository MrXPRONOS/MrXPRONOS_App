const allowedInvite = "MX_ADHESION_";
const channels = {LIVE:"Pronos Live",COUPONS:"Coupons du jour",ACTU_FOOT:"Actu Foot"};
function answer(value,status=200){return new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}});}
function safe(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
async function sha256(s){const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s));return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,"0")).join("");}
async function telegram(token,method,body){const r=await fetch("https://api.telegram.org/bot"+token+"/"+method,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:AbortSignal.timeout(12000)});const j=await r.json().catch(()=>({}));if(!r.ok||j.ok!==true)throw new Error("Telegram request failed: "+method+" status "+r.status);return j.result;}
export default {async fetch(req){
  if(req.method==="GET")return answer({ok:true,service:"telegram-membership",configured:Boolean(process.env.TELEGRAM_BOT_TOKEN||process.env.FOOTBALL_NEWS_BOT_TOKEN)});
  if(req.method!=="POST")return answer({error:"method_not_allowed"},405);
  const token=process.env.TELEGRAM_BOT_TOKEN||process.env.FOOTBALL_NEWS_BOT_TOKEN||"";
  if(!token)return answer({error:"bot_not_configured"},503);
  const expected="mx_"+(await sha256(token)).slice(0,48);
  if(req.headers.get("x-telegram-bot-api-secret-token")!==expected)return answer({error:"unauthorized"},401);
  const size=Number(req.headers.get("content-length")||0);if(size>65536)return answer({error:"payload_too_large"},413);
  let update;try{const txt=await req.text();if(txt.length>65536)return answer({error:"payload_too_large"},413);update=JSON.parse(txt);}catch{return answer({error:"invalid_json"},400);}
  const join=update?.chat_join_request;if(!join)return answer({ok:true,ignored:"not_join_request"});
  const invite=String(join?.invite_link?.name||"");if(!invite.startsWith(allowedInvite))return answer({ok:true,ignored:"other_invite"});
  const chat=join.chat?.id, user=join.from?.id; if(!chat||!user)return answer({error:"invalid_join_request"},400);
  const label=channels[invite.slice(allowedInvite.length)]||join.chat?.title||"Mr XPRONOS";
  const person=safe([join.from?.first_name,join.from?.last_name].filter(Boolean).join(" ")||join.from?.username||"supporter");
  if(join.user_chat_id){try{await telegram(token,"sendMessage",{chat_id:join.user_chat_id,parse_mode:"HTML",disable_web_page_preview:true,text:"👑 <b>BIENVENUE CHEZ MR XPRONOS</b>\n\nSalut <b>"+person+"</b> 👋\nTa demande pour <b>"+safe(label)+"</b> est bien reçue.\nTon accès est en cours de validation.\nActive la cloche 🔔 après ton adhésion."});}catch(e){console.warn("welcome_message_failed",String(e));}}
  try{await telegram(token,"approveChatJoinRequest",{chat_id:chat,user_id:user});}catch(e){console.error("approval_failed",String(e));return answer({ok:false,error:"approval_failed"},502);}
  return answer({ok:true,approved:true,channel:String(label)});
}};