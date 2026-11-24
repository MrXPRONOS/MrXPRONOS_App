import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {ensureManualFallbackSchema} from '../manual-fallback-inbox.mjs';
import {auditManualStock} from '../manual-fallback-audit.mjs';

function fixture(){
 const sqlite=new DatabaseSync(':memory:');
 const env={DB:{prepare(sql){
  let params=[];
  return {bind(...p){params=p;return this},
   async run(){return {meta:{changes:sqlite.prepare(sql).run(...params).changes}}},
   async first(){return sqlite.prepare(sql).get(...params)||null},
   async all(){return {results:sqlite.prepare(sql).all(...params)}},
  };
 }}};
 return {sqlite,env};
}
test('missing database cannot report live readiness',async()=>{
 const s=await auditManualStock({});
 assert.equal(s.ready,false);
});
test('empty manual stock reports no sources and no eligible sends',async()=>{
 const {env}=fixture();
 const s=await auditManualStock(env);
 assert.equal(s.ready,true);
 assert.equal(s.inboxIndexed,0);
 assert.equal(s.eligibleToPublish,0);
 assert.equal(s.publicationEnabled,false);
});
test('read-only summary never exposes private channel IDs, captions or files',async()=>{
 const {sqlite,env}=fixture();
 await ensureManualFallbackSchema(env);
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_sources "+
  "(chat_id,category,rights_attested,bot_access_verified,owner_approved,enabled) "+
  "VALUES ('-1001234567890','films',1,1,1,1)").run();
 const stmt=sqlite.prepare(
  "INSERT INTO cine_manual_fallback_inbox "+
  "(chat_id,message_id,category,kind,caption,file_unique_id,filename,state) "+
  "VALUES ('-1001234567890',?,'films',?,?,?,'private-film.mkv','indexed')");
 stmt.run(1,'poster','Titre: Secret Film\nAnnée: 2025','cover-fingerprint');
 stmt.run(2,'video','Titre: Secret Film\nAnnée: 2025','video-fingerprint');
 const s=await auditManualStock(env);
 assert.equal(s.plans.movies.candidates,1);
 assert.equal(s.eligibleToPublish,0);
 assert.deepEqual(s.authorizedSourceCounts,{films:1});
 const report=JSON.stringify(s);
 assert.ok(!report.includes('-1001234567890'));
 assert.ok(!report.includes('Secret Film'));
 assert.ok(!report.includes('private-film.mkv'));
});
test('not owner-approved or disabled source can never enter candidate report',async()=>{
 const {sqlite,env}=fixture();
 await ensureManualFallbackSchema(env);
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_sources (chat_id,category) "+
  "VALUES ('-1001234567890','films')").run();
 sqlite.prepare(
  "INSERT INTO cine_manual_fallback_inbox "+
  "(chat_id,message_id,category,kind,caption,file_unique_id) "+
  "VALUES ('-1001234567890',1,'films','video','Titre: Secret Film','vid-id')").run();
 const s=await auditManualStock(env);
 assert.equal(s.inboxIndexed,0);
 assert.equal(s.plans.movies.candidates,0);
});
