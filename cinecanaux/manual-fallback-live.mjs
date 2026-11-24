// GitHub Actions bot-only fallback publishing engine for owner-approved
// CinéX/Formation vaults. All Telegram writes use the existing D1 journal.
// Never bypass user-session FloodWait or ambiguous responses.
import {randomBytes} from 'node:crypto';
import {planMovies,planSeasons,planCourses,selectManualCycle}
 from './manual-fallback-planner.mjs';
import {performJournaledCopy,ManualReceiptBlocked}
 from './manual-fallback-journal.mjs';

const ID=/^-100\d{6,}$/;
const HANDLE=/^@[A-Za-z][A-Za-z0-9_]{4,31}$/;
const FOLDER=/^https:\/\/t\.me\/addlist\/[A-Za-z0-9_-]{8,100}$/;
const INVITE=/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})\/?$/;
const LABEL={films:'🎬 VOIR LE FILM',comedie:'😂 VOIR LE FILM',desir:'❤️ VOIR LE FILM',
 action:'🎬 VOIR LE FILM',series:'📺 VOIR LA SÉRIE',animes:"🌸 VOIR L'ANIMÉ"};
const cap={'films':2,'comedie':2,'desir':2,'action':2,'series':2,'animes':2,
 formation_general:1,formation_business:1,formation_finance:1,
 formation_digitale:1,formation_mindset:1};
