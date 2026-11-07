import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ALLOWED_ORIGINS = new Set([
  "https://mrxpronos.github.io",
  "http://localhost:3000",
  "http://127.0.0.1:3000",
]);

function corsHeaders(req: Request) {
  const origin = req.headers.get("origin") ?? "";
  const allowOrigin = ALLOWED_ORIGINS.has(origin)
    ? origin
    : "https://mrxpronos.github.io";

  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Headers":
      "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
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
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(req) });
  }
  if (req.method !== "GET") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: corsHeaders(req),
    });
  }

  try {
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
    const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY");

    if (!SUPABASE_URL || !SERVICE_KEY || !ANON_KEY) {
      return json(req, {
        error:
          "Env manquantes. Requis: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY",
      }, 500);
    }

    // JWT user (admin)
    const authHeader = req.headers.get("Authorization") || "";
    if (!authHeader.toLowerCase().startsWith("bearer ")) {
      return json(req, { error: "Missing Authorization Bearer token" }, 401);
    }

    // Client user pour vérifier is_admin
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

    // Service role: lire toutes les subscriptions
    const sbService = createClient(SUPABASE_URL, SERVICE_KEY);

    const { data, error } = await sbService
      .from("push_subscriptions")
      .select("user_id, endpoint, created_at")
      .order("created_at", { ascending: false })
      .limit(5000);

    if (error) return json(req, { error: error.message }, 500);

    const map = new Map<string, { user_id: string; endpoints: number; last_subscribed_at: string }>();

    for (const row of data || []) {
      const uid = String(row.user_id || "").trim();
      if (!uid) continue;

      const prev = map.get(uid);
      if (!prev) {
        map.set(uid, {
          user_id: uid,
          endpoints: 1,
          last_subscribed_at: row.created_at,
        });
      } else {
        prev.endpoints += 1;
        if (row.created_at > prev.last_subscribed_at) {
          prev.last_subscribed_at = row.created_at;
        }
      }
    }

    const subscribers = Array.from(map.values())
      .sort((a, b) => (b.last_subscribed_at || "").localeCompare(a.last_subscribed_at || ""));

    return json(req, { success: true, count: subscribers.length, subscribers }, 200);
  } catch (e) {
    return json(req, { error: String((e as any)?.message ?? e) }, 500);
  }
});