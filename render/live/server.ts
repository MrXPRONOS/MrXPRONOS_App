// Render transport-only launcher for the original 9,422-line Deno LIVE engine.
// No prediction calculations or business rules are implemented here.
const required = ["SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","CRON_SECRET","BSD_API_TOKEN"];
const missing = required.filter(k => !(Deno.env.get(k) || "").trim());
const requested = Deno.env.get("RENDER_LIVE_ENABLED") === "1";
const enabled = requested && missing.length === 0;
const port = Number(Deno.env.get("PORT") || "10000");
const upstream = "http://127.0.0.1:8000";
let child: Deno.ChildProcess | null = null;
if (enabled) {
  const env = {
    ...Deno.env.toObject(),
    LIVE_BATCH_ENDPOINT: upstream + "/refresh/batch",
  };
  child = new Deno.Command(Deno.execPath(), {
    args: ["run", "--allow-all", "supabase/functions/live/index.ts"],
    env, stdin: "null", stdout: "inherit", stderr: "inherit",
  }).spawn();
  child.status.then(({code}) => {
    console.error("RENDER_LIVE_ENGINE_EXIT", code);
    Deno.exit(code || 1);
  });
} else {
  console.warn("RENDER_LIVE_STANDBY", {
    requested,
    missing_env_names: missing,
    message:"No database writes, Telegram posts or engine calculations are started.",
  });
}

const cors = {
  "Access-Control-Allow-Origin":"*",
  "Access-Control-Allow-Methods":"GET, POST, OPTIONS",
  "Access-Control-Allow-Headers":"Content-Type, Authorization, x-cron-secret, apikey",
};
Deno.serve({hostname:"0.0.0.0",port}, async (req) => {
  const url = new URL(req.url);
  if (url.pathname === "/healthz" || url.pathname === "/") {
    if (!enabled) return Response.json({
      status:"standby", engine_running:false,
      requested_activation:requested, missing_env_names:missing,
      audit_source:"supabase/functions/live/index.ts",
      migration_rule:"Original source preserved, except local batch endpoint.",
    }, {status:200,headers:cors});
    try {
      const check = await fetch(upstream + "/render-health-probe", {
        signal:AbortSignal.timeout(1800),
      });
      return Response.json({
        status: "live", engine_running: true, engine_http_status:check.status,
        audit_source:"supabase/functions/live/index.ts",
      }, {headers:cors});
    } catch (e) {
      return Response.json({status:"starting",engine_running:false,
        error:String(e)}, {status:503,headers:cors});
    }
  }
  if (url.pathname === "/audit") {
    return Response.json({
      upstream_blob_sha:"36c0f2b2b9c4a24e62e03e83f5f4818849af16e2",
      scope:"full LIVE engine, including source merge, 3 prediction markets, backtest, validation, Telegram, daily endpoints",
      source_hash_verification:"deno run --allow-read render/live/verify_engine.ts",
      engine_running:enabled,
      original_logic_modified:false,
      required_env_names:required,
    }, {headers:cors});
  }
  if (!enabled) return Response.json({
    error:"RENDER_LIVE_IN_STANDBY", 
    reason:"Secret configuration and explicit activation required before any write.",
    missing_env_names:missing,
  }, {status:503,headers:cors});

  // Transparently stream requests/responses; calculation lives only in original engine.
  const target = upstream + url.pathname + url.search;
  const headers = new Headers(req.headers);
  headers.delete("host");
  const requestInit: RequestInit = {
    method:req.method,
    headers,
    body:["GET","HEAD"].includes(req.method)?undefined:req.body,
    redirect:"manual",
  };
  try {
    const response = await fetch(target, requestInit);
    return new Response(response.body, {
      status:response.status,
      statusText:response.statusText,
      headers:response.headers,
    });
  } catch (e) {
    console.error("RENDER_PROXY_UPSTREAM_ERROR", String(e));
    return Response.json({error:"Engine unavailable"}, {status:503,headers:cors});
  }
});
