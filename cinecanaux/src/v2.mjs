// Cine Radar V2 — public channel directory, search, quality feedback, and link checks.
// Requires cinecanaux/migrations/001_v2.sql. No media is copied or redistributed.
const CORS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
const LINK=/^https:\/\/t\.me\/([a-z][a-z0-9_]{4,31})\/?$/i;
const TYPES=new Set(['films','series','animes']);
const REASONS=new Set(['wrong_category','misleading','dead_link','spam','copyright','other']);
const json=(body,status=200)=>Response.json(body,{status,headers:CORS});
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
const enc=new TextEncoder();
const hex=u=>Array.from(new Uint8Array(u)).map(b=>b.toString(16).padStart(2,'0')).join('');
function escapeLike(s){return s.replace(/[%_]/g,'');}
function linkUsername(url){return LINK.exec(String(url||'').trim())?.[1]?.toLowerCase()||null;}
async function hmac(key,content){
 const k=await crypto.subtle.importKey('raw',typeof key==='string'?enc.encode(key):key,{name:'HMAC',hash:'SHA-256'},false,['sign']);
 return new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(content)));
}
function equalHex(a,b){
 if(!/^[a-f0-9]{64}$/i.test(a)||a.length!==b.length)return false;
 let mismatch=0;for(let i=0;i<a.length;i++)mismatch|=a.charCodeAt(i)^b.charCodeAt(i);
 return mismatch===0;
}
async function identity(request,env){
 const raw=request.headers.get('X-Telegram-Init-Data')||'';
 if(!raw||raw.length>5000||!env.TELEGRAM_TOKEN||!env.TELEGRAM_WEBHOOK_SECRET)return null;
 const params=new URLSearchParams(raw),hash=params.get('hash')||'',auth=Number(params.get('auth_date')||0);
 if(!auth||Math.abs(Date.now()/1000-auth)>86400)return null;
 const signed=Array.from(params.entries()).filter(([k])=>k!=='hash'&&k!=='signature').sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>k+'='+v).join('\n');
 const secret=await hmac('WebAppData',env.TELEGRAM_TOKEN);
 const signedHash=hex(await hmac(secret,signed));
 if(!equalHex(hash.toLowerCase(),signedHash))return null;
 let user;try{user=JSON.parse(params.get('user')||'null');}catch{return null;}
 if(!Number.isSafeInteger(user?.id)||user.id<=0)return null;
 return hex(await crypto.subtle.digest('SHA-256',enc.encode(env.TELEGRAM_WEBHOOK_SECRET+':'+user.id)));
}
async function bodyJson(request){
 if(Number(request.headers.get('content-length')||0)>4000)throw Error('too_large');
 const raw=await request.text();if(raw.length>4000)throw Error('too_large');
 return JSON.parse(raw);
}
async function limit(env,uid,table,max=15){
 // Simple per-identity daily cap; one review per channel is additionally enforced by a unique index.
 const allowed=new Set(['channel_reviews','channel_reports','channel_suggestions']);
 if(!allowed.has(table))throw Error('Invalid rate table');
 const r=await env.DB.prepare('SELECT COUNT(*) AS n FROM '+table+" WHERE telegram_user_hash=? AND created_at>=datetime('now','-1 day')").bind(uid).first();
 return Number(r?.n||0)<max;
}
const BAD_WORDS=['https://','http://','t.me/','@'];
function sanitizedComment(value){
 const s=String(value||'').trim().slice(0,500);
 return s;
}
function tokenize(query){
 return norm(query).split(/\s+/).filter(Boolean).slice(0,8).map(t=>{
  if(['film','films','cinema','movie','movies'].includes(t))return 'films';
  if(['serie','series','tv','television'].includes(t))return 'series';
  if(['anime','animes','animation','manga'].includes(t))return 'animes';
  if(['vf','francais','french'].includes(t))return 'vf';
  return t;
 });
}
function distanceOne(a,b){
 if(Math.abs(a.length-b.length)>1||a.length<4||b.length<4)return false;
 let i=0,j=0,errors=0;while(i<a.length&&j<b.length){
  if(a[i]===b[j]){i++;j++;continue;}errors++;if(errors>1)return false;
  if(a.length>b.length)i++;else if(a.length<b.length)j++;else{i++;j++;}
 }
 return true;
}
function matchToken(token,c){
 const name=norm(c.title),description=norm(c.description),username=norm(c.link.split('/').pop());
 const kinds=[c.content_type,...String(c.tags||'').split(',')].map(norm);
 if(token==='films'||token==='series'||token==='animes')return kinds.includes(token)?12:0;
 if(token==='vf')return (norm(c.language)==='vf'||norm(c.language)==='fr'||norm(c.language)==='francais')?5:0;
 if(name.includes(token)||username.includes(token))return 10;
 if(norm(c.genre).includes(token)||kinds.some(k=>k.includes(token)))return 7;
 if(description.includes(token))return 3;
 if(name.split(/\W+/).some(w=>distanceOne(token,w)))return 2;
 return 0;
}
function rank(row,tokens){
 let match=0;
 for(const token of tokens){const value=matchToken(token,row);if(!value)return null;match+=value;}
 const count=Number(row.review_count||0),rating=Number(row.rating||0);
 const quality=count?Math.min(1,count/5)*rating:0;
 const activity=row.last_post_at&&Date.now()-Date.parse(row.last_post_at)<30*86400000?1:0;
 const reach=row.link_status==='reachable'?1:0;
 return match*10+quality*2+activity+reach;
}
async function getCatalog(env,{query='',types='',sort='relevant',limit=60,offset=0}={}){
 const selected=String(types||'').split(',').filter(t=>TYPES.has(t));
 const tokens=tokenize(query);
 // A single bounded query for a medium directory; later expand with FTS/pagination if needed.
 const result=await env.DB.prepare(`SELECT c.id,c.title,c.link,c.description,c.content_type,c.genre,c.language,
 c.last_post_at,COALESCE(NULLIF(p.post_image_url,''),NULLIF(p.avatar_url,''),'') AS photo,
 COALESCE(m.listing_status,'listed') AS listing_status,COALESCE(m.link_status,'unknown') AS link_status,
 COALESCE((SELECT group_concat(category,',') FROM channel_categories cc WHERE cc.channel_id=c.id),'') AS tags,
 (SELECT COUNT(*) FROM channel_reviews r WHERE r.channel_id=c.id AND r.visibility IN ('visible','held')) AS review_count,
 (SELECT ROUND(AVG(rating),2) FROM channel_reviews r WHERE r.channel_id=c.id AND r.visibility IN ('visible','held')) AS rating,
 (SELECT ROUND(AVG(CASE WHEN matches_description='yes' THEN 1.0 WHEN matches_description='part' THEN 0.5 ELSE 0 END)*100) FROM channel_reviews r WHERE r.channel_id=c.id AND r.visibility IN ('visible','held')) AS accuracy
 FROM channels c LEFT JOIN channel_profile_cache p ON p.channel_id=c.id
 LEFT JOIN channel_index_meta m ON m.channel_id=c.id
 WHERE c.status='approved' AND COALESCE(m.listing_status,'listed')='listed'
 ORDER BY c.updated_at DESC LIMIT 2500`).all();
 const rows=(result.results||[]).filter(c=>linkUsername(c.link)&&(!selected.length||selected.includes(c.content_type)||String(c.tags||'').split(',').some(t=>selected.includes(t))));
 const ranked=rows.map(c=>({c,score:rank(c,tokens)})).filter(x=>x.score!==null);
 if(sort==='rated')ranked.sort((a,b)=>(Number(b.c.review_count)>=3?Number(b.c.rating):0)-(Number(a.c.review_count)>=3?Number(a.c.rating):0)||b.score-a.score);
 else if(sort==='recent')ranked.sort((a,b)=>(Date.parse(b.c.last_post_at)||0)-(Date.parse(a.c.last_post_at)||0)||b.score-a.score);
 else if(sort==='new')ranked.sort((a,b)=>b.c.id-a.c.id);
 else ranked.sort((a,b)=>b.score-a.score||Number(b.c.review_count)-Number(a.c.review_count)||a.c.id-b.c.id);
 return {total:ranked.length,channels:ranked.slice(offset,offset+limit).map(({c})=>({id:c.id,title:c.title,link:c.link,type:c.content_type,genre:c.genre,language:c.language,photo:c.photo||null,rating:c.review_count?Number(c.rating):null,review_count:Number(c.review_count),accuracy:c.review_count?Number(c.accuracy):null,link_status:c.link_status,last_post_at:c.last_post_at||null}))};
}
async function reviews(env,channelId){
 const info=await env.DB.prepare("SELECT COUNT(*) AS total,ROUND(AVG(rating),2) AS rating,ROUND(AVG(CASE WHEN matches_description='yes' THEN 1.0 WHEN matches_description='part' THEN 0.5 ELSE 0 END)*100) AS accuracy FROM channel_reviews WHERE channel_id=? AND visibility IN ('visible','held')").bind(channelId).first();
 const data=await env.DB.prepare("SELECT rating,matches_description,comment,created_at FROM channel_reviews WHERE channel_id=? AND visibility='visible' AND comment<>'' ORDER BY created_at DESC LIMIT 20").bind(channelId).all();
 return {summary:{count:Number(info?.total||0),rating:info?.rating==null?null:Number(info.rating),accuracy:info?.accuracy==null?null:Number(info.accuracy)},reviews:data.results||[]};
}
async function activeChannel(env,id){
 return env.DB.prepare("SELECT c.id,c.link FROM channels c LEFT JOIN channel_index_meta m ON m.channel_id=c.id WHERE c.id=? AND c.status='approved' AND COALESCE(m.listing_status,'listed')='listed'").bind(id).first();
}
async function postReview(request,env,id,uid){
 const c=await activeChannel(env,id);if(!c)return json({error:'Canal indisponible'},404);
 const data=await bodyJson(request);
 const rating=Number(data.rating),matches=data.matches_description,comment=sanitizedComment(data.comment);
 if(!Number.isInteger(rating)||rating<1||rating>5||!['yes','part','no'].includes(matches)||comment.length>500)return json({error:'Avis invalide'},400);
 const prev=await env.DB.prepare('SELECT id FROM channel_reviews WHERE channel_id=? AND telegram_user_hash=?').bind(id,uid).first();
 if(!prev&&!await limit(env,uid,'channel_reviews',15))return json({error:'Limite quotidienne atteinte'},429);
 // Comments containing links are held for moderation; ratings remain usable.
 const visibility=BAD_WORDS.some(w=>comment.toLowerCase().includes(w))?'held':'visible';
 await env.DB.prepare("INSERT INTO channel_reviews(channel_id,telegram_user_hash,rating,matches_description,comment,visibility) VALUES(?,?,?,?,?,?) ON CONFLICT(channel_id,telegram_user_hash) DO UPDATE SET rating=excluded.rating,matches_description=excluded.matches_description,comment=excluded.comment,visibility=excluded.visibility,updated_at=CURRENT_TIMESTAMP").bind(id,uid,rating,matches,comment,visibility).run();
 return json({ok:true,moderation:visibility==='held'?'pending':'visible'});
}
async function postReport(request,env,id,uid){
 const c=await activeChannel(env,id);if(!c)return json({error:'Canal indisponible'},404);
 const data=await bodyJson(request);
 const reason=String(data.reason||''),details=sanitizedComment(data.details);
 if(!REASONS.has(reason)||details.length>500)return json({error:'Signalement invalide'},400);
 if(!await limit(env,uid,'channel_reports',10))return json({error:'Limite quotidienne atteinte'},429);
 await env.DB.prepare("INSERT INTO channel_reports(channel_id,telegram_user_hash,reason,details) VALUES(?,?,?,?) ON CONFLICT(channel_id,telegram_user_hash,reason) DO UPDATE SET details=excluded.details,status='open',updated_at=CURRENT_TIMESTAMP").bind(id,uid,reason,details).run();
 // Prioritize the next link check for dead-link reports.
 if(reason==='dead_link')await env.DB.prepare("INSERT INTO channel_index_meta(channel_id,next_check_at) VALUES(?,datetime('now')) ON CONFLICT(channel_id) DO UPDATE SET next_check_at=datetime('now')").bind(id).run();
 return json({ok:true});
}
async function postSuggestion(request,env,uid){
 const data=await bodyJson(request);
 const username=linkUsername(data.link),category=String(data.category||'films');
 if(!username||!TYPES.has(category))return json({error:'Lien public ou catégorie invalide'},400);
 if(!await limit(env,uid,'channel_suggestions',10))return json({error:'Limite quotidienne atteinte'},429);
 const excluded=await env.DB.prepare('SELECT username FROM channel_exclusions WHERE username=?').bind(username).first();
 if(excluded)return json({error:'Canal non admissible'},409);
 const existing=await env.DB.prepare('SELECT id FROM channels WHERE LOWER(link)=?').bind('https://t.me/'+username).first();
 if(existing)return json({ok:true,status:'already_listed'});
 await env.DB.prepare('INSERT INTO channel_suggestions(telegram_user_hash,link,username,suggested_category) VALUES(?,?,?,?) ON CONFLICT(username) DO UPDATE SET updated_at=CURRENT_TIMESTAMP').bind(uid,'https://t.me/'+username,username,category).run();
 return json({ok:true,status:'pending'});
}
export async function v2API(env,request){
 const u=new URL(request.url),path=u.pathname,method=request.method;
 if(method==='GET'&&(path==='/api/search'||path==='/api/catalog')){
  const limit=Math.min(80,Math.max(1,Number(u.searchParams.get('limit'))||60));
  const offset=Math.min(10000,Math.max(0,Number(u.searchParams.get('offset'))||0));
  const query=String(u.searchParams.get('q')||'').slice(0,120);
  const types=String(u.searchParams.get('types')||'').slice(0,60);
  const sort=String(u.searchParams.get('sort')||'relevant');
  return json(await getCatalog(env,{query,types,sort,limit,offset}));
 }
 const m=/^\/api\/channels\/(\d+)\/reviews$/.exec(path);
 if(method==='GET'&&m){const id=Number(m[1]);if(!Number.isSafeInteger(id))return json({error:'ID invalide'},400);return json(await reviews(env,id));}
 if(method!=='POST')return json({error:'Méthode non autorisée'},405);
 const uid=await identity(request,env);
 if(!uid)return json({error:'Ouvre Ciné Radar dans Telegram pour participer'},401);
 try{
  if(m)return postReview(request,env,Number(m[1]),uid);
  if(path==='/api/reports'){const data=await bodyJson(request);if(!Number.isSafeInteger(Number(data.channel_id)))return json({error:'ID invalide'},400);const clone=new Request(request.url,{method:'POST',headers:request.headers,body:JSON.stringify(data)});return postReport(clone,env,Number(data.channel_id),uid);}
  if(path==='/api/suggestions')return postSuggestion(request,env,uid);
  return json({error:'Route inconnue'},404);
 }catch(e){console.error('v2_api_failed',String(e).slice(0,100));return json({error:'Requête invalide'},400);}
}
export {getCatalog,linkUsername};
