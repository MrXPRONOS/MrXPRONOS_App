// Pure offline preparation for owner-imported CineX/Formation stock.
// No Telegram/API calls or changes to the existing publication workflows.
// All ambiguous media is quarantined rather than guessed.
import {normalizedManualTitle,manualIdentity} from './manual-fallback-inbox.mjs';
import {inspectFormationCover,matchFormationFilename,formationFilePart}
 from './formation-content-safety.mjs';

const MEDIA_CATEGORIES=new Set(['films','comedie','desir','action','series','animes']);
const COURSE_CATEGORIES=new Set([
 'formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset'
]);
const LIMITS={films:2,comedie:2,desir:2,action:2,series:2,animes:2,
 formation_general:1,formation_business:1,formation_finance:1,
 formation_digitale:1,formation_mindset:1};
const SEASON=/\bS0*([1-9]\d?)\b/i;
const EPISODE=/\bS0*([1-9]\d?)[ ._-]*E0*([1-9]\d{0,2})\b/i;
const TITLE=/^\s*(?:titre|title)\s*:\s*(.+?)\s*$/im;
const COURSE=/^\s*(?:cours|course)\s*:\s*([a-z][a-z0-9_-]{3,80})\s*$/im;
const AUTHOR=/^\s*(?:auteur|author|cr[eé]dit)\s*:\s*([^\n\r]{3,100})\s*$/im;
const TOTAL=/^\s*(?:total|fichiers)\s*:\s*([1-9]\d{0,2})\s*$/im;
const PART=/^\s*(?:partie|part|fichier)\s*:\s*([1-9]\d{0,2})\s*\/\s*([1-9]\d{0,2})\s*$/im;
const ALLOWED_COURSE_EXT=/\.(pdf|mp4|mkv|webm|mov|avi|mp3|m4a|wav|epub|docx|pptx|xlsx|csv|zip|rar|7z|txt|md|srt|vtt)$/i;
const ID=/^-100\d{6,}$/;

function active(row){
 return row && row.state==='indexed' && ID.test(String(row.chat_id||''))
  && Number.isSafeInteger(Number(row.message_id)) && Number(row.message_id)>0;
}
function exactTitle(row){
 const m=TITLE.exec(String(row.caption||''));
 return m?normalizedManualTitle(m[1]):'';
}
function filmKey(row){
 const k=manualIdentity(row);
 return k.key;
}
function rawFingerprint(row){
 return String(row.file_unique_id||'').trim();
}
function reviewPush(result,reason,refs){
 result.review.push({reason,source:refs.map(r=>({chat_id:String(r.chat_id),message_id:Number(r.message_id)}))});
}
function uniques(rows){return [...new Set(rows)];}

export function planMovies(rows){
 const result={items:[],review:[],duplicates:[]};
 const byKey=new Map();
 for(const row of rows||[]){
  if(!active(row)||!MEDIA_CATEGORIES.has(row.category)||row.category==='series'||row.category==='animes')continue;
  if(row.kind!=='poster'&&row.kind!=='video')continue;
  const key=filmKey(row);
  if(!key||!exactTitle(row)){
   reviewPush(result,'film_requires_explicit_title_and_year',[row]);continue;
  }
  const q=byKey.get(key)||{key,posters:[],videos:[],refs:[]};
  q[row.kind==='poster'?'posters':'videos'].push(row);
  q.refs.push(row);byKey.set(key,q);
 }
 const pairs=[];
 for(const q of byKey.values()){
  const distinctPosters=uniques(q.posters.map(x=>String(x.chat_id)+':'+x.message_id));
  const distinctVideos=uniques(q.videos.map(x=>String(x.chat_id)+':'+x.message_id));
  if(distinctPosters.length!==1||distinctVideos.length!==1){
   reviewPush(result,'incomplete_or_ambiguous_film',q.refs);continue;
  }
  const poster=q.posters[0],video=q.videos[0],fingerprint=rawFingerprint(video);
  if(!fingerprint){
   reviewPush(result,'missing_file_unique_id',[video]);continue;
  }
  if(String(poster.chat_id)!==String(video.chat_id)){
   reviewPush(result,'poster_and_video_different_vaults',q.refs);continue;
  }
  pairs.push({category:video.category,key:q.key,
   source_chat_id:String(video.chat_id),
   poster_message_id:Number(poster.message_id),
   video_message_id:Number(video.message_id),
   file_unique_id:fingerprint,
   original_caption:String(poster.caption||'')});
 }
 // Different keys that share file_unique_id are NEVER auto-selected.
 const perFile=new Map();
 for(const pair of pairs){
  const l=perFile.get(pair.file_unique_id)||[];
  l.push(pair);perFile.set(pair.file_unique_id,l);
 }
 for(const pair of pairs){
  if((perFile.get(pair.file_unique_id)||[]).length>1){
   reviewPush(result,'film_media_collision',[{
    chat_id:pair.source_chat_id,message_id:pair.video_message_id
   }]);continue;
  }
  result.items.push(pair);
 }
 return result;
}

