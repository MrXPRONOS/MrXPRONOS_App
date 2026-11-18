// Ciné Radar — tendances et index des trois canaux officiels.
// N'enregistre jamais de fichiers média, clés de fichiers ni données des spectateurs.
export const RADAR_CHANNELS=Object.freeze([
 {kind:'films',username:'CineXFilms_vf'},
 {kind:'series',username:'seriesvf_cinex'},
 {kind:'animes',username:'CineXAnimeFR'}
]);
const TYPES=new Set(['films','series','animes']);
const POSTER=/^https:\/\/(?:image\.tmdb\.org\/t\/p\/w342\/[a-z0-9_-]{8,100}\.(?:jpe?g|png|webp)|s4\.anilist\.co\/file\/anilistcdn\/media\/anime\/cover\/[^\s"'<>]{5,240}|static\.tvmaze\.com\/uploads\/images\/(?:medium_portrait|original)\/[0-9]+\/[0-9]+\.(?:jpe?g|png|webp)|simkl\.in\/posters\/[a-z0-9_/-]{2,160}_m\.jpg)$/i;
const TIME_MS=72*60*60*1000;
const clean=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
const plain=s=>String(s||'').replace(/<[^>]+>/g,' ').replace(/&[^;]{1,12};/g,' ').replace(/\s+/g,' ').trim().slice(0,420);
const validSource=s=>/^https:\/\/(?:www\.themoviedb\.org\/(?:movie|tv)\/[0-9]+|anilist\.co\/anime\/[0-9]+|www\.tvmaze\.com\/shows\/[0-9]+\/[a-z0-9-]+|simkl\.com\/(?:movies|tv|anime)\/[0-9]+(?:\/[a-z0-9-]+)?)\/?$/i.test(String(s||''));
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
 if((!title.kind||title.kind==='films')&&title.year&&years.length&&years.some(y=>Number(y)!==Number(title.year)))return 0;
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
// TVmaze provides a free, current list of series with episodes released today.
// This is an 'upcoming/recently airing' fallback, NOT a TMDB popularity ranking.
async function tvmazeNewSeries(){
 const days=[0,-1,-2],now=Date.now(),picked=new Map();
 for(const day of days){
  const date=new Date(now+day*86400000).toISOString().slice(0,10);
  const response=await fetch('https://api.tvmaze.com/schedule/web?date='+date,{headers:{Accept:'application/json'},signal:AbortSignal.timeout(10500)});
  const items=await parseList(response);
  if(!Array.isArray(items))throw Error('TVmaze schedule is not an array');
  for(const ep of items){
   const show=ep._embedded?.show||ep.show||{};
   if(!Number.isSafeInteger(show.id)||!show.name||!show.url||!show.image?.medium)continue;
   if(show.type==='Animation'&&show.genres?.includes('Anime'))continue; // AniList is authoritative for anime
   if(picked.has(show.id))continue;
   const id=String(show.id);
   const poster=String(show.image.medium).replace(/^http:/,'https:');
   const rank=picked.size+1;
   const title=rowFor('tvmaze','series',{
    id,title:show.name,original:show.name,aliases:'',
    summary:show.summary||'',year:String(show.premiered||'').slice(0,4),
    poster,sourceUrl:show.url
   },rank);
   if(title.title&&title.poster&&title.sourceUrl)picked.set(show.id,title);
   if(picked.size>=20)break;
  }
  if(picked.size>=20)break;
 }
 return {rows:[...picked.values()]};
}
// Official Simkl prebuilt weekly community-watch charts are public and do not need a key.
// Treat Simkl watcher rankings as a distinct source; never label them TMDB trends.
export async function simklPublicTrends(kind){
 const categories={films:'movies',series:'tv',animes:'anime'};
 const category=categories[kind];
 if(!category)throw Error('Invalid Simkl category');
 const url='https://data.simkl.in/discover/trending/'+category+'/week_100.json';
 const data=await parseList(await fetch(url,{headers:{Accept:'application/json','User-Agent':'CineRadar/1.2'},signal:AbortSignal.timeout(12000)}));
 const records=Array.isArray(data)?data:Array.isArray(data?.[category])?data[category]:
   Array.isArray(data?.movies)&&kind==='films'?data.movies:
   Array.isArray(data?.shows)&&kind==='series'?data.shows:
   Array.isArray(data?.anime)&&kind==='animes'?data.anime:[];
 if(!records.length)throw Error('Empty Simkl weekly chart');
 const rows=[];
 for(const item of records.slice(0,60)){
  const entry=item?.movie||item?.show||item?.anime||item;
  const rawUrl=String(entry?.url||item?.url||'').trim();
  const path=/^\/(movies|tv|anime)\/([0-9]{1,12})(?:\/[a-z0-9-]+)?\/?$/i.exec(rawUrl);
  const fullUrl=/^https:\/\/simkl\.com\/(?:movies|tv|anime)\/[0-9]{1,12}(?:\/[a-z0-9-]+)?\/?$/i.test(rawUrl)?rawUrl:
   path?'https://simkl.com'+rawUrl:'';
  const urlId=path?.[2]||/^https:\/\/simkl\.com\/(?:movies|tv|anime)\/([0-9]+)/i.exec(fullUrl)?.[1]||'';
  const id=Number(entry?.ids?.simkl||item?.ids?.simkl||urlId);
  if(!Number.isSafeInteger(id)||id<=0)continue;
  const title=String(entry?.title||item?.title||'').trim();
  const ref=fullUrl;
  const posterKey=String(entry?.poster||item?.poster||'').trim();
  const poster=/^https:\/\/simkl\.in\/posters\//i.test(posterKey)?posterKey:
   /^[a-z0-9_/-]{2,160}$/i.test(posterKey)?'https://simkl.in/posters/'+posterKey+'_m.jpg':'';
  const release=String(entry?.release_date||item?.release_date||'');
  const year=Number(entry?.year||item?.year||release.slice(0,4))||null;
  const x=rowFor('simkl',kind,{id,title,original:title,summary:entry?.overview||item?.overview||'',
   year,poster,sourceUrl:ref},rows.length+1);
  if(x.title&&x.sourceUrl&&x.poster)rows.push(x);
  if(rows.length>=20)break;
 }
 if(!rows.length)throw Error('Simkl chart has no verified URLs/posters');
 return {rows};
}
async function anilistTrends(){
 const query='query { Page(page:1,perPage:20) { media(type:ANIME,sort:TRENDING_DESC,isAdult:false) { id title { english romaji native } description(asHtml:false) coverImage { large } siteUrl seasonYear } } }';
 const data=await parseList(await fetch('https://graphql.anilist.co',{method:'POST',headers:{'content-type':'application/json',accept:'application/json'},body:JSON.stringify({query}),signal:AbortSignal.timeout(12000)}));
 return {rows:(data.data?.Page?.media||[]).map((x,i)=>rowFor('anilist','animes',{
  id:x.id,title:x.title?.english||x.title?.romaji||x.title?.native,
  original:x.title?.romaji||x.title?.native,aliases:[x.title?.native,x.title?.romaji].filter(Boolean).join('|'),
  summary:x.description,poster:x.coverImage?.large,year:x.seasonYear,sourceUrl:'https://anilist.co/anime/'+x.id
 },i+1)).filter(x=>x.title&&x.sourceUrl)};
}
export async function runTrendRefresh(env,{force=false}={}){
 const result={updated:0,skipped:[],errors:[],notified:0};
 for(const kind of ['films','series','animes']){
  const job='trends_'+kind,stamp=await env.DB.prepare("SELECT last_success_at FROM radar_runs WHERE job_name=?").bind(job).first();
  if(!force&&stamp?.last_success_at&&Date.now()-Date.parse(String(stamp.last_success_at).replace(' ','T')+'Z')<TIME_MS){result.skipped.push(kind);continue;}
  let provider;
  try{
   if(kind==='animes'){
    try{provider=await anilistTrends();}
    catch(e){provider=await simklPublicTrends(kind);result.skipped.push('animes: AniList indisponible, tendances Simkl utilisées');}
   }else{
    try{provider=await tmdbTrends(env,kind);}
    catch(e){provider={disabled:true,rows:[]};result.errors.push(kind+': TMDB indisponible, essai Simkl');}
    if(provider.disabled){
     try{provider=await simklPublicTrends(kind);result.skipped.push(kind+': tendances Simkl utilisées (clé TMDB absente)');}
     catch(e){
      if(kind==='series'){
       provider=await tvmazeNewSeries();
       result.skipped.push('series: nouveautés TVmaze utilisées, pas un classement popularité');
      }else throw e;
     }
    }
   }
  }catch(e){result.errors.push(kind+': '+String(e).slice(0,90));continue;}
  if(provider.disabled){result.skipped.push(kind+' (source manquante)');continue;}
  if(!provider.rows.length){result.errors.push(kind+': empty provider response');continue;}
  for(const item of provider.rows){
   await env.DB.prepare("INSERT INTO radar_titles(id,kind,title,title_original,aliases,summary,year,poster_url,source_url,source,trend_rank) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,title_original=excluded.title_original,aliases=excluded.aliases,summary=excluded.summary,year=excluded.year,poster_url=excluded.poster_url,source_url=excluded.source_url,trend_rank=excluded.trend_rank,last_seen_at=CURRENT_TIMESTAMP")
   .bind(item.id,item.kind,item.title,item.original,item.aliases,item.summary,item.year,item.poster,item.sourceUrl,item.source,item.rank).run();
   result.updated++;
  }
  await env.DB.prepare("INSERT INTO radar_runs(job_name,last_success_at,last_attempt_at,last_error,last_count) VALUES(?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'',?) ON CONFLICT(job_name) DO UPDATE SET last_success_at=CURRENT_TIMESTAMP,last_attempt_at=CURRENT_TIMESTAMP,last_error='',last_count=excluded.last_count").bind(job,provider.rows.length).run();

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
 const known=await env.DB.prepare('SELECT chat_id FROM radar_primary_channels WHERE kind=?').bind(selected.kind).first();
 if(known?.chat_id&&String(known.chat_id)!==id)return {ignored:true,reason:'channel_identity_changed'};
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
  if(!/^(?:tmdb-(?:films|series)|anilist-animes|tvmaze-series|simkl-(?:films|series|animes))-[0-9]{1,12}$/.test(id))return Response.json({error:'Invalid ID'},{status:400});
  const result=await env.DB.prepare("UPDATE radar_titles SET click_count=click_count+1,last_clicked_at=CURRENT_TIMESTAMP WHERE id=? AND authorized=1 AND EXISTS(SELECT 1 FROM radar_matches m WHERE m.title_id=radar_titles.id AND m.media_kind='video')").bind(id).run();
  return Response.json({ok:Number(result.meta?.changes||0)>0},{headers:{'cache-control':'no-store'}});
 }
 return Response.json({error:'Not found'},{status:404});
}
export async function authorizeRadarTitle(env,id,ownerId){
 if(!/^(?:tmdb-(?:films|series)|anilist-animes|tvmaze-series|simkl-(?:films|series|animes))-[0-9]{1,12}$/.test(String(id||'')))return false;
 const owner=await env.DB.prepare("SELECT role FROM admin_users WHERE user_id=?").bind(ownerId).first();
 if(owner?.role!=='owner')return false;
 const result=await env.DB.prepare("UPDATE radar_titles SET authorized=1 WHERE id=?").bind(id).run();
 return Number(result.meta?.changes||0)>0;
}
export async function radarOwnerDigest(env){
 const rows=(await env.DB.prepare("SELECT t.id,t.kind,t.title,t.year,t.authorized,t.source_url,(SELECT COUNT(*) FROM radar_matches m WHERE m.title_id=t.id AND m.media_kind='video') matches FROM radar_titles t ORDER BY t.last_seen_at DESC,t.trend_rank ASC LIMIT 10").all()).results||[];
 return rows.length?'🎬 Tendances Ciné Radar\n'+rows.map(x=>({films:'🎬',series:'📺',animes:'🎌'}[x.kind]+' '+x.title+(x.year?' ('+x.year+')':'')+' — '+(x.authorized?'✅ Autorisé':x.matches?'🔐 À autoriser':'⏳ À publier')+'\n'+x.id+'\n'+x.source_url)).join('\n\n'):'Aucune tendance indexée pour le moment. Les sources sont contrôlées au prochain passage.';
}
