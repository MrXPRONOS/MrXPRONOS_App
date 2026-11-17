import test from 'node:test';
import assert from 'node:assert/strict';
import {
 NVIDIA_PRIMARY_MODEL,NVIDIA_MODELS,NVIDIA_MODEL_TIMEOUT_MS,NVIDIA_REQUEST_BUDGET_MS,
 stickyNvidiaOrder,fetchLastSuccessfulNvidiaModel,rememberSuccessfulNvidiaModel,
 runNvidiaFailover,launchTelegramBackground
} from '../index.js';

test('Mistral Large 4 is the fresh-start priority, before old successes',()=>{
 assert.equal(NVIDIA_PRIMARY_MODEL,'mistralai/mistral-large-4-1t-a52b');
 assert.equal(NVIDIA_MODELS[0],NVIDIA_PRIMARY_MODEL);
 assert.deepEqual(stickyNvidiaOrder(null),[...NVIDIA_MODELS]);
 assert.equal(new Set(NVIDIA_MODELS).size,10);
});
test('next message uses the most recently successful model, even on a new worker',async()=>{
 const storage=[];
 const selected='poolside/laguna-xs-2.1';
 await rememberSuccessfulNvidiaModel(selected,async (events,source)=>{
  assert.equal(source,'routing_v28');
  storage.push(...events);
 });
 let query='';
 const previous=await fetchLastSuccessfulNvidiaModel(async path=>{
  query=path;
  return storage.slice(-1);
 });
 assert.match(query,/source=eq.routing_v28/);
 assert.match(query,/order=id.desc/);
 assert.equal(previous,selected);
 assert.equal(stickyNvidiaOrder(previous)[0],selected);
 assert.equal(stickyNvidiaOrder(previous).length,NVIDIA_MODELS.length);
 assert.equal(stickyNvidiaOrder('unknown-model')[0],NVIDIA_PRIMARY_MODEL);
});
test('each model gets a full minute; a timeout invokes the next model',async()=>{
 const tried=[],windows=[];
 const output=await runNvidiaFailover({
  apiKey:'fake',messages:[{role:'user',content:'Bonjour'}],
  signalFactory:ms=>{windows.push(ms);return undefined;},
  fetchImpl:async (_url,opt)=>{
   const model=JSON.parse(opt.body).model;tried.push(model);
   if(tried.length===1)throw Object.assign(new Error('slow'),{name:'TimeoutError'});
   return {ok:true,json:async()=>({choices:[{message:{content:'Réponse confirmée.'}}]})};
  }
 });
 assert.deepEqual(tried,NVIDIA_MODELS.slice(0,2));
 assert.deepEqual(windows,[60000,60000]);
 assert.equal(output.attempts[0].status,'timeout');
 assert.equal(output.model,NVIDIA_MODELS[1]);
});
test('fast responses are sent when ready, without an imposed one-minute delay',async()=>{
 let attempts=0;
 const result=await runNvidiaFailover({apiKey:'fake',messages:[],
  signalFactory:()=>undefined,
  fetchImpl:async()=>{attempts++;return {ok:true,json:async()=>({choices:[{message:{content:'Salut !'}}]})};}
 });
 assert.equal(attempts,1);
 assert.equal(result.text,'Salut !');
});
test('runtime cannot start a third truncated attempt after two full-minute timeouts',async()=>{
 assert.equal(NVIDIA_MODEL_TIMEOUT_MS,60000);
 assert.equal(NVIDIA_REQUEST_BUDGET_MS,125000);
 let elapsed=0,attempts=0;
 const seen=[];
 const result=await runNvidiaFailover({apiKey:'fake',messages:[],
  now:()=>elapsed,signalFactory:ms=>{seen.push(ms);return undefined;},
  fetchImpl:async()=>{attempts++;elapsed+=60000;throw Object.assign(new Error('timeout'),{name:'TimeoutError'});}
 });
 assert.equal(attempts,2);
 assert.deepEqual(seen,[60000,60000]);
 assert.equal(result.reason,'time_budget');
});
test('an early HTTP error immediately triggers next model',async()=>{
 const attempted=[];
 const result=await runNvidiaFailover({apiKey:'fake',messages:[],
  signalFactory:()=>undefined,
  fetchImpl:async (_url,opt)=>{
   attempted.push(JSON.parse(opt.body).model);
   return attempted.length===1?{ok:false,status:500}:{ok:true,json:async()=>({choices:[{message:{content:'OK'}}]})};
  }
 });
 assert.deepEqual(attempted,NVIDIA_MODELS.slice(0,2));
 assert.equal(result.model,NVIDIA_MODELS[1]);
});
test('Telegram webhook schedules work without waiting for slow NVIDIA',async()=>{
 let resolveWork,started=false,registered=null;
 const work=()=>{started=true;return new Promise(resolve=>{resolveWork=resolve;});};
 assert.equal(launchTelegramBackground(work,p=>{registered=p;}),true);
 assert.ok(registered);
 await Promise.resolve();
 assert.equal(started,true);
 resolveWork();
 await registered;
 assert.equal(launchTelegramBackground(work,null),false);
});
