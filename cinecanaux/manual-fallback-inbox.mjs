// Owner-uploaded Telegram backup stock, indexed by CineRadar's existing webhook.
// No user session, bot sends, channel creation or automatic publication here.
const CHAT=/^-100[0-9]{6,}$/;
const CATEGORIES=new Set(['films','series','animes','comedie','action','desir',
 'formation_general','formation_business','formation_finance',
 'formation_digitale','formation_mindset']);
const FILMS=new Set(['films','comedie','action','desir']);
const VIDEO_EXT=/\.(mp4|mkv|mov|avi|webm|m4v)$/i;
const SQL=[
 "CREATE TABLE IF NOT EXISTS cine_manual_fallback_sources (chat_id TEXT PRIMARY KEY CHECK(chat_id GLOB '-100[0-9]*'),category TEXT NOT NULL,rights_attested INTEGER NOT NULL DEFAULT 0,bot_access_verified INTEGER NOT NULL DEFAULT 0,owner_approved INTEGER NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 0,CHECK(enabled=0 OR (rights_attested=1 AND bot_access_verified=1 AND owner_approved=1)))",
 "CREATE TABLE IF NOT EXISTS cine_manual_fallback_inbox (chat_id TEXT NOT NULL,message_id INTEGER NOT NULL CHECK(message_id>0),category TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('poster','video','course_file','text')),file_unique_id TEXT NOT NULL DEFAULT '',filename TEXT NOT NULL DEFAULT '',mime_type TEXT NOT NULL DEFAULT '',bytes INTEGER NOT NULL DEFAULT 0,caption TEXT NOT NULL DEFAULT '',grouped_id TEXT NOT NULL DEFAULT '',posted_at INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL DEFAULT 'indexed' CHECK(state IN('indexed','needs_review','published')),review_code TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(chat_id,message_id))",
 "CREATE TABLE IF NOT EXISTS cine_manual_fallback_receipts (category TEXT NOT NULL,content_key TEXT NOT NULL,stage TEXT NOT NULL CHECK(stage IN ('central_stock','private_poster','private_video','private_index','public_poster','public_video','formation_file')),status TEXT NOT NULL CHECK(status IN ('reserved','inflight','uncertain','complete')),target_chat_id TEXT NOT NULL,source_chat_id TEXT NOT NULL,source_message_id INTEGER NOT NULL,target_message_id INTEGER,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(category,content_key,stage),CHECK(target_message_id IS NULL OR target_message_id>0))",
 "CREATE INDEX IF NOT EXISTS idx_cine_manual_inbox_category ON cine_manual_fallback_inbox(category,state,posted_at,message_id)",
 "CREATE INDEX IF NOT EXISTS idx_cine_manual_inbox_unique ON cine_manual_fallback_inbox(file_unique_id) WHERE file_unique_id!=''",
 "CREATE INDEX IF NOT EXISTS idx_cine_manual_receipts_status ON cine_manual_fallback_receipts(status,updated_at)"
];
const setupPromises=new WeakMap();
export async function ensureManualFallbackSchema(env){
 if(!env?.DB?.prepare)throw Error('manual_fallback_database_missing');
 let p=setupPromises.get(env.DB);
 if(!p){
  p=(async()=>{for(const sql of SQL)await env.DB.prepare(sql).run()})();
  setupPromises.set(env.DB,p);
 }
 try{await p}catch(e){setupPromises.delete(env.DB);throw e}
}

export function identifyManualMedia(message,category){
 if(!CATEGORIES.has(category)||message?.has_protected_content||
    message?.animation||message?.sticker||message?.video_note)return null;
 if(Array.isArray(message?.photo)&&message.photo.length){
  const p=message.photo.at(-1)||{};
  return {kind:'poster',file_unique_id:String(p.file_unique_id||''),
   filename:'',mime_type:'image/jpeg',bytes:Number(p.file_size||0)};
 }
 const document=message?.video||message?.document;
 if(document){
  const filename=String(document.file_name||'').slice(0,250);
  const mime=String(document.mime_type||'').toLowerCase().slice(0,100);
  const video=!!message.video||mime.startsWith('video/')||VIDEO_EXT.test(filename);
  if(!video&&!category.startsWith('formation_'))return null;
  return {kind:video?'video':'course_file',
   file_unique_id:String(document.file_unique_id||'').slice(0,160),
   filename,mime_type:mime,bytes:Math.max(0,Math.floor(Number(document.file_size)||0))};
 }
 if(typeof message?.text==='string'&&message.text.trim())
  return {kind:'text',file_unique_id:'',filename:'',mime_type:'',bytes:0};
 return null;
}

