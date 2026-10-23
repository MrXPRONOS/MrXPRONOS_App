// Neon Node.js 24 request transport for the historical Supabase serve(handler).
// Adds only Neon schedule authentication; original business functions remain unchanged.
type Handler = (request: Request) => Response | Promise<Response>;
let handler: Handler | null = null;
const SCHEDULE_TRIGGER_ID = "trigger-539f987f-b22b-4108-a1c2-05d41f9fe929";
export function serve(fn: Handler) { handler = fn; }
export function neonGetHandler(): Handler {
 if (!handler) throw new Error("LIVE_HANDLER_NOT_REGISTERED");
 return async (request: Request) => {
  const url=new URL(request.url);
  const invocation=request.headers.get("x-neon-trigger-invocation-id");
  // Neon strips spoofed x-neon-* request headers at its edge. Only the
  // registered production trigger can satisfy both this header and body.
  if(request.method==="POST" && url.pathname.replace(/\/$/,"")==="/refresh" && invocation){
   const payload=await request.clone().json().catch(()=>null);
   const ok=payload?.version===1 &&
    payload?.invocation_id===invocation &&
    payload?.trigger?.type==="schedule" &&
    payload?.trigger?.id===SCHEDULE_TRIGGER_ID &&
    payload?.trigger?.name==="mrxpronos-live-refresh-v1" &&
    typeof payload?.data?.scheduled_at==="string" &&
    Math.abs(Date.now()-Date.parse(payload.data.scheduled_at))<=180000 &&
    Boolean(process.env.CRON_SECRET);
   if(!ok)return new Response(JSON.stringify({error:"invalid_neon_trigger"}),{status:403,headers:{"content-type":"application/json"}});
   const headers=new Headers(request.headers);
   headers.set("x-cron-secret",process.env.CRON_SECRET!);
   return await handler!(new Request(request,{headers}));
  }
  return await handler!(request);
 };
}
