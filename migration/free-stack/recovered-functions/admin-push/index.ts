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
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
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
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405, headers: corsHeaders(req) });

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY");
    const CRON_SECRET = Deno.env.get("CRON_SECRET");

    if (!SUPABASE_URL || !SERVICE_KEY || !ANON_KEY || !CRON_SECRET) {
      return json(req, {
        error: "Env manquantes. Requis: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY, CRON_SECRET",
      }, 500);
    }

    // JWT user (depuis admin)
    const authHeader = req.headers.get("Authorization") || "";
    if (!authHeader.toLowerCase().startsWith("bearer ")) {
      return json(req, { error: "Missing Authorization Bearer token" }, 401);
    }

    // Client user : vérifier user + is_admin
    const sbUser = createClient(SUPABASE_URL, ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
    });

    const { data: userRes, error: userErr } = await sbUser.auth.getUser();
    if (userErr || !userRes?.user) {
      return json(req, { error: "Unauthorized (invalid session)" }, 401);
    }

    const { data: isAdmin, error: adminErr } = await sbUser.rpc("is_admin");
    if (adminErr) return json(req, { error: `RPC is_admin error: ${adminErr.message}` }, 500);
    if (isAdmin !== true) return json(req, { error: "Forbidden (not admin)" }, 403);

    // Payload attendu depuis l'admin
    const body = await req.json().catch(() => ({} as any));
    const title = String(body?.title ?? "").trim();
    const msg = String(body?.body ?? "").trim();
    const url = String(body?.url ?? "").trim();
    const user_id = body?.user_id ? String(body.user_id).trim() : "";
    const tag = body?.tag ? String(body.tag).trim() : "";

    if (!title || !msg) return json(req, { error: "Champs requis: title, body" }, 400);

    // Appel push-notifications avec CRON_SECRET
    const pushRes = await fetch(`${SUPABASE_URL}/functions/v1/push-notifications`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${CRON_SECRET}`,
      },
      body: JSON.stringify({
        title,
        body: msg,
        url: url || null,
        user_id: user_id || null, // null => tous
        tag: tag || null,
      }),
    });

    const pushData = await pushRes.json().catch(() => ({}));
    if (!pushRes.ok) {
      return json(req, { error: pushData?.error || "Erreur push-notifications", details: pushData }, 500);
    }

    // Audit optionnel
    try {
      const sbService = createClient(SUPABASE_URL, SERVICE_KEY);
      await sbService.from("audit_log").insert({
        action: "admin_push",
        details: {
          title,
          url: url || null,
          user_id: user_id || null,
          tag: tag || null,
          results_count: Array.isArray(pushData?.results) ? pushData.results.length : null,
        },
      });
    } catch (_) {}

    return json(req, pushData, 200);
  } catch (e) {
    return json(req, { error: String((e as any)?.message ?? e) }, 500);
  }
});