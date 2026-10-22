import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import * as webpush from "npm:web-push@3.6.7";

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
    const CRON_SECRET = Deno.env.get("CRON_SECRET");

    const VAPID_PUBLIC_KEY = Deno.env.get("VAPID_PUBLIC_KEY");
    const VAPID_PRIVATE_KEY = Deno.env.get("VAPID_PRIVATE_KEY");
    const VAPID_SUBJECT = Deno.env.get("VAPID_SUBJECT"); // ex: mailto:contact@mrxpronos.com
    const VAPID_EMAIL = Deno.env.get("VAPID_EMAIL"); // fallback si pas VAPID_SUBJECT

    if (!SUPABASE_URL || !SERVICE_KEY || !CRON_SECRET) {
      return json(req, { error: "Env manquantes: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, CRON_SECRET" }, 500);
    }
    if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY || (!VAPID_SUBJECT && !VAPID_EMAIL)) {
      return json(req, { error: "Env manquantes: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT (ou VAPID_EMAIL)" }, 500);
    }

    // Sécurité: uniquement CRON_SECRET (admin-push et cron)
    const auth = req.headers.get("Authorization") || "";
    if (auth !== `Bearer ${CRON_SECRET}`) {
      return json(req, { error: "Unauthorized" }, 401);
    }

    const supabase = createClient(SUPABASE_URL, SERVICE_KEY);

    const body = await req.json().catch(() => ({} as any));
    const user_id = body?.user_id ? String(body.user_id).trim() : "";
    const title = String(body?.title ?? "").trim();
    const msg = String(body?.body ?? "").trim();
    const url = (String(body?.url ?? "").trim() || "./pronos.html");
    const tag = (String(body?.tag ?? "").trim() || "admin");

    if (!title || !msg) return json(req, { error: "Champs requis: title, body" }, 400);

    const subject = VAPID_SUBJECT || `mailto:${VAPID_EMAIL}`;
    webpush.setVapidDetails(subject, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

    // Sélection abonnements
    let query = supabase.from("push_subscriptions").select("endpoint, keys, user_id");
    if (user_id) query = query.eq("user_id", user_id);

    const { data: subs, error } = await query;
    if (error) return json(req, { error: error.message }, 500);

    // ✅ On inclut tag dans le payload (service-worker l'utilise)
    const payload = JSON.stringify({ title, body: msg, url, tag });

    const results: any[] = [];
    for (const sub of subs || []) {
      const endpoint = sub.endpoint;
      let keys: any = sub.keys;

      // Si keys stocké en string par erreur, tenter parse
      if (typeof keys === "string") {
        try { keys = JSON.parse(keys); } catch { keys = null; }
      }

      if (!endpoint || !keys?.p256dh || !keys?.auth) {
        results.push({ endpoint, status: "skipped_invalid_subscription" });
        continue;
      }

      try {
        await webpush.sendNotification({ endpoint, keys } as any, payload);
        results.push({ endpoint, status: "sent" });
      } catch (err: any) {
        const msgErr = String(err?.message ?? err);
        const statusCode = err?.statusCode || err?.status || null;

        // abonnement expiré => suppression
        if (statusCode === 410 || msgErr.includes("410")) {
          await supabase.from("push_subscriptions").delete().eq("endpoint", endpoint);
          results.push({ endpoint, status: "deleted_410" });
        } else {
          results.push({ endpoint, status: "failed", error: msgErr, statusCode });
        }
      }
    }

    return json(req, { success: true, results }, 200);
  } catch (e) {
    return json(req, { error: String((e as any)?.message ?? e) }, 500);
  }
});