export function planSeasons(rows,{publishedEpisodes=new Set(),maxEpisodes=50}={}){
 const result={items:[],review:[],duplicates:[]},groups=new Map();
 const safeMax=Math.min(50,Math.max(1,Number(maxEpisodes)||50));
 for(const row of rows||[]){
  if(!active(row)||!['series','animes'].includes(row.category))continue;
  const title=exactTitle(row),text=String(row.caption||'')+' '+String(row.filename||'');
  const explicitEpisode=EPISODE.exec(text);
  const season=explicitEpisode? [null,explicitEpisode[1]]:SEASON.exec(text);
  if(!title||!season){
   reviewPush(result,'missing_explicit_series_title_or_season',[row]);continue;
  }
  const sn=Number(season[1]);
  if(sn>50){reviewPush(result,'invalid_season',[row]);continue}
  const key=row.category+':'+title+':S'+String(sn).padStart(2,'0');
  let group=groups.get(key);
  if(!group){
   group={key,category:row.category,title,season:sn,
    source_chat_id:String(row.chat_id),posters:[],episodes:new Map(),invalid:false,refs:[]};
   groups.set(key,group);
  }
  if(group.source_chat_id!==String(row.chat_id))group.invalid=true;
  group.refs.push(row);
  if(row.kind==='poster'){
   group.posters.push(row);continue;
  }
  if(row.kind!=='video')continue;
  const ep=EPISODE.exec(text);
  if(!ep||Number(ep[1])!==sn||Number(ep[2])>999){
   group.invalid=true;continue;
  }
  const number=Number(ep[2]);
  const l=group.episodes.get(number)||[];
  l.push(row);group.episodes.set(number,l);
 }
 const candidateEpisodes=new Map();
 for(const group of groups.values()){
  if(group.invalid||group.posters.length!==1||!group.episodes.size){
   reviewPush(result,'series_missing_poster_or_ambiguous',group.refs);continue;
  }
  const ordered=[...group.episodes].sort((a,b)=>a[0]-b[0]);
  if(ordered.length>safeMax){
   reviewPush(result,'series_batch_over_limit',group.refs);continue;
  }
  if(ordered.some(([_,records])=>records.length!==1||
                 !rawFingerprint(records[0]))){
   reviewPush(result,'series_ambiguous_or_missing_fingerprint',group.refs);continue;
  }
  // Published episodes may be absent from the new source batch.
  const pending=ordered.filter(([n])=>!publishedEpisodes.has(group.key+':E'+n));
  if(!pending.length){result.duplicates.push({key:group.key,reason:'already_published'});continue;}
  // Avoid shipping an episode through an unpublished gap. A later cycle
  // may start after a fully published prefix only.
  let next=1;let hole=false;
  for(const [number] of ordered){
   while(next<number&&publishedEpisodes.has(group.key+':E'+next))next++;
   if(number!==next){hole=true;break;}
   next++;
  }
  if(hole){
   reviewPush(result,'series_episode_gap',group.refs);continue;
  }
  const fingerprintSet=new Set(pending.map(([_,r])=>rawFingerprint(r[0])));
  if(fingerprintSet.size!==pending.length){
   reviewPush(result,'same_video_for_multiple_episodes',group.refs);continue;
  }
  const item={category:group.category,key:group.key,season:group.season,
    title:group.title,source_chat_id:group.source_chat_id,
    poster_message_id:Number(group.posters[0].message_id),
    episodes:pending.map(([n,rs])=>({
     number:n,video_message_id:Number(rs[0].message_id),
     file_unique_id:rawFingerprint(rs[0])}))};
  for(const e of item.episodes){
   const all=candidateEpisodes.get(e.file_unique_id)||[];
   all.push(item.key+':E'+e.number);candidateEpisodes.set(e.file_unique_id,all);
  }
  result.items.push(item);
 }
 const collisions=new Set([...candidateEpisodes.entries()]
  .filter(([_,keys])=>new Set(keys).size>1).map(([key])=>key));
 if(collisions.size){
  result.items=result.items.filter(group=>{
   if(group.episodes.some(ep=>collisions.has(ep.file_unique_id))){
    reviewPush(result,'series_cross_title_video_collision',[{
     chat_id:group.source_chat_id,message_id:group.episodes[0].video_message_id
    }]);return false;
   }
   return true;
  });
 }
 return result;
}


