import { serve } from "https://deno.land/std@0.170.0/http/server.ts";

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
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, authorization, apikey, x-client-info",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(req) });
  if (req.method !== "GET") return new Response("Method Not Allowed", { status: 405, headers: corsHeaders(req) });

  const publicKey = (Deno.env.get("VAPID_PUBLIC_KEY") || "").trim();
  if (!publicKey) {
    return new Response(JSON.stringify({ error: "VAPID_PUBLIC_KEY not configured" }), {
      status: 500,
      headers: { ...corsHeaders(req), "Content-Type": "application/json" },
    });
  }

  return new Response(publicKey, {
    status: 200,
    headers: {
      ...corsHeaders(req),
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
});