const allowed=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000"]);
export default {async fetch(req){
 const origin=req.headers.get("origin")||"";
 const headers={"content-type":"application/json","Access-Control-Allow-Origin":allowed.has(origin)?origin:"https://mrxpronos.github.io","Access-Control-Allow-Methods":"POST,OPTIONS","Access-Control-Allow-Headers":"Content-Type,Authorization","Vary":"Origin"};
 const reply=(v,status=200)=>new Response(JSON.stringify(v),{status,headers});
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers});
 if(req.method!=="POST")return reply({error:"Method not allowed"},405);
 const key=process.env.MISTRAL_API_KEY||"";
 const secret=process.env.EMBEDDING_API_TOKEN||"";
 if(!key||!secret)return reply({error:"Service not configured"},503);
 if(req.headers.get("authorization")!=="Bearer "+secret)return reply({error:"Unauthorized"},401);
 let body;try{body=await req.json()}catch{return reply({error:"Invalid JSON"},400)}
 if(typeof body.text!=="string"||!body.text.trim()||body.text.length>5000)return reply({error:"Invalid text"},400);
 try{
  const resp=await fetch("https://api.mistral.ai/v1/embeddings",{method:"POST",headers:{"Content-Type":"application/json","Authorization":"Bearer "+key},body:JSON.stringify({model:"mistral-embed",input:body.text}),signal:AbortSignal.timeout(15000)});
  if(!resp.ok)return reply({error:"Embedding provider unavailable"},502);
  const payload=await resp.json();const embedding=payload?.data?.[0]?.embedding;
  return Array.isArray(embedding)?reply({embedding}):reply({error:"Invalid provider response"},502);
 }catch{return reply({error:"Embedding provider unavailable"},502)}
}};