// Bot-only scheduled fallback using the VERIFIED private CineRadar D1 inbox.
// Invoked by a separate GitHub Actions job after the personal session probe.
// All logs are aggregate counts; never print media IDs, private chat IDs, or tokens.
import {readFileSync} from 'node:fs';
import {D1Remote,TelegramBot,FallbackPublisher,readManualFallbackQueue,
 chooseLiveFallback} from './manual-fallback-live.mjs';
import {normalizedManualTitle} from './manual-fallback-inbox.mjs';

const env=process.env;
const CHAT=/^-100\d{6,}$/;
const HANDLE=/^@[A-Za-z][A-Za-z0-9_]{4,31}$/;
const account='9c86118191b804d91b5f5b2c89114999';
const database='fa8b5009-bc1a-4a6e-b143-7a487c7297a5';
const norm=x=>String(x||'').trim();

function targets(){
 const ordinary={
  films:['TG_PRIVATE_CHANNEL','TG_PUBLIC_CHANNEL','CINEX_BOT_TOKEN'],
  desir:['DESIR_PRIVATE_CHANNEL','DESIR_PUBLIC_CHANNEL','DESIR_BOT_TOKEN'],
  comedie:['COMEDIE_PRIVATE_CHANNEL','COMEDIE_PUBLIC_CHANNEL','COMEDIE_BOT_TOKEN'],
  action:['ACTION_PRIVATE_CHANNEL','ACTION_PUBLIC_CHANNEL','ACTION_BOT_TOKEN'],
  series:['SERIES_PRIVATE_CHANNEL','SERIES_PUBLIC_CHANNEL','SERIES_BOT_TOKEN'],
  animes:['ANIME_PRIVATE_CHANNEL','ANIME_PUBLIC_CHANNEL','ANIME_BOT_TOKEN'],
 };
 const chats={},bots={};
 for(const [category,refs] of Object.entries(ordinary)){
  const [privateKey,publicKey,tokenKey]=refs;
  const privateChat=norm(env[privateKey]),publicHandle=norm(env[publicKey]);
  const token=norm(env[tokenKey]);
  if(!CHAT.test(privateChat)||!HANDLE.test(publicHandle)||!token)continue;
  chats[category]={private:privateChat,public:publicHandle};
  bots[category]=new TelegramBot(token);
 }
 const forms={};
 try{
  const x=JSON.parse(env.FORMATION_DESTINATIONS_JSON||'{}');
  if(x&&typeof x==='object'&&!Array.isArray(x))
   for(const cat of ['general','business','finance','digitale','mindset']){
    const str=norm(x[cat]);
    if(CHAT.test(str)||HANDLE.test(str))forms[cat]=str;
   }
 }catch{}
 const formationToken=norm(env.FORMATION_BOT_TOKEN);
 if(formationToken){
  const bot=new TelegramBot(formationToken);
  for(const cat of ['general','business','finance','digitale','mindset']){
   if(forms[cat])bots['formation_'+cat]=bot;
  }
 }
 return {chats,bots,forms,stage:norm(env.FORMATION_STAGE_CHAT)};
}

function publishedEpisodes(){
 const found=new Set();
 const inventories=[
  ['series','telegram-film-relay/state/series_catalog.json'],
  ['animes','telegram-film-relay/state/anime_catalog.json']
 ];
 for(const [category,path] of inventories){
  try{
   const data=JSON.parse(readFileSync(path,'utf8'));
   for(const entry of Object.values(data.series||{})){
    if(!entry||typeof entry!=='object'||!entry.episodes)continue;
    const title=normalizedManualTitle(entry.title||'');
    if(title.length<5)continue;
    for(const [season,records] of Object.entries(entry.episodes)){
     const sn=Number(season);
     if(!Number.isInteger(sn)||sn<1||sn>50||!records)continue;
     const prefix=category+':'+title+':S'+String(sn).padStart(2,'0')+':E';
     for(const number of Object.keys(records)){
      const en=Number(number);
      if(Number.isInteger(en)&&en>=1&&en<=999&&records[number]?.message_id)
       found.add(prefix+en);
     }
    }
   }
  }catch{/* A missing history must BLOCK its category, not indicate no posts. */
   return null;
  }
 }
 return found;
}

