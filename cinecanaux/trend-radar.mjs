// Ciné Radar — tendances et index des trois canaux officiels.
// N'enregistre jamais de fichiers média, clés de fichiers ni données des spectateurs.
export const RADAR_CHANNELS=Object.freeze([
 {kind:'films',username:'CineXFilms_vf'},
 {kind:'series',username:'seriesvf_cinex'},
 {kind:'animes',username:'CineXAnimeFR'}
]);
const TYPES=new Set(['films','series','animes']);
const POSTER=/^https:\/\/(?:image\.tmdb\.org\/t\/p\/w342\/[a-z0-9_-]{8,100}\.(?:jpe?g|png|webp)|s4\.anilist\.co\/file\/anilistcdn\/media\/anime\/cover\/[^\s"'<>]{5,240})$/i;
const TIME_MS=72*60*60*1000;
const clean=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
const plain=s=>String(s||'').replace(/<[^>]+>/g,' ').replace(/&[^;]{1,12};/g,' ').replace(/\s+/g,' ').trim().slice(0,420);
const validSource=s=>/^https:\/\/(?:www\.themoviedb\.org\/(?:movie|tv)\/[0-9]+|anilist\.co\/anime\/[0-9]+)\/?$/.test(String(s||''));
function rowFor(source,kind,data,rank){
 const year=Number(data.year);
 return {id:source+'-'+kind+'-'+data.id,kind,
  title:String(data.title||'').trim().slice(0,130),
  original:String(data.original||'').trim().slice(0,130),
  aliases:String(data.aliases||'').trim().slice(0,300),
  summary:plain(data.summary),year:year>=1900&&year<=2100?year:null,
  poster:POSTER.test(String(data.poster||''))?data.poster:'',
  sourceUrl:validSource(data.sourceUrl)?data.sourceUrl:'',
  source,rank:Math.max(1,Math.min(100,rank))};
}
export function matchRadarTitle(caption,title){
 const body=' '+clean(caption)+' ';
 const variants=[title.title,title.title_original,...String(title.aliases||'').split('|')].map(clean).filter(x=>x.length>=5);
 if(!body.trim()||!variants.length)return 0;
 const years=String(caption||'').match(/\b(?:19|20)\d{2}\b/g)||[];
 if(title.year&&years.length&&years.some(y=>Number(y)!==Number(title.year)))return 0;
 let best=0;
 for(const name of variants){
  if(name.length<5)continue;
  if(body.includes(' '+name+' '))best=Math.max(best,92);
  else{
   const tokens=name.split(' ').filter(x=>x.length>=3);
   if(tokens.length>=2&&tokens.every(x=>body.includes(' '+x+' ')))best=Math.max(best,72);
  }
 }
 return best;
}
const parseList=async response=>{
 if(!response.ok)throw Error('Provider HTTP '+response.status);
 const data=await response.json();
 if(data.errors?.length)throw Error('Provider GraphQL error');
 return data;
};
async function tmdbTrends(env,kind){
 const token=String(env.TMDB_READ_ACCESS_TOKEN||env.TMDB_API_KEY||'').trim();
 if(!token)return {disabled:true,rows:[]};
 const media=kind==='films'?'movie':'tv';
 const url='https://api.themoviedb.org/3/trending/'+media+'/week?language=fr-FR';
 const headers={Accept:'application/json'};
 let target=url;
 if(token.startsWith('eyJ'))headers.Authorization='Bearer '+token;
 else target+='&api_key='+encodeURIComponent(token);
 const body=await parseList(await fetch(target,{headers,signal:AbortSignal.timeout(12000)}));
 return {rows:(body.results||[]).filter(x=>!x.adult).slice(0,20).map((x,i)=>rowFor('tmdb',kind,{
  id:x.id,title:x.title||x.name,original:x.original_title||x.original_name,
  summary:x.overview,year:String(x.release_date||x.first_air_date||'').slice(0,4),
  poster:x.poster_path?'https://image.tmdb.org/t/p/w342'+x.poster_path:'',
  sourceUrl:'https://www.themoviedb.org/'+media+'/'+x.id
 },i+1)).filter(x=>x.title&&x.sourceUrl)};
}
async function anilistTrends(){
 const query='query { Page(page:1,perPage:20) { media(type:ANIME,sort:TRENDING_DESC,isAdult:false) { id title { english romaji native } description(asHtml:false) coverImage { large } siteUrl seasonYear } } }';
 const data=await parseList(await fetch('https://graphql.anilist.co',{method:'POST',headers:{'content-type':'application/json',accept:'application/json'},body:JSON.stringify({query}),signal:AbortSignal.timeout(12000)}));
 return {rows:(data.data?.Page?.media||[]).map((x,i)=>rowFor('anilist','animes',{
  id:x.id,title:x.title?.english||x.title?.romaji||x.title?.native,
  original:x.title?.romaji||x.title?.native,aliases:[x.title?.native,x.title?.romaji].filter(Boolean).join('|'),
  summary:x.description,poster:x.coverImage?.large,year:x.seasonYear,sourceUrl:x.siteUrl
 },i+1)).filter(x=>x.title&&x.sourceUrl)};
}
async function sendOwner(env,message){
 if(!env.TELEGRAM_TOKEN)return {sent:0};
 const owners=(await env.DB.prepare("SELECT user_id FROM admin_users WHERE role='owner' LIMIT 2").all()).results||[];
 let sent=0;
 for(const owner of owners){
  const r=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_TOKEN+'/sendMessage',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({chat_id:owner.user_id,text:message.slice(0,3900),disable_web_page_preview:true}),
   signal:AbortSignal.timeout(7500)});
  if(r.ok&&(await r.json()).ok)sent++;
 }
 return {sent};
}
export async function runTrendRefresh(env,{force=false}={}){
 const result={updated:0,skipped:[],errors:[],notified:0};
 for(const kind of ['films','series','animes']){
  const job='trends_'+kind,stamp=await env.DB.prepare("SELECT last_success_at FROM radar_runs WHERE job_name=?").bind(job).first();
  if(!force&&stamp?.last_success_at&&Date.now()-Date.parse(String(stamp.last_success_at).replace(' ','T')+'Z')<TIME_MS){result.skipped.push(kind);continue;}
  let provider;
  try{provider=kind==='animes'?await anilistTrends():await tmdbTrends(env,kind);}
  catch(e){result.errors.push(kind+': '+String(e).slice(0,90));continue;}
  if(provider.disabled){result.skipped.push(kind+' (TMDB_API_KEY missing)');continue;}
  if(!provider.rows.length){result.errors.push(kind+': empty provider response');continue;}
  let fresh=[];
  for(const item of provider.rows){
   const old=await env.DB.prepare('SELECT id FROM radar_titles WHERE id=?').bind(item.id).first();
   await env.DB.prepare("INSERT INTO radar_titles(id,kind,title,title_original,aliases,summary,year,poster_url,source_url,source,trend_rank) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,title_original=excluded.title_original,aliases=excluded.aliases,summary=excluded.summary,year=excluded.year,poster_url=excluded.poster_url,source_url=excluded.source_url,trend_rank=excluded.trend_rank,last_seen_at=CURRENT_TIMESTAMP")
   .bind(item.id,item.kind,item.title,item.original,item.aliases,item.summary,item.year,item.poster,item.sourceUrl,item.source,item.rank).run();
   if(!old)fresh.push(item);result.updated++;
  }
  await env.DB.prepare("INSERT INTO radar_runs(job_name,last_success_at,last_attempt_at,last_error,last_count) VALUES(?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'',?) ON CONFLICT(job_name) DO UPDATE SET last_success_at=CURRENT_TIMESTAMP,last_attempt_at=CURRENT_TIMESTAMP,last_error='',last_count=excluded.last_count").bind(job,provider.rows.length).run();
  if(fresh.length){
   const message='🎬 CINÉ RADAR — '+({films:'Films',series:'Séries',animes:'Animés'}[kind])+' tendance\n\n'+fresh.slice(0,7).map(x=>'• '+x.title+(x.year?' ('+x.year+')':'')+'\n'+x.sourceUrl+'\nID : '+x.id).join('\n\n')+'\n\nCes fiches sont des suggestions, pas des fichiers vidéo. Tu peux publier tes propres contenus autorisés dans le canal correspondant. Commande /tendances pour revoir la liste.';
   try{result.notified+=(await sendOwner(env,message)).sent;}catch(e){result.errors.push('notification: '+String(e).slice(0,60));}
  }
 }
 if(result.updated)await reconcileRadarPosts(env,120);
 return result;
}
export async function ingestRadarPost(env,update){
 const post=update?.channel_post||update?.edited_channel_post;
 if(!post||post.chat?.type!=='channel'||!Number.isSafeInteger(post.message_id))return {ignored:true};
 const name=String(post.chat.username||'').toLowerCase(),id=String(post.chat.id||'');
 const channels=RADAR_CHANNELS;
 let selected=channels.find(x=>x.username.toLowerCase()===name);
 if(!selected&&id){
  const bound=await env.DB.prepare('SELECT kind,username FROM radar_primary_channels WHERE chat_id=?').bind(id).first();
  if(bound)selected={kind:bound.kind,username:bound.username};
 }
 if(!selected||!id)return {ignored:true};
 // A Telegram-verified channel identity is stable even if its username later changes.
 if(name&&name===selected.username.toLowerCase())
  await env.DB.prepare("UPDATE radar_primary_channels SET chat_id=?,updated_at=CURRENT_TIMESTAMP WHERE kind=? AND (chat_id IS NULL OR chat_id=?)").bind(id,selected.kind,id).run();
 const caption=String(post.caption||post.text||post.video?.file_name||post.document?.file_name||'').slice(0,500);
 const mediaKind=post.video||(/^video\//.test(post.document?.mime_type||''))?'video':post.photo?'photo':'text';
 const timestamp=Number.isFinite(Number(post.date))&&post.date>0?new Date(post.date*1000).toISOString():new Date().toISOString();
 await env.DB.prepare("INSERT INTO radar_posts(chat_id,message_id,kind,username,caption,media_kind,posted_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(chat_id,message_id) DO UPDATE SET caption=excluded.caption,media_kind=excluded.media_kind,updated_at=CURRENT_TIMESTAMP").bind(id,post.message_id,selected.kind,selected.username,caption,mediaKind,timestamp).run();
 return {ignored:false,kind:selected.kind,matched:await matchStoredPost(env,{chat_id:id,message_id:post.message_id,kind:selected.kind,username:selected.username,caption,media_kind:mediaKind})};
}
async function matchStoredPost(env,post){
 const candidates=(await env.DB.prepare('SELECT id,kind,title,title_original,aliases,year FROM radar_titles WHERE kind=? ORDER BY last_seen_at DESC LIMIT 200').bind(post.kind).all()).results||[];
 let matched=0;
 for(const title of candidates){
  const confidence=matchRadarTitle(post.caption,title);
  if(confidence<85)continue;
  const link='https://t.me/'+post.username+'/'+post.message_id;
  await env.DB.prepare("INSERT INTO radar_matches(title_id,chat_id,message_id,kind,message_url,confidence,media_kind) VALUES(?,?,?,?,?,?,?) ON CONFLICT(title_id,chat_id,message_id) DO UPDATE SET confidence=excluded.confidence,media_kind=excluded.media_kind,message_url=excluded.message_url,matched_at=CURRENT_TIMESTAMP").bind(title.id,post.chat_id,post.message_id,post.kind,link,confidence,post.media_kind).run();
  matched++;
 }
 return matched;
}
export async function reconcileRadarPosts(env,limit=150){
 const posts=(await env.DB.prepare("SELECT chat_id,message_id,kind,username,caption,media_kind FROM radar_posts WHERE updated_at>=datetime('now','-90 days') ORDER BY updated_at DESC LIMIT ?").bind(Math.max(1,Math.min(200,limit))).all()).results||[];
 let matches=0;
 for(const post of posts)matches+=await matchStoredPost(env,post);
 return {checked:posts.length,matches};
}
export async function radarFeed(env,kind='all',limit=24){
 const selected=TYPES.has(kind)?kind:'all';
 const rows=(await env.DB.prepare("SELECT t.id,t.kind,t.title,t.summary,t.year,t.poster_url,t.source_url,t.source,t.trend_rank,t.last_seen_at,t.click_count,t.last_clicked_at,m.message_url,m.media_kind,m.confidence,m.matched_at FROM radar_titles t JOIN radar_matches m ON m.title_id=t.id WHERE t.authorized=1 AND m.media_kind='video' AND t.poster_url<>'' AND (?='all' OR t.kind=?) ORDER BY m.matched_at DESC LIMIT 300").bind(selected,selected).all()).results||[];
 const today=Date.now(),seen=new Set();
 const result=rows.filter(r=>{
  if(seen.has(r.id)||!POSTER.test(r.poster_url)||!validSource(r.source_url)||!/^https:\/\/t\.me\/[a-z][a-z0-9_]{4,31}\/[1-9][0-9]{0,12}$/i.test(r.message_url))return false;
  seen.add(r.id);return true;
 }).map(r=>{
  const age=Math.max(0,(today-Date.parse(String(r.last_seen_at).replace(' ','T')+'Z'))/86400000);
  const popularity=Math.log1p(Math.max(0,Number(r.click_count)||0))*24;
  const freshness=Math.max(0,35-age*1.2);
  const trend=Math.max(0,70-Math.max(1,Number(r.trend_rank)||100)*2);
  return {...r,score:popularity+freshness+trend};
 }).sort((a,b)=>b.score-a.score).slice(0,Math.max(1,Math.min(36,limit)));
 return {items:result.map(x=>({id:x.id,kind:x.kind,title:x.title,summary:x.summary,year:x.year,poster:x.poster_url,link:x.message_url,source_url:x.source_url,clicks:Number(x.click_count)||0})),total:result.length};
}
export async function radarApi(env,request){
 const u=new URL(request.url);
 if(request.method==='GET'&&u.pathname==='/api/radar'){
  const data=await radarFeed(env,u.searchParams.get('kind')||'all',Number(u.searchParams.get('limit'))||24);
  return Response.json(data,{headers:{'cache-control':'public,max-age=60'}});
 }
 if(request.method==='POST'&&u.pathname==='/api/radar/click'){
  if(request.headers.get('origin')&&request.headers.get('origin')!==u.origin)return Response.json({error:'Origin denied'},{status:403});
  if(Number(request.headers.get('content-length')||0)>350)return Response.json({error:'Body too large'},{status:413});
  let body;try{body=await request.json()}catch{return Response.json({error:'Invalid JSON'},{status:400})}
  const id=String(body?.id||'');
  if(!/^(?:tmdb-(?:films|series)|anilist-animes)-[0-9]{1,12}$/.test(id))return Response.json({error:'Invalid ID'},{status:400});
  const result=await env.DB.prepare("UPDATE radar_titles SET click_count=click_count+1,last_clicked_at=CURRENT_TIMESTAMP WHERE id=? AND authorized=1 AND EXISTS(SELECT 1 FROM radar_matches m WHERE m.title_id=radar_titles.id AND m.media_kind='video')").bind(id).run();
  return Response.json({ok:Number(result.meta?.changes||0)>0},{headers:{'cache-control':'no-store'}});
 }
 return Response.json({error:'Not found'},{status:404});
}
export async function authorizeRadarTitle(env,id,ownerId){
 if(!/^(?:tmdb-(?:films|series)|anilist-animes)-[0-9]{1,12}$/.test(String(id||'')))return false;
 const owner=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(ownerId).first();
 if(owner?.role!=='owner')return false;
 const result=await env.DB.prepare("UPDATE radar_titles SET authorized=1 WHERE id=?").bind(id).run();
 return Number(result.meta?.changes||0)>0;
}
export async function radarOwnerDigest(env){
 const rows=(await env.DB.prepare("SELECT t.id,t.kind,t.title,t.year,t.authorized,t.source_url,(SELECT COUNT(*) FROM radar_matches m WHERE m.title_id=t.id AND m.media_kind='video') matches FROM radar_titles t ORDER BY t.last_seen_at DESC,t.trend_rank ASC LIMIT 24").all()).results||[];
 return rows.length?'🎬 Tendances Ciné Radar\n'+rows.map(x=>({films:'🎬',series:'📺',animes:'🎌'}[x.kind]+' '+x.title+(x.year?' ('+x.year+')':'')+' — '+(x.authorized?'✅ Autorisé':x.matches?'🔐 À autoriser':'⏳ À publier')+'\n'+x.id+'\n'+x.source_url).join('\n\n'):'Aucune tendance indexée pour le moment. Les sources sont contrôlées au prochain passage.';
}