const safe=x=>String(x||'').trim();
const n=x=>Number.isSafeInteger(Number(x))&&Number(x)>0?Number(x):null;
function assert(cond,reason){if(!cond)throw Error(reason)}
export function internalMessageUrl(chat,id){
 assert(ID.test(String(chat))&&n(id),'invalid_private_message_link');
 return 'https://t.me/c/'+String(chat).slice(4)+'/'+Number(id);
}
const tgDownload=token=>'https://t.me/CineRadarFr_Bot?start=d_'+token;
export function publicKeyboard(category,watch,download,rescue,folder){
 assert(LABEL[category]&&watch.startsWith('https://t.me/c/')&&
  (download.startsWith('https://t.me/c/')||
   /^https:\/\/t\.me\/CineRadarFr_Bot\?start=d_[A-Za-z0-9_-]{24}$/.test(download))&&
  INVITE.test(rescue)&&FOLDER.test(folder),'invalid_public_v4_links');
 const links=[watch,download,rescue,folder];
 assert(new Set(links).size===4,'same_public_buttons_url');
 return {inline_keyboard:[
  [{text:LABEL[category],url:watch}],
  [{text:category==='series'||category==='animes'?'⬇️ TÉLÉCHARGER LES VIDÉOS':'⬇️ TÉLÉCHARGER',url:download}],
  [{text:'🛟 REJOINDRE LE CANAL SECOURS',url:rescue}],
  [{text:'📁 REJOINDRE LE DOSSIER',url:folder}]
 ]};
}
export function privateKeyboard(publicHandle,download,folder){
 assert(HANDLE.test(publicHandle)&&FOLDER.test(folder)&&
  /^https:\/\/t\.me\//.test(download),'invalid_private_v4_links');
 return {inline_keyboard:[
  [{text:'📢 REJOINDRE LE CANAL',url:'https://t.me/'+publicHandle.slice(1)}],
  [{text:'📁 REJOINDRE LE DOSSIER',url:folder}],
  [{text:'⬇️ TÉLÉCHARGER',url:download}]
 ]};
}

export class D1Remote{
 constructor({token,account,db,fetchFn=fetch}){
  assert(token&&/^[a-f0-9]{32}$/.test(account)&&/^[a-f0-9-]{36}$/.test(db),
   'd1_auth_missing_or_invalid');
  this.url='https://api.cloudflare.com/client/v4/accounts/'+account+'/d1/database/'+db+'/query';
  this.token=token;this.fetchFn=fetchFn;
 }
 async query(sql,params=[]){
  let response,body;
  try{
   response=await this.fetchFn(this.url,{method:'POST',headers:{
    Authorization:'Bearer '+this.token,'Content-Type':'application/json'},
    body:JSON.stringify({sql,params}),signal:AbortSignal.timeout(15000)});
   body=await response.json();
  }catch{throw Error('d1_network_uncertain')}
  if(!response.ok||!body?.success||body?.result?.[0]?.success!==true)
   throw Error('d1_query_failed');
  return body.result[0];
 }
 env(){
  const client=this;
  return {DB:{prepare(sql){
   let params=[];
   return {
    bind(...values){params=values;return this},
    async run(){const r=await client.query(sql,params);return {meta:r.meta||{}}},
    async all(){const r=await client.query(sql,params);return {results:r.results||[]}},
    async first(){const r=await client.query(sql,params);return r.results?.[0]||null}
   }
  }}};
 }
}
export class TelegramBot{
 constructor(token,fetchFn=fetch){
  assert(/^\d{6,12}:[A-Za-z0-9_-]{20,}$/.test(safe(token)),'telegram_bot_token_missing');
  this.token=token;this.fetchFn=fetchFn;this.me=null;
 }
 async api(method,payload={}){
  try{
   const res=await this.fetchFn('https://api.telegram.org/bot'+this.token+'/'+method,{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify(payload),signal:AbortSignal.timeout(25000)});
   const body=await res.json();
   if(!res.ok||body?.ok!==true)
    throw Error('telegram_'+String(body?.error_code||res.status));
   return body.result;
  }catch(err){
   if(err?.message?.startsWith('telegram_'))throw err;
   throw Error('telegram_response_uncertain');
  }
 }
 async identity(){
  if(!this.me){
   const m=await this.api('getMe');
   assert(n(m?.id)&&m?.is_bot===true,'invalid_bot_identity');
   this.me=m;
  }
  return this.me;
 }
 async verifyChannel(chat,{privateOnly=false,publicOnly=false,mayProtected=false}={}){
  const me=await this.identity();
  const info=await this.api('getChat',{chat_id:chat});
  assert(info?.type==='channel'&&n(info.id),'not_broadcast_channel');
  if(privateOnly)assert(!info.username,'source_or_library_not_private');
  if(publicOnly)assert(info.username,'target_not_public');
  if(!mayProtected)assert(!info.has_protected_content,'protected_channel_refused');
  const member=await this.api('getChatMember',{chat_id:info.id,user_id:me.id});
  assert(['administrator','creator'].includes(member?.status)&&
   (member?.status==='creator'||member.can_post_messages===true),
   'bot_missing_channel_post_right');
  return info;
 }
}

export class FallbackPublisher{
 constructor({db,categoryBots,targets,formationTargets,stage,folder,env,tokenGenerator}){
  this.db=db;this.env=env;this.journalEnv=db.env();
  this.categoryBots=categoryBots;this.targets=targets;
  this.formationTargets=formationTargets;this.stage=stage;
  this.folder=folder;this.tokenGenerator=tokenGenerator||
   (()=>randomBytes(18).toString('base64url'));
  this.audit={selected:0,published:0,blocked:0,uncertain:0,categories:{}};
 }
 async lookup(sql,params=[]){return (await this.db.query(sql,params)).results||[]}
 async receipt(bot,{category,key,stage,target,source,messageId,method='copyMessage',payload={}}){
  const op={category,content_key:key,stage,target_chat_id:String(target),
   source_chat_id:String(source),source_message_id:Number(messageId)};
  return await performJournaledCopy(this.journalEnv,op,async()=>{
   const body=method==='copyMessage'?{
    chat_id:target,from_chat_id:source,message_id:messageId,
    disable_notification:true,...payload
   }:{chat_id:target,...payload};
   const result=await bot.api(method,body);
   assert(n(result?.message_id),'telegram_send_without_message_receipt');
   return Number(result.message_id);
  });
 }
 async registry(stockChat,stockMessage,title,publicHandle){
  const ready=await this.lookup("SELECT stock_chat_id,radar_bot_id FROM cine_private_stock_config WHERE singleton=1 AND ready=1");
  assert(ready.length===1&&String(ready[0].stock_chat_id)===String(stockChat)&&n(ready[0].radar_bot_id),'stock_registry_mismatch');
  const enabled=await this.lookup("SELECT value FROM bot_settings WHERE setting_key='cine_delivery_enabled'");
  assert(enabled.length===1&&String(enabled[0].value)==='1','radar_downloads_disabled');
  const prior=await this.lookup('SELECT token,status FROM cine_classic_links WHERE source_chat_id=? AND source_message_id=?',
   [String(stockChat),Number(stockMessage)]);
  if(prior.length){
   assert(prior.length===1&&prior[0].status==='published'&&/^[A-Za-z0-9_-]{24}$/.test(prior[0].token),
    'registry_existing_link_not_published');
   return tgDownload(prior[0].token);
  }
  const token=this.tokenGenerator();
  assert(/^[A-Za-z0-9_-]{24}$/.test(token),'invalid_registry_token');
  await this.db.query(
   "INSERT OR IGNORE INTO cine_classic_links"+
   "(token,source_chat_id,source_message_id,title,public_handle,status)"+
   " VALUES(?,?,?,?,?,'published')",
   [token,String(stockChat),Number(stockMessage),String(title).slice(0,180),publicHandle]
  );
  const confirmed=await this.lookup('SELECT token,status FROM cine_classic_links WHERE source_chat_id=? AND source_message_id=?',
   [String(stockChat),Number(stockMessage)]);
  assert(confirmed.length===1&&confirmed[0].status==='published'&&
   /^[A-Za-z0-9_-]{24}$/.test(confirmed[0].token),'registry_receipt_uncertain');
  return tgDownload(confirmed[0].token);
 }
 async verifiedTargets(category,source){
  const bot=this.categoryBots[category];
  const t=this.targets[category];
  assert(bot&&t&&ID.test(String(t.private))&&HANDLE.test(String(t.public)),'missing_category_bot_or_targets');
  const [src,priv,pub]=await Promise.all([
   bot.verifyChannel(source,{privateOnly:true}),
   bot.verifyChannel(t.private,{privateOnly:true}),
   bot.verifyChannel(t.public,{publicOnly:true})
  ]);
  assert(String(src.id)===String(source)&&String(priv.id)===String(t.private)&&
   String(pub.username).toLowerCase()===t.public.slice(1).toLowerCase(),
   'telegram_channel_identity_mismatch');
  assert(src.id!==priv.id&&src.id!==pub.id&&pub.id!==priv.id,
   'overlapping_source_and_destinations');
  const rescue=await this.lookup(
   'SELECT invite_url FROM cine_classic_rescue_config WHERE LOWER(public_handle)=LOWER(?)',
   [t.public]
  );
  assert(rescue.length===1&&INVITE.test(safe(rescue[0].invite_url)),
   'verified_rescue_link_missing');
  const stock=await this.lookup('SELECT stock_chat_id FROM cine_private_stock_config WHERE singleton=1 AND ready=1');
  assert(stock.length===1&&ID.test(String(stock[0].stock_chat_id)),
   'verified_central_stock_missing');
  const central=String(stock[0].stock_chat_id);
  await bot.verifyChannel(central,{privateOnly:true});
  const identity=await bot.identity();
  const allowed=await this.lookup('SELECT bot_id FROM cine_private_stock_bots WHERE bot_id=? AND can_post=1',
   [Number(identity.id)]);
  assert(allowed.length===1,'publisher_not_authorized_for_central_stock');
  return {bot,privateChat:String(priv.id),publicChat:String(pub.id),
   publicHandle:t.public,central,rescue:rescue[0].invite_url};
 }
 async copyFilm(item){
  const t=await this.verifiedTargets(item.category,item.source_chat_id);
  assert(FOLDER.test(this.folder),'folder_missing');
  const title=item.key.split(':').slice(1).join(' ');
  const mainKey=item.key;
  // Register central media before any public links can be advertised.
  const stock=await this.receipt(t.bot,{category:item.category,key:mainKey,
   stage:'central_stock',target:t.central,source:item.source_chat_id,
   messageId:item.video_message_id,payload:{caption:'🎞️ '+title}});
  const download=await this.registry(t.central,stock.message_id,title,t.publicHandle);
  const privateVideo=await this.receipt(t.bot,{category:item.category,key:mainKey,
   stage:'private_video',target:t.privateChat,source:item.source_chat_id,
   messageId:item.video_message_id,payload:{caption:'🎞️ '+title}});
  assert(privateVideo.status==='complete','private_video_receipt_incomplete');
  const cover=await this.receipt(t.bot,{category:item.category,key:mainKey,
   stage:'private_poster',target:t.privateChat,source:item.source_chat_id,
   messageId:item.poster_message_id,payload:{caption:'🎬 '+title,
    reply_markup:privateKeyboard(t.publicHandle,download,this.folder)}});
  const buttons=publicKeyboard(item.category,
   internalMessageUrl(t.privateChat,cover.message_id),download,t.rescue,this.folder);
  await this.receipt(t.bot,{category:item.category,key:mainKey,
   stage:'public_poster',target:t.publicChat,source:item.source_chat_id,
   messageId:item.poster_message_id,payload:{caption:'🎬 '+title,reply_markup:buttons}});
  await this.receipt(t.bot,{category:item.category,key:mainKey,
   stage:'public_video',target:t.publicChat,source:item.source_chat_id,
   messageId:item.video_message_id,payload:{caption:'🎞️ '+title,reply_markup:buttons}});
  await this.db.query(
   "UPDATE cine_manual_fallback_inbox SET state='published',updated_at=CURRENT_TIMESTAMP "+
   "WHERE chat_id=? AND message_id IN (?,?) AND state='indexed'",
   [item.source_chat_id,item.poster_message_id,item.video_message_id]);
 }
 async copySeason(item){
  const t=await this.verifiedTargets(item.category,item.source_chat_id);
  const icon=item.category==='animes'?'🌸':'📺';
  const title=item.title+' — S'+String(item.season).padStart(2,'0');
  const downloads=[];
  for(const ep of item.episodes){
   const key=item.key+':E'+ep.number;
   const label=title+'E'+String(ep.number).padStart(2,'0');
   const stock=await this.receipt(t.bot,{category:item.category,key,
    stage:'central_stock',target:t.central,source:item.source_chat_id,
    messageId:ep.video_message_id,payload:{caption:icon+' '+label}});
   const link=await this.registry(t.central,stock.message_id,label,t.publicHandle);
   downloads.push({ep,key,link});
  }
  const indexBody=icon+' '+title+'\n'+'Téléchargement :\n'+
   downloads.map(x=>'E'+String(x.ep.number).padStart(2,'0')+' — '+x.link).join('\n');
  assert(indexBody.length<=3500,'index_too_long');
  const index=await this.receipt(t.bot,{category:item.category,key:item.key,
   stage:'private_index',target:t.privateChat,source:item.source_chat_id,
   messageId:item.poster_message_id,method:'sendMessage',payload:{
    text:indexBody,disable_web_page_preview:true}});
  const indexUrl=internalMessageUrl(t.privateChat,index.message_id);
  for(const {ep,key} of downloads){
   await this.receipt(t.bot,{category:item.category,key,stage:'private_video',
    target:t.privateChat,source:item.source_chat_id,
    messageId:ep.video_message_id,payload:{caption:icon+' '+title+' E'+ep.number}});
  }
  const cover=await this.receipt(t.bot,{category:item.category,key:item.key,
   stage:'private_poster',target:t.privateChat,source:item.source_chat_id,
   messageId:item.poster_message_id,payload:{caption:icon+' '+title,
    reply_markup:privateKeyboard(t.publicHandle,indexUrl,this.folder)}});
  const buttons=publicKeyboard(item.category,
   internalMessageUrl(t.privateChat,cover.message_id),indexUrl,t.rescue,this.folder);
  await this.receipt(t.bot,{category:item.category,key:item.key,
   stage:'public_poster',target:t.publicChat,source:item.source_chat_id,
   messageId:item.poster_message_id,payload:{caption:icon+' '+title,reply_markup:buttons}});
  for(const {ep,key} of downloads){
   await this.receipt(t.bot,{category:item.category,key,stage:'public_video',
    target:t.publicChat,source:item.source_chat_id,messageId:ep.video_message_id,
    payload:{caption:icon+' '+title+' E'+ep.number,reply_markup:buttons}});
  }
  // Mark only after the ENTIRE season batch completed. A partial season must
  // remain eligible for resumption with its same durable per-episode receipts.
  await this.db.query(
   "UPDATE cine_manual_fallback_inbox SET state='published',updated_at=CURRENT_TIMESTAMP "+
   "WHERE chat_id=? AND message_id IN ("+
   [item.poster_message_id,...item.episodes.map(x=>x.video_message_id)].map(()=>'?').join(',')+
   ") AND state='indexed'",
   [item.source_chat_id,item.poster_message_id,...item.episodes.map(x=>x.video_message_id)]);
 }
 async copyCourse(item){
  const bot=this.categoryBots[item.category];
  const dest=this.formationTargets[item.category.slice('formation_'.length)];
  const stage=this.stage;
  assert(bot&&ID.test(String(item.source_chat_id))&&ID.test(String(stage))&&
   (ID.test(String(dest))||HANDLE.test(String(dest))),
   'formation_bot_or_target_missing');
  const [src,technical,target]=await Promise.all([
   bot.verifyChannel(item.source_chat_id,{privateOnly:true}),
   bot.verifyChannel(stage,{privateOnly:true}),
   bot.verifyChannel(dest)
  ]);
  assert(src.id!==target.id&&technical.id!==target.id,
   'formation_stage_and_destination_overlap');
  const label='📚 '+item.key.split(':').slice(1).join(' ');
  for(const part of item.parts){
   const base=item.key+':part'+part.number;
   const mid=await this.receipt(bot,{category:item.category,
    key:base+':stage',stage:'formation_file',target:String(technical.id),
    source:item.source_chat_id,messageId:part.message_id,
    payload:{caption:label+' — '+part.number+'/'+item.parts.length}});
   await this.receipt(bot,{category:item.category,key:base+':destination',
    stage:'formation_file',target:String(target.id),
    source:String(technical.id),messageId:mid.message_id,
    payload:{caption:label+' — '+part.number+'/'+item.parts.length+
     '\nSource : dépôt autorisé du propriétaire'}});
  }
  await this.db.query(
   "UPDATE cine_manual_fallback_inbox SET state='published',updated_at=CURRENT_TIMESTAMP "+
   "WHERE chat_id=? AND category=? AND message_id IN ("+
   item.parts.map(()=>'?').join(',')+") AND state='indexed'",
   [item.source_chat_id,item.category,...item.parts.map(x=>x.message_id)]);
 }
 async publishSelection(selection){
  for(const item of selection.eligible){
   try{
    if(item.episodes)await this.copySeason(item);
    else if(item.parts)await this.copyCourse(item);
    else await this.copyFilm(item);
    this.audit.published++;
   }catch(err){
    this.audit.uncertain++;
    // Stop the entire batch. Partial operations might have reached Telegram.
    // No global retry until D1 receipts are reconciled.
    throw Error('manual_fallback_category_stopped_'+String(item.category)+
     '_'+String(err?.name||'error'));
   }
  }
  return this.audit;
 }
}
export async function readManualFallbackQueue(db){
 const rows=(await db.query(
  "SELECT i.chat_id,i.message_id,i.category,i.kind,i.file_unique_id,"+
  "i.filename,i.mime_type,i.caption,i.grouped_id,i.posted_at,i.state "+
  "FROM cine_manual_fallback_inbox i JOIN cine_manual_fallback_sources s "+
  "ON i.chat_id=s.chat_id AND i.category=s.category "+
  "WHERE i.state='indexed' AND s.enabled=1 AND s.owner_approved=1 "+
  "AND s.rights_attested=1 AND s.bot_access_verified=1 "+
  "ORDER BY i.posted_at,i.chat_id,i.message_id LIMIT 2001"
 )).results||[];
 assert(rows.length<=2000,'manual_vault_queue_too_large_for_single_safe_scan');
 return rows;
}
export async function chooseLiveFallback(db,rows,{personalStatus,enabled,
 publishedKeys=new Set(),publishedFiles=new Set(),
 publishedEpisodes=new Set(),existingCounts={}}={}){
 const plans={movies:planMovies(rows),seasons:planSeasons(rows,{publishedEpisodes}),
              courses:planCourses(rows)};
 const uncertain=(await db.query(
  "SELECT DISTINCT content_key FROM cine_manual_fallback_receipts "+
  "WHERE status IN ('inflight','uncertain')")).results||[];
 const existing=await db.query("SELECT COUNT(*) AS n FROM cine_manual_fallback_sources "+
  "WHERE enabled=1 AND owner_approved=1 AND rights_attested=1 AND bot_access_verified=1");
 const ready=Number(existing.results?.[0]?.n||0)>0;
 const selection=selectManualCycle(plans,{
  personalStatus,fallbackEnabled:Boolean(enabled),botReady:ready,
  stockReady:ready,rightsAttested:ready,receiptsReady:true,
  existingCounts,publishedKeys,publishedFiles,
  uncertainKeys:new Set(uncertain.map(x=>x.content_key))});
 if(uncertain.length) {
  // Any unknown write blocks the whole cycle, including different titles,
  // until an operator reconciles the previous Telegram response.
  selection.eligible=[];
  selection.reason='unknown_publication_receipts_require_reconciliation';
 }
 return {selection,plans};
}
