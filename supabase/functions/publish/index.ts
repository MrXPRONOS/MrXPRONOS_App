import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const GITHUB_OWNER = Deno.env.get("GITHUB_OWNER") || "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "";
const GITHUB_BRANCH = Deno.env.get("GITHUB_BRANCH") || "main";
const GITHUB_PAT = Deno.env.get("GITHUB_PAT") || "";

// Optionnel: limiter l'origine CORS si tu veux (sinon *)
const ALLOW_ORIGIN = Deno.env.get("PUBLISH_CORS_ORIGIN") || "*";

const corsHeaders = {
  "Access-Control-Allow-Origin": ALLOW_ORIGIN,
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
};

const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function nowIso() {
  return new Date().toISOString();
}

// Base64 UTF-8 safe (Deno)
function toBase64Utf8(s: string) {
  const bytes = new TextEncoder().encode(s);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

async function requireAdmin(req: Request) {
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("Server misconfigured: missing Supabase env");
  }

  const auth = req.headers.get("Authorization") || "";
  const token = auth.toLowerCase().startsWith("bearer ")
    ? auth.slice(7).trim()
    : "";

  if (!token) {
    const err: any = new Error("Missing bearer token");
    err.code = 401;
    throw err;
  }

  const { data, error } = await sb.auth.getUser(token);
  if (error || !data?.user) {
    const err: any = new Error("Invalid session");
    err.code = 401;
    throw err;
  }

  const uid = data.user.id;

  // Vérification admin par table
  const { data: adminRow, error: adminErr } = await sb
    .from("admin_users")
    .select("user_id, active")
    .eq("user_id", uid)
    .maybeSingle();

  if (adminErr) throw adminErr;
  if (!adminRow || adminRow.active !== true) {
    const err: any = new Error("not_admin");
    err.code = 403;
    throw err;
  }

  return uid;
}

function ghHeaders() {
  return {
    "Authorization": `Bearer ${GITHUB_PAT}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "mrxpronos-publish-bot",
  };
}

async function ghGetSha(path: string) {
  const url =
    `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}` +
    `?ref=${encodeURIComponent(GITHUB_BRANCH)}`;

  const res = await fetch(url, { headers: ghHeaders() });

  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`GitHub get sha failed ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();
  return data?.sha || null;
}

async function ghPutFile(path: string, contentText: string, message: string) {
  if (!GITHUB_OWNER || !GITHUB_REPO || !GITHUB_PAT) {
    throw new Error("GitHub env missing (GITHUB_OWNER/GITHUB_REPO/GITHUB_PAT)");
  }

  const sha = await ghGetSha(path);

  const body: any = {
    message,
    content: toBase64Utf8(contentText),
    branch: GITHUB_BRANCH,
  };

  if (sha) body.sha = sha;

  const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${path}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: ghHeaders(),
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(`GitHub put failed ${res.status}: ${await res.text()}`);
  }

  return await res.json();
}