// Natural Telegram course bundles: a descriptive photo and uniquely matching
// document filename(s). Do NOT connect messages merely by adjacency; unrelated
// announcements and saved documents may be interleaved arbitrarily.
export function planNaturalCourses(rows,{maxParts=100}={}){
 const result={items:[],review:[],duplicates:[]};
 const limit=Math.min(100,Math.max(1,Number(maxParts)||100));
 const posts=(rows||[]).filter(r=>active(r)&&r.kind==='poster'&&
  COURSE.exec(String(r.caption||''))===null&&COURSE_CATEGORIES.has(r.category)&&
  inspectFormationCover(r.caption));
 const files=(rows||[]).filter(r=>active(r)&&
  ['course_file','video'].includes(r.kind)&&
  !COURSE.exec(String(r.caption||''))&&COURSE_CATEGORIES.has(r.category));
 const assigned=new Map();
 for(const row of files){
  if(!ALLOWED_COURSE_EXT.test(String(row.filename||''))){
   reviewPush(result,'natural_course_unsupported_extension',[row]);continue;
  }
  const candidates=posts.filter(p=>String(p.chat_id)===String(row.chat_id));
  const match=matchFormationFilename(row.filename,candidates);
  if(!match.cover){
   // A file without an unambiguous cover stays untouched, even if adjacent.
   reviewPush(result,match.reason,[row]);continue;
  }
  if(match.cover.category!==row.category){
   reviewPush(result,'natural_course_category_mismatch',[row]);continue;
  }
  const part=formationFilePart(row.caption,row.filename);
  if(!part||part.number>limit){
   reviewPush(result,'natural_course_invalid_part',[row]);continue;
  }
  const key=String(row.chat_id)+':'+String(match.cover.message_id);
  const group=assigned.get(key)||[];
  group.push({...part,row});
  assigned.set(key,group);
 }
 for(const cover of posts){
  const meta=inspectFormationCover(cover.caption);
  if(!meta)continue;
  const group=assigned.get(String(cover.chat_id)+':'+String(cover.message_id))||[];
  if(!group.length)continue;
  const numbers=group.map(p=>p.number);
  const explicitTotals=[...new Set(group.filter(p=>p.explicit).map(p=>p.total))];
  if(explicitTotals.length>1){
   reviewPush(result,'natural_course_conflicting_totals',[cover,...group.map(p=>p.row)]);continue;
  }
  // No reliable end marker for a split archive? Keep it for manual review.
  // A contiguous prefix alone does not prove all course parts were uploaded.
  if(group.some(p=>!p.explicit&&(p.total===null)) && !explicitTotals.length){
   reviewPush(result,'natural_course_total_required_for_multipart',[cover,...group.map(p=>p.row)]);continue;
  }
  const count=explicitTotals[0]||1;
  if(count>limit||group.length!==count||new Set(numbers).size!==count||
     numbers.some(n=>n<1||n>count)||
     group.some(p=>p.total!==null&&p.total!==count)||
     group.some(p=>!rawFingerprint(p.row))){
   reviewPush(result,'natural_course_incomplete_or_ambiguous',[cover,...group.map(p=>p.row)]);continue;
  }
  const fingerprint=new Set(group.map(p=>rawFingerprint(p.row)));
  if(fingerprint.size!==group.length){
   reviewPush(result,'natural_course_duplicate_media',[cover,...group.map(p=>p.row)]);continue;
  }
  const titleSlug=normalizedManualTitle(meta.title).slice(0,80);
  if(titleSlug.length<5){
   reviewPush(result,'natural_course_title_unusable',[cover]);continue;
  }
  result.items.push({
   key:meta.category+':auto-'+titleSlug.replace(/\s+/g,'-'),
   category:meta.category,title:meta.title,author:meta.author,
   description:meta.caption,
   source_chat_id:String(cover.chat_id),
   poster_message_id:Number(cover.message_id),
   parts:group.sort((a,b)=>a.number-b.number).map(p=>({
    number:p.number,message_id:Number(p.row.message_id),
    file_unique_id:rawFingerprint(p.row)}))
  });
 }
 return result;
}

