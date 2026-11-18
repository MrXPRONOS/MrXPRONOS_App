// Durable diagnostics for Cloudflare scheduled jobs; logs contain no user data.
const ALLOWED=new Set(['link_check','discovery','housekeeping']);
export async function runLoggedJob(env,name,handler){
 if(!ALLOWED.has(name))throw Error('Unknown scheduled task');
 let id=null;
 try{
  const created=await env.DB.prepare("INSERT INTO automated_job_runs(job_name) VALUES(?)").bind(name).run();
  id=created.meta?.last_row_id??null;
 }catch(e){console.warn('job_log_initialization_failed',name,String(e).slice(0,80));}
 try{
  const data=await handler();
  const examined=Number(data?.checked??data?.inspected??data?.examined??0);
  const inserted=Number(data?.inserted??data?.indexed??0);
  const updated=Number(data?.updated??0),errors=Number(data?.errors??0);
  if(id!==null)await env.DB.prepare("UPDATE automated_job_runs SET finished_at=CURRENT_TIMESTAMP,status=?,examined=?,inserted=?,updated=?,errors=? WHERE id=?").bind(errors?'partial':'success',examined,inserted,updated,errors,id).run();
  return data;
 }catch(e){
  if(id!==null)try{
   await env.DB.prepare("UPDATE automated_job_runs SET finished_at=CURRENT_TIMESTAMP,status='error',errors=1,details=? WHERE id=?").bind(String(e).slice(0,240),id).run();
  }catch(logError){console.warn('job_log_failure',String(logError).slice(0,70))}
  console.error('scheduled_job_failed',name,String(e).slice(0,150));
  throw e;
 }
}
