// Official cross-promotion channels shown inside Cine Radar's discovery grid.
// No third-party tracker, stored visitor identity or external ad scripts.
import {parseTelegramPublicProfile} from "./channel-preview.mjs";

export const PARTNERS=Object.freeze([
 Object.freeze({handle:"actufoot_mrxp",label:"Actu Foot MRXP",summary:"Actualités, résultats et temps forts du football.",icon:"⚽",kind:"football"}),
 Object.freeze({handle:"ActuCrypto24H",label:"Actu Crypto 24H/7",summary:"Mouvements du marché, annonces et tendances crypto.",icon:"₿",kind:"crypto"}),
 Object.freeze({handle:"mrxpronosfr",label:"MR X PRONOS FR",summary:"Pronostics et analyses de rencontres. 18+ · Joue responsablement.",icon:"📊",kind:"pronos"})
]);
const FOUND=new Map(PARTNERS.map(x=>[x.handle.toLowerCase(),x]));
const LIMIT=2200000;
const SAFE_PATH=/^[A-Za-z0-9_./-]{1,350}$/;
const ALLOWED_IMAGE=/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org)\/[^\s"'<>]{15,1200}$/i;
const shorten=(s,max)=>String(s||"").replace(/<[^>]*>/g," ").replace(/[\u0000-\u001f\u007f]/g," ").replace(/\s+/g," ").trim().slice(0,max);
const fetchLimited=(url,opts={},ms=5000)=>fetch(url,{...opts,signal:AbortSignal.timeout(ms)});
const publicMeta=new Map();
function trusted(handle){return FOUND.get(String(handle||"").toLowerCase())||null}

async function fetchProfile(channel){
 const cached=publicMeta.get(channel.handle);
 if(cached&&cached.expires>Date.now())return cached.data;
 let data={name:channel.label,description:channel.summary,image:null};
 // Telegram public preview is independent of whether the bot belongs to the channel.
 try{
  const response=await fetchLimited("https://t.me/"+channel.handle,{headers:{accept:"text/html"}},5500);
  if(response.ok){
   const page=await response.text();
   const info=parseTelegramPublicProfile(page,channel.handle);
   if(info.title)data.name=shorten(info.title,68);
   if(info.description)data.description=shorten(info.description,160);
   if(info.avatar_url&&ALLOWED_IMAGE.test(info.avatar_url))data.image=info.avatar_url;
  }
 }catch(e){console.warn("promo_public_profile_unavailable",channel.kind,String(e?.name||"network").slice(0,45))}
 // Only use Telegram-provided title, description and image; no fabricated metrics.
 publicMeta.set(channel.handle,{data,expires:Date.now()+30*60*1000});
 return data;
}
async function imageFromBot(env,channel){
 if(!env.TELEGRAM_TOKEN)return null;
 const base="https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/";
 const request=async(method,payload)=>{
  const response=await fetchLimited(base+method,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload)},5000);
  if(!response.ok)return null;
  const j=await response.json();return j?.ok?j.result:null;
 };
 const info=await request("getChat",{chat_id:"@"+channel.handle});
 if(!info||String(info.username||"").toLowerCase()!==channel.handle.toLowerCase())return null;
 const id=info.photo?.big_file_id||info.photo?.small_file_id;
 if(typeof id!=="string"||!id||id.length>550)return null;
 const file=await request("getFile",{file_id:id});
 if(!file||typeof file.file_path!=="string"||!SAFE_PATH.test(file.file_path)||file.file_path.includes("..")||file.file_size>LIMIT)return null;
 return fetchLimited("https://api.telegram.org/file/bot"+env.TELEGRAM_TOKEN+"/"+file.file_path,{},7000);
}
async function readImage(res){
 if(!res?.ok)return null;
 if(Number(res.headers.get("content-length")||0)>LIMIT)return null;
 const bytes=await res.arrayBuffer();
 if(!bytes.byteLength||bytes.byteLength>LIMIT)return null;
 const a=new Uint8Array(bytes);
 const mime=a.length>3&&a[0]===255&&a[1]===216&&a[2]===255?"image/jpeg":
  a.length>=8&&a[0]===137&&a[1]===80&&a[2]===78&&a[3]===71?"image/png":
  a.length>=12&&String.fromCharCode(...a.slice(0,4))==="RIFF"&&String.fromCharCode(...a.slice(8,12))==="WEBP"?"image/webp":null;
 return mime?{bytes,mime}:null;
}
export function partnersAsCards(){
 return PARTNERS.map(c=>({handle:c.handle,kind:c.kind,name:c.label,description:c.summary,url:"https://t.me/"+c.handle,avatar:"/assets/promo-avatar/"+c.handle+".jpg",icon:c.icon,
  notice:c.kind==="pronos"?"18+ · Joue responsablement":""}));
}
export async function servePartnerCards(request){
 if(request.method!=="GET")return Response.json({error:"Method not allowed"},{status:405});
 // Only these three whitelisted channels can appear. Description is a public profile, not an ad tag.
 const cards=await Promise.all(PARTNERS.map(async c=>{
  const data=await fetchProfile(c);
  const item=partnersAsCards().find(x=>x.handle===c.handle);
  return {...item,name:data.name||item.name,description:data.description||item.description};
 }));
 return Response.json({items:cards},{headers:{"cache-control":"public,max-age=1200","x-content-type-options":"nosniff"}});
}
export async function servePartnerAvatar(request,env,ctx,handle){
 const channel=trusted(handle);
 if(request.method!=="GET"||!channel)return new Response("Not found",{status:404});
 const cache=typeof caches!=="undefined"?caches.default:null;
 const canonical=new Request(new URL("/assets/promo-avatar/"+channel.handle+".jpg",request.url));
 try{
  const cached=cache?await cache.match(canonical):null;
  if(cached)return cached;
 }catch{}
 let img=null;
 try{
  const profile=await fetchProfile(channel);
  if(profile.image&&ALLOWED_IMAGE.test(profile.image)){
   try{img=await readImage(await fetchLimited(profile.image,{},7000));}catch{}
  }
  if(!img)img=await readImage(await imageFromBot(env,channel));
 }catch(e){console.warn("promo_avatar_unavailable",channel.kind,String(e?.name||"network").slice(0,45))}
 if(!img)return new Response("Avatar unavailable",{status:404,headers:{"cache-control":"no-store","x-content-type-options":"nosniff"}});
 const response=new Response(img.bytes,{headers:{"content-type":img.mime,"cache-control":"public,max-age=21600","x-content-type-options":"nosniff"}});
 if(cache){try{if(ctx?.waitUntil)ctx.waitUntil(cache.put(canonical,response.clone()));else await cache.put(canonical,response.clone());}catch{}}
 return response;
}
