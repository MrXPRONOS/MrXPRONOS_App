import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {ownerOperationsOverview} from '../admin-ops.mjs';
import {ADMIN_OPS_HTML} from '../admin-ops-ui.mjs';

test('CinéX shows technical incidents in read-only owner operations, without chat IDs', async()=>{
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){return {
  async first(){return sqlite.prepare(sql).get()||null},
  async all(){return {results:sqlite.prepare(sql).all()}},
  async run(){const x=sqlite.prepare(sql).run();return {meta:{changes:Number(x.changes)}}}
 }}};
 try{
  sqlite.exec("CREATE TABLE radar_ops_status(job_name TEXT,status TEXT,last_attempt_at TEXT,last_success_at TEXT)");
  sqlite.exec("CREATE TABLE automated_job_runs(id INTEGER,job_name TEXT,status TEXT,errors INTEGER,started_at TEXT)");
  sqlite.exec("CREATE TABLE bot_webhook_status(id INTEGER,status TEXT,updated_at TEXT)");
  sqlite.exec("INSERT INTO bot_webhook_status VALUES(1,'ok',CURRENT_TIMESTAMP)");
  sqlite.exec("CREATE TABLE cine_delivery_jobs(id INTEGER,status TEXT)");
  sqlite.exec("INSERT INTO cine_delivery_jobs VALUES(1,'needs_review'),(2,'queued')");
  sqlite.exec("CREATE TABLE cine_delivery_job_items(state TEXT,delete_state TEXT,delete_after TEXT,delete_last_error TEXT)");
  sqlite.exec("INSERT INTO cine_delivery_job_items VALUES('sent','manual_review',datetime('now','-1 hour'),'telegram_48h_window')");
  sqlite.exec("CREATE TABLE bot_settings(setting_key TEXT,value TEXT,updated_at TEXT)");
  sqlite.exec("INSERT INTO bot_settings VALUES('cine_delivery_enabled','1',CURRENT_TIMESTAMP)");
  const data=await ownerOperationsOverview({DB});
  assert.equal(data.cinex.enabled,true);
  assert.equal(data.cinex.needs_review,1);
  assert.equal(data.cinex.queued,1);
  assert.equal(data.cinex.deletion_manual_review,1);
  assert.equal(data.cinex.reasons[0].reason,'telegram_48h_window');
  assert.ok(data.alerts.some(x=>x.title.includes('CinéX')));
  assert.ok(ADMIN_OPS_HTML.includes('ad-ops-cinex'));
  assert.ok(!ADMIN_OPS_HTML.includes('cinex-approve'));
  assert.ok(!JSON.stringify(data).includes('telegram_chat_id'));
 }finally{sqlite.close()}
});


test('owner monitoring includes series, classic films, franchise and archival queue failures',async()=>{
 const sqlite=new DatabaseSync(':memory:');
 const DB={prepare(sql){return {
  async first(){return sqlite.prepare(sql).get()||null},
  async all(){return {results:sqlite.prepare(sql).all()}},
  async run(){const r=sqlite.prepare(sql).run();return {meta:{changes:Number(r.changes)}}},
 }}};
 try{
  sqlite.exec("CREATE TABLE radar_ops_status(job_name TEXT,status TEXT,last_attempt_at TEXT,last_success_at TEXT)");
  sqlite.exec("CREATE TABLE automated_job_runs(id INTEGER,job_name TEXT,status TEXT,errors INTEGER,started_at TEXT)");
  sqlite.exec("CREATE TABLE bot_webhook_status(id INTEGER,status TEXT,updated_at TEXT)");
  sqlite.exec("CREATE TABLE cine_delivery_jobs(id INTEGER,status TEXT)");
  sqlite.exec("CREATE TABLE cine_delivery_job_items(state TEXT,delete_state TEXT,delete_after TEXT,delete_last_error TEXT)");
  sqlite.exec("CREATE TABLE bot_settings(setting_key TEXT,value TEXT,updated_at TEXT)");
  sqlite.exec("INSERT INTO bot_settings VALUES('cine_delivery_enabled','1',CURRENT_TIMESTAMP)");
  sqlite.exec("CREATE TABLE cine_series_jobs(status TEXT)");
  sqlite.exec("INSERT INTO cine_series_jobs VALUES('queued'),('queued'),('needs_review')");
  sqlite.exec("CREATE TABLE cine_series_job_items(state TEXT,delete_after TEXT,delete_state TEXT)");
  sqlite.exec("INSERT INTO cine_series_job_items VALUES('sent',datetime('now','-1 hour'),'pending')");
  sqlite.exec("CREATE TABLE cine_classic_deliveries(status TEXT,delete_state TEXT,delete_after TEXT)");
  sqlite.exec("INSERT INTO cine_classic_deliveries VALUES('needs_review','manual_review',datetime('now','-1 hour'))");
  sqlite.exec("CREATE TABLE cine_franchise_jobs(status TEXT)");
  sqlite.exec("INSERT INTO cine_franchise_jobs VALUES('queued')");
  sqlite.exec("CREATE TABLE cine_franchise_job_items(state TEXT,delete_after TEXT,delete_state TEXT)");
  sqlite.exec("INSERT INTO cine_franchise_job_items VALUES('sent',datetime('now','-1 hour'),'retry')");
  sqlite.exec("CREATE TABLE cine_owner_vault(status TEXT)");
  sqlite.exec("INSERT INTO cine_owner_vault VALUES('needs_review')");
  const data=await ownerOperationsOverview({DB});
  assert.equal(data.cinex.total_queued,3);
  assert.equal(data.cinex.total_needs_review,3);
  assert.equal(data.cinex.total_overdue,2);
  assert.equal(data.cinex.total_deletion_manual_review,1);
  assert.deepEqual(data.cinex.families.map(x=>x.family),['libraries','series','classics','franchise','owner_archive']);
  assert.ok(data.alerts.some(x=>x.title.includes('nettoyage en retard')));
  assert.ok(!JSON.stringify(data).includes('telegram_chat_id'));
 }finally{sqlite.close()}
});
