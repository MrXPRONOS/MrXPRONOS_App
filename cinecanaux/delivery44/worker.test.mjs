import test from 'node:test';
import assert from 'node:assert/strict';
import {validIntent,signBody,handleRequest} from './worker.mjs';

const secret='local-test-secret-not-for-production';
const env={DB:{prepare(){throw Error('unexpected_database_access')}},CINE_BRIDGE_SECRET:secret};
function candidate(){return {
 request_id:'classic:123',
 method:'copyMessage',
 bot_token:'123456789:ABCDEFGHIJKLMNOPQRSTUVabcdefghijkl',
 payload:{chat_id:1234567,from_chat_id:'-100123456789',message_id:42}
}}
test('validate expected copy request',()=>assert.equal(validIntent(candidate()),true));
test('reject unknown method and unsafe chat ids',()=>{
 for(const x of [
  {...candidate(),method:'sendVideo'},
  {...candidate(),request_id:'../../hello'},
  {...candidate(),payload:{...candidate().payload,chat_id:-1}},
  {...candidate(),payload:{...candidate().payload,message_id:0}},
  {...candidate(),payload:{...candidate().payload,from_chat_id:'bad'}}
 ])assert.equal(validIntent(x),false);
});
test('health does not expose tokens',async()=>{
 const r=await handleRequest(new Request('https://example.test/health'),env);
 assert.equal(r.status,200);
 const data=await r.json();
 assert.equal(data.webhook,false);
 assert.equal(data.status,'ready');
 assert.equal(JSON.stringify(data).includes(secret),false);
});
test('unsigned request is rejected before database or Telegram',async()=>{
 const r=await handleRequest(new Request('https://example.test/internal/v1/copy',{
 method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(candidate())
 }),env);
 assert.equal(r.status,403);
});
test('stale signed request is rejected',async()=>{
 const body=JSON.stringify(candidate()),time=String(Date.now()-120000);
 const r=await handleRequest(new Request('https://example.test/internal/v1/copy',{
 method:'POST',headers:{
 'content-type':'application/json',
 'x-cine-time':time,
 'x-cine-signature':await signBody(secret,time,body)
 },body
 }),env);
 assert.equal(r.status,403);
});
test('valid signature but invalid action stops before database',async()=>{
 const bad={...candidate(),method:'sendVideo'};
 const body=JSON.stringify(bad),time=String(Date.now());
 const r=await handleRequest(new Request('https://example.test/internal/v1/copy',{
 method:'POST',headers:{
 'content-type':'application/json',
 'x-cine-time':time,
 'x-cine-signature':await signBody(secret,time,body)
 },body
 }),env);
 assert.equal(r.status,400);
});
