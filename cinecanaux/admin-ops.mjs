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
 const [actions,operations,jobs,webhook]=await Promise.all([
  env.DB.prepare("SELECT id,action,target,detail,created_at FROM cine_admin_audit ORDER BY id DESC LIMIT 40").all(),
  env.DB.prepare("SELECT job_name,status,last_attempt_at,last_success_at FROM radar_ops_status ORDER BY job_name LIMIT 30").all(),
  env.DB.prepare("SELECT job_name,status,errors,started_at FROM automated_job_runs ORDER BY id DESC LIMIT 15").all(),
  env.DB.prepare("SELECT status,updated_at FROM bot_webhook_status WHERE id=1").first()
 ]);
 const statuses=operations.results||[],runs=jobs.results||[];
 const alerts=[];
 if(webhook&&webhook.status!=='ok')alerts.push({level:'warning',title:'Connexion Telegram à contrôler',detail:'Le contrôle du webhook ne signale pas un état normal.'});
 for(const item of statuses.filter(x=>['error','partial'].includes(x.status)).slice(0,4))
  alerts.push({level:'warning',title:'Automatisation à contrôler : '+item.job_name,detail:'Dernier contrôle : '+String(item.last_attempt_at||'inconnu')});
 for(const item of runs.filter(x=>Number(x.errors||0)>0).slice(0,3))
  alerts.push({level:'warning',title:'Exécution partiellement réussie : '+item.job_name,detail:Number(item.errors||0)+' erreur(s) · '+String(item.started_at||'')});
 return {alerts,operations:statuses,jobs:runs,actions:actions.results||[],checked_at:new Date().toISOString()};
}
