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
 let post_image_url=null;
 for(const fragment of html.matchAll(/tgme_widget_message_photo_wrap[\s\S]{0,1400}?background-image\s*:\s*url\s*\(\s*['"]?(https:\/\/[^'"\s)<>]{10,1050})/gi)){
  const candidate=htmlDecode(fragment[1]).replace(/\\u0026/g,"&");
  if(IMAGE_URL.test(candidate)){post_image_url=candidate;break;}
 }
 // Telegram often shows its own "Telegram" title when a preview is unavailable.
 const trustedTitle=cleanTitle&&!/^telegram(?:\s*messenger)?$/i.test(cleanTitle)?cleanTitle:"";
 // Last visible public posting time, not a guarantee of complete channel history.
 const dates=[...html.matchAll(/<time\b[^>]{0,400}\bdatetime=["']([0-9T:+Z.-]{16,40})["']/gi)]
  .map(x=>Date.parse(x[1])).filter(t=>Number.isFinite(t)&&t<=Date.now()+86400000&&t>Date.now()-3650*86400000);
 return {title:trustedTitle||null,description:description||null,avatar_url:image_url,post_image_url,
  last_post_at:dates.length?new Date(Math.max(...dates)).toISOString():null,
  username,source:"public_telegram_preview"};
}
const errPreview=(channel,username)=>({
 id:channel.id,username,title:channel.title,description:channel.description||null,
 avatar_url:null,post_image_url:null,last_post_at:channel.last_post_at||null,
 link:channel.link,public_posts_url:"https://t.me/s/"+username,preview_status:"unavailable"
});
export async function channelPreview(env,id){
 if(!Number.isSafeInteger(id)||id<1)return {status:400,error:"Identifiant de canal invalide"};
 // One joined D1 read instead of two sequential round trips for every preview.
 const c=await env.DB.prepare(
  "SELECT c.id,c.title,c.link,c.description,c.last_post_at,"+
  "p.title AS cached_title,p.description AS cached_description,"+
  "p.avatar_url AS cached_avatar_url,p.post_image_url AS cached_post_image_url,"+
  "p.last_post_at AS cached_last_post_at,p.checked_at AS cached_checked_at,"+
  "p.preview_status AS cached_preview_status "+
  "FROM channels c LEFT JOIN channel_profile_cache p ON p.channel_id=c.id "+
  "WHERE c.id=? AND c.status='approved'"
 ).bind(id).first();
 if(!c)return {status:404,error:"Canal non disponible"};
 const match=PUBLIC_LINK.exec(c.link||"");
 if(!match)return {status:404,error:"Lien public invalide"};
 const username=match[1],fallback=errPreview(c,username);
 if(c.cached_checked_at){
  const checked=Date.parse(String(c.cached_checked_at).replace(" ","T")+"Z");
  if(Number.isFinite(checked)&&Date.now()-checked<(c.cached_preview_status==="available"?7:1)*86400000) {
   return {status:200,data:{...fallback,
    title:c.cached_title||c.title,description:c.cached_description||c.description,
    avatar_url:c.cached_avatar_url||null,post_image_url:c.cached_post_image_url||null,
    last_post_at:c.cached_last_post_at||c.last_post_at,
    preview_status:c.cached_preview_status||"unavailable",cached:true}};
  }
 }
 // Retrieve the landing preview and the public post preview concurrently.
 // A slow Telegram endpoint cannot block the other endpoint.
 const fetchPublic=async(location)=>{
  try{
   const response=await fetch(location,{method:"GET",redirect:"error",signal:AbortSignal.timeout(3300),
    headers:{"accept":"text/html","user-agent":"Mozilla/5.0 (compatible; CineRadarChannelPreview/1.0)"}});
   if(!response.ok||!String(response.headers.get("content-type")||"").includes("text/html"))return null;
   return parseTelegramPublicProfile((await response.text()).slice(0,350000),username);
  }catch(e){
   console.warn(JSON.stringify({event:"public_profile_fetch_failed",reason:String(e).slice(0,90)}));
   return null;
  }
 };
 const [home,posts]=await Promise.all([
  fetchPublic("https://t.me/"+username),
  fetchPublic("https://t.me/s/"+username)
 ]);
 const gotPage=!!(home||posts);
 const found={
  title:home?.title||posts?.title||null,
  description:home?.description||posts?.description||null,
  avatar_url:home?.avatar_url||posts?.avatar_url||null,
  post_image_url:posts?.post_image_url||home?.post_image_url||null,
  last_post_at:posts?.last_post_at||home?.last_post_at||null
 };
 const final={...fallback,title:found.title||c.title,description:found.description||c.description,
  avatar_url:found.avatar_url,post_image_url:found.post_image_url,last_post_at:found.last_post_at||c.last_post_at,
  preview_status:gotPage&&(found.title||found.description||found.avatar_url)?"available":"unavailable"};
 await env.DB.prepare(
 "INSERT INTO channel_profile_cache(channel_id,title,description,avatar_url,post_image_url,last_post_at,preview_status) VALUES(?,?,?,?,?,?,?) ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title,description=excluded.description,avatar_url=excluded.avatar_url,post_image_url=excluded.post_image_url,last_post_at=excluded.last_post_at,preview_status=excluded.preview_status,checked_at=CURRENT_TIMESTAMP"
 ).bind(c.id,final.title,final.description||"",final.avatar_url||"",final.post_image_url||"",final.last_post_at||null,final.preview_status).run();
 return {status:200,data:final};
}
