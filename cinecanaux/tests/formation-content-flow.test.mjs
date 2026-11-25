import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {ensureManualFallbackSchema,ingestManualChannelPost}
 from '../manual-fallback-inbox.mjs';
import {readManualFallbackQueue} from '../manual-fallback-live.mjs';
import {planCourses} from '../manual-fallback-planner.mjs';
const source='-1001111111111';
function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){let params=[];return {
  bind(...x){params=x;return this},
  async run(){return {meta:{changes:sqlite.prepare(sql).run(...params).changes}}},
  async first(){return sqlite.prepare(sql).get(...params)||null},
  async all(){return {results:sqlite.prepare(sql).all(...params)}}
 }}};
 const env={DB,CINEX_MANUAL_INBOX_ENABLED:'true'};
 const db={async query(sql,args=[]){return {results:sqlite.prepare(sql).all(...args)}}};
 return {sqlite,env,db};
}
async function seed(f){
 await ensureManualFallbackSchema(f.env);
 const stmt=f.sqlite.prepare(
  'INSERT INTO cine_manual_fallback_sources'+
  '(chat_id,category,rights_attested,bot_access_verified,owner_approved,enabled)'+
  'VALUES(?,?,?,1,1,?)');
 stmt.run(source,'formation_general',0,0);
 stmt.run('-1002222222222','formation_digitale',1,1);
 stmt.run('-1003333333333','formation_business',1,1);
 stmt.run('-1004444444444','formation_finance',0,0);
 stmt.run('-1005555555555','formation_mindset',0,0);
}
function post(id,kind,caption='',filename=''){
 const m={chat:{type:'channel',id:Number(source)},message_id:id,date:1795600000+id,caption};
 if(kind==='poster')m.photo=[{file_unique_id:'image-'+id,file_size:10000}];
 if(kind==='file')m.document={file_unique_id:'doc-'+id,
  file_name:filename,mime_type:'application/zip',file_size:300000};
 if(kind==='text'){m.text=caption;delete m.caption}
 return {channel_post:m};
}
test('rich technical course + interleaved like request + file => only two eligible posts',async()=>{
 const f=fixture();await seed(f);
 const cover='📊 Tout savoir sur WordPress 6 – Formation complète\n'+
  '🎥 Vidéo | 🗣 Français | 🎓 Formateur : Enseignant autorisé\n'+
  '🚀 Apprenez à créer et publier un site avec WordPress.\n'+
  'Abonnez-vous sur @third_party\nhttps://t.me/thirdparty';
 const a=await ingestManualChannelPost(f.env,post(1,'poster',cover));
 assert.equal(a.category,'formation_digitale');
 assert.equal(a.state,'indexed');
 const ad=await ingestManualChannelPost(f.env,post(2,'text','Il faut liker, partager et vous abonner'));
 assert.equal(ad.accepted,false);
 assert.equal(ad.reason,'unrelated_formation_text');
 const b=await ingestManualChannelPost(f.env,post(3,'file','',
  'WordPress 6 - Créer, configurer et publier votre site.rar'));
 assert.equal(b.category,'formation_digitale');
 assert.equal(b.state,'indexed');
 const rows=await readManualFallbackQueue(f.db);
 assert.equal(rows.length,2);
 const plans=planCourses(rows);
 assert.equal(plans.items.length,1);
 assert.equal(plans.items[0].poster_message_id,1);
 assert.deepEqual(plans.items[0].parts.map(x=>x.message_id),[3]);
 assert.match(plans.items[0].description,/Apprenez à créer/);
 assert.equal(plans.items[0].description.includes('t.me/'),false);
 assert.equal(plans.items[0].description.includes('@third_party'),false);
});
test('unrelated stored file cannot piggyback on a nearby real course cover',async()=>{
 const f=fixture();await seed(f);
 await ingestManualChannelPost(f.env,post(5,'poster',
  '📚 Apprendre Python et la Data Science – Formation complète\n🎥 Vidéo en français, 12 heures\n'+
  'Un guide pédagogique avec des exercices.'));
 const unrelated=await ingestManualChannelPost(f.env,post(6,'file','','mes-notes-personnelles.zip'));
 assert.equal(unrelated.state,'needs_review');
 assert.equal((await readManualFallbackQueue(f.db)).length,1);
 assert.equal(planCourses(await readManualFallbackQueue(f.db)).items.length,0);
});
test('natural multipart archives without a declared final total stay quarantined',async()=>{
 const f=fixture();await seed(f);
 await ingestManualChannelPost(f.env,post(11,'poster',
  '📊 Tout savoir sur Power BI – Formation complète\n🎥 Vidéo de formation, 8h\n'+
  'Apprenez Power BI et analysez vos données.'));
 await ingestManualChannelPost(f.env,post(12,'file','','Power_BI_formation_part1.rar'));
 await ingestManualChannelPost(f.env,post(13,'text','Likez pour la suite !'));
 await ingestManualChannelPost(f.env,post(14,'file','','Power_BI_formation_part2.rar'));
 const plans=planCourses(await readManualFallbackQueue(f.db));
 assert.equal(plans.items.length,0);
 assert.ok(plans.review.some(x=>x.reason==='natural_course_total_required_for_multipart'));
});
test('explicit multipart course remains complete through arbitrary interruptions',async()=>{
 const f=fixture();await seed(f);
 await ingestManualChannelPost(f.env,post(20,'poster',
  'Cours: intro-web-2026\nCatégorie: Digitale\nTitre: Initiation au développement web\nAuteur: Enseignant autorisé'));
 await ingestManualChannelPost(f.env,post(21,'file','Cours: intro-web-2026\nTotal: 2\nPartie: 1/2','fichier1.zip'));
 await ingestManualChannelPost(f.env,post(22,'text','Abonnez-vous à @promo'));
 await ingestManualChannelPost(f.env,post(23,'file','Cours: intro-web-2026\nTotal: 2\nPartie: 2/2','fichier2.zip'));
 const result=planCourses(await readManualFallbackQueue(f.db));
 assert.equal(result.items.length,1);
 assert.deepEqual(result.items[0].parts.map(x=>x.number),[1,2]);
 assert.equal(f.sqlite.prepare('SELECT COUNT(*) n FROM cine_manual_fallback_inbox').get().n,3);
});
