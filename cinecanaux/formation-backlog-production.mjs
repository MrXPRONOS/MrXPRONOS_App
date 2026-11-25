// Formation Storage: bot-only ongoing publishing of COMPLETE owner-licensed
// courses. Never guess grouping by Telegram adjacency or silently publish
// personal messages saved in the private source.
import {pathToFileURL} from 'node:url';
import {D1Remote,TelegramBot,FallbackPublisher} from './manual-fallback-live.mjs';
import {planCourses} from './manual-fallback-planner.mjs';
import {inspectFormationCover,matchFormationFilename,sanitizeFormationText} from './formation-content-safety.mjs';
import {courseId} from './formation-private-classifier.mjs';

const CATS=['formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset'];
const ID=/^-100\d{6,}$/;
const SAFE_REVIEW=new Set(['','rights_not_attested','training_category_unknown',
 'unlinked_course_file','no_verified_cover_match','training_category_unknown',
 'description_requires_course_cover']);
const LIMIT=2; // Up to two courses per job, never more than one per category.
function guard(ok,reason){if(!ok)throw Error(reason)}
function flag(row){return row?.state!=='published'&&
 (row?.state==='indexed'||row?.state==='needs_review'&&
 SAFE_REVIEW.has(String(row.review_code||'')));}
function unique(xs){return [...new Set(xs)]}
export function planFormationBacklog(rows,{maxCourses=LIMIT}={}){
 const remaining=(rows||[]).filter(r=>flag(r)&&CATS.includes(r.category)&&
  ID.test(String(r.chat_id||'')));
 const covers=remaining.filter(r=>r.kind==='poster')
  .map(r=>({row:r,meta:inspectFormationCover(r.caption)}))
  .filter(p=>p.meta!==null);
 // Reuse the EXACT accepted course ID, if present; otherwise require a
 // unique filename-to-cover match over the whole source channel.
 const proposed=[];
 for(const {row,meta} of covers){
  proposed.push({...row,caption:sanitizeFormationText(row.caption),
   category:meta.category,state:'indexed',review_code:''});
 }
 for(const row of remaining.filter(r=>['course_file','video'].includes(r.kind))){
  if(!row.filename||!row.file_unique_id)continue;
  const cid=courseId(row.caption);
  let cover=null;
  if(cid){
   const found=covers.filter(c=>c.row.chat_id===row.chat_id&&
    courseId(c.row.caption)===cid);
   if(found.length===1)cover=found[0].meta;
  }else{
   cover=matchFormationFilename(row.filename,
    covers.filter(c=>c.row.chat_id===row.chat_id).map(c=>({
     message_id:c.row.message_id,caption:c.row.caption}))).cover;
  }
  if(!cover)continue;
  proposed.push({...row,caption:sanitizeFormationText(row.caption),
   category:cover.category,state:'indexed',review_code:''});
 }
 for(const row of remaining.filter(r=>r.kind==='text'&&
  courseId(r.caption)&&/^\s*description\s*:/im.test(r.caption))){
  const found=covers.filter(c=>c.row.chat_id===row.chat_id&&
   courseId(c.row.caption)===courseId(row.caption));
  if(found.length!==1)continue;
  proposed.push({...row,caption:sanitizeFormationText(row.caption),
   category:found[0].meta.category,state:'indexed',review_code:''});
 }
 const plan=planCourses(proposed);
 const perKey=new Map(),perFile=new Map();
 for(const item of plan.items){
  perKey.set(item.key,(perKey.get(item.key)||0)+1);
  for(const part of item.parts)
   perFile.set(part.file_unique_id,(perFile.get(part.file_unique_id)||0)+1);
 }
 const accepted=[],usedCats=new Set();
 for(const item of plan.items.sort((a,b)=>a.poster_message_id-b.poster_message_id)){
  if(perKey.get(item.key)!==1||usedCats.has(item.category)||
     item.parts.some(p=>perFile.get(p.file_unique_id)!==1))continue;
  if(accepted.length>=maxCourses)break;
  // Require a unique, unchanged, fingerprinted set of original D1 messages.
  const needed=[item.poster_message_id,...item.parts.map(p=>p.message_id)];
  const originals=needed.map(id=>remaining.filter(r=>r.chat_id===item.source_chat_id&&
   Number(r.message_id)===Number(id)));
  if(originals.some(q=>q.length!==1))continue;
  const selected=originals.map(x=>x[0]);
  if(selected[0].kind!=='poster'||selected.some((r,i)=>
   !r.file_unique_id||
   (i>0&&r.file_unique_id!==item.parts[i-1].file_unique_id)))continue;
  accepted.push({item,originals:selected,
   proposals:needed.map(id=>proposed.find(r=>String(r.chat_id)===String(item.source_chat_id)&&
    Number(r.message_id)===Number(id)))});
  usedCats.add(item.category);
 }
 return {accepted,review_count:plan.review.length,
  candidate_count:plan.items.length,inspected:remaining.length};
}
async function loadSource(db,source){
 const records=[],pageSize=400;
 for(let page=0,last=0;page<40;page++){
  const result=(await db.query(
   "SELECT chat_id,message_id,category,kind,file_unique_id,filename,caption,"+
   "state,review_code,posted_at FROM cine_manual_fallback_inbox "+
   "WHERE chat_id=? AND category LIKE 'formation_%' AND message_id>? "+
   "ORDER BY message_id LIMIT "+pageSize,[source,last])).results||[];
  if(!result.length)return records;
  records.push(...result);
  guard(records.length<=12000,'formation_backlog_too_large');
  const next=Number(result.at(-1).message_id);
  guard(Number.isSafeInteger(next)&&next>last,'formation_backlog_cursor_invalid');
  last=next;
  if(result.length<pageSize)return records;
 }
 throw Error('formation_backlog_pagination_exhausted');
}
async function authorizeAndProvePilot(db,source){
 const rights=(await db.query(
  "SELECT category,owner_approved,bot_access_verified,rights_attested,enabled "+
  "FROM cine_manual_fallback_sources WHERE category IN (?,?,?,?,?)",CATS)).results||[];
 guard(rights.length===5&&rights.every(r=>CATS.includes(r.category)&&
  Number(r.owner_approved)===1&&Number(r.bot_access_verified)===1&&
  Number(r.rights_attested)===1&&Number(r.enabled)===1),
  'formation_rights_not_attested');
 const pilot=(await db.query(
  "SELECT message_id,state FROM cine_manual_fallback_inbox "+
  "WHERE chat_id=? AND message_id IN (93,94)",[source])).results||[];
 guard(pilot.length===2&&pilot.every(r=>r.state==='published'),
  'formation_first_pilot_not_yet_confirmed');
 const verified=(await db.query(
  "SELECT COUNT(*) AS n FROM cine_manual_fallback_receipts "+
  "WHERE category='formation_digitale' AND "+
  "stage IN ('public_poster','formation_file') AND status='complete' "+
  "AND content_key LIKE 'formation_digitale:auto-%'")).results||[];
 guard(Number(verified[0]?.n||0)>=2,'formation_pilot_receipts_missing');
 const pending=(await db.query(
  "SELECT COUNT(*) AS n FROM cine_manual_fallback_receipts "+
  "WHERE status IN ('inflight','uncertain')")).results||[];
 guard(Number(pending[0]?.n||0)===0,'formation_uncertain_delivery_requires_review');
}
async function indexOne(db,entry){
 for(let i=0;i<entry.originals.length;i++){
  const original=entry.originals[i],proposed=entry.proposals[i];
  guard(original&&proposed&&original.file_unique_id===proposed.file_unique_id,
   'formation_inbox_source_changed');
  const result=await db.query(
   "UPDATE cine_manual_fallback_inbox "+
   "SET category=?,caption=?,state='indexed',review_code='',updated_at=CURRENT_TIMESTAMP "+
   "WHERE chat_id=? AND message_id=? AND file_unique_id=? "+
   "AND state IN ('needs_review','indexed') AND "+
   "(review_code IN ('','rights_not_attested','training_category_unknown',"+
   "'unlinked_course_file','no_verified_cover_match',"+
   "'description_requires_course_cover') OR state='indexed')",
   [entry.item.category,proposed.caption,String(original.chat_id),
    Number(original.message_id),String(original.file_unique_id)]);
  guard(Number(result.meta?.changes||0)===1,'formation_inbox_atomic_promotion_failed');
 }
}
export async function processFormationBacklog({db,source,bot,radar,targets,maxCourses=LIMIT}){
 guard(ID.test(String(source))&&targets&&
  ['general','business','finance','digitale','mindset'].every(k=>targets[k]),
  'formation_production_configuration_invalid');
 await authorizeAndProvePilot(db,source);
 const raw=await loadSource(db,source);
 const planning=planFormationBacklog(raw,{maxCourses});
 let published=0;
 const publisher=new FallbackPublisher({
  db,radarBot:radar,categoryBots:Object.fromEntries(
   CATS.map(cat=>[cat,bot])),
  formationTargets:targets,stage:source,targets:{}
 });
 for(const entry of planning.accepted){
  // Detect duplicate file instances in the whole D1 inbox, not just this batch.
  let uniqueFiles=true;
  for(const part of entry.item.parts){
   const count=(await db.query(
    "SELECT COUNT(*) n FROM cine_manual_fallback_inbox WHERE file_unique_id=?",
    [part.file_unique_id])).results||[];
   if(Number(count[0]?.n||0)!==1){uniqueFiles=false;break;}
  }
  if(!uniqueFiles)continue;
  const existing=(await db.query(
   "SELECT status FROM cine_manual_fallback_receipts WHERE category=? "+
   "AND content_key=? AND stage='public_poster'",
   [entry.item.category,entry.item.key])).results||[];
  if(existing.length){
   // Already complete or uncertain records require no new Telegram writes.
   continue;
  }
  await indexOne(db,entry);
  await publisher.copyCourse(entry.item);
  published++;
 }
 return {published,considered:planning.candidate_count,
  review_count:planning.review_count,inspected:planning.inspected};
}
async function main(){
 const e=process.env;
 guard(e.GITHUB_REPOSITORY==='MrXPRONOS/MrXPRONOS_App'&&
  e.GITHUB_REF==='refs/heads/main'&&
  e.FORMATION_PRODUCTION_ENABLED==='true','formation_production_not_authorized');
 const db=new D1Remote({token:e.CLOUDFLARE_API_TOKEN||e.CF_API_TOKEN,
  account:e.CLOUDFLARE_ACCOUNT_ID,db:e.CINERADAR_D1_DATABASE_ID});
 let targets;try{targets=JSON.parse(e.FORMATION_DESTINATIONS_JSON||'{}')}
 catch{throw Error('formation_destinations_invalid')}
 const result=await processFormationBacklog({db,source:e.FORMATION_STAGE_CHAT,
  bot:new TelegramBot(e.FORMATION_BOT_TOKEN),
  radar:new TelegramBot(e.CINE_RADAR_BOT_TOKEN),targets});
 console.log('FORMATION_LICENSED_BACKLOG_CYCLE',JSON.stringify(result));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)
 main().catch(e=>{
  console.error('FORMATION_LICENSED_BACKLOG_STOPPED',
   String(e?.message||'error').replace(/-100\d+/g,'[private]'));
  process.exitCode=1;
 });
