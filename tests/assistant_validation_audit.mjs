const base='https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
const tests=[
 {id:'empty_question',method:'POST',body:JSON.stringify({question:'',user_id:'audit_validation'})},
 {id:'numeric_question',method:'POST',body:JSON.stringify({question:123,user_id:'audit_validation'})},
 {id:'oversized_question',method:'POST',body:JSON.stringify({question:'a'.repeat(1201),user_id:'audit_validation'})},
 {id:'malformed_json',method:'POST',body:'{invalid'},
 {id:'invalid_feedback',method:'POST',body:JSON.stringify({action:'feedback',feedback:'yes',user_id:'audit_validation'})},
 {id:'get_suggestions',method:'GET',url:base+'/suggestions'},
 {id:'wrong_method',method:'GET'}
];
for(const t of tests){
 try{
  const response=await fetch(t.url||base,{method:t.method,headers:{'Content-Type':'application/json'},body:t.body,signal:AbortSignal.timeout(13000)});
  const text=await response.text();
  console.log('VALIDATION',JSON.stringify({case:t.id,status:response.status,body:text.slice(0,450)}));
 }catch(error){console.log('VALIDATION',JSON.stringify({case:t.id,error:String(error)}))}
}