export function planCourses(rows,{maxParts=100}={}){
 const result={items:[],review:[],duplicates:[]},groups=new Map();
 const limit=Math.min(100,Math.max(1,Number(maxParts)||100));
 for(const row of rows||[]){
  if(!active(row)||!COURSE_CATEGORIES.has(row.category))continue;
  const text=String(row.caption||'');
  const course=COURSE.exec(text);
  if(!course){
   reviewPush(result,'course_id_required',[row]);continue;
  }
  const key=row.category+':'+course[1].toLowerCase();
  const id=String(row.chat_id)+':'+key;
  let group=groups.get(id);
  if(!group){group={key,category:row.category,source_chat_id:String(row.chat_id),
    posters:[],parts:[],descriptions:[],refs:[],author:null};groups.set(id,group)}
  group.refs.push(row);
  if(row.kind==='poster'){
   group.posters.push(row);
   const credit=AUTHOR.exec(text);
   if(credit)group.author=credit[1].trim();
   continue;
  }
  if(row.kind==='text'){
   // Only a separately tagged, course-specific description is allowed.
   if(/^\s*description\s*:/im.test(text))group.descriptions.push(row);
   else group.invalid=true;
   continue;
  }
  if(!['course_file','video'].includes(row.kind))continue;
  const part=PART.exec(text),total=TOTAL.exec(text);
  if(!part||!total||Number(part[2])!==Number(total[1])||
     Number(total[1])>limit||!ALLOWED_COURSE_EXT.test(String(row.filename||''))){
   reviewPush(result,'course_part_or_format_invalid',[row]);
   group.invalid=true;continue;
  }
  group.parts.push({number:Number(part[1]),total:Number(total[1]),
   message_id:Number(row.message_id),file_unique_id:rawFingerprint(row)});
 }
 for(const group of groups.values()){
  const count=group.parts[0]?.total||0;
  if(group.invalid||group.descriptions.length>1||
     group.posters.length!==1||!group.author||
     /https?:\/\/|@|t\.me\/|[<>]/i.test(group.author)||
     count<1||count>limit||group.parts.length!==count||
     group.parts.some(x=>x.total!==count||!x.file_unique_id)){
   reviewPush(result,'course_incomplete_or_ambiguous',group.refs);continue;
  }
  group.parts.sort((a,b)=>a.number-b.number);
  if(group.parts.some((p,i)=>p.number!==i+1)||
     new Set(group.parts.map(p=>p.file_unique_id)).size!==count){
   reviewPush(result,'course_missing_or_duplicate_parts',group.refs);continue;
  }
  result.items.push({key:group.key,category:group.category,
   source_chat_id:group.source_chat_id,author:group.author,
   title:exactTitle(group.posters[0])||group.key.split(':').slice(1).join(':'),
   description:[String(group.posters[0].caption||''),
    ...group.descriptions.map(r=>String(r.caption||''))].filter(Boolean).join('\n\n'),
   poster_message_id:Number(group.posters[0].message_id),
   parts:group.parts.map(p=>({...p}))});
 }
 const natural=planNaturalCourses(rows,{maxParts:limit});
 result.items.push(...natural.items);
 result.review.push(...natural.review);
 result.duplicates.push(...natural.duplicates);
 return result;
}

