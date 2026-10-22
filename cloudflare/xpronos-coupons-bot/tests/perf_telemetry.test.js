import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';
import {routeLabel,coloLabel,metricValue,newBotMetrics,recordTelegram,storeSample,summarizeSamples,performanceReport} from '../src/telemetry.js';
import {adminApi} from '../src/admin-ui.js';

test('Sampling never records user or message identifiers',async()=>{
 const queries=[];const db={prepare(sql){return {bind(...args){
  queries.push({sql,args});
  return {run:async()=>({meta:{changes:1}})};
 }}}};
 const result=await storeSample({DB:db},{
  kind:'bot_callback',route:'/callback',colo:'LFW',response_ms:233.4,status:'ok',
  metrics:{telegram_ms:120.2,ack_ms:82.4,reply_ms:212.5,calls:2},
  user_id:8099115334,chat_id:8099115334,message:'Private message',token:'TEST'
 });
 assert.equal(result,true);
 assert.equal(queries.length,1);
 assert.match(queries[0].sql,/INSERT INTO perf_samples/);
 assert.deepEqual(queries[0].args,['bot_callback','/callback','LFW',233,120,82,213,2,'ok']);
 assert.ok(!queries[0].args.includes(8099115334));
 assert.ok(!queries[0].args.includes('Private message'));
});
test('Route, colo and timings are normalized to bounded categories',()=>{
 assert.equal(routeLabel('/api/coupons'),'/coupons');
 assert.equal(routeLabel('/callback'),'/callback');
 assert.equal(routeLabel('/api/unknown-private-user'),'/other');
 assert.equal(coloLabel('LFW'),'LFW');
 assert.equal(coloLabel('long-private-location'),'UNK');
 assert.equal(metricValue(-20),0);
 assert.equal(metricValue(150000),120000);
});
test('Webhook confirms Telegram callback before reply with distinct elapsed metrics',()=>{
 const m=newBotMetrics(100);
 recordTelegram(m,'answerCallbackQuery',66,155);
 recordTelegram(m,'sendMessage',113,288);
 assert.equal(m.calls,2);
 assert.equal(m.ack_ms,55);
 assert.equal(m.reply_ms,188);
 assert.equal(m.telegram_ms,179);
});
test('Percentiles are grouped by real Cloudflare colo without user metadata',()=>{
 const rows=[
  {kind:'bot_callback',route:'/callback',colo:'LFW',response_ms:100,telegram_ms:50,callback_ack_ms:20,first_reply_ms:90},
  {kind:'bot_callback',route:'/callback',colo:'LFW',response_ms:200,telegram_ms:100,callback_ack_ms:40,first_reply_ms:180},
  {kind:'miniapp',route:'/coupons',colo:'FRA',response_ms:120,telegram_ms:0,callback_ack_ms:null,first_reply_ms:null}
 ];
 const groups=summarizeSamples(rows);
 const tg=groups.find(x=>x.kind==='bot_callback');
 assert.equal(tg.samples,2);
 assert.equal(tg.p50_ms,100);
 assert.equal(tg.p95_ms,200);
 assert.equal(tg.first_reply_p95_ms,180);
 assert.equal(groups.length,2);
});
test('Admin report includes D1 read probe but never exposes identifiers',async()=>{
 const db={prepare(sql){return {bind(){return {
  first:async()=>({ready:1}),
  all:async()=>({results:[{kind:'miniapp',route:'/me',colo:'LFW',response_ms:111,telegram_ms:0,callback_ack_ms:null,first_reply_ms:null}]})
 }},first:async()=>({ready:1}),all:async()=>({results:[]})}}};
 const report=await performanceReport({DB:db});
 assert.equal(report.samples,1);
 assert.equal(report.groups[0].colo,'LFW');
 assert.equal(typeof report.d1_probe_ms,'number');
 assert.equal(report.groups[0].route,'/me');
 const denied=await adminApi(new Request('https://test.invalid/api/admin/performance'),{CF_BOT_ADMIN_IDS:'100'},201);
 assert.equal(denied.status,403);
});
