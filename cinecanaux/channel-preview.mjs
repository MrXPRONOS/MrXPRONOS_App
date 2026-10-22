// Public channel profiles for the Ciné Radar Mini App.
// Read-only metadata from public Telegram preview pages. No login or media download.
const PUBLIC_LINK=/^https:\/\/t\.me\/([A-Za-z][A-Za-z0-9_]{4,31})\/?$/;
const IMAGE_URL=/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org|t\.me)\/[^\s"'<>]{1,1200}$/i;

export function htmlDecode(s) {
 return String(s||"").replace(/&(#(?:x[0-9a-f]+|[0-9]+)|amp|lt|gt|quot|apos|nbsp|#39);/gi,(_,token)=>{
  const t=token.toLowerCase();
  if(t[0]==="#"){
   const v=t[1]==="x"?parseInt(t.slice(2),16):parseInt(t.slice(1),10);
   return Number.isFinite(v)&&v>0&&v<=0x10ffff&&!(v>=0xd800&&v<=0xdfff)?String.fromCodePoint(v):"";
  }
  return ({amp:"&",lt:"<",gt:">",quot:'"',apos:"'",nbsp:" ", "#39":"'"}[t]||"");
 });
}
function plain(s,max=400){
 return htmlDecode(String(s||"").replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim()).slice(0,max).trim();
}
function metaTags(body){
 const result={};
 for(const match of String(body||"").matchAll(/<meta\b[^>]*>/gi)){
  const tag=match[0],attrs={};
  for(const attr of tag.matchAll(/\b([a-z][a-z0-9_-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/gi))attrs[attr[1].toLowerCase()]=htmlDecode(attr[2]??attr[3]??"");
  const key=String(attrs.property||attrs.name||"").toLowerCase();
  if(key&&typeof attrs.content==="string")result[key]=attrs.content;
 }
 return result;
}
export function parseTelegramPublicProfile(page,username){
 const html=String(page||"").slice(0,350000);
 const metadata=metaTags(html);
 const cleanTitle=plain(metadata["og:title"]||metadata["twitter:title"]||"",140).replace(/\s*\|\s*Telegram\s*$/i,"");
 const description=plain(metadata["og:description"]||metadata.description||metadata["twitter:description"]||"",460);
 const avatar=String(metadata["og:image"]||metadata["twitter:image"]||"").trim();
 const image_url=IMAGE_URL.test(avatar)?avatar:null;
 // Telegram often shows its own "Telegram" title when a preview is unavailable.
 const trustedTitle=cleanTitle&&!/^telegram(?:\s*messenger)?$/i.test(cleanTitle)?cleanTitle:"";
 // Last visible public posting time, not a guarantee of complete channel history.
 const dates=[...html.matchAll(/<time\b[^>]{0,400}\bdatetime=["']([0-9T:+Z.-]{16,40})["']/gi)]
  .map(x=>Date.parse(x[1])).filter(t=>Number.isFinite(t)&&t<=Date.now()+86400000&&t>Date.now()-3650*86400000);
 return {title:trustedTitle||null,description:description||null,avatar_url:image_url,
  last_post_at:dates.length?new Date(Math.max(...dates)).toISOString():null,
  username,source:"public_telegram_preview"};
}
const errPreview=(channel,username)=>({
 id:channel.id,username,title:channel.title,description:channel.description||null,
 avatar_url:null,last_post_at:channel.last_post_at||null,
 link:channel.link,public_posts_url:"https://t.me/s/"+username,preview_status:"unavailable"
});
export async function channelPreview(env,id){
 if(!Number.isSafeInteger(id)||id<1)return {status:400,error:"Identifiant de canal invalide"};
 const c=await env.DB.prepare("SELECT id,title,link,description,last_post_at FROM channels WHERE id=? AND status='approved'").bind(id).first();
 if(!c)return {status:404,error:"Canal non disponible"};
 const match=PUBLIC_LINK.exec(c.link||"");
 if(!match)return {status:404,error:"Lien public invalide"};
 const username=match[1],fallback=errPreview(c,username);
 const cached=await env.DB.prepare("SELECT title,description,avatar_url,last_post_at,checked_at,preview_status FROM channel_profile_cache WHERE channel_id=?").bind(id).first();
 if(cached){
  const checked=Date.parse(String(cached.checked_at||"").replace(" ","T")+"Z");
  if(Number.isFinite(checked)&&Date.now()-checked<2*3600000) {
   return {status:200,data:{...fallback,title:cached.title||c.title,description:cached.description||c.description,
    avatar_url:cached.avatar_url||null,last_post_at:cached.last_post_at||c.last_post_at,
    preview_status:cached.preview_status||"unavailable",cached:true}};
  }
 }
 let found={title:null,description:null,avatar_url:null,last_post_at:null},gotPage=false;
 // Fixed Telegram host: a link in the catalog cannot induce arbitrary server-side requests.
 for(const location of ["https://t.me/"+username,"https://t.me/s/"+username]){
  try{
   const response=await fetch(location,{method:"GET",redirect:"error",signal:AbortSignal.timeout(4500),
    headers:{"accept":"text/html","user-agent":"Mozilla/5.0 (compatible; CineRadarChannelPreview/1.0)"}});
   if(!response.ok||!String(response.headers.get("content-type")||"").includes("text/html"))continue;
   const content=(await response.text()).slice(0,350000);
   const parsed=parseTelegramPublicProfile(content,username);
   gotPage=true;
   found={
    title:found.title||parsed.title,
    description:found.description||parsed.description,
    avatar_url:found.avatar_url||parsed.avatar_url,
    last_post_at:parsed.last_post_at||found.last_post_at
   };
   if(found.title&&found.avatar_url&&found.description)break;
  }catch(e){console.warn(JSON.stringify({event:"public_profile_fetch_failed",reason:String(e).slice(0,95)}));}
 }
 const final={...fallback,title:found.title||c.title,description:found.description||c.description,
  avatar_url:found.avatar_url,last_post_at:found.last_post_at||c.last_post_at,
  preview_status:gotPage&&(found.title||found.description||found.avatar_url)?"available":"unavailable"};
 await env.DB.prepare(
 "INSERT INTO channel_profile_cache(channel_id,title,description,avatar_url,last_post_at,preview_status) VALUES(?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title,description=excluded.description,avatar_url=excluded.avatar_url,last_post_at=excluded.last_post_at,preview_status=excluded.preview_status,checked_at=CURRENT_TIMESTAMP"
 ).bind(c.id,final.title,final.description||"",final.avatar_url||"",final.last_post_at||null,final.preview_status).run();
 return {status:200,data:final};
}
