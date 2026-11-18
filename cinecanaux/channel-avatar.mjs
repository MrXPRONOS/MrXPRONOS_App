// Same-origin channel avatar proxy. Supports public @handles and verified private channels.
// Never exposes Telegram bot tokens, numeric Telegram chat IDs, or direct file URLs.
const PUBLIC_RE=/^https:\/\/t\.me\/([A-Za-z][A-Za-z0-9_]{4,31})\/?$/i;
const TITLE_MAX=200;
const LIMIT=2_000_000;
const SAFE_FILE=/^[a-zA-Z0-9_./-]{1,350}$/;
const fetchWithin=(url,options={},ms=6500)=>fetch(url,{...options,signal:AbortSignal.timeout(ms)});
const esc=x=>String(x||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
const API={headers:{'Content-Type':'application/json'}};
const themed={films:['#1c3260','#a04f81'],series:['#153e5d','#3294a8'],animes:['#34266a','#b65aab']};
export function avatarFallback(channel){
 const colors=themed[channel?.content_type]||themed.films;
 const title=String(channel?.title||'Ciné Radar').normalize('NFC');
 const first=(Array.from(title.replace(/^[^\p{L}\p{N}]+/u,'').trim())[0]||'C').toUpperCase();
 const safe=esc(first.slice(0,2));
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256"><defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="${colors[0]}"/><stop offset="1" stop-color="${colors[1]}"/></linearGradient></defs><rect width="256" height="256" rx="28" fill="url(#g)"/><circle cx="128" cy="128" r="93" fill="#fff" fill-opacity=".10" stroke="#fff" stroke-opacity=".23" stroke-width="3"/><text x="128" y="153" text-anchor="middle" font-family="Arial,sans-serif" font-size="86" font-weight="800" fill="#fff">${safe}</text><path d="M57 218h142" stroke="#fff" stroke-opacity=".35" stroke-width="6" stroke-linecap="round"/></svg>`;
 return new Response(svg,{status:200,headers:{'content-type':'image/svg+xml; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','x-cineradar-avatar':'fallback'}});
}
async function imageBytes(response){
 if(!response.ok||!String(response.headers.get('content-type')||'').toLowerCase().startsWith('image/'))return null;
 const len=Number(response.headers.get('content-length')||0);
 if(len>LIMIT)return null;
 const bytes=await response.arrayBuffer();
 if(!bytes.byteLength||bytes.byteLength>LIMIT)return null;
 return {bytes,mime:String(response.headers.get('content-type')||'image/jpeg').split(';')[0]};
}
async function telegramAvatar(env,identifier){
 if(!env.TELEGRAM_TOKEN||!identifier)return null;
 const base='https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/';
 const args={method:'POST',headers:{'content-type':'application/json'}};
 const chat=await (await fetchWithin(base+'getChat',{...args,body:JSON.stringify({chat_id:identifier})},6000)).json();
 const fileid=chat?.ok&&chat?.result?.type==='channel'
   ?chat.result?.photo?.big_file_id||chat.result?.photo?.small_file_id:null;
 if(typeof fileid!=='string'||fileid.length>500)return null;
 const file=await (await fetchWithin(base+'getFile',{...args,body:JSON.stringify({file_id:fileid})},6000)).json();
 const path=file?.ok?file.result?.file_path:null;
 if(typeof path!=='string'||!SAFE_FILE.test(path)||path.includes('..'))return null;
 const image=await fetchWithin('https://api.telegram.org/file/bot'+env.TELEGRAM_TOKEN+'/'+path,{},6500);
 return await imageBytes(image);
}
async function repoAvatar(handle,id){
 const base='https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/cinecanaux/assets/avatars/';
 for(const file of ['d1_'+id+'.jpg',handle?handle.toLowerCase()+'.jpg':null]){
  if(!file)continue;
  try{
   const image=await imageBytes(await fetchWithin(base+encodeURIComponent(file),{cf:{cacheEverything:true,cacheTtl:3600}},4500));
   if(image)return image;
  }catch{}
 }
 return null;
}
export async function serveChannelAvatar(request,env,ctx,channelId){
 const id=Number(channelId);
 if(!Number.isSafeInteger(id)||id<1)return new Response('Not found',{status:404});
 const channel=await env.DB.prepare(`SELECT c.id,c.title,c.link,c.content_type,
 f.telegram_chat_id FROM channels c
 LEFT JOIN channel_index_meta m ON m.channel_id=c.id
 LEFT JOIN owned_channel_features f ON f.channel_id=c.id AND f.enabled=1
 WHERE c.id=? AND c.status='approved' AND COALESCE(m.listing_status,'listed')='listed'`).bind(id).first();
 if(!channel)return new Response('Not found',{status:404});
 const fallback=avatarFallback(channel);
 if(new URL(request.url).searchParams.get('fallback')==='1')return fallback;
 const cache=typeof caches!=='undefined'?caches.default:null;
 const key=new Request(new URL('/assets/channel-avatar/'+id+'.jpg',request.url).toString());
 try{
  const hit=cache?await cache.match(key):null;
  if(hit)return hit;
 }catch{}
 const handle=PUBLIC_RE.exec(channel.link||'')?.[1]||null;
 let image=null;
 try{image=await repoAvatar(handle,id);}catch{}
 if(!image){
  const identifier=channel.telegram_chat_id|| (handle?'@'+handle:null);
  try{image=await telegramAvatar(env,identifier);}catch(e){console.warn('avatar_fetch_unavailable',id,e?.name||'error');}
 }
 if(!image)return fallback;
 const result=new Response(image.bytes,{headers:{'content-type':image.mime,'cache-control':'public, max-age=86400','x-content-type-options':'nosniff','x-cineradar-avatar':'telegram'}});
 if(cache){try{if(ctx?.waitUntil)ctx.waitUntil(cache.put(key,result.clone()));else await cache.put(key,result.clone());}catch{}}
 return result;
}
