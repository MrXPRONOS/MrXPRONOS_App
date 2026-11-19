// Private Ciné Radar moderation API. All requests require valid Telegram Mini App initData
// AND a matching Telegram user ID in the existing admin_users table.
import {verifiedIdentity,linkUsername} from './v2.mjs';
import {checkDailyLinks} from './maintenance-v2.mjs';
import {runLoggedJob} from './job-log.mjs';
import {adminAnalytics} from './analytics.mjs';
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
async function verifyAdmin(request,env){
 const u=await verifiedIdentity(request,env);
 if(!u)return null;
 const admin=await env.DB.prepare('SELECT role FROM admin_users WHERE user_id=?').bind(u.telegram_id).first();
 return admin?.role==='owner'?u:null;
}
async function parseBody(req){
 if(Number(req.headers.get('content-length')||0)>4096)throw Error('oversized');
 const text=await req.text();if(text.length>4096)throw Error('oversized');
 return JSON.parse(text);
}
export async function adminAPI(env,request){
 const admin=await verifyAdmin(request,env);if(!admin)return json({error:'Accès réservé'},403);
 const u=new URL(request.url),path=u.pathname;
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
   if(!Number.isSafeInteger(id)||id<1||!['hide','show','exclude'].includes(action))return json({error:'Action invalide'},400);
   const channel=await env.DB.prepare('SELECT id,link FROM channels WHERE id=?').bind(id).first();
   if(!channel)return json({error:'Canal inexistant'},404);
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
