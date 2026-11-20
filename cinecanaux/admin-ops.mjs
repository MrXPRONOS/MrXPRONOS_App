import {cleanupHealthOverview} from './cinex-cleanup-coordinator.mjs';
// V1.3 — minimal owner-only operational alerts and activity journal.
// Only bounded action names and targets are persisted. Never log Telegram initData
// or raw messages, access tokens, personal Telegram IDs, IPs or private chats.
export async function ensureAdminAuditTable(env){
 await env.DB.prepare("CREATE TABLE IF NOT EXISTS cine_admin_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)").run();
}
export async function recordAdminAudit(env,owner,action,target,detail=''){
 if(!Number.isSafeInteger(Number(owner))||Number(owner)<1)return;
 const safeAction=String(action||'').slice(0,55),safeTarget=String(target||'').slice(0,90);
 if(!/^[a-z][a-z0-9_.-]*$/.test(safeAction)||!safeTarget)return;
 try{
  await ensureAdminAuditTable(env);
  await env.DB.prepare("INSERT INTO cine_admin_audit(owner_id,action,target,detail) VALUES(?,?,?,?)")
   .bind(Number(owner),safeAction,safeTarget,String(detail||'').slice(0,120)).run();
 }catch(e){console.warn('cine_admin_audit_unavailable',String(e?.name||'Error'))}
}
export async function ownerOperationsOverview(env){
 await ensureAdminAuditTable(env);
 const [actions,operations,jobs,webhook,scheduler,deliveryJobs,deliveryCopies,deliverySwitch,issues]=await Promise.all([
  env.DB.prepare("SELECT id,action,target,detail,created_at FROM cine_admin_audit ORDER BY id DESC LIMIT 40").all(),
  env.DB.prepare("SELECT job_name,status,last_attempt_at,last_success_at FROM radar_ops_status ORDER BY job_name LIMIT 30").all(),
  env.DB.prepare("SELECT job_name,status,errors,started_at FROM automated_job_runs ORDER BY id DESC LIMIT 15").all(),
  env.DB.prepare("SELECT status,updated_at FROM bot_webhook_status WHERE id=1").first(),
  env.DB.prepare("SELECT last_tick_at,status,error_count FROM cine_broadcast_scheduler_status WHERE id=1").first().catch(()=>null),
  env.DB.prepare("SELECT COUNT(*) AS total, SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued, SUM(CASE WHEN status='needs_review' THEN 1 ELSE 0 END) AS needs_review FROM cine_delivery_jobs").first().catch(()=>null),
  env.DB.prepare("SELECT SUM(CASE WHEN delete_state='manual_review' THEN 1 ELSE 0 END) AS manual_review, SUM(CASE WHEN delete_state='retry' THEN 1 ELSE 0 END) AS retries, SUM(CASE WHEN state='sent' AND delete_after<CURRENT_TIMESTAMP AND delete_state IN ('pending','retry','deleting') THEN 1 ELSE 0 END) AS overdue FROM cine_delivery_job_items").first().catch(()=>null),
  env.DB.prepare("SELECT value,updated_at FROM bot_settings WHERE setting_key='cine_delivery_enabled'").first().catch(()=>null),
  env.DB.prepare("SELECT COALESCE(delete_last_error,'not_specified') AS reason,COUNT(*) AS count FROM cine_delivery_job_items WHERE delete_state='manual_review' GROUP BY COALESCE(delete_last_error,'not_specified') ORDER BY count DESC LIMIT 5").all().catch(()=>({results:[]}))
 ]);
 // Include every active CineX Bot API queue, not just legacy libraries.
 // Read-only aggregations: no chat IDs, tokens, or private message IDs returned.
 const extraQuery=[
  "SELECT 'series' family,(SELECT COUNT(*) FROM cine_series_jobs WHERE status='queued') queued,"+
  "(SELECT COUNT(*) FROM cine_series_jobs WHERE status='needs_review') needs_review,"+
  "(SELECT COUNT(*) FROM cine_series_job_items WHERE state='sent' AND delete_after<CURRENT_TIMESTAMP AND delete_state IN ('pending','retry','deleting')) overdue,"+
  "(SELECT COUNT(*) FROM cine_series_job_items WHERE delete_state='manual_review') manual_review",
  "SELECT 'classics' family,(SELECT COUNT(*) FROM cine_classic_deliveries WHERE status='queued') queued,"+
  "(SELECT COUNT(*) FROM cine_classic_deliveries WHERE status='needs_review') needs_review,"+
  "(SELECT COUNT(*) FROM cine_classic_deliveries WHERE status='sent' AND delete_after<CURRENT_TIMESTAMP AND delete_state IN ('pending','retry','deleting')) overdue,"+
  "(SELECT COUNT(*) FROM cine_classic_deliveries WHERE delete_state='manual_review') manual_review",
  "SELECT 'franchise' family,(SELECT COUNT(*) FROM cine_franchise_jobs WHERE status='queued') queued,"+
  "(SELECT COUNT(*) FROM cine_franchise_jobs WHERE status='needs_review') needs_review,"+
  "(SELECT COUNT(*) FROM cine_franchise_job_items WHERE state='sent' AND delete_after<CURRENT_TIMESTAMP AND delete_state IN ('pending','retry','deleting')) overdue,"+
  "(SELECT COUNT(*) FROM cine_franchise_job_items WHERE delete_state='manual_review') manual_review",
  "SELECT 'owner_archive' family,(SELECT COUNT(*) FROM cine_owner_vault WHERE status='queued') queued,"+
  "(SELECT COUNT(*) FROM cine_owner_vault WHERE status='needs_review') needs_review,0 overdue,0 manual_review",
 ].join(" UNION ALL ");
 const extra=await env.DB.prepare(extraQuery).all().catch(()=>({results:[]}));
 const statuses=operations.results||[],runs=jobs.results||[];
 const now=Date.now();
 const age=scheduler?.last_tick_at?now-Date.parse(String(scheduler.last_tick_at).replace(' ','T')+'Z'):Infinity;
 const schedulerHealthy=Number.isFinite(age)&&age>=0&&age<15*60000&&scheduler?.status==='ok';
 const scheduleState={last_tick_at:scheduler?.last_tick_at||null,status:scheduler?.status||'waiting',error_count:Number(scheduler?.error_count||0),healthy:schedulerHealthy};
 const alerts=[];
 const cinex={enabled:deliverySwitch?.value==='1',configuration_available:!!deliverySwitch,
  queued:Number(deliveryJobs?.queued||0),needs_review:Number(deliveryJobs?.needs_review||0),
  deletion_manual_review:Number(deliveryCopies?.manual_review||0),deletion_retries:Number(deliveryCopies?.retries||0),
  overdue:Number(deliveryCopies?.overdue||0),reasons:(issues?.results||[]).map(x=>({reason:String(x.reason||'unknown').slice(0,55),count:Number(x.count||0)}))};
 cinex.families=[
  {family:'libraries',queued:cinex.queued,needs_review:cinex.needs_review,
   overdue:cinex.overdue,manual_review:cinex.deletion_manual_review},
  ...(extra.results||[]).filter(x=>['series','classics','franchise','owner_archive'].includes(x.family)).map(x=>({
   family:x.family,queued:Number(x.queued||0),needs_review:Number(x.needs_review||0),
   overdue:Number(x.overdue||0),manual_review:Number(x.manual_review||0),
  }))
 ];
 cinex.total_queued=cinex.families.reduce((a,x)=>a+x.queued,0);
 cinex.total_needs_review=cinex.families.reduce((a,x)=>a+x.needs_review,0);
 cinex.total_overdue=cinex.families.reduce((a,x)=>a+x.overdue,0);
 cinex.total_deletion_manual_review=cinex.families.reduce((a,x)=>a+x.manual_review,0);
 // T03: actual cleanup heartbeat and outcomes, not just overdue alerts.
 const expiryHealth=await cleanupHealthOverview(env);
 cinex.cleanup_health=expiryHealth;
 cinex.cleanup_healthy=expiryHealth.active;
 if(!expiryHealth.active)alerts.push({level:'warning',title:'CinéX : nettoyage privé à vérifier',
  detail:'Aucun passage récent et réussi des quatre suppressions à 24 h n’est confirmé.'});
 for(const family of expiryHealth.families.filter(x=>x.status==='error'))
  alerts.push({level:'warning',title:'CinéX : suppression interrompue ('+family.family+')',
   detail:'Une file de suppression a échoué lors du dernier contrôle ; la prochaine minute relancera les copies éligibles.'});

 if(cinex.total_needs_review)alerts.push({level:'warning',title:'CinéX : files d’envoi à vérifier',detail:cinex.total_needs_review+' demande(s) en erreur sur l’ensemble des catalogues.'});
 if(cinex.total_overdue)alerts.push({level:'warning',title:'CinéX : nettoyage en retard',detail:cinex.total_overdue+' copie(s) à supprimer sur l’ensemble des catalogues.'});
 if(cinex.total_deletion_manual_review)alerts.push({level:'warning',title:'CinéX : suppressions en révision manuelle',detail:cinex.total_deletion_manual_review+' copie(s) non supprimées automatiquement.'});
 if(cinex.needs_review)alerts.push({level:'warning',title:'CinéX : envois nécessitant un diagnostic',detail:cinex.needs_review+' demandes à examiner dans les journaux techniques (aucune autorisation manuelle de film).'});
 if(cinex.deletion_manual_review)alerts.push({level:'warning',title:'CinéX : copies non supprimées automatiquement',detail:cinex.deletion_manual_review+' suppressions exigent un diagnostic technique.'});
 if(cinex.overdue)alerts.push({level:'warning',title:'CinéX : suppressions en retard',detail:cinex.overdue+' copies attendent le nettoyage après leur échéance.'});
 if(!schedulerHealthy)alerts.push({level:'warning',title:'Horloge des annonces à contrôler',detail:!scheduler?.last_tick_at?'Aucun passage du déclencheur encore confirmé.':scheduler.status!=='ok'?'Le dernier passage a signalé une erreur.':'Le dernier passage est trop ancien.'});
 if(webhook&&webhook.status!=='ok')alerts.push({level:'warning',title:'Connexion Telegram à contrôler',detail:'Le contrôle du webhook ne signale pas un état normal.'});
 for(const item of statuses.filter(x=>['error','partial'].includes(x.status)).slice(0,4))
  alerts.push({level:'warning',title:'Automatisation à contrôler : '+item.job_name,detail:'Dernier contrôle : '+String(item.last_attempt_at||'inconnu')});
 for(const item of runs.filter(x=>Number(x.errors||0)>0).slice(0,3))
  alerts.push({level:'warning',title:'Exécution partiellement réussie : '+item.job_name,detail:Number(item.errors||0)+' erreur(s) · '+String(item.started_at||'')});
 return {alerts,scheduler:scheduleState,operations:statuses,jobs:runs,actions:actions.results||[],cinex,checked_at:new Date().toISOString()};
}
