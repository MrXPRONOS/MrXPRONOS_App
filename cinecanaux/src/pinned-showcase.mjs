// Cine Radar - covers of pinned posts from three verified public channels.
// Bot API getChat returns only the most recent pin, not all historic pins.
// Owner can forward older pinned posts privately to backfill. No video files are copied.
export const PRIMARY_PINS=Object.freeze([
 {kind:"films",username:"CineXFilms_vf"},
 {kind:"series",username:"seriesvf_cinex"},
 {kind:"animes",username:"CineXAnimeFR"}
]);
const KINDS=new Set(PRIMARY_PINS.map(c=>c.kind));
const BAD_IMAGE=/[\s"'<>]/;
const safeFileId=s=>typeof s==="string"&&s.length>20&&s.length<500&&!BAD_IMAGE.test(s);
const tgApi=(env,method,payload)=>fetch("https://api.telegram.org/bot"+env.TELEGRAM_TOKEN+"/"+method,{
 method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload),signal:AbortSignal.timeout(6500)
}).then(async r=>{if(!r.ok)throw Error("Telegram HTTP "+r.status);const j=await r.json();if(!j.ok)throw Error("Telegram "+String(j.error_code||"unknown"));return j.result;});
export function pinCoverFile(message){
 const photo=Array.isArray(message?.photo)?message.photo.filter(p=>safeFileId(p.file_id)&&(!p.file_size||p.file_size<=3500000)).at(-1):null;
 const thumb=message?.video?.thumbnail||message?.document?.thumbnail||message?.animation?.thumbnail;
 const fileId=photo?.file_id||(safeFileId(thumb?.file_id)?thumb.file_id:"");
 return fileId||"";
}
export function pinnedTitle(message){
 const text=String(message?.caption||message?.text||message?.video?.file_name||message?.document?.file_name||"").slice(0,1000);
 const lines=text.split("\n").map(x=>x.trim()).filter(Boolean);
 const candidate=lines.find(x=>x.length>=3&&!/^#(?:films?|s[eé]ries?|anim[eé]s?|cinema)$/i.test(x)&&!/^https?:\/\//i.test(x)&&!/^[@#][a-z0-9_]{3,}$/i.test(x))||"";
 return candidate.replace(/https?:\/\/\S+/g,"").replace(/\.(?:mp4|mkv|mov)$/i,"").trim().slice(0,100)||"Publication épinglée";
}
const messageKind=message=>message.video||message.document?.mime_type?.startsWith("video/")?"video":Array.isArray(message.photo)?"photo":"text";
function asPin(channel,message,source,chatId){
 if(!message||!Number.isSafeInteger(Number(message.message_id))||Number(message.message_id)<1)return null;
 const image=pinCoverFile(message);
 if(!image)return null; // No invented artwork or links.
 return {kind:channel.kind,chatId:String(chatId),id:Number(message.message_id),title:pinnedTitle(message),
  caption:String(message.caption||message.text||"").slice(0,600),image,media:messageKind(message),source};
}
async function insertPin(env,pin){
 if(!pin)return false;
 const known=await env.DB.prepare("SELECT chat_id FROM radar_primary_channels WHERE kind=?").bind(pin.kind).first();
 if(known?.chat_id&&String(known.chat_id)!==pin.chatId)return false;
 await env.DB.prepare("INSERT INTO cine_pinned_posts(kind,chat_id,message_id,title,caption,image_file_id,media_kind,source) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(kind,message_id) DO UPDATE SET title=excluded.title,caption=excluded.caption,image_file_id=CASE WHEN excluded.image_file_id<>'' THEN excluded.image_file_id ELSE cine_pinned_posts.image_file_id END,media_kind=excluded.media_kind,last_seen_at=CURRENT_TIMESTAMP,active=1")
 .bind(pin.kind,pin.chatId,pin.id,pin.title,pin.caption,pin.image,pin.media,pin.source).run();
 return true;
}
export async function syncLatestPinned(env,{force=false}={}){
 const stats={checked:0,found:0,stored:0,errors:[]};
 if(!env.TELEGRAM_TOKEN)return {...stats,errors:["Telegram token unavailable"]};
 await Promise.all(PRIMARY_PINS.map(async channel=>{
  const previous=await env.DB.prepare("SELECT last_attempt_at FROM cine_pins_poll WHERE kind=?").bind(channel.kind).first();
  const at=previous?.last_attempt_at?Date.parse(String(previous.last_attempt_at).replace(" ","T")+"Z"):0;
  if(!force&&at&&Date.now()-at<60*60*1000)return;
  stats.checked++;
  let detail="";let ok=false;
  try{
   const info=await tgApi(env,"getChat",{chat_id:"@"+channel.username});
   const verified=String(info?.username||"").toLowerCase()===channel.username.toLowerCase()&&info?.type==="channel";
   if(!verified)throw Error("Telegram channel identity changed");
   const chatId=String(info.id);
   const known=await env.DB.prepare("SELECT chat_id FROM radar_primary_channels WHERE kind=?").bind(channel.kind).first();
   if(known?.chat_id&&String(known.chat_id)!==chatId)throw Error("Telegram chat ID mismatch");
   await env.DB.prepare("UPDATE radar_primary_channels SET chat_id=?,updated_at=CURRENT_TIMESTAMP WHERE kind=? AND (chat_id IS NULL OR chat_id=?)").bind(chatId,channel.kind,chatId).run();
   const pin=asPin(channel,info.pinned_message,"getchat",chatId);
   if(pin){stats.found++;if(await insertPin(env,pin))stats.stored++;}
   detail=pin?"Most recent pin indexed":"No accessible image in most recent pin";
   ok=true;
  }catch(e){detail=String(e).slice(0,100);stats.errors.push(channel.kind+": "+detail);}
  await env.DB.prepare("INSERT INTO cine_pins_poll(kind,last_attempt_at,last_success_at,detail) VALUES(?,CURRENT_TIMESTAMP,CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,?) ON CONFLICT(kind) DO UPDATE SET last_attempt_at=CURRENT_TIMESTAMP,last_success_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE cine_pins_poll.last_success_at END,detail=excluded.detail")
   .bind(channel.kind,ok?1:0,detail,ok?1:0).run();
 }));
 return stats;
}
export async function ingestPinUpdate(env,update){
 const post=update?.channel_post||update?.edited_channel_post;
 if(!post?.pinned_message||post?.chat?.type!=="channel")return false;
 const channel=PRIMARY_PINS.find(c=>c.username.toLowerCase()===String(post.chat.username||"").toLowerCase());
 if(!channel)return false;
 return insertPin(env,asPin(channel,post.pinned_message,"pin_event",post.chat.id));
}
export async function ingestOwnerForward(env,message){
 if(message?.chat?.type!=="private"||!message?.from?.id)return {handled:false};
 const origin=message.forward_origin;
 if(origin?.type!=="channel"||!origin.chat?.id||!origin.message_id)return {handled:false};
 const admin=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(message.from.id).first();
 if(admin?.role!=="owner")return {handled:false};
 const channel=PRIMARY_PINS.find(x=>x.username.toLowerCase()===String(origin.chat.username||"").toLowerCase());
 if(!channel)return {handled:true,stored:false,reason:"Canal non reconnu"};
 const pinned=asPin(channel,{...message,message_id:origin.message_id},"owner_forward",origin.chat.id);
 const stored=await insertPin(env,pinned);
 return {handled:true,stored,kind:channel.kind,reason:stored?"Affiche enregistrée":"Image ou identité Telegram non vérifiable"};
}
const covers=kind=>KINDS.has(kind);
export async function listPinned(env,{limit=24}={}){
 const rows=(await env.DB.prepare("SELECT p.kind,p.message_id,p.title,p.media_kind,p.click_count,p.last_seen_at,c.username FROM cine_pinned_posts p JOIN radar_primary_channels c ON c.kind=p.kind AND c.chat_id=p.chat_id WHERE p.active=1 AND p.image_file_id<>'' ORDER BY p.last_seen_at DESC LIMIT 200").all()).results||[];
 const dated=rows.map(x=>{
  const age=Math.max(0,(Date.now()-Date.parse(String(x.last_seen_at).replace(" ","T")+"Z"))/86400000);
  return {...x,rank:Math.log1p(Math.max(0,Number(x.click_count)||0))*24+Math.max(0,40-age*.45)};
 }).sort((a,b)=>b.rank-a.rank||b.message_id-a.message_id);
 const kinds=["films","series","animes"],ordered=[],used=new Set();
 // First show one item per category when available, then score-ranked items.
 for(const kind of kinds){const item=dated.find(x=>x.kind===kind);if(item){ordered.push(item);used.add(kind+":"+item.message_id)}}
 for(const row of dated){const id=row.kind+":"+row.message_id;if(!used.has(id)){ordered.push(row);used.add(id)}}
 return {source:"Épingles Telegram",items:ordered.slice(0,Math.max(1,Math.min(32,limit))).map(x=>({
  type:x.kind,title:x.title,poster:"/assets/pin-cover/"+x.kind+"/"+x.message_id+".jpg",
  link:"https://t.me/"+x.username+"/"+x.message_id,
  message_id:x.message_id,clicks:Number(x.click_count)||0
 })),total:dated.length};
}
export async function servePinned(env,request){
 if(request.method!=="GET")return Response.json({error:"Method not allowed"},{status:405});
 // Best-effort initial bootstrap; rate-limited in D1 to one query per channel per hour.
 try{await syncLatestPinned(env);}catch(e){console.warn("pin_bootstrap_unavailable",String(e).slice(0,100));}
 return Response.json(await listPinned(env),{headers:{"cache-control":"public,max-age=120","x-content-type-options":"nosniff"}});
}
export async function servePinCover(env,request,kind,id){
 if(request.method!=="GET"||!covers(kind)||!Number.isSafeInteger(Number(id))||Number(id)<1)return new Response("Invalid cover",{status:400});
 const row=await env.DB.prepare("SELECT image_file_id FROM cine_pinned_posts WHERE kind=? AND message_id=? AND active=1").bind(kind,Number(id)).first();
 if(!row||!safeFileId(row.image_file_id))return new Response("Cover not found",{status:404});
 try{
  const file=await tgApi(env,"getFile",{file_id:row.image_file_id});
  const path=String(file.file_path||"");
  if(!/^[a-zA-Z0-9_./-]{1,300}$/.test(path)||path.includes("..")||Number(file.file_size||0)>5000000)throw Error("Invalid image path or size");
  const res=await fetch("https://api.telegram.org/file/bot"+env.TELEGRAM_TOKEN+"/"+path,{signal:AbortSignal.timeout(7000)});
  const content=String(res.headers.get("content-type")||"").split(";")[0].trim().toLowerCase();
  if(!res.ok||!["image/jpeg","image/png","image/webp"].includes(content))throw Error("Invalid image response");
  const size=Number(res.headers.get("content-length")||0);
  if(size>5000000)throw Error("Cover too large");
  const bytes=await res.arrayBuffer();if(!bytes.byteLength||bytes.byteLength>5000000)throw Error("Cover too large");
  return new Response(bytes,{headers:{"content-type":content,"cache-control":"public,max-age=1800","x-content-type-options":"nosniff"}});
 }catch(e){console.warn("pin_cover_unavailable",kind,Number(id),String(e).slice(0,80));return new Response("Cover temporarily unavailable",{status:503,headers:{"cache-control":"no-store"}});}
}
export async function registerPinClick(env,request){
 if(request.method!=="POST")return Response.json({error:"Method not allowed"},{status:405});
 const origin=request.headers.get("origin"),url=new URL(request.url);
 if(origin&&origin!==url.origin)return Response.json({error:"Origin denied"},{status:403});
 if(Number(request.headers.get("content-length")||0)>300)return Response.json({error:"Too large"},{status:413});
 let data;try{data=await request.json()}catch{return Response.json({error:"Invalid data"},{status:400})}
 if(!covers(data?.kind)||!Number.isSafeInteger(data?.message_id)||data.message_id<1)return Response.json({error:"Invalid pin"},{status:400});
 await env.DB.prepare("UPDATE cine_pinned_posts SET click_count=click_count+1 WHERE kind=? AND message_id=? AND active=1").bind(data.kind,data.message_id).run();
 return Response.json({ok:true},{headers:{"cache-control":"no-store"}});
}
