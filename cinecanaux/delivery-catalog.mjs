// Stage 1 + 2: verify CineRadar bot membership in owner-approved private libraries.
// Uses the existing Cloudflare Worker TELEGRAM_TOKEN, never logs tokens, never
// publishes or forwards media, and NEVER sets delivery approval on titles/files.
const CHAT_ID=/^-100[0-9]{5,}$/;
const CATEGORIES=new Set(['series','action']);
async function method(env,name,params){
  const response=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/'+name,{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(params),signal:AbortSignal.timeout(6500)
  });
  if(!response.ok)return {ok:false};
  return response.json();
}
export function classifyLibraryBotAccess(identity,chat,member,expectedId){
  if(!identity?.ok||!Number.isSafeInteger(identity.result?.id))return 'error';
  if(!chat?.ok||String(chat.result?.id)!==String(expectedId))return 'not_member';
  if(!member?.ok)return 'not_member';
  const status=String(member.result?.status||'');
  return ['creator','administrator'].includes(status)?'verified':'not_member';
}
export async function auditCineRadarLibraryMembership(env){
  if(!env?.DB||!env.TELEGRAM_TOKEN)throw Error('CineRadar configuration missing');
  const result=await env.DB.prepare(
    "SELECT category,private_chat_id FROM cine_delivery_libraries WHERE rights_attested=1 AND owner_access='verified' ORDER BY category"
  ).all();
  const libraries=result?.results||[];
  if(!libraries.length)return {checked:0,verified:0,blocked:0};
  const identity=await method(env,'getMe',{});
  let verified=0,blocked=0;
  for(const row of libraries){
    if(!CATEGORIES.has(row.category)||!CHAT_ID.test(String(row.private_chat_id||'')))continue;
    let status='error';
    try{
      const chat=await method(env,'getChat',{chat_id:row.private_chat_id});
      const member=chat.ok&&identity.ok?await method(env,'getChatMember',{
        chat_id:row.private_chat_id,user_id:identity.result.id
      }):{ok:false};
      status=classifyLibraryBotAccess(identity,chat,member,row.private_chat_id);
    }catch{status='error';}
    await env.DB.prepare(
      "UPDATE cine_delivery_libraries SET bot_access=?,last_bot_checked_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE category=? AND private_chat_id=?"
    ).bind(status,row.category,row.private_chat_id).run();
    if(status==='verified')verified++;else blocked++;
  }
  return {checked:libraries.length,verified,blocked};
}
