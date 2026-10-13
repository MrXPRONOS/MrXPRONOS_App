import fs from 'node:fs';
const all=JSON.parse(fs.readFileSync('tests/assistant_qa50_cases.json','utf8'));
const batch=Number(process.argv[2]||0);
const cases=all.slice(batch*10,batch*10+10);
const endpoint='https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
const base='https://mrxpronos.github.io/MrXPRONOS_App';
const answers=[];
const started=new Date().toISOString();
for(const test of cases){
 const begin=Date.now();
 try{
  const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:test.question,user_id:'audit50_'+batch+'_'+test.id,historique:[],page_context:{pathname:test.page==='home'?'/':'/'+test.page+'.html'}}),signal:AbortSignal.timeout(20000)});
  const body=await r.json();
  const response=String(body.answer||body.error||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
  const item={id:test.id,question:test.question,status:r.status,answer:response.slice(0,1400),source:body.source||null,degraded:!!body.degraded,latency_ms:Date.now()-begin};
  answers.push(item);console.log('QA50_RESULT '+JSON.stringify(item));
 }catch(e){const item={id:test.id,question:test.question,error:String(e),latency_ms:Date.now()-begin};answers.push(item);console.log('QA50_RESULT '+JSON.stringify(item));}
}
fs.mkdirSync('assistant-qa50-results',{recursive:true});
fs.writeFileSync('assistant-qa50-results/batch-'+batch+'.json',JSON.stringify({started,batch,answers},null,2));
console.log('QA50_COMPLETE '+JSON.stringify({batch,completed:answers.length,errors:answers.filter(x=>x.error||x.status>=400).length}));
// Regression rerun against deployed Supabase Edge Function version 66.
