export default {async fetch(req) {
 if(req.method!=="POST")return Response.json({error:"Method not allowed"},{status:405});
 const token=process.env.QUICK_ACTION_TOKEN||"";
 if(!token)return Response.json({error:"Authentication not configured"},{status:503});
 if(req.headers.get("authorization")!=="Bearer "+token)return Response.json({error:"Unauthorized"},{status:401});
 let v;try{v=await req.json()}catch{return Response.json({error:"Invalid JSON"},{status:400})}
 if(typeof v.name!=="string"||v.name.length>100)return Response.json({error:"Invalid name"},{status:400});
 return Response.json({message:"Hello "+v.name+"!"});
}};