import fs from 'node:fs';
const site='https://mrxpronos.github.io/MrXPRONOS_App';
const api='https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
const questions=JSON.parse(fs.readFileSync('tests/assistant_audit_cases.json','utf8'));
const output={time:new Date().toISOString(),pages:[],answers:[]};
for(const path of ['/', '/pronos.html','/live.html','/historique.html','/bonus.html','/contact.html','/assets/js/assistant.js']){
 try {
  const res=await fetch(site+path,{signal:AbortSignal.timeout(16000)});
  const html=await res.text();
  const item={path,status:res.status,assistantLoaded:html.includes('assistant.js'),bytes:html.length,free:/gratuit/i.test(html)};
  output.pages.push(item);console.log('PAGE',JSON.stringify(item));
 }catch(error){output.pages.push({path,error:String(error)});}
}
for(const item of questions){
 try {
  const res=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:item.question,user_id:'audit_v2',historique:[],page_context:{pathname:item.page}}),signal:AbortSignal.timeout(22000)});
  const data=await res.json();
  const answer=String(data.answer||data.error||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
  const row={id:item.id,question:item.question,status:res.status,answer:answer.slice(0,1100),degraded:!!data.degraded,source:data.source||null};
  output.answers.push(row);console.log('CASE',JSON.stringify(row));
  if(res.status===429)break;
 }catch(error){const row={id:item.id,error:String(error)};output.answers.push(row);console.log('CASE',JSON.stringify(row))}
}
fs.mkdirSync('assistant-audit-results',{recursive:true});
fs.writeFileSync('assistant-audit-results/results.json',JSON.stringify(output,null,2));
console.log('COMPLETE',output.answers.length,'queries');