export function selectManualCycle(plans,{
 personalStatus='unknown',fallbackEnabled=false,botReady=false,stockReady=false,
 rightsAttested=false,receiptsReady=false,existingCounts={},
 publishedKeys=new Set(),publishedFiles=new Set(),uncertainKeys=new Set(),
}={}){
 const status={eligible:[],blocked:[],reason:null,remaining:{...LIMITS}};
 const allowed=fallbackEnabled&&botReady&&stockReady&&rightsAttested&&receiptsReady&&
  ['session_missing','session_revoked'].includes(personalStatus);
 if(!allowed){
  status.reason='not_eligible_or_personal_session_still_available';
  return status;
 }
 const counts={...existingCounts};
 for(const [category,cap] of Object.entries(LIMITS)){
  const used=Number(counts[category]||0);
  if(!Number.isSafeInteger(used)||used<0){
   status.reason='invalid_existing_quota';
   status.eligible=[];return status;
  }
  status.remaining[category]=Math.max(0,cap-used);
 }
 const selectedFiles=new Set();
 const selectedKeys=new Set();
 const queue=[...(plans?.movies?.items||[]),
              ...(plans?.seasons?.items||[]),
              ...(plans?.courses?.items||[])];
 // Full-queue preflight: one Telegram file cannot claim two distinct
 // movies, episodes or courses. Quarantine BOTH candidates, irrespective
 // of which content type is processed first.
 const ownersByFingerprint=new Map();
 const contentFingerprints=item=>item.file_unique_id?[item.file_unique_id]:
  item.episodes?item.episodes.map(x=>x.file_unique_id):
  item.parts?item.parts.map(x=>x.file_unique_id):[];
 for(const item of queue){
  const contentIdentity=String(item.category)+':'+String(item.key);
  for(const file of contentFingerprints(item)){
   if(!file)continue;
   const owners=ownersByFingerprint.get(file)||new Set();
   owners.add(contentIdentity);
   ownersByFingerprint.set(file,owners);
  }
 }
 const conflictingFiles=new Set([...ownersByFingerprint]
  .filter(([_,owners])=>owners.size>1).map(([fingerprint])=>fingerprint));
 // Same title/year across film genres, same series+season across series/anime,
 // or same multi-file course in distinct categories must be reviewed.
 const semanticIdentity=item=>{
  if(['films','comedie','action','desir'].includes(item.category))
   return 'film:'+item.key.split(':').slice(1).join(':');
  if(['series','animes'].includes(item.category))
   return 'season:'+item.key.split(':').slice(1).join(':');
  if(String(item.category).startsWith('formation_'))
   return 'course:'+item.key.split(':').slice(1).join(':');
  return null;
 };
 const ownersBySemantic=new Map();
 for(const item of queue){
  const semantic=semanticIdentity(item);
  if(!semantic)continue;
  const entries=ownersBySemantic.get(semantic)||[];
  entries.push(item);ownersBySemantic.set(semantic,entries);
 }
 const conflictingSemantics=new Set([...ownersBySemantic.entries()]
  .filter(([_,items])=>items.length>1).map(([key])=>key));
 for(const item of queue){
  const cap=status.remaining[item.category];
  const files=item.file_unique_id?[item.file_unique_id]:
   item.episodes?item.episodes.map(x=>x.file_unique_id):
   item.parts?item.parts.map(x=>x.file_unique_id):[];
  if(!item.key||!Object.hasOwn(status.remaining,item.category)||
     uncertainKeys.has(item.key)){
   status.blocked.push({key:item.key,reason:'invalid_or_uncertain'});continue;
  }
  if(files.some(x=>conflictingFiles.has(x))){
   status.blocked.push({key:item.key,reason:'cross_category_media_collision'});continue;
  }
  if(conflictingSemantics.has(semanticIdentity(item))){
   status.blocked.push({key:item.key,reason:'cross_category_title_or_season_collision'});continue;
  }
  if(publishedKeys.has(item.key)||selectedKeys.has(item.key)||
     files.some(x=>publishedFiles.has(x)||selectedFiles.has(x))){
   status.blocked.push({key:item.key,reason:'already_published'});continue;
  }
  if(cap<=0){status.blocked.push({key:item.key,reason:'cycle_cap'});continue}
  status.eligible.push(item);
  status.remaining[item.category]--;
  selectedKeys.add(item.key);
  files.forEach(x=>selectedFiles.add(x));
 }
 return status;
}
