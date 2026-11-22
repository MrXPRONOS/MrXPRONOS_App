import test from 'node:test';
import assert from 'node:assert/strict';
import {validIntent,verifySignedBody,handleRequest} from './worker.mjs';

const env={DB:{prepare(){throw Error('unexpected_database_access')}}};
function candidate(){return {
 request_id:'classic:123',method:'copyMessage',
 bot_token:'123456789:ABCDEFGHIJKLMNOPQRSTUVabcdefghijkl',
 payload:{chat_id:1234567,from_chat_id:'-100123456789',message_id:42}
}}
test('validate approved copy request formats',()=>{
 assert.equal(validIntent(candidate()),true);
 for(const prefix of ['library','series','franchise'])
   assert.equal(validIntent({...candidate(),request_id:prefix+':123:1'}),true);
});
test('reject forbidden methods, unsafe IDs and oversized fields',()=>{
 for(const x of [
  {...candidate(),method:'sendVideo'},
  {...candidate(),request_id:'../../hello'},
  {...candidate(),payload:{...candidate().payload,chat_id:-1}},
  {...candidate(),payload:{...candidate().payload,message_id:0}},
  {...candidate(),payload:{...candidate().payload,from_chat_id:'bad'}},
  {...candidate(),payload:{...candidate().payload,reply_markup:{bad:'x'.repeat(4000)}}}
 ])assert.equal(validIntent(x),false);
});
test('health does not expose tokens',async()=>{
 const r=await handleRequest(new Request('https://example.test/health'),env);
 assert.equal(r.status,200);
 const data=await r.json();
 assert.equal(data.webhook,false);
 assert.equal(data.status,'ready');
 assert.equal(JSON.stringify(data).includes(candidate().bot_token),false);
});
test('unsigned request denied before database or Telegram',async()=>{
 const r=await handleRequest(new Request('https://example.test/internal/v1/copy',{
  method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(candidate())
 }),env);
 assert.equal(r.status,403);
});
test('expired signature denied',async()=>{
 const body=JSON.stringify(candidate()),time=String(Date.now()-120000);
 const r=await handleRequest(new Request('https://example.test/internal/v1/copy',{
  method:'POST',headers:{'content-type':'application/json','x-cine-time':time,
  'x-cine-signature':'0'.repeat(128)},body
 }),env);
 assert.equal(r.status,403);
});
test('ECDSA P-256 signs and verifies, refuses tampering and stale signatures',async()=>{
 const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},true,['sign','verify']);
 const publicJwk=await crypto.subtle.exportKey('jwk',pair.publicKey);
 const timestamp=String(Date.now()),body=JSON.stringify(candidate());
 const bytes=await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},pair.privateKey,
  new TextEncoder().encode(timestamp+'.'+body));
 const signature=Array.from(new Uint8Array(bytes), x=>x.toString(16).padStart(2,'0')).join('');
 assert.equal(await verifySignedBody(publicJwk,timestamp,signature,body),true);
 assert.equal(await verifySignedBody(publicJwk,timestamp,signature,body+' '),false);
 assert.equal(await verifySignedBody(publicJwk,String(Date.now()-120000),signature,body),false);
 assert.equal(await verifySignedBody(publicJwk,timestamp,'0'.repeat(128),body),false);
});