export function normalizedManualTitle(text){
 return String(text||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
  .toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
}
export function manualIdentity(row){
 // Exact pairing is a later explicit publication preflight, never a guess.
 const category=String(row.category||'');
 const text=String(row.caption||'').slice(0,1200);
 const filename=String(row.filename||'');
 const titleLine=text.split(/\r?\n/).find(x=>/^\s*(?:titre|title)\s*:/i.test(x));
 const title=titleLine?titleLine.replace(/^\s*(?:titre|title)\s*:\s*/i,''):
  text.split(/\r?\n/).find(x=>x.trim())||'';
 const clean=normalizedManualTitle(title).replace(/\b(?:19|20)\d{2}\b/g,'').trim();
 const year=/(?:^|\D)((?:19|20)\d{2})(?!\d)/.exec(text+' '+filename)?.[1]||'';
 const episode=/(?:^|[^a-z0-9])s0?([1-9]\d?)\s*[-._ ]*e0?([1-9]\d{0,2})(?=$|[^0-9])/i.exec(text+' '+filename);
 if(category==='series'||category==='animes'){
  if(!episode||clean.length<5)return {key:null,reason:'missing_episode_or_title'};
  return {key:category+':'+clean+':S'+episode[1]+':E'+episode[2],reason:''};
 }
 if(FILMS.has(category)){
  if(!year||clean.length<5)return {key:null,reason:'missing_title_or_year'};
  return {key:category+':'+clean+':'+year,reason:''};
 }
 if(category.startsWith('formation_'))
  return {key:null,reason:'course_boundary_requires_review'};
 return {key:null,reason:'unknown_category'};
}

export async function ingestManualChannelPost(env,update){
 if(env?.CINEX_MANUAL_INBOX_ENABLED!=='true')
  return {enabled:false,accepted:false};
 const message=update?.channel_post||update?.edited_channel_post;
 if(!message||message.chat?.type!=='channel')
  return {enabled:true,accepted:false,reason:'not_a_channel_post'};
 const chat=String(message.chat.id||''),id=Number(message.message_id||0);
 if(!CHAT.test(chat)||!Number.isSafeInteger(id)||id<1)
  return {enabled:true,accepted:false,reason:'invalid_source_reference'};
 await ensureManualFallbackSchema(env);
 const cfg=await env.DB.prepare(
  "SELECT category FROM cine_manual_fallback_sources WHERE chat_id=? "+
  "AND rights_attested=1 AND bot_access_verified=1 "+
  "AND owner_approved=1 AND enabled=1"
 ).bind(chat).first();
 if(!cfg||!CATEGORIES.has(cfg.category))
  return {enabled:true,accepted:false,reason:'not_owner_approved'};
 const media=identifyManualMedia(message,cfg.category);
 if(!media)return {enabled:true,accepted:false,reason:'unsupported_or_protected'};
 const fingerprint=media.file_unique_id||'';
 const caption=String(message.caption||message.text||'').slice(0,1200);
 const old=await env.DB.prepare(
  "SELECT state,kind,file_unique_id FROM cine_manual_fallback_inbox "+
  "WHERE chat_id=? AND message_id=?"
 ).bind(chat,id).first();
 if(old?.state==='published')return {enabled:true,accepted:false,reason:'already_published'};
 if(old&&(old.kind!==media.kind||(old.file_unique_id&&
           old.file_unique_id!==fingerprint))){
  await env.DB.prepare(
   "UPDATE cine_manual_fallback_inbox SET state='needs_review',"+
   "review_code='source_media_changed',updated_at=CURRENT_TIMESTAMP "+
   "WHERE chat_id=? AND message_id=? AND state!='published'"
  ).bind(chat,id).run();
  return {enabled:true,accepted:false,reason:'source_media_changed'};
 }
 await env.DB.prepare(
  "INSERT OR IGNORE INTO cine_manual_fallback_inbox "+
  "(chat_id,message_id,category,kind,file_unique_id,filename,mime_type,"+
  "bytes,caption,grouped_id,posted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
 ).bind(chat,id,cfg.category,media.kind,fingerprint,media.filename,
  media.mime_type,media.bytes,caption,
  String(message.media_group_id||''),Number(message.date||0)).run();
 if(old){
  await env.DB.prepare(
   "UPDATE cine_manual_fallback_inbox SET caption=?,filename=?,"+
   "updated_at=CURRENT_TIMESTAMP WHERE chat_id=? AND message_id=? "+
   "AND state='indexed'"
  ).bind(caption,media.filename,chat,id).run();
 }
 return {enabled:true,accepted:true,category:cfg.category,kind:media.kind};
}

export function planManualMediaPairs(rows){
 // Two passes: inspect *all* candidate variants before releasing any item.
 // One movie/episode pointing to two distinct files is ambiguous; one file
 // claiming two different movies/episodes is also ambiguous.
 const result={pairs:[],review:[],duplicates:[]}, groups=new Map();
 for(const row of rows||[]){
  if(!row||!CATEGORIES.has(row.category)||row.state!=='indexed')continue;
  const id=manualIdentity(row);
  if(!id.key){
   result.review.push({chat_id:row.chat_id,message_id:row.message_id,
    reason:id.reason});continue;
  }
  const key=row.chat_id+':'+id.key;
  if(!groups.has(key))groups.set(key,{posters:[],videos:[],key:id.key});
  if(row.kind==='poster')groups.get(key).posters.push(row);
  else if(row.kind==='video')groups.get(key).videos.push(row);
 }
 const drafts=[];
 for(const group of groups.values()){
  if(group.posters.length!==1||group.videos.length!==1){
   result.review.push({key:group.key,reason:'missing_or_ambiguous_pair'});continue;
  }
  const poster=group.posters[0],video=group.videos[0],
   fingerprint=String(video.file_unique_id||'');
  if(!fingerprint){
   result.review.push({key:group.key,reason:'missing_video_fingerprint'});continue;
  }
  drafts.push({key:group.key,category:video.category,
   source_chat_id:video.chat_id,poster_message_id:poster.message_id,
   video_message_id:video.message_id,file_unique_id:fingerprint});
 }
 const byKey=new Map(),byFile=new Map();
 for(const row of drafts){
  if(!byKey.has(row.key))byKey.set(row.key,[]);
  if(!byFile.has(row.file_unique_id))byFile.set(row.file_unique_id,[]);
  byKey.get(row.key).push(row);byFile.get(row.file_unique_id).push(row);
 }
 const selectedKeys=new Set(),selectedFiles=new Set();
 for(const row of drafts){
  const sameKey=byKey.get(row.key),sameFile=byFile.get(row.file_unique_id);
  if(new Set(sameKey.map(x=>x.file_unique_id)).size>1){
   result.review.push({key:row.key,reason:'multiple_video_versions'});continue;
  }
  if(new Set(sameFile.map(x=>x.key)).size>1){
   result.review.push({key:row.key,reason:'same_video_conflicting_title'});continue;
  }
  if(selectedKeys.has(row.key)||selectedFiles.has(row.file_unique_id)){
   result.duplicates.push({key:row.key,reason:'duplicate_video'});continue;
  }
  selectedKeys.add(row.key);selectedFiles.add(row.file_unique_id);
  result.pairs.push(row);
 }
 return result;
}
export async function manualFallbackCounts(env){
 await ensureManualFallbackSchema(env);
 const rows=(await env.DB.prepare(
  "SELECT category,state,COUNT(*) AS n FROM cine_manual_fallback_inbox "+
  "GROUP BY category,state"
 ).all()).results||[];
 return rows.map(x=>({category:x.category,state:x.state,count:Number(x.n||0)}));
}