async function historical(db,chats,rows){
 const keys=new Set(),files=new Set();
 const receipts=(await db.query(
  "SELECT category,content_key,stage,status FROM cine_manual_fallback_receipts "+
  "WHERE status='complete'")).results||[];
 for(const r of receipts){
  if(r.stage==='public_video'||r.stage==='public_poster')
   keys.add(r.content_key);
  if(r.stage==='formation_file'&&String(r.content_key).includes(':destination'))
   keys.add(String(r.content_key).split(':part')[0]);
 }
 // The previous personal mode registered films/episodes at CineRadar. Match
 // only normalized titles in the exact configured public channel; a renamed
 // movie with a new Telegram file ID may still require manual review.
 const old=(await db.query(
  "SELECT title,public_handle,created_at FROM cine_classic_links WHERE status='published'"
 )).results||[];
 const now=new Date(),floor=Math.floor(now.getUTCHours()/6)*6;
 const started=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),
  now.getUTCDate(),floor)).toISOString().slice(0,19).replace('T',' ');
 const counts={};
 for(const r of old){
  const h=norm(r.public_handle).toLowerCase();
  const cat=Object.entries(chats).find(([_,value])=>
   value.public.toLowerCase()===h)?.[0];
  if(!cat)continue;
  if(norm(r.created_at)>=started)
   counts[cat]=(counts[cat]||0)+1;
  const seen=normalizedManualTitle(r.title).replace(/\b(?:19|20)\d{2}\b/g,'').trim();
  for(const item of rows){
   if(item.category!==cat||item.kind!=='video')continue;
   const t=String(item.caption||'');
   const match=/^\s*(?:titre|title)\s*:\s*(.+?)\s*$/im.exec(t);
   if(!match)continue;
   const expected=normalizedManualTitle(match[1]).replace(/\b(?:19|20)\d{2}\b/g,'').trim();
   if(expected.length>=7&&(seen===expected||seen.startsWith(expected+' ')))
    keys.add(cat+':'+expected+':'+
     (/(?:19|20)\d{2}/.exec(t)||[])[0]);
  }
 }
 for(const row of rows){
  if(row.state==='published'&&row.file_unique_id)files.add(row.file_unique_id);
 }
 return {keys,files,counts};
}

async function main(){
 const enabled=env.CINEX_MANUAL_FALLBACK_ENABLED==='true';
 const status=norm(env.PERSONAL_SESSION_STATUS);
 if(!enabled){
  console.log('MANUAL_FALLBACK_DISABLED');return;
 }
 if(!['session_missing','session_revoked'].includes(status)){
  console.log('MANUAL_FALLBACK_NO_ACTIVATION_PERSONAL_STATUS',status||'unknown');
  return;
 }
 const token=norm(env.CLOUDFLARE_API_TOKEN||env.CF_API_TOKEN);
 if(!token)throw Error('cloudflare_d1_credentials_missing');
 const db=new D1Remote({token,account:env.CLOUDFLARE_ACCOUNT_ID||account,
  db:env.CINERADAR_D1_DATABASE_ID||database});
 const sources=(await db.query(
  "SELECT category,COUNT(*) AS n FROM cine_manual_fallback_sources "+
  "WHERE owner_approved=1 AND enabled=1 AND rights_attested=1 "+
  "AND bot_access_verified=1 GROUP BY category")).results||[];
 if(!sources.length){
  console.log('MANUAL_FALLBACK_NO_VERIFIED_SOURCES');return;
 }
 const {chats,bots,forms,stage}=targets();
 const rows=await readManualFallbackQueue(db);
 if(!rows.length){console.log('MANUAL_FALLBACK_NO_NEW_MEDIA');return;}
 const oldEpisodes=publishedEpisodes();
 if(!oldEpisodes){
  console.log('MANUAL_FALLBACK_HISTORICAL_CATALOG_UNAVAILABLE');return;
 }
 const history=await historical(db,chats,rows);
 const {selection,plans}=await chooseLiveFallback(db,rows,{
  personalStatus:status,enabled,publishedKeys:history.keys,
  publishedFiles:history.files,publishedEpisodes:oldEpisodes,
  existingCounts:history.counts
 });
 console.log('MANUAL_FALLBACK_PREFLIGHT',JSON.stringify({
  eligible:selection.eligible.length,
  blocked:selection.blocked.length,
  films:plans.movies.items.length,
  seasons:plans.seasons.items.length,
  formations:plans.courses.items.length,
  reviews:plans.movies.review.length+plans.seasons.review.length+plans.courses.review.length,
  reason:selection.reason||'none'
 }));
 if(!selection.eligible.length)return;
 const engine=new FallbackPublisher({db,categoryBots:bots,targets:chats,
  formationTargets:forms,stage,
  folder:env.CINEX_FILM_FOLDER_URL||'',
  env});
 await engine.publishSelection(selection);
 console.log('MANUAL_FALLBACK_PUBLISHED',engine.audit.published);
}
main().catch(e=>{
 // Never print raw Telegram exception or private D1 source identifiers.
 console.error('MANUAL_FALLBACK_STOPPED',String(e?.message||'error').replace(/-100\d+/g,'[private]'));
 process.exitCode=1;
});
