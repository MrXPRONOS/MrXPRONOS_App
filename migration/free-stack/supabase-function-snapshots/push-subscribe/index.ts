import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ALLOWED_ORIGINS = new Set([
  "https://mrxpronos.github.io",
  "http://localhost:3000",
  "http://127.0.0.1:3000",
]);

function corsHeaders(req: Request) {
  const origin = req.headers.get("origin") ?? "";
  const allowOrigin = ALLOWED_ORIGINS.has(origin) ? origin : "https://mrxpronos.github.io";
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, authorization, apikey, x-client-info",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function json(req: Request, data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders(req), "Content-Type": "application/json" },
  });
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(req) });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders(req) });

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!SUPABASE_URL || !SERVICE_KEY) {
      return json(req, { error: "Missing env SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY" }, 500);
    }

    const supabase = createClient(SUPABASE_URL, SERVICE_KEY);

    const body = await req.json().catch(() => null as any);
    const user_id = body?.user_id;
    const subscription = body?.subscription;
    const endpoint = subscription?.endpoint;
    const keys = subscription?.keys;

    if (!user_id || !endpoint || !keys?.p256dh || !keys?.auth) {
      return json(req, { error: "Payload invalide (user_id/subscription/keys)" }, 400);
    }

    // Upsert sur endpoint (endpoint doit être UNIQUE en DB)
    const { error } = await supabase
      .from("push_subscriptions")
      .upsert({ user_id, endpoint, keys }, { onConflict: "endpoint" });

    if (error) return json(req, { error: error.message }, 500);

    return json(req, { success: true }, 200);
  } catch (e) {
    return json(req, { error: String((e as any)?.message ?? e) }, 500);
  }
});