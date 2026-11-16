// Stable Telegram channel identity; getChat is authoritative when available.
// Never infer a moved channel solely from a matching title or reused username.
const USER=/^[a-z][a-z0-9_]{4,31}$/i;
export async function getPublicChat(env,lookup){
 if(!env?.TELEGRAM_TOKEN)return null;
 try{
  const res=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/getChat',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({chat_id:lookup}),signal:AbortSignal.timeout(6000)
  });
  if(!res.ok)return null;
  const data=await res.json();
  const c=data?.result;
  if(!data?.ok||c?.type!=='channel'||!c.username||!USER.test(c.username)||!Number.isSafeInteger(c.id))return null;
  return {id:String(c.id),username:c.username.toLowerCase(),
   title:String(c.title||c.username).slice(0,120),
   description:String(c.description||'').slice(0,450)};
 }catch(e){console.warn('telegram_chat_identity_unavailable',String(e).slice(0,70));return null;}
}
export function publicUsername(value){
 const username=String(value||'').replace(/^@/,'').trim();
 return USER.test(username)?username.toLowerCase():null;
}
export async function canonicalForChat(env,username,stableId){
 if(stableId){
  const byId=await getPublicChat(env,stableId);
  if(byId){
   if(byId.id!==String(stableId))return {state:'mismatch'};
   return {state:'verified',chat:byId};
  }
  const byUsername=await getPublicChat(env,'@'+username);
  if(byUsername&&byUsername.id!==String(stableId))return {state:'mismatch'};
  if(byUsername)return {state:'verified',chat:byUsername};
  return {state:'unverifiable'};
 }
 const chat=await getPublicChat(env,'@'+username);
 return chat?{state:'verified',chat}:{state:'unverifiable'};
}
export async function safeUpdateChannelLink(env,channelId,oldLink,chat){
 const newUsername=publicUsername(chat?.username);
 if(!newUsername||!chat?.id)return {changed:false,reason:'invalid_identity'};
 const newLink='https://t.me/'+newUsername;
 if(newLink.toLowerCase()===String(oldLink).toLowerCase())return {changed:false,reason:'unchanged'};
 const barred=await env.DB.prepare('SELECT username FROM channel_exclusions WHERE username=?').bind(newUsername).first();
 if(barred)return {changed:false,reason:'excluded'};
 const conflict=await env.DB.prepare('SELECT id FROM channels WHERE LOWER(link)=LOWER(?) AND id<>?').bind(newLink,channelId).first();
 if(conflict)return {changed:false,reason:'conflict'};
 const changed=await env.DB.prepare(
  "UPDATE channels SET link=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND LOWER(link)=LOWER(?) AND NOT EXISTS(SELECT 1 FROM channels WHERE LOWER(link)=LOWER(?) AND id<>?)"
 ).bind(newLink,channelId,oldLink,newLink,channelId).run();
 if(Number(changed.meta?.changes||0)!==1)return {changed:false,reason:'concurrent'};
 const prev=publicUsername(String(oldLink).split('/').pop());
 if(prev)await env.DB.prepare("INSERT INTO channel_aliases(username,channel_id,verified_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(username) DO UPDATE SET channel_id=excluded.channel_id,verified_at=CURRENT_TIMESTAMP").bind(prev,channelId).run();
 return {changed:true,link:newLink};
}
