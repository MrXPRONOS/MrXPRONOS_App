// Private owner enrollment initiated exclusively by an authenticated Telegram webhook.
// Never grant a privileged role from a URL or an unverified username lookup.
const enc=new TextEncoder();
const hex=a=>[...new Uint8Array(a)].map(x=>x.toString(16).padStart(2,"0")).join("");
async function digest(text){return hex(await crypto.subtle.digest("SHA-256",enc.encode(text)))}
const fixedEqual=(a,b)=>{if(!a||a.length!==b.length)return false;let mismatch=0;for(let i=0;i<a.length;i++)mismatch|=a.charCodeAt(i)^b.charCodeAt(i);return mismatch===0};

export async function tryOwnerClaim(env,update){
 const message=update?.message;
 if(!message?.from||message.chat?.type!=="private")return {handled:false};
 const command=/^\/lieradmin(?:@[A-Za-z0-9_]+)?(?:\s+(.+))?$/i.exec(String(message.text||"").trim());
 if(!command)return {handled:false};
 const reply=async messageText=>{
  const response=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/sendMessage",{
   method:"POST",headers:{"content-type":"application/json"},
   body:JSON.stringify({chat_id:message.chat.id,text:messageText,
    reply_markup:{inline_keyboard:[[{text:"🔐 Ouvrir l'administration",web_app:{url:"https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/admin"}}]]}}),
   signal:AbortSignal.timeout(7000)});
  if(!response.ok)throw Error("Telegram owner claim reply failed");
 };
 const userId=message.from.id,username=String(message.from.username||"").toLowerCase();
 if(!Number.isSafeInteger(userId)||userId<1||username!=="mr_xpronos"){
  await reply("🔒 Cette activation est réservée au compte Telegram @mr_xpronos.");
  return {handled:true,activated:false};
 }
 const code=String(command[1]||"").trim();
 if(!/^[a-zA-Z0-9_-]{20,72}$/.test(code)){
  await reply("Code d'activation invalide ou manquant. Reprends le code sécurisé transmis lors de la configuration.");
  return {handled:true,activated:false};
 }
 const hash=await digest(code);
 const claim=await env.DB.prepare("SELECT code_sha256,expires_at,used_at FROM owner_claim_request WHERE id=1 AND username='mr_xpronos'").first();
 if(!claim||claim.used_at||Date.parse(String(claim.expires_at).replace(" ","T")+"Z")<Date.now()||!fixedEqual(claim.code_sha256,hash)){
  await reply("Code incorrect, expiré ou déjà utilisé. Aucune modification des droits n'a été effectuée.");
  return {handled:true,activated:false};
 }
 // Consume the one-use activation atomically before changing any privileges.
 const consumed=await env.DB.prepare("UPDATE owner_claim_request SET used_at=CURRENT_TIMESTAMP WHERE id=1 AND used_at IS NULL AND code_sha256=? AND expires_at>datetime('now')").bind(hash).run();
 if(Number(consumed.meta?.changes||0)!==1)throw Error("Owner claim race/replay prevented");
 await env.DB.batch([
  env.DB.prepare("DELETE FROM admin_users WHERE role='owner'"),
  env.DB.prepare("INSERT INTO admin_users(user_id,role) VALUES(?,'owner') ON CONFLICT(user_id) DO UPDATE SET role='owner'").bind(userId),
  env.DB.prepare("INSERT INTO bot_settings(setting_key,value) VALUES('profile_version','9') ON CONFLICT(setting_key) DO UPDATE SET value='9',updated_at=CURRENT_TIMESTAMP")
 ]);
 await reply("✅ Compte administrateur activé.\n\nOuvre le bouton ci-dessous depuis cette conversation Telegram. Ne partage pas ton code d'activation.");
 return {handled:true,activated:true,ownerId:userId};
}