function isBonusActive(b: any) {
  const now = new Date();
  const s = b?.start_date ? new Date(b.start_date + "T00:00:00") : null;
  const e = b?.end_date ? new Date(b.end_date + "T23:59:59") : null;
  if (s && now < s) return false;
  if (e && now > e) return false;
  return true;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

    const actorUid = await requireAdmin(req);

    // ARTICLES
    const { data: articles, error: aErr } = await sb
      .from("cms_articles")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (aErr) throw aErr;

    const articlesJson = (articles || []).map((a: any) => ({
      slug: a.slug,
      title: a.title,
      date: (a.published_at || a.updated_at || nowIso()),
      author: a.author || "Mr XPRONOS",
      excerpt: a.excerpt || "",
      meta_description: a.meta_description || "",
      keywords: a.keywords || "",
      faq: a.faq || [],
      content: a.content || "",
      image_url: a.image_url || "",
      og_image: a.og_image || a.image_url || "",
      active: a.active !== false,
    }));

    // CONSEILS
    const { data: conseils, error: cErr } = await sb
      .from("cms_conseils")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (cErr) throw cErr;

    const conseilsJson = (conseils || []).map((c: any) => ({
      slug: c.slug,
      title: c.title,
      content: c.content || "",
      date: (c.published_at || c.updated_at || nowIso()),
      excerpt: c.excerpt || "",
      image_url: c.image_url || "",
      active: c.active !== false,
      keywords: c.keywords || "",
    }));

    // BONUS (✅ filtrés par dates + active)
    const { data: bonus, error: bErr } = await sb
      .from("cms_bonus")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (bErr) throw bErr;

    const bonusJson = (bonus || [])
      .filter((b: any) => (b.active !== false) && isBonusActive(b))
      .map((b: any) => ({
        bookmaker: b.bookmaker,
        title: b.title,
        description: b.description,
        image: b.image_url || "",
        link: b.link || "",
        footer: b.footer || "",
        start_date: b.start_date || null,
        end_date: b.end_date || null,
        active: true,
      }));

    // INFOS
    const { data: infos, error: iErr } = await sb
      .from("cms_infos")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (iErr) throw iErr;

    const infosJson = (infos || []).map((i: any) => ({
      title: i.title,
      content: i.content,
      date: (i.published_at || i.updated_at || nowIso()),
      active: i.active !== false,
    }));

    // BOOKMAKERS
    const { data: books, error: bkErr } = await sb
      .from("cms_bookmakers")
      .select("*")
      .eq("status", "published")
      .order("updated_at", { ascending: false });

    if (bkErr) throw bkErr;

    const bookmakersJson = (books || []).map((b: any) => ({
      name: b.name,
      logo: b.logo || "",
      url: b.url || "",
      description: b.description || "",
      active: b.active !== false,
    }));

    // PUSH GITHUB (5 fichiers)
    const stamp = new Date().toISOString();
    await ghPutFile("articles.json", JSON.stringify(articlesJson, null, 2), `Publish articles ${stamp}`);
    await ghPutFile("conseils.json", JSON.stringify(conseilsJson, null, 2), `Publish conseils ${stamp}`);
    await ghPutFile("bonus.json", JSON.stringify(bonusJson, null, 2), `Publish bonus ${stamp}`);
    await ghPutFile("infos.json", JSON.stringify(infosJson, null, 2), `Publish infos ${stamp}`);
    await ghPutFile("bookmakers.json", JSON.stringify(bookmakersJson, null, 2), `Publish bookmakers ${stamp}`);

    // HISTORY + AUDIT (✅ plus léger : pas le payload complet)
    const { error: historyError } = await sb.from("publish_history").insert({
      actor_user_id: actorUid,
      payload: {
        files: ["articles.json","conseils.json","bonus.json","infos.json","bookmakers.json"],
        counts: {
          articles: articlesJson.length,
          conseils: conseilsJson.length,
          bonus: bonusJson.length,
          infos: infosJson.length,
          bookmakers: bookmakersJson.length,
        },
        published_at: nowIso()
      }
    });
    if (historyError) throw new Error("Publication appliquée, mais historique non enregistré: "+historyError.message);
    const { error: auditError } = await sb.from("audit_log").insert({
      actor_user_id: actorUid,
      action: "publish_json",
      details: {
        files: ["articles.json","conseils.json","bonus.json","infos.json","bookmakers.json"],
        counts: {
          articles: articlesJson.length,
          conseils: conseilsJson.length,
          bonus: bonusJson.length,
          infos: infosJson.length,
          bookmakers: bookmakersJson.length,
        },
      },
    });

    return json({
      success: true,
      counts: {
        articles: articlesJson.length,
        conseils: conseilsJson.length,
        bonus: bonusJson.length,
        infos: infosJson.length,
        bookmakers: bookmakersJson.length,
      },
    });

  } catch (e: any) {
    const msg = e?.message || String(e);
    const code = e?.code && Number.isFinite(e.code) ? e.code : (
      msg === "not_admin" ? 403 :
      msg.toLowerCase().includes("token") ? 401 :
      500
    );
    return json({ error: msg }, code);
  }
});