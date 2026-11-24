import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {
 ensureManualFallbackSchema,identifyManualMedia,ingestManualChannelPost,
 manualIdentity,planManualMediaPairs,manualFallbackCounts,
} from '../manual-fallback-inbox.mjs';

function fixture(enabled='true'){
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){
  let values=[];
  return {
   bind(...items){values=items;return this;},
   async run(){return {meta:{changes:sqlite.prepare(sql).run(...values).changes}}},
   async first(){return sqlite.prepare(sql).get(...values)||null;},
   async all(){return {results:sqlite.prepare(sql).all(...values)}},
  };
 }};
 return {sqlite,env:{DB,CINEX_MANUAL_INBOX_ENABLED:enabled}};
}
const chat=-1001234567890;
function post(id,kind='video',caption='Titre: Un Film (2025)',unique='distinct-video-111'){
 const m={message_id:id,chat:{type:'channel',id:chat},
  caption,date:1795560000};
 if(kind==='poster')m.photo=[{file_unique_id:unique,file_size:1000}];
 if(kind==='video')m.document={
  file_unique_id:unique,file_name:'un-film-2025.mkv',mime_type:'video/x-matroska',file_size:250000000};
 if(kind==='course')m.document={
  file_unique_id:unique,file_name:'training.zip',mime_type:'application/zip',file_size:5000000};
 return {channel_post:m,update_id:id};
}
async function approved(sqlite,category='films'){
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_sources "+
  "(chat_id,category,rights_attested,bot_access_verified,owner_approved,enabled)"+
  " VALUES (?,?,1,1,1,1)"
 ).run(String(chat),category);
}

test('inbox defaults OFF with zero SQL or Telegram side effects',async()=>{
 const {env}=fixture('false');
 env.DB={prepare(){throw Error('must never access DB')}};
 const reply=await ingestManualChannelPost(env,post(1));
 assert.deepEqual(reply,{enabled:false,accepted:false});
});

test('only explicit approved, rights-attested, bot-verified chat IDs',async()=>{
 const {sqlite,env}=fixture();
 assert.equal((await ingestManualChannelPost(env,post(1))).reason,'not_owner_approved');
 await approved(sqlite);
 const accepted=await ingestManualChannelPost(env,post(2));
 assert.equal(accepted.accepted,true);
 assert.equal(accepted.category,'films');
 assert.equal((await manualFallbackCounts(env))[0].count,1);
});

test('strictly reject unapproved category messages and protected media',async()=>{
 const {sqlite,env}=fixture();await ensureManualFallbackSchema(env);await approved(sqlite);
 const rejected=post(4);
 rejected.channel_post.has_protected_content=true;
 assert.equal((await ingestManualChannelPost(env,rejected)).reason,'unsupported_or_protected');
 assert.equal(sqlite.prepare('SELECT COUNT(*) AS c FROM cine_manual_fallback_inbox').get().c,0);
});

test('duplicate webhook deliveries do not create two messages',async()=>{
 const {sqlite,env}=fixture();await ensureManualFallbackSchema(env);await approved(sqlite);
 await ingestManualChannelPost(env,post(1));
 await ingestManualChannelPost(env,post(1));
 assert.equal(sqlite.prepare('SELECT COUNT(*) AS c FROM cine_manual_fallback_inbox').get().c,1);
});

test('source media swaps are quarantined, no replay',async()=>{
 const {sqlite,env}=fixture();await ensureManualFallbackSchema(env);await approved(sqlite);
 await ingestManualChannelPost(env,post(1));
 const edited=post(1,'video','Titre: Modified (2025)','new-file-222');
 edited.edited_channel_post=edited.channel_post;delete edited.channel_post;
 assert.equal((await ingestManualChannelPost(env,edited)).reason,'source_media_changed');
 assert.equal(sqlite.prepare('SELECT state FROM cine_manual_fallback_inbox').get().state,'needs_review');
});

test('never modify a message already published when edited on Telegram',async()=>{
 const {sqlite,env}=fixture();await ensureManualFallbackSchema(env);await approved(sqlite);
 await ingestManualChannelPost(env,post(1));
 sqlite.prepare("UPDATE cine_manual_fallback_inbox SET state='published'").run();
 assert.equal((await ingestManualChannelPost(env,post(1))).reason,'already_published');
});

