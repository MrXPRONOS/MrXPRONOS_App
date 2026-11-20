import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import {
  reserveTelegramSend, guardTelegramMethod, noteTelegramFloodWait,
  pruneTelegramQuota, GLOBAL_PER_SECOND, PRIVATE_CHAT_PER_SECOND,
} from '../telegram-global-quota.mjs';

function fixture() {
  const sqlite = new DatabaseSync(':memory:');
  const DB = {prepare(sql) {
    let args=[];
    return {
      bind(...values){args=values;return this;},
      async run(){const result=sqlite.prepare(sql).run(...args);return {meta:{changes:result.changes||0}};},
      async first(){return sqlite.prepare(sql).get(...args)||null;},
      async all(){return {results:sqlite.prepare(sql).all(...args)};},
    };
  }};
  return {sqlite,env:{DB,TELEGRAM_TOKEN:'test:bot-token',TELEGRAM_WEBHOOK_SECRET:'secret-for-hmac'}};
}

test('T01: D1 upsert refuses global bursts above ten reservations per second',async()=>{
  const {sqlite,env}=fixture();
  try{
    const n=await Promise.all(Array.from({length:35},()=>reserveTelegramSend(env,{now:100001})));
    assert.equal(n.filter(x=>x.allowed).length,GLOBAL_PER_SECOND);
    assert.equal(n.filter(x=>!x.allowed).length,25);
    assert.ok(n.every(x=>x.allowed||x.retryAfter>=1));
    assert.equal(sqlite.prepare("SELECT used FROM cine_telegram_send_quota WHERE scope='telegram:global'").get().used,GLOBAL_PER_SECOND);
    assert.equal((await reserveTelegramSend(env,{now:101001})).allowed,true);
  }finally{sqlite.close()}
});

test('T01: one recipient gets one send per second even across catalogues',async()=>{
  const {sqlite,env}=fixture();
  try{
    assert.equal(PRIVATE_CHAT_PER_SECOND,1);
    assert.equal((await reserveTelegramSend(env,{chatId:12345,now:5000})).allowed,true);
    assert.equal((await reserveTelegramSend(env,{chatId:'12345',now:5001})).allowed,false);
    assert.equal((await reserveTelegramSend(env,{chatId:45678,now:5002})).allowed,true);
    assert.equal((await reserveTelegramSend(env,{chatId:12345,now:6000})).allowed,true);
    const scopes=sqlite.prepare("SELECT scope FROM cine_telegram_send_quota").all().map(x=>x.scope);
    assert.equal(scopes.length,3);
    assert.ok(scopes.every(x=>!x.includes('12345')&&!x.includes('45678')));
  }finally{sqlite.close()}
});

test('T01: one Telegram 429 pauses every family until shared cooldown ends',async()=>{
  const {sqlite,env}=fixture();
  try{
    assert.equal((await reserveTelegramSend(env,{now:100000})).allowed,true);
    assert.equal((await noteTelegramFloodWait(env,60,{now:100000})).recorded,true);
    const denied=await reserveTelegramSend(env,{chatId:22,now:110000});
    assert.equal(denied.allowed,false);
    assert.ok(denied.retryAfter>=50);
    assert.equal((await reserveTelegramSend(env,{now:160001})).allowed,true);
  }finally{sqlite.close()}
});

test('T01: fail closed if D1 is unavailable, never grant a quota token',async()=>{
  assert.deepEqual(await reserveTelegramSend({DB:null,TELEGRAM_TOKEN:'test:x'}),{
    allowed:false,retryAfter:60,reason:'quota_unavailable',
  });
  const env={DB:{prepare(){throw Error('database offline')}},TELEGRAM_TOKEN:'test:x'};
  assert.equal((await reserveTelegramSend(env,{chatId:1})).allowed,false);
  assert.equal((await guardTelegramMethod(env,'getChat',{chat_id:1})),null);
  assert.equal((await guardTelegramMethod(env,'copyMessage',{chat_id:1})).allowed,false);
  assert.equal((await noteTelegramFloodWait(env,30)).recorded,false);
});

test('T01: all outgoing methods are throttled while Telegram reads and deletion are not',async()=>{
  const {sqlite,env}=fixture();
  try{
    assert.equal(await guardTelegramMethod(env,'getMe',{}),null);
    assert.equal(await guardTelegramMethod(env,'deleteMessage',{chat_id:123}),null);
    const a=await guardTelegramMethod(env,'copyMessage',{chat_id:123});
    assert.equal(a.allowed,true);
    const b=await guardTelegramMethod(env,'sendPhoto',{chat_id:123});
    assert.equal(b.allowed,false);
    const react=await guardTelegramMethod(env,'setMessageReaction',{chat_id:-100123});
    assert.equal(react.allowed,true);
  }finally{sqlite.close()}
});

test('T01: prune removes expired hashed recipients but retains global cooldown',async()=>{
  const {sqlite,env}=fixture();
  try{
    await reserveTelegramSend(env,{chatId:999,now:100001});
    sqlite.prepare("UPDATE cine_telegram_send_quota SET updated_at=datetime('now','-4 days') WHERE scope<>'telegram:global'").run();
    const result=await pruneTelegramQuota(env);
    assert.equal(result.removed,1);
    assert.equal(sqlite.prepare("SELECT COUNT(*) AS n FROM cine_telegram_send_quota").get().n,1);
  }finally{sqlite.close()}
});

test('T01: every CineX media queue, owner vault, broadcasts and reactions share the quota helper',()=>{
  const files=['cinex-delivery','individual-series','cinex-classic','franchise-films',
    'owner-chat-vault','broadcast','channel-reactions'];
  for(const name of files){
    const contents=readFileSync(new URL('../'+name+'.mjs',import.meta.url),'utf8');
    assert.match(contents,/from '.\/telegram-global-quota\.mjs'/,name);
  }
  const migration=readFileSync(new URL('../migrations/025_cinex_global_telegram_quota.sql',import.meta.url),'utf8');
  assert.match(migration,/CREATE TABLE IF NOT EXISTS cine_telegram_send_quota/);
});
