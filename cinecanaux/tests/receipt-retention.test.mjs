import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {pruneFinalizedCineReceipts} from '../receipt-retention.mjs';

function fixture(){
 const sql=new DatabaseSync(':memory:');
 for(const [jobs,items] of [
  ['cine_delivery_jobs','cine_delivery_job_items'],
  ['cine_series_jobs','cine_series_job_items'],
  ['cine_franchise_jobs','cine_franchise_job_items']
 ]){
  sql.exec('CREATE TABLE '+jobs+'(id INTEGER PRIMARY KEY,status TEXT,created_at TEXT,telegram_chat_id INTEGER)');
  sql.exec('CREATE TABLE '+items+'(job_id INTEGER,state TEXT,delete_state TEXT)');
  sql.exec("INSERT INTO "+jobs+" VALUES(1,'complete',datetime('now','-100 days'),123)");
  sql.exec("INSERT INTO "+jobs+" VALUES(2,'complete',datetime('now','-100 days'),456)");
  sql.exec("INSERT INTO "+jobs+" VALUES(3,'queued',datetime('now','-100 days'),567)");
  sql.exec("INSERT INTO "+jobs+" VALUES(4,'complete',CURRENT_TIMESTAMP,890)");
  sql.exec("INSERT INTO "+items+" VALUES(1,'sent','deleted')");
  sql.exec("INSERT INTO "+items+" VALUES(2,'sent','manual_review')");
  sql.exec("INSERT INTO "+items+" VALUES(3,'queued','pending')");
  sql.exec("INSERT INTO "+items+" VALUES(4,'sent','deleted')");
 }
 sql.exec('CREATE TABLE cine_classic_deliveries(id INTEGER PRIMARY KEY,status TEXT,delete_state TEXT,created_at TEXT)');
 sql.exec("INSERT INTO cine_classic_deliveries VALUES(1,'deleted','already_gone',datetime('now','-100 days'))");
 sql.exec("INSERT INTO cine_classic_deliveries VALUES(2,'needs_review','manual_review',datetime('now','-100 days'))");
 sql.exec("INSERT INTO cine_classic_deliveries VALUES(3,'deleted','deleted',CURRENT_TIMESTAMP)");
 sql.exec('CREATE TABLE cine_owner_vault(id INTEGER PRIMARY KEY,source_message_id INTEGER)');
 sql.exec('INSERT INTO cine_owner_vault VALUES(1,999)');
 const DB={prepare(command){let params=[];return {
  bind(...args){params=args;return this},
  async all(){return {results:sql.prepare(command).all(...params)}},
  async run(){const r=sql.prepare(command).run(...params);return {meta:{changes:Number(r.changes)}}},
 }}};
 return {sql,DB};
}
test('privacy purge removes only >90-day fully deleted receipts, keeps all active/manual/source rows',async()=>{
 const {sql,DB}=fixture();
 try{
  const report=await pruneFinalizedCineReceipts({DB},{days:1,perFamily:25});
  assert.equal(report.deleted_jobs,3);
  assert.equal(report.deleted_items,3);
  assert.equal(report.deleted_classics,1);
  for(const [jobs,items] of [
   ['cine_delivery_jobs','cine_delivery_job_items'],
   ['cine_series_jobs','cine_series_job_items'],
   ['cine_franchise_jobs','cine_franchise_job_items']]){
   assert.deepEqual(sql.prepare('SELECT id FROM '+jobs+' ORDER BY id').all().map(x=>x.id),[2,3,4]);
   assert.deepEqual(sql.prepare('SELECT job_id FROM '+items+' ORDER BY job_id').all().map(x=>x.job_id),[2,3,4]);
  }
  assert.deepEqual(sql.prepare('SELECT id FROM cine_classic_deliveries ORDER BY id').all().map(x=>x.id),[2,3]);
  assert.equal(sql.prepare('SELECT source_message_id FROM cine_owner_vault').get().source_message_id,999);
  const again=await pruneFinalizedCineReceipts({DB});
  assert.equal(again.deleted_jobs,0);
  assert.equal(again.deleted_classics,0);
 }finally{sql.close()}
});
test('the retention job does not call Telegram or edit media/published catalogues',()=>{
 const src=readFileSync(new URL('../receipt-retention.mjs',import.meta.url),'utf8');
 const worker=readFileSync(new URL('../worker.mjs',import.meta.url),'utf8');
 assert.ok(worker.includes('pruneFinalizedCineReceipts(env)'));
 assert.doesNotMatch(src,/fetch\(|https:\/\/api\.telegram\.org|DELETE FROM cine_owner_vault|DELETE FROM cine_series_episodes|DELETE FROM cine_franchise_films/);
});
