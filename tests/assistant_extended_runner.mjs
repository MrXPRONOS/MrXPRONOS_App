import fs from 'node:fs';
const url='https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
const cases=JSON.parse(fs.readFileSync('tests/assistant_extended_cases.json','utf8')).slice(0,12);
const answers=[];
for(const test of cases){
 try{
  const resp=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:test.question,user_id:'real_audit_extended',historique:[],page_context:{pathname:test.page}}),signal:AbortSignal.timeout(22000)});
  const data=await resp.json();
  const answer=String(data.answer||data.error||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
  const result={id:test.id,question:test.question,http:resp.status,answer:answer.slice(0,1600),degraded:!!data.degraded,source:data.source??null};
  answers.push(result);console.log('EXT_CASE',JSON.stringify(result));
  if(resp.status===429)break;
 }catch(e){const result={id:test.id,error:String(e)};answers.push(result);console.log('EXT_CASE',JSON.stringify(result))}
}
fs.mkdirSync('assistant-extended-out',{recursive:true});
fs.writeFileSync('assistant-extended-out/answers.json',JSON.stringify(answers,null,2));
console.log('EXT_COMPLETE',answers.length);