// Read-only readiness report over the private D1 manual stock.
// No public endpoint, no Telegram API or publication side effects.
// Never prints or returns chat/message IDs, filenames or private captions.
import {ensureManualFallbackSchema} from './manual-fallback-inbox.mjs';
import {planMovies,planSeasons,planCourses,selectManualCycle} from './manual-fallback-planner.mjs';

function tallyReasons(items){
 const reasons={};
 for(const row of items)reasons[row.reason]=(reasons[row.reason]||0)+1;
 return reasons;
}
export async function auditManualStock(env){
 if(!env?.DB?.prepare)return {ready:false,reason:'database_missing'};
 // The main CineX worker gates ingestion independently; this report is safe
 // in read-only diagnostics even when ingestion has not been enabled.
 await ensureManualFallbackSchema(env);
 const sourceRows=(await env.DB.prepare(
  "SELECT category,COUNT(*) AS n FROM cine_manual_fallback_sources "+
  "WHERE rights_attested=1 AND bot_access_verified=1 "+
  "AND owner_approved=1 AND enabled=1 GROUP BY category"
 ).all()).results||[];
 const sources=Object.fromEntries(sourceRows.map(x=>[x.category,Number(x.n||0)]));
 const records=(await env.DB.prepare(
  "SELECT i.chat_id,i.message_id,i.category,i.kind,i.file_unique_id,"+
  "i.filename,i.mime_type,i.caption,i.grouped_id,i.posted_at,i.state "+
  "FROM cine_manual_fallback_inbox i JOIN cine_manual_fallback_sources s "+
  "ON s.chat_id=i.chat_id AND s.category=i.category "+
  "WHERE s.enabled=1 AND s.owner_approved=1 AND s.rights_attested=1 "+
  "AND s.bot_access_verified=1 AND i.state='indexed' "+
  "ORDER BY i.posted_at,i.chat_id,i.message_id LIMIT 2001"
 ).all()).results||[];
 if(records.length>2000)return {
  ready:false,reason:'manual_inbox_exceeds_safe_audit_window',
  authorizedSourceCounts:sources,
 };
 const plans={movies:planMovies(records),seasons:planSeasons(records),
              courses:planCourses(records)};
 const summary={};
 for(const [family,plan] of Object.entries(plans)){
  summary[family]={candidates:plan.items.length,
   quarantined:plan.review.length,
   reasons:tallyReasons(plan.review),
   duplicates:plan.duplicates.length};
 }
 // The selection engine is invoked in non-publishing mode here. Historical
 // receipts must be reconciled before *any* live fallback can be authorized.
 const selection=selectManualCycle(plans,{
  personalStatus:'unknown',fallbackEnabled:false,botReady:false,
  stockReady:false,rightsAttested:false,receiptsReady:false});
 return {ready:true,mode:'diagnostics_only',authorizedSourceCounts:sources,
  inboxIndexed:records.length,plans:summary,
  eligibleToPublish:selection.eligible.length,
  historicalReconciliation:'not_implemented',
  publicationEnabled:false};
}
