// Cine Radar V2 scheduled maintenance: links are never deleted on transient errors.
import {parseTelegramPublicProfile} from './channel-preview.mjs';
import {linkUsername} from './v2.mjs';
const URL_RE=/^[a-z][a-z0-9_]{4,31}$/i;
const safeHost=url=>/^https:\/\/(?:t\.me|telegram\.me)\//i.test(String(url||''));
async function verify(username){
 if(!URL_RE.test(username))return {outcome:'not_found',reason:'invalid_username'};
 const urls=['https://t.me/'+username,'https://t.me/s/'+username],results=[];
 for(const url of urls){
  try{
   const response=await fetch(url,{method:'GET',redirect:'error',signal:AbortSignal.timeout(5500),headers:{'accept':'text/html','user-agent':'CineRadarDirectoryMonitor/2.0'}});
   let parsed=null;
   if(response.ok&&String(response.headers.get('content-type')||'').includes('text/html')){
    parsed=parseTelegramPublicProfile((await response.text()).slice(0,180000),username);
   }
   results.push({status:response.status,parsed});
  }catch(e){results.push({status:0,error:String(e).slice(0,70)})}
 }
 if(results.some(x=>x.status===200&&x.parsed&&(x.parsed.title||x.parsed.description))){
  return {outcome:'reachable',profile:results.find(x=>x.status===200&&x.parsed&&(x.parsed.title||x.parsed.description)).parsed};
 }
 if(results.every(x=>x.status===404))return {outcome:'not_found',reason:'two_404'};
 return {outcome:'unverifiable',reason:'transient_or_private'};
}
async function excluded(env,username){
 return !!await env.DB.prepare('SELECT username FROM channel_exclusions WHERE username=?').bind(username).first();
}
async function addIfPublic(env,username,category){
 if(!URL_RE.test(username)||await excluded(env,username))return {status:'excluded'};
 const url='https://t.me/'+username;
 const found=await env.DB.prepare('SELECT id FROM channels WHERE link=?').bind(url).first();
 if(found)return {status:'listed',id:found.id};
 const checked=await verify(username);
 if(checked.outcome!=='reachable')return {status:checked.outcome};
 const type=['films','series','animes'].includes(category)?category:'films';
 const title=String(checked.profile?.title||username).slice(0,120);
 const description=String(checked.profile?.description||'Canal Telegram public').slice(0,450);
 // No manual approval is required for a technically accessible public directory entry.
 await env.DB.prepare("INSERT INTO channels(title,link,description,content_type,genre,status,rights_confirmed,language,verified_at) VALUES(?,?,?,?,'general','approved',0,'unknown',CURRENT_TIMESTAMP) ON CONFLICT(link) DO NOTHING").bind(title,url,description,type).run();
 const row=await env.DB.prepare('SELECT id FROM channels WHERE link=?').bind(url).first();
 if(!row)return {status:'unverifiable'};
 await env.DB.batch([
  env.DB.prepare("INSERT OR IGNORE INTO channel_index_meta(channel_id,listing_status,link_status,last_checked_at,last_healthy_at) VALUES(?,'listed','reachable',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)").bind(row.id),
  env.DB.prepare('INSERT OR IGNORE INTO channel_categories(channel_id,category) VALUES(?,?)').bind(row.id,type)
 ]);
 return {status:'listed',id:row.id};
}
export async function integrateSuggestions(env,limit=12){
 const rows=(await env.DB.prepare("SELECT username,suggested_category FROM channel_suggestions WHERE status IN ('pending','unverifiable') ORDER BY updated_at ASC LIMIT ?").bind(limit).all()).results||[];
 let indexed=0;
 for(const item of rows){
  const result=await addIfPublic(env,item.username,item.suggested_category);
  if(result.status==='listed')indexed++;
  const state=result.status==='listed'?'indexed':result.status==='excluded'?'rejected':'unverifiable';
  await env.DB.prepare("UPDATE channel_suggestions SET status=?,updated_at=CURRENT_TIMESTAMP WHERE username=?").bind(state,item.username).run();
 }
 return {examined:rows.length,indexed};
}
async function checkOne(env,c){
 const username=linkUsername(c.link);
 const result=username?await verify(username):{outcome:'not_found',reason:'invalid_url'};
 const current=await env.DB.prepare('SELECT consecutive_failures,first_failure_at,listing_status FROM channel_index_meta WHERE channel_id=?').bind(c.id).first();
 const fail=result.outcome==='not_found';
 const failures=fail?Number(current?.consecutive_failures||0)+1:0;
 const first=fail?(current?.first_failure_at||new Date().toISOString()):null;
 const eligible=fail&&failures>=2&&Date.now()-Date.parse(String(first).includes('T')?String(first):String(first).replace(' ','T')+'Z')>=23*3600000;
 const listing=eligible?'hidden':result.outcome==='reachable'?'listed':current?.listing_status||'listed';
 // A 404 cannot establish a moved Telegram username; never guess a replacement URL.
 const jobs=[
  env.DB.prepare(`INSERT INTO channel_index_meta(channel_id,listing_status,link_status,last_checked_at,next_check_at,consecutive_failures,first_failure_at,last_healthy_at,updated_at)
    VALUES(?,?,?,CURRENT_TIMESTAMP,datetime('now',?),?,?,CASE WHEN ?='reachable' THEN CURRENT_TIMESTAMP END,CURRENT_TIMESTAMP)
    ON CONFLICT(channel_id) DO UPDATE SET listing_status=excluded.listing_status,link_status=excluded.link_status,
    last_checked_at=CURRENT_TIMESTAMP,next_check_at=excluded.next_check_at,
    consecutive_failures=excluded.consecutive_failures,first_failure_at=excluded.first_failure_at,
    last_healthy_at=CASE WHEN excluded.link_status='reachable' THEN CURRENT_TIMESTAMP ELSE channel_index_meta.last_healthy_at END,
    updated_at=CURRENT_TIMESTAMP`).bind(c.id,listing,result.outcome,fail?'+1 day':'+4 days',failures,first,result.outcome),
  env.DB.prepare('INSERT INTO channel_checks(channel_id,outcome,old_link,details) VALUES(?,?,?,?)').bind(c.id,result.outcome,c.link,String(result.reason||'').slice(0,80))
 ];
 if(result.outcome==='reachable'&&result.profile?.title){
  jobs.push(env.DB.prepare("INSERT INTO channel_profile_cache(channel_id,title,description,avatar_url,post_image_url,last_post_at,preview_status) VALUES(?,?,?,?,?,?,'available') ON CONFLICT(channel_id) DO UPDATE SET title=excluded.title,description=excluded.description,avatar_url=excluded.avatar_url,post_image_url=excluded.post_image_url,last_post_at=excluded.last_post_at,checked_at=CURRENT_TIMESTAMP,preview_status='available'").bind(c.id,result.profile.title,result.profile.description||'',result.profile.avatar_url||'',result.profile.post_image_url||'',result.profile.last_post_at||null));
 }
 await env.DB.batch(jobs);
 return {id:c.id,outcome:result.outcome,listing};
}
export async function checkDailyLinks(env,limit=10){
 await env.DB.prepare('INSERT OR IGNORE INTO channel_index_meta(channel_id) SELECT id FROM channels').run();
 const rows=(await env.DB.prepare(`SELECT c.id,c.link FROM channels c
  JOIN channel_index_meta m ON m.channel_id=c.id
  WHERE c.status='approved' AND m.listing_status IN ('listed','checking','hidden')
   AND (m.next_check_at IS NULL OR m.next_check_at<=CURRENT_TIMESTAMP)
  ORDER BY CASE WHEN m.link_status='not_found' THEN 0 ELSE 1 END,
           COALESCE(m.last_checked_at,'1970-01-01') ASC,c.id ASC LIMIT ?`).bind(Math.max(1,Math.min(10,limit))).all()).results||[];
 const results=[];
 for(const row of rows){
  try{results.push(await checkOne(env,row));}
  catch(e){console.error('cine_radar_check_failed',row.id,String(e).slice(0,100));results.push({id:row.id,outcome:'error'});}
 }
 return {checked:results.length,results};
}
export async function syncCategoryTags(env){
 await env.DB.prepare("INSERT OR IGNORE INTO channel_categories(channel_id,category) SELECT id,content_type FROM channels WHERE status='approved' AND content_type IN ('films','series','animes')").run();
}
