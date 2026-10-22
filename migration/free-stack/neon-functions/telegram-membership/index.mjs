import {createHash,timingSafeEqual} from "node:crypto";
const origins=new Set(["https://mrxpronos.github.io"]);
const prefix="MX_ADHESION_";
const labelMap={LIVE:"Pronos Live",COUPONS:"Coupons du jour",ACTU_FOOT:"Actu Foot"};
const json=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const escape=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
const safeCompare=(a,b)=>{const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y)};
async function telegram(token,method,payload){
 const r=await fetch("https://api.telegram.org/bot"+token+"/"+method,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});
 const body=await r.json().catch(()=>({}));
 if(!r.ok||body.ok!==true)throw new Error("telegram "+method+" failed");
 return body.result;
}
export default {async fetch(req){
 if(req.method==="GET")return json({service:"telegram-membership",ready:!!(process.env.TELEGRAM_BOT_TOKEN||process.env.FOOTBALL_NEWS_BOT_TOKEN)});
 if(req.method!=="POST")return json({error:"Method not allowed"},405);
 const token=process.env.TELEGRAM_BOT_TOKEN||process.env.FOOTBALL_NEWS_BOT_TOKEN||"";
 if(!token)return json({error:"Telegram not configured"},503);
 const secret="mx_"+createHash("sha256").update(token).digest("hex").slice(0,48);
 const received=req.headers.get("x-telegram-bot-api-secret-token")||"";
 if(!safeCompare(received,secret))return json({error:"Unauthorized"},401);
 let update;try{update=await req.json()}catch{return json({error:"Invalid JSON"},400)}
 const join=update?.chat_join_request;
 if(!join)return json({ok:true,ignored:"not_chat_join_request"});
 const linkName=String(join?.invite_link?.name||"");
 if(!linkName.startsWith(prefix))return json({ok:true,ignored:"not_mrxpronos_membership_link"});
 const chatId=join?.chat?.id,userId=join?.from?.id,userChatId=join?.user_chat_id;
 if(!chatId||!userId)return json({error:"Join request incomplete"},400);
 const key=linkName.slice(prefix.length);
 const label=escape(labelMap[key]||join?.chat?.title||"Mr XPRONOS");
 const user=join.from||{};
 const name=escape([user.first_name,user.last_name].filter(Boolean).join(" ").trim()||user.username||"supporter");
 if(userChatId){
  try{
   await telegram(token,"sendMessage",{
    chat_id:userChatId,parse_mode:"HTML",disable_web_page_preview:true,
    text:"👑 <b>BIENVENUE CHEZ MR XPRONOS</b>\n\n"+
         "<i>Salut <b>"+name+"</b> 👋</i>\n\n"+
         "<blockquote>✅ Ta demande pour <b>"+label+"</b> a bien été reçue.</blockquote>\n\n"+
         "<b>Ton accès est en cours de validation.</b>\n\n"+
         "Une fois dans le canal :\n• <b>active la cloche 🔔</b>\n• consulte les dernières publications\n• reste attentif aux nouvelles alertes\n\n"+
         "<blockquote>⚡ Le bon contenu, au bon moment.</blockquote>\n\n"+
         "<i>Merci de rejoindre la communauté Mr XPRONOS.</i>"
   });
  }catch(e){console.warn("welcome message failed");}
 }
 try{await telegram(token,"approveChatJoinRequest",{chat_id:chatId,user_id:userId});}
 catch{return json({ok:false,error:"approval_failed"},502)}
 return json({ok:true,approved:true,channel:label});
}};