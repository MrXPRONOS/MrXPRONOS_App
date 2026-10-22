const origins=new Set(["https://mrxpronos.github.io","http://localhost:3000","http://127.0.0.1:3000"]);
export default { async fetch(req) {
 const origin=req.headers.get("origin")||"";
 const headers={"Access-Control-Allow-Origin":origins.has(origin)?origin:"https://mrxpronos.github.io","Access-Control-Allow-Methods":"GET, OPTIONS","Access-Control-Allow-Headers":"content-type, authorization, apikey, x-client-info","Vary":"Origin"};
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers});
 if(req.method!=="GET")return new Response("Method Not Allowed",{status:405,headers});
 const key=(process.env.VAPID_PUBLIC_KEY||"").trim();
 if(!key)return new Response(JSON.stringify({error:"VAPID_PUBLIC_KEY not configured"}),{status:503,headers:{...headers,"Content-Type":"application/json"}});
 return new Response(key,{headers:{...headers,"Content-Type":"text/plain; charset=utf-8","Cache-Control":"public, max-age=3600"}});
}};