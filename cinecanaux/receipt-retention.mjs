// Privacy retention for CineRadar delivery *receipts only*.
// Never touches Telegram source media, owner vault, published posters, active
// queues, or 24-hour copies awaiting deletion. Keep failed/ambiguous delivery
// records available for investigation until they are explicitly resolved.
const FINAL_COPY_STATES="'deleted','already_gone'";
const CATALOGUES=Object.freeze([
 {name:'libraries',job:'cine_delivery_jobs',item:'cine_delivery_job_items'},
 {name:'series',job:'cine_series_jobs',item:'cine_series_job_items'},
 {name:'franchise',job:'cine_franchise_jobs',item:'cine_franchise_job_items'},
]);

export async function pruneFinalizedCineReceipts(env,{perFamily=25,days=90}={}){
 const result={families:{},deleted_jobs:0,deleted_items:0,deleted_classics:0,disabled:false};
 if(!env?.DB)return {...result,disabled:true};
 const limit=Math.max(1,Math.min(50,Math.floor(Number(perFamily)||25)));
 // Never allow API callers to shorten retention beyond 90 days.
 const cutoff=Math.max(90,Math.floor(Number(days)||90));
 const age='-'+cutoff+' days';
 for(const family of CATALOGUES){
  let jobs;
  try{
   jobs=(await env.DB.prepare(
    'SELECT j.id FROM '+family.job+' j WHERE j.status=? AND j.created_at<datetime(?,?) '+
    'AND NOT EXISTS(SELECT 1 FROM '+family.item+' i WHERE i.job_id=j.id '+
    'AND (i.state!=? OR i.delete_state NOT IN ('+FINAL_COPY_STATES+'))) '+
    'ORDER BY j.id LIMIT ?'
   ).bind('complete','now',age,'sent',limit).all()).results||[];
  }catch(e){result.families[family.name]={error:'table_unavailable'};continue;}
  let complete=0,items=0;
  for(const row of jobs){
   const id=Number(row.id);
   if(!Number.isSafeInteger(id)||id<1)continue;
   // Both DELETE predicates are repeated to avoid race-induced data loss
   // between the safety SELECT and the final DELETE.
   const erased=await env.DB.prepare(
    'DELETE FROM '+family.item+' WHERE job_id=? AND state=? AND delete_state IN ('+FINAL_COPY_STATES+') '+
    'AND EXISTS(SELECT 1 FROM '+family.job+' j WHERE j.id=? AND j.status=? AND j.created_at<datetime(?,?))'
   ).bind(id,'sent',id,'complete','now',age).run();
   const dropped=await env.DB.prepare(
    'DELETE FROM '+family.job+' WHERE id=? AND status=? AND created_at<datetime(?,?) '+
    'AND NOT EXISTS(SELECT 1 FROM '+family.item+' i WHERE i.job_id='+family.job+'.id)'
   ).bind(id,'complete','now',age).run();
   complete+=Number(dropped.meta?.changes||0);
   items+=Number(erased.meta?.changes||0);
  }
  result.families[family.name]={deleted_jobs:complete,deleted_items:items};
  result.deleted_jobs+=complete;
  result.deleted_items+=items;
 }
 try{
  const r=await env.DB.prepare(
   "DELETE FROM cine_classic_deliveries WHERE id IN "+
   "(SELECT id FROM cine_classic_deliveries WHERE status='deleted' "+
   "AND delete_state IN ("+FINAL_COPY_STATES+") AND created_at<datetime('now',?) LIMIT ?)"
  ).bind(age,limit).run();
  result.deleted_classics=Number(r.meta?.changes||0);
 }catch{result.families.classics={error:'table_unavailable'};}
 return result;
}
