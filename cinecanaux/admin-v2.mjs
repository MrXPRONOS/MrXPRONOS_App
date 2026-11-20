// Private Ciné Radar moderation API. All requests require valid Telegram Mini App initData
// AND a matching Telegram user ID in the existing admin_users table.
import {verifiedIdentity,telegramAuthStatus,linkUsername} from './v2.mjs';
import {checkDailyLinks} from './maintenance-v2.mjs';
import {runLoggedJob} from './job-log.mjs';
import {adminAnalytics} from './analytics.mjs';
import {launchFunnelStats} from './launch-funnel.mjs';
import {broadcastAdminAPI,deliverBroadcastBatch} from './broadcast.mjs';
import {bindPrimaryRadarChannels,missingRadarTitles,notifyOwnerMissingRadarTitles} from './radar-owner-ops.mjs';
import {runTrendRefresh,reconcileRadarPosts,authorizeRadarTitle,radarOwnerDigest} from './trend-radar.mjs';
import {initializeProfile,invalidateDirectoryCache} from './radar-lean.mjs';
import {ownerPinnedList,ownerRemovePin} from './pinned-showcase.mjs';
import {adminDeliveryAction} from './cinex-delivery.mjs';
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
async function verifyAdmin(request,env){
 const u=await verifiedIdentity(request,env);
 if(!u)return null;
 const admin=await env.DB.prepare('SELECT role FROM admin_users WHERE user_id=?').bind(u.telegram_id).first();
 if(admin?.role==='owner')return u;
 // Recovery for the designated account: identity AND username are validated
 // inside the HMAC-signed Telegram initData. Never trust a URL-supplied handle.
 if(u.telegram_username!=='mr_xpronos')return null;
 // Rebind the unique owner to the authenticated Telegram user ID, removing
 // obsolete owner rows; this does not grant access by plain username alone.
 await env.DB.batch([
  env.DB.prepare("DELETE FROM admin_users WHERE role='owner' AND user_id<>?").bind(u.telegram_id),
  env.DB.prepare("INSERT INTO admin_users(user_id,role) VALUES(?,'owner') ON CONFLICT(user_id) DO UPDATE SET role='owner'").bind(u.telegram_id)
 ]);
 return u;
}
// Owner can edit directory metadata, but not bypass exclusion or rights checks.
function validAdminChannel(data){
 const title=String(data.title||'').trim(),description=String(data.description||'').trim();
 const content_type=String(data.content_type||''),genre=String(data.genre||'').trim().toLowerCase();
 const language=String(data.language||'').trim();
 if(title.length<3||title.length>120)return {error:'Nom du canal : entre 3 et 120 caractères.'};
 if(description.length>600)return {error:'Description limitée à 600 caractères.'};
 if(!['films','series','animes'].includes(content_type))return {error:'Catégorie invalide.'};
 if(!/^[a-z0-9_-]{1,40}$/.test(genre))return {error:'Genre invalide (lettres minuscules, chiffres ou tirets).'};
 if(!/^[A-Za-z0-9 ,/+-]{1,30}$/.test(language))return {error:'Langue invalide.'};
 return {title,description,content_type,genre,language};
}
async function parseBody(req){
 if(Number(req.headers.get('content-length')||0)>4096)throw Error('oversized');
 const text=await req.text();if(text.length>4096)throw Error('oversized');
 return JSON.parse(text);
}
export async function adminAPI(env,request,ctx){
 let admin;
 try{admin=await verifyAdmin(request,env)}
 catch(e){console.warn('cine_admin_verify_error',String(e?.name||'Error'));return json({error:'Vérification administrateur indisponible',code:'server_error'},503)}
 if(!admin){
  const status=await telegramAuthStatus(request,env);
  // Do not disclose the signed identity, role records, bot token or raw initData.
  return json({error:'Accès réservé',code:status==='verified'?'owner_not_linked':status},status==='server_configuration'?503:403);
 }
 const u=new URL(request.url),path=u.pathname;
 if(request.method==='GET'&&path==='/api/admin/access')return json({ok:true,role:'owner'});
 if(request.method==='GET'&&path==='/api/admin/cinex/catalog'){
  const [flag,entries,libraries]=await Promise.all([
   env.DB.prepare("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first(),
   env.DB.prepare("SELECT t.title_key,t.category,t.display_title,t.content_kind,t.approval,m.season_number,COUNT(m.source_message_id) AS media_count,COALESCE(l.enabled,0) AS link_enabled,l.token FROM cine_delivery_titles t LEFT JOIN cine_delivery_media m ON m.title_key=t.title_key AND m.category=t.category LEFT JOIN cine_delivery_links l ON l.title_key=t.title_key AND l.category=t.category AND l.season_key=COALESCE(m.season_number,0) GROUP BY t.title_key,m.season_number ORDER BY t.category,t.display_title,m.season_number LIMIT 200").all(),
   env.DB.prepare("SELECT category,owner_access,bot_access,observed_videos,last_scanned_at FROM cine_delivery_libraries ORDER BY category").all()
  ]);
  return json({enabled:flag?.value==='1',entries:entries.results||[],libraries:libraries.results||[]});
 }

 if(request.method==='GET'&&path==='/api/admin/channel-list'){
  const rows=await env.DB.prepare("SELECT c.id,c.title,c.link,c.description,c.content_type,c.genre,c.language,c.status,COALESCE(m.listing_status,'listed') listing_status,COALESCE(m.link_status,'unknown') link_status FROM channels c LEFT JOIN channel_index_meta m ON m.channel_id=c.id ORDER BY c.updated_at DESC,c.id DESC LIMIT 350").all();
  return json({channels:rows.results||[]});
 }
 if(request.method==='GET'&&path==='/api/admin/launch-funnel')return json(await launchFunnelStats(env));
 if(request.method==='GET'&&path==='/api/admin/pins')return json(await ownerPinnedList(env));
 if(request.method==='GET'&&path==='/api/admin/radar-ops'){
  const [missing,channels,digest]=await Promise.all([
   missingRadarTitles(env,admin.telegram_id,{limit:24}),
   env.DB.prepare('SELECT kind,username,chat_id IS NOT NULL AS connected FROM radar_primary_channels ORDER BY kind').all(),
   radarOwnerDigest(env)
  ]);
  return json({missing,channels:channels.results||[],digest});
 }
 if(path==='/api/admin/broadcast-image'||path==='/api/admin/broadcasts'||/^\/api\/admin\/broadcasts\/\d+\/(?:preview|start|cancel)$/.test(path)){
  const answer=await broadcastAdminAPI(env,request,admin.telegram_id);
  if(request.method==='POST'&&/\/start$/.test(path)&&answer.ok&&ctx?.waitUntil){
   ctx.waitUntil(deliverBroadcastBatch(env).catch(e=>console.warn('broadcast_batch_failed',String(e?.name||'error'))));
  }
  return answer;
 }
 if(request.method==='GET'&&path==='/api/admin/analytics')return adminAnalytics(env,request);
 if(request.method==='GET'&&path==='/api/admin/overview'){
  const items=await env.DB.prepare(`SELECT
  (SELECT COUNT(*) FROM channels WHERE status='approved') AS indexed,
  (SELECT COUNT(*) FROM channel_index_meta WHERE listing_status='listed') AS visible,
  (SELECT COUNT(*) FROM channel_index_meta WHERE listing_status='hidden') AS hidden,
  (SELECT COUNT(*) FROM channel_reviews) AS reviews,
  (SELECT COUNT(*) FROM channel_reports WHERE status IN ('open','reviewing')) AS open_reports,
  (SELECT COUNT(*) FROM channel_suggestions WHERE status IN ('pending','unverifiable')) AS pending_suggestions,
  (SELECT COUNT(*) FROM channel_checks WHERE checked_at>=datetime('now','-1 day')) AS checks_24h,
  (SELECT COALESCE(SUM(searches),0) FROM search_daily_stats WHERE date_utc=date('now')) AS searches_today,
  (SELECT COALESCE(SUM(empty_results),0) FROM search_daily_stats WHERE date_utc=date('now')) AS empty_searches_today`).first();
  return json(items||{});
 }
 if(request.method==='GET'&&path==='/api/admin/jobs'){
  const r=await env.DB.prepare("SELECT id,job_name,started_at,finished_at,status,examined,inserted,updated,errors,details FROM automated_job_runs ORDER BY id DESC LIMIT 35").all();
  return json({jobs:r.results||[]});
 }
 if(request.method==='GET'&&path==='/api/admin/reports'){
  const r=await env.DB.prepare("SELECT r.id,r.channel_id,c.title,c.link,r.reason,r.details,r.status,r.created_at FROM channel_reports r JOIN channels c ON c.id=r.channel_id WHERE r.status IN ('open','reviewing') ORDER BY r.created_at DESC LIMIT 60").all();
  return json({reports:r.results||[]});
 }
 if(request.method==='GET'&&path==='/api/admin/reviews'){
  const result=await env.DB.prepare("SELECT r.id,r.channel_id,c.title,r.rating,r.matches_description,r.comment,r.visibility,r.created_at FROM channel_reviews r JOIN channels c ON c.id=r.channel_id ORDER BY r.created_at DESC LIMIT 60").all();
  return json({reviews:result.results||[]});
 }
 if(request.method==='GET'&&path==='/api/admin/suggestions'){
  const r=await env.DB.prepare("SELECT id,username,link,suggested_category,status,created_at FROM channel_suggestions ORDER BY updated_at DESC LIMIT 80").all();
  return json({suggestions:r.results||[]});
 }
 if(request.method!=='POST')return json({error:'Méthode inconnue'},405);
 try{
  const data=await parseBody(request);
  if(path==='/api/admin/channels'){
   if(data.action!=='add')return json({error:'Action inconnue'},400);
   if(data.rights_confirmed!==true)return json({error:'Confirme que tu disposes du droit de référencer ce canal.'},400);
   const fields=validAdminChannel(data);
   if(fields.error)return json({error:fields.error},400);
   const username=linkUsername(String(data.link||'').trim());
   if(!username)return json({error:'Entre un lien public Telegram valide (https://t.me/nomducanal).'},400);
   const normalized='https://t.me/'+username;
   const excluded=await env.DB.prepare('SELECT username FROM channel_exclusions WHERE username=?').bind(username).first();
   if(excluded)return json({error:'Canal précédemment exclu. Révision nécessaire avant ajout.'},409);
   const exists=await env.DB.prepare('SELECT id FROM channels WHERE LOWER(link)=?').bind(normalized.toLowerCase()).first();
   if(exists)return json({error:'Ce canal existe déjà (#'+exists.id+').'},409);
   const created=await env.DB.prepare("INSERT INTO channels(title,link,description,content_type,genre,language,status,rights_confirmed) VALUES(?,?,?,?,?,?,'approved',1)")
    .bind(fields.title,normalized,fields.description,fields.content_type,fields.genre,fields.language).run();
   invalidateDirectoryCache();
   return json({ok:true,id:Number(created.meta?.last_row_id||0)},201);
  }
  const pinAction=/^\/api\/admin\/pins\/(films|series|animes)\/([1-9][0-9]{0,12})\/(hide|unpin)$/.exec(path);
  if(pinAction){
   const kind=pinAction[1],id=Number(pinAction[2]);
   if(!Number.isSafeInteger(id))return json({error:'Identifiant invalide'},400);
   try{
    const result=await ownerRemovePin(env,kind,id,{unpinTelegram:pinAction[3]==='unpin'});
    return json(result,result.ok?200:404);
   }catch(e){return json({error:"Telegram n'a pas confirmé le désépinglage. Vérifie que le bot est administrateur du canal et dispose des droits nécessaires."},502)}
  }
  if(path==='/api/admin/sync-bot-identity'){
   await initializeProfile(env);
   return json({ok:true,message:"Identité Telegram synchronisée. La photo et le message /start sont configurés."});
  }
  if(path==='/api/admin/radar-refresh'){
   const stamp=await env.DB.prepare("SELECT last_success_at FROM radar_runs WHERE job_name='trends_films'").first();
   if(stamp?.last_success_at&&Date.now()-Date.parse(String(stamp.last_success_at).replace(' ','T')+'Z')<60000)
    return json({error:'Actualisation trop récente. Réessaie dans une minute.'},429);
   const binding=await bindPrimaryRadarChannels(env);
   const refreshed=await runTrendRefresh(env,{force:true});
   const reconciled=await reconcileRadarPosts(env,120);
   // Preserve the owner-only missing-title alerts that the former /actualiser
   // command delivered. Deduplication is maintained by radar_notice_log.
   const notices=await notifyOwnerMissingRadarTitles(env);
   return json({ok:true,bound:binding.bound,updated:refreshed.updated,reconciled:reconciled||{},
    notifications:{sent:notices.sent,listed:notices.listed,errors:notices.errors.length},
    warnings:(binding.errors?.length||0)+(refreshed.errors?.length||0)+notices.errors.length});
  }
  if(path==='/api/admin/cinex/state'||path==='/api/admin/cinex/approve'){
   const answer=await adminDeliveryAction(env,path,data);
   return json(answer.body,answer.status);
  }
  if(path==='/api/admin/radar-authorize'){
   const id=String(data.id||'').trim();
   if(!/^[0-9]{1,12}$/.test(id))return json({error:'Identifiant de titre invalide'},400);
   const authorized=await authorizeRadarTitle(env,id,admin.telegram_id);
   return json({ok:!!authorized},authorized?200:404);
  }
  if(path==='/api/admin/run-check'){
   const active=await env.DB.prepare("SELECT id FROM automated_job_runs WHERE job_name='link_check' AND started_at>datetime('now','-15 minutes') LIMIT 1").first();
   if(active)return json({error:'Contrôle déjà exécuté récemment'},429);
   const count=Number(data.count||10);
   if(!Number.isInteger(count)||count<1||count>10)return json({error:'Nombre invalide'},400);
   return json(await runLoggedJob(env,'link_check',()=>checkDailyLinks(env,count)));
  }
  const rev=/^\/api\/admin\/reviews\/(\d+)$/.exec(path);
  if(rev){
   const id=Number(rev[1]),visibility=String(data.visibility||'');
   if(!Number.isSafeInteger(id)||id<1||!['visible','held','hidden'].includes(visibility))return json({error:'Avis invalide'},400);
   await env.DB.prepare('UPDATE channel_reviews SET visibility=?,updated_at=CURRENT_TIMESTAMP WHERE id=?').bind(visibility,id).run();
   return json({ok:true});
  }
  const rm=/^\/api\/admin\/reports\/(\d+)$/.exec(path);
  if(rm){
   const id=Number(rm[1]),status=String(data.status||'');
   if(!Number.isSafeInteger(id)||id<1||!['reviewing','resolved','dismissed'].includes(status))return json({error:'Données invalides'},400);
   await env.DB.prepare('UPDATE channel_reports SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?').bind(status,id).run();
   return json({ok:true});
  }
  const cm=/^\/api\/admin\/channels\/(\d+)$/.exec(path);
  if(cm){
   const id=Number(cm[1]),action=String(data.action||'');
   if(!Number.isSafeInteger(id)||id<1||!['hide','show','exclude','update'].includes(action))return json({error:'Action invalide'},400);
   const channel=await env.DB.prepare('SELECT id,link FROM channels WHERE id=?').bind(id).first();
   if(!channel)return json({error:'Canal inexistant'},404);
   if(action==='update'){
    const fields=validAdminChannel(data);
    if(fields.error)return json({error:fields.error},400);
    await env.DB.prepare("UPDATE channels SET title=?,description=?,content_type=?,genre=?,language=?,updated_at=CURRENT_TIMESTAMP WHERE id=?")
     .bind(fields.title,fields.description,fields.content_type,fields.genre,fields.language,id).run();
    invalidateDirectoryCache();
    return json({ok:true,id});
   }
   if(action==='exclude'){
    const username=linkUsername(channel.link);
    if(!username)return json({error:'Lien du canal invalide'},400);
    await env.DB.batch([
     env.DB.prepare("INSERT INTO channel_exclusions(username,reason) VALUES(?,'admin_excluded') ON CONFLICT(username) DO NOTHING").bind(username),
     env.DB.prepare("INSERT INTO channel_index_meta(channel_id,listing_status,admin_hidden) VALUES(?,'excluded',1) ON CONFLICT(channel_id) DO UPDATE SET listing_status='excluded',admin_hidden=1,updated_at=CURRENT_TIMESTAMP").bind(id)
    ]);
   }else{
    // 'show' never overrides an explicit exclusion.
    const check=await env.DB.prepare('SELECT listing_status FROM channel_index_meta WHERE channel_id=?').bind(id).first();
    if(action==='show'&&check?.listing_status==='excluded')return json({error:'Exclusion permanente : demande de révision nécessaire'},409);
    await env.DB.prepare("INSERT INTO channel_index_meta(channel_id,listing_status,admin_hidden) VALUES(?,?,?) ON CONFLICT(channel_id) DO UPDATE SET listing_status=excluded.listing_status,admin_hidden=excluded.admin_hidden,updated_at=CURRENT_TIMESTAMP").bind(id,action==='show'?'listed':'hidden',action==='show'?0:1).run();
   }
   return json({ok:true});
  }
  return json({error:'Route inconnue'},404);
 }catch(e){console.warn('cine_admin_error',String(e).slice(0,80));return json({error:'Requête invalide'},400)}
}
