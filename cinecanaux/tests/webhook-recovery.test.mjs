import test from 'node:test';
import assert from 'node:assert/strict';
import {provisionTelegramWebhook} from '../worker.mjs';

const TARGET='https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/telegram';
function env(){
 const updates=[];
 const DB={prepare(sql){
  assert.match(sql,/bot_webhook_status/);
  return {bind(...params){return {async run(){updates.push({sql,params});return {success:true}}}}};
 }};
 return {DB,TELEGRAM_TOKEN:'test-token',TELEGRAM_WEBHOOK_SECRET:'test-secret',updates};
}
async function withMockTelegram(handlers,fn){
 const real=globalThis.fetch,calls=[];
 globalThis.fetch=async(url,options)=>{
  const method=String(url).split('/').pop(),body=JSON.parse(options?.body||'{}');
  calls.push({method,body});
  const result=handlers[method];
  assert.ok(result,'Unexpected Telegram call '+method);
  return Response.json(typeof result==='function'?result(body):result);
 };
 try{await fn(calls)}finally{globalThis.fetch=real}
}
test('healthy live Telegram webhook stays configured even when D1 status is old',async()=>{
 const e=env();
 await withMockTelegram({getWebhookInfo:{ok:true,result:{url:TARGET,allowed_updates:['message','callback_query','channel_post','edited_channel_post']}}},async calls=>{
  await provisionTelegramWebhook(e);
  assert.deepEqual(calls.map(x=>x.method),['getWebhookInfo']);
  assert.equal(e.updates.at(-1)?.params[0],'ok');
  assert.equal(e.updates.at(-1)?.params[1],'Webhook Telegram vérifié');
 });
});
test('stale Telegram webhook is corrected even if old D1 flag previously said ok',async()=>{
 const e=env();
 await withMockTelegram({
  getWebhookInfo:{ok:true,result:{url:'https://example.org/old-hook',allowed_updates:['message']}},
  setWebhook:{ok:true,result:true}
 },async calls=>{
  await provisionTelegramWebhook(e);
  assert.deepEqual(calls.map(x=>x.method),['getWebhookInfo','setWebhook']);
  assert.equal(calls[1].body.url,TARGET);
  assert.deepEqual(calls[1].body.allowed_updates,['message','callback_query','channel_post','edited_channel_post']);
  assert.equal(calls[1].body.secret_token,'test-secret');
  assert.equal(e.updates.at(-1)?.params[0],'ok');
 });
});
test('API failure triggers safe recovery instead of trusting a stored success flag',async()=>{
 const e=env();
 await withMockTelegram({getWebhookInfo:{ok:false,error_code:503},setWebhook:{ok:true,result:true}},async calls=>{
  await provisionTelegramWebhook(e);
  assert.equal(calls.length,2);
  assert.equal(e.updates.at(-1)?.params[0],'ok');
 });
});
test('Telegram refusal is recorded as error instead of marking webhook healthy',async()=>{
 const e=env();
 await withMockTelegram({getWebhookInfo:{ok:true,result:{url:'',allowed_updates:[]}},setWebhook:{ok:false,error_code:401,description:'Unauthorized'}},async()=>{
  await assert.rejects(()=>provisionTelegramWebhook(e),/Configuration webhook refusée/);
  assert.equal(e.updates.at(-1)?.params[0],'error');
 });
});