test('video as MKV document and PDF or ZIP training archives are captured',()=>{
 assert.equal(identifyManualMedia(post(1).channel_post,'films').kind,'video');
 assert.equal(identifyManualMedia(post(2,'course').channel_post,'formation_business').kind,'course_file');
 assert.equal(identifyManualMedia(post(3,'course').channel_post,'films'),null);
});

test('films must have reliable title and year for a pairing',()=>{
 const film=manualIdentity({category:'films',caption:'Titre: Un Film\nAnnée: 2025'});
 assert.equal(film.reason,'');
 assert.equal(manualIdentity({category:'films',caption:'Un Film'}).key,null);
});

test('series need explicit episode; formation remains grouped separately',()=>{
 const series=manualIdentity({category:'series',caption:'Titre: La Série\nS02E03'});
 assert.equal(series.reason,'');
 assert.equal(manualIdentity({category:'series',caption:'Titre: La Série'}).key,null);
 assert.equal(manualIdentity({category:'formation_finance',caption:'Cours crypto'}).key,null);
});

test('pair exactly one genuine poster and one unique video',()=>{
 const rows=[
  {chat_id:String(chat),message_id:1,category:'films',kind:'poster',state:'indexed',
   caption:'Titre: Un Film\nAnnée: 2025'},
  {chat_id:String(chat),message_id:2,category:'films',kind:'video',state:'indexed',
   caption:'Titre: Un Film\nAnnée: 2025',file_unique_id:'vid-1'},
 ];
 const result=planManualMediaPairs(rows);
 assert.equal(result.pairs.length,1);
 assert.equal(result.pairs[0].video_message_id,2);
 assert.equal(planManualMediaPairs([...rows,{...rows[1],message_id:3}]).pairs.length,0);
});

test('different videos with same title are all quarantined',()=>{
 const a=[
  {chat_id:String(chat),message_id:1,category:'films',kind:'poster',
   state:'indexed',caption:'Titre: Un Film\nAnnée: 2025'},
  {chat_id:String(chat),message_id:2,category:'films',kind:'video',
   state:'indexed',caption:'Titre: Un Film\nAnnée: 2025',
   file_unique_id:'unique-file-a'},
 ];
 const b=a.map(x=>({...x,chat_id:'-1002222222222',
  file_unique_id:x.kind==='video'?'unique-file-b':x.file_unique_id}));
 const out=planManualMediaPairs([...a,...b]);
 assert.equal(out.pairs.length,0);
 assert.ok(out.review.every(x=>x.reason==='multiple_video_versions'));
});

test('same Telegram file claiming two titles is quarantined across categories',()=>{
 const film=[
  {chat_id:String(chat),message_id:1,category:'films',kind:'poster',
   state:'indexed',caption:'Titre: Premier Film\nAnnée: 2025'},
  {chat_id:String(chat),message_id:2,category:'films',kind:'video',
   state:'indexed',caption:'Titre: Premier Film\nAnnée: 2025',
   file_unique_id:'same-telegram-video'},
 ];
 const other=[
  {chat_id:'-1002222222222',message_id:3,category:'comedie',kind:'poster',
   state:'indexed',caption:'Titre: Autre Film\nAnnée: 2025'},
  {chat_id:'-1002222222222',message_id:4,category:'comedie',kind:'video',
   state:'indexed',caption:'Titre: Autre Film\nAnnée: 2025',
   file_unique_id:'same-telegram-video'},
 ];
 const out=planManualMediaPairs([...film,...other]);
 assert.equal(out.pairs.length,0);
 assert.ok(out.review.every(x=>x.reason==='same_video_conflicting_title'));
});

test('training files cannot masquerade as stand-alone videos',()=>{
 const rows=[{chat_id:String(chat),message_id:1,category:'formation_business',
  kind:'course_file',state:'indexed',caption:'Titre: Mon cours'}];
 const result=planManualMediaPairs(rows);
 assert.equal(result.pairs.length,0);
 assert.equal(result.review[0].reason,'course_boundary_requires_review');
});
