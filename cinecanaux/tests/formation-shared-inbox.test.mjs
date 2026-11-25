import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {ensureManualFallbackSchema,ingestManualChannelPost}
 from '../manual-fallback-inbox.mjs';
import {readManualFallbackQueue} from '../manual-fallback-live.mjs';
import {planCourses} from '../manual-fallback-planner.mjs';
const shared='-1001111111111',specialized='-1002222222222';
function setup(){
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){let params=[];return {
  bind(...xs){params=xs;return this},
  async run(){return {meta:{changes:sqlite.prepare(sql).run(...params).changes}}},
  async first(){return sqlite.prepare(sql).get(...params)||null},
  async all(){return {results:sqlite.prepare(sql).all(...params)}},
 };}};
 const env={DB,CINEX_MANUAL_INBOX_ENABLED:'true'};
 const db={async query(sql,params=[]){const stmt=sqlite.prepare(sql);
  if(/^\s*SELECT/i.test(sql))return {results:stmt.all(...params)};
  return {results:[],meta:{changes:stmt.run(...params).changes}};
 }};
 return {sqlite,env,db};
}
async function seed(f,{licensedBusiness=false,licensedFinance=false}={}){
 await ensureManualFallbackSchema(f.env);
 const stmt=f.sqlite.prepare(
  'INSERT INTO cine_manual_fallback_sources'+
  '(chat_id,category,rights_attested,bot_access_verified,owner_approved,enabled)'+
  ' VALUES(?,?,?,1,1,?)');
 stmt.run(shared,'formation_general',0,0);
 stmt.run(specialized,'formation_business',licensedBusiness?1:0,licensedBusiness?1:0);
 stmt.run('-1003333333333','formation_finance',licensedFinance?1:0,licensedFinance?1:0);
 stmt.run('-1004444444444','formation_digitale',0,0);
 stmt.run('-1005555555555','formation_mindset',0,0);
}
function event(id,caption,kind='poster',chat=shared){
 const message={message_id:id,chat:{id:Number(chat),type:'channel'},
  caption,date:1795600000+id};
 if(kind==='poster')
  message.photo=[{file_unique_id:'poster-unique-'+id,file_size:12000}];
 else message.document={file_unique_id:'course-file-'+id,
  file_name:'part-'+id+'.zip',mime_type:'application/zip',file_size:155000};
 return {channel_post:message,update_id:id};
}
test('single shared private source accepts five routes without bypassing rights',async()=>{
 const f=setup();await seed(f);
 const a=await ingestManualChannelPost(f.env,event(1,
  'Cours: ventes-2026\nCatégorie: Business\nAuteur: Formateur autorisé'));
 const b=await ingestManualChannelPost(f.env,event(2,
  'Cours: bitcoin-2026\nCatégorie: Finance\nAuteur: Formateur autorisé'));
 assert.equal(a.category,'formation_business');
 assert.equal(b.category,'formation_finance');
 assert.equal(a.state,'needs_review');assert.equal(b.state,'needs_review');
 assert.equal((await readManualFallbackQueue(f.db)).length,0);
 assert.deepEqual(f.sqlite.prepare('SELECT DISTINCT chat_id FROM cine_manual_fallback_inbox')
  .all().map(x=>x.chat_id),[shared]);
});
test('licensed route receives ordered complete course from one private source',async()=>{
 const f=setup();await seed(f,{licensedBusiness:true});
 await ingestManualChannelPost(f.env,event(10,
  'Cours: cours-vente-2026\nCatégorie: Business\nAuteur: Formateur autorisé'));
 for(let part=1;part<=2;part++){
  const caption='Cours: cours-vente-2026\nTotal: 2\nPartie: '+part+'/2';
  const result=await ingestManualChannelPost(f.env,event(10+part,caption,'file'));
  assert.equal(result.category,'formation_business');
  assert.equal(result.state,'indexed');
 }
 const rows=await readManualFallbackQueue(f.db);
 assert.equal(rows.length,3);
 const plans=planCourses(rows);
 assert.equal(plans.items.length,1);
 assert.equal(plans.items[0].category,'formation_business');
 assert.deepEqual(plans.items[0].parts.map(x=>x.number),[1,2]);
});
test('cover arriving after parts safely reconciles only matching unknown files',async()=>{
 const f=setup();await seed(f,{licensedFinance:true});
 const early=await ingestManualChannelPost(f.env,event(1,
  'Cours: formation-avancee-2026\nTotal: 1\nPartie: 1/1','file'));
 assert.equal(early.state,'needs_review');
 assert.equal(early.category,'formation_general');
 const cover=await ingestManualChannelPost(f.env,event(2,
  'Cours: formation-avancee-2026\nCatégorie: Finance\nAuteur: Auteur autorisé'));
 assert.equal(cover.category,'formation_finance');
 const rows=await readManualFallbackQueue(f.db);
 assert.equal(rows.length,2);
 assert.ok(rows.every(x=>x.category==='formation_finance'));
 assert.equal(planCourses(rows).items.length,1);
});

test('specialist libraries are never alternative intake vaults',async()=>{
 const f=setup();await seed(f,{licensedBusiness:true});
 const r=await ingestManualChannelPost(f.env,event(99,
  'Cours: cours-vente-2026\nCatégorie: Business','poster',specialized));
 assert.equal(r.accepted,false);
 assert.equal(r.reason,'use_shared_formation_source');
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) AS n FROM cine_manual_fallback_inbox').get().n,0);
});
test('ambiguous course title stays in review even with licensed destinations',async()=>{
 const f=setup();await seed(f,{licensedBusiness:true,licensedFinance:true});
 const r=await ingestManualChannelPost(f.env,event(8,
  'Cours: trading-marketing-2026\nAuteur: Formateur autorisé'));
 assert.equal(r.category,'formation_general');
 assert.equal(r.state,'needs_review');
 assert.equal(f.sqlite.prepare('SELECT review_code FROM cine_manual_fallback_inbox').get().review_code,
  'ambiguous_training_domain');
 assert.equal((await readManualFallbackQueue(f.db)).length,0);
});
test('editing an indexed course to another category quarantines it',async()=>{
 const f=setup();await seed(f,{licensedBusiness:true,licensedFinance:true});
 await ingestManualChannelPost(f.env,event(5,
  'Cours: cours-vente-2026\nCatégorie: Business\nAuteur: Formateur autorisé'));
 const altered=event(5,'Cours: cours-vente-2026\nCatégorie: Finance');
 altered.edited_channel_post=altered.channel_post;delete altered.channel_post;
 const reply=await ingestManualChannelPost(f.env,altered);
 assert.equal(reply.reason,'source_media_changed');
 assert.equal(f.sqlite.prepare('SELECT state FROM cine_manual_fallback_inbox').get().state,'needs_review');
});
test('same course ID in two categories blocks the second poster and files',async()=>{
 const f=setup();await seed(f,{licensedBusiness:true,licensedFinance:true});
 await ingestManualChannelPost(f.env,event(20,
  'Cours: cours-mix-2026\nCatégorie: Business\nAuteur: Formateur autorisé'));
 const result=await ingestManualChannelPost(f.env,event(21,
  'Cours: cours-mix-2026\nCatégorie: Finance\nAuteur: Formateur autorisé'));
 assert.equal(result.state,'needs_review');
 assert.equal(result.review,'conflicting_course_covers');
 const part=await ingestManualChannelPost(f.env,event(22,
  'Cours: cours-mix-2026\nTotal: 1\nPartie: 1/1','file'));
 assert.equal(part.state,'needs_review');
});
