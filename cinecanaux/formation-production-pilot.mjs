// One-time bot-only authorized Formation pilot, using exact verified D1 posts.
// Do not infer source grouping from Telegram adjacency or upload timestamps.
import {pathToFileURL} from 'node:url';
import {planCourses} from './manual-fallback-planner.mjs';
import {D1Remote,TelegramBot,FallbackPublisher} from './manual-fallback-live.mjs';
const ID=/^-100\d{6,}$/;
const SOURCE_POSTER=93,SOURCE_FILE=94;
const CATS=['formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset'];
const assert=(condition,reason)=>{if(!condition)throw Error(reason)};

export function selectVerifiedPilot(rows,source){
 assert(ID.test(String(source)),'pilot_source_invalid');
 assert(Array.isArray(rows)&&rows.length===2,'pilot_source_rows_not_exactly_two');
 assert(rows.every(r=>String(r.chat_id)===String(source)&&r.state==='indexed'),
  'pilot_source_or_state_mismatch');
 const byId=new Map(rows.map(r=>[Number(r.message_id),r]));
 assert(byId.size===2&&byId.get(SOURCE_POSTER)?.kind==='poster'&&
  byId.get(SOURCE_FILE)?.kind==='course_file',
  'pilot_cover_or_file_missing');
 assert(rows.every(r=>r.category==='formation_digitale'&&r.file_unique_id),
  'pilot_category_or_media_invalid');
 const planned=planCourses(rows);
 assert(planned.items.length===1,'pilot_complete_course_not_unique');
 const course=planned.items[0];
 assert(course.category==='formation_digitale'&&
  course.poster_message_id===SOURCE_POSTER&&course.parts.length===1&&
  Number(course.parts[0].message_id)===SOURCE_FILE&&
  course.parts[0].file_unique_id===byId.get(SOURCE_FILE).file_unique_id,
  'pilot_unverified_course_parts');
 assert(course.title&&course.description,'pilot_metadata_missing');
 return course;
}

export async function firstAuthorizedPilot({db,bot,radar,source,destinations}){
 assert(ID.test(String(source)),'pilot_source_invalid');
 assert(destinations&&Object.keys(destinations).length===5 &&
  ['general','business','finance','digitale','mindset'].every(k=>destinations[k]),
  'pilot_destinations_invalid');
 const checked=(await db.query(
  "SELECT category,owner_approved,bot_access_verified,rights_attested,enabled "+
  "FROM cine_manual_fallback_sources WHERE category IN (?,?,?,?,?)",
  CATS)).results||[];
 assert(checked.length===5&&checked.every(r=>CATS.includes(r.category)&&
  Number(r.owner_approved)===1&&Number(r.bot_access_verified)===1&&
  Number(r.rights_attested)===1&&Number(r.enabled)===1),
  'pilot_rights_or_bot_access_not_verified');
 const sourceRows=(await db.query(
  "SELECT chat_id,message_id,category,kind,file_unique_id,filename,caption,state,posted_at "+
  "FROM cine_manual_fallback_inbox WHERE chat_id=? AND message_id IN (?,?) "+
  "ORDER BY message_id", [source,SOURCE_POSTER,SOURCE_FILE])).results||[];
 const item=selectVerifiedPilot(sourceRows,source);
 const unique=(await db.query(
  "SELECT COUNT(*) AS n FROM cine_manual_fallback_inbox WHERE "+
  "file_unique_id=?",[sourceRows.find(r=>Number(r.message_id)===SOURCE_FILE).file_unique_id]
 )).results||[];
 assert(unique.length===1&&Number(unique[0].n)===1,'pilot_file_duplicate_in_global_inbox');
 const pending=(await db.query(
  "SELECT COUNT(*) AS n FROM cine_manual_fallback_receipts "+
  "WHERE status IN ('inflight','uncertain')")).results||[];
 assert(pending.length===1&&Number(pending[0].n)===0,'pilot_uncertain_receipts_blocked');
 // Every Telegram write is idempotently journaled by FallbackPublisher.
 const pub=new FallbackPublisher({
  db,radarBot:radar,categoryBots:{formation_digitale:bot},
  formationTargets:destinations,stage:source,targets:{},
 });
 await pub.copyCourse(item);
 const proof=(await db.query(
  "SELECT stage,status,target_chat_id,target_message_id FROM "+
  "cine_manual_fallback_receipts WHERE category='formation_digitale' "+
  "AND content_key LIKE ? ORDER BY stage,content_key",
  [item.key+'%'])).results||[];
 assert(proof.some(r=>r.stage==='public_poster'&&r.status==='complete'&&
  Number(r.target_message_id)>0)&&
  proof.some(r=>r.stage==='formation_file'&&r.status==='complete'&&
  Number(r.target_message_id)>0),'pilot_publication_receipts_missing');
 return {course_count:1,category:'formation_digitale',
  receipt_count:proof.filter(r=>r.status==='complete').length,
  destination_message_ids:proof.filter(r=>r.status==='complete'&&
   r.stage==='formation_file').map(r=>Number(r.target_message_id))};
}
async function main(){
 const env=process.env;
 assert(env.GITHUB_REPOSITORY==='MrXPRONOS/MrXPRONOS_App'&&
  env.GITHUB_ACTOR==='MrXPRONOS'&&
  env.GITHUB_REF==='refs/heads/main'&&
  env.FORMATION_PILOT_EXPLICIT==='true','pilot_owner_gate_not_met');
 const db=new D1Remote({token:env.CLOUDFLARE_API_TOKEN||env.CF_API_TOKEN,
  account:env.CLOUDFLARE_ACCOUNT_ID,db:env.CINERADAR_D1_DATABASE_ID});
 let targets;
 try{targets=JSON.parse(env.FORMATION_DESTINATIONS_JSON||'{}');}
 catch{throw Error('pilot_formation_destinations_invalid')}
 const result=await firstAuthorizedPilot({db,
  bot:new TelegramBot(env.FORMATION_BOT_TOKEN),
  radar:new TelegramBot(env.CINE_RADAR_BOT_TOKEN),
  source:env.FORMATION_STAGE_CHAT,destinations:targets});
 console.log('FORMATION_AUTHORIZED_FIRST_PILOT_SUCCESS',JSON.stringify(result));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)
 main().catch(e=>{console.error('FORMATION_AUTHORIZED_FIRST_PILOT_STOPPED',
  String(e?.message||'error').replace(/-100\d+/g,'[private]'));
  process.exitCode=1});
