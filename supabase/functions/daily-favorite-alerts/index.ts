// Mr XPRONOS: favorite updates only after explicit opt-in.
// Existing general push subscribers are never enrolled automatically.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import * as webpush from "npm:web-push@3.6.7";

const SITE = "https://mrxpronos.github.io/MrXPRONOS_App/";
const TABLE = "daily_favorite_alerts_v1";
const ALLOWED_ORIGINS = new Set([
  "https://mrxpronos.github.io", "http://localhost:3000", "http://127.0.0.1:3000"
]);
const MAX_MESSAGES_PER_RUN = 200;

function cors(req) {
  const origin = req.headers.get("origin") || "";
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.has(origin) ? origin : SITE.slice(0, -("/MrXPRONOS_App/".length)),
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Vary": "Origin"
  };
}
function json(req, value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { ...cors(req), "Content-Type": "application/json", "Cache-Control": "no-store" }
  });
}
function db() {
  const url = Deno.env.get("SUPABASE_URL") || "";
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  if (!url || !key) throw new Error("Configuration serveur manquante");
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false }
  });
}
function normalize(text) {
  return String(text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\s+/g, " ").trim();
}
function cleanFavorites(value) {
  const output = { teams: [], leagues: [] };
  if (!value || typeof value !== "object") return output;
  for (const field of ["teams", "leagues"]) {
    const arr = Array.isArray(value[field]) ? value[field] : [];
    if (arr.length > 20) throw new Error("Maximum 20 favoris par catégorie");
    const seen = new Set();
    for (const raw of arr) {
      if (typeof raw !== "string" || raw.length > 90) throw new Error("Favori invalide");
      const cleaned = raw.trim().replace(/\s+/g, " ");
      const key = normalize(cleaned);
      if (!cleaned || seen.has(key)) continue;
      seen.add(key);
      output[field].push(cleaned);
    }
  }
  return output;
}
function subscriptionInfo(value) {
  const endpoint = String(value?.endpoint || "");
  const auth = String(value?.keys?.auth || "");
  const key = String(value?.keys?.p256dh || "");
  if (!/^https:\/\/[^ ]{20,2200}$/.test(endpoint) ||
      !/^[A-Za-z0-9_-]{10,200}$/.test(auth) ||
      !/^[A-Za-z0-9_-]{20,200}$/.test(key)) throw new Error("Abonnement push invalide");
  return { endpoint, auth, p256dh: key };
}
async function confirmOwnership(sb, value) {
  const sub = subscriptionInfo(value);
  const { data, error } = await sb.from("push_subscriptions")
    .select("endpoint,keys").eq("endpoint", sub.endpoint).maybeSingle();
  if (error) throw new Error("Abonnement temporairement indisponible");
  const keys = typeof data?.keys === "string" ? JSON.parse(data.keys) : data?.keys;
  if (!data || keys?.auth !== sub.auth || keys?.p256dh !== sub.p256dh)
    throw new Error("Abonnement push non vérifié");
  return sub.endpoint;
}
async function manage(req, body) {
  const origin = req.headers.get("origin");
  if (origin && !ALLOWED_ORIGINS.has(origin))
    return json(req, { error: "Origine non autorisée" }, 403);
  const sb = db();
  let endpoint;
  try { endpoint = await confirmOwnership(sb, body.subscription); }
  catch (error) { return json(req, { error: String(error?.message || error) }, 403); }
  const action = String(body.action || "");
  if (action === "status") {
    const { data, error } = await sb.from(TABLE).select(
      "enabled,favorites,hour_local,timezone_offset_minutes"
    ).eq("endpoint", endpoint).maybeSingle();
    if (error) return json(req, { error: "Statut indisponible" }, 500);
    return json(req, {
      enabled: data?.enabled === true,
      favorites: data?.favorites || { teams: [], leagues: [] },
      hour_local: data?.hour_local ?? 9
    });
  }
  if (action === "disable") {
    const { error } = await sb.from(TABLE).update({
      enabled: false, updated_at: new Date().toISOString()
    }).eq("endpoint", endpoint);
    if (error) return json(req, { error: "Désactivation impossible" }, 500);
    return json(req, { enabled: false });
  }
  if (action !== "save") return json(req, { error: "Action non prise en charge" }, 400);
  let favorites;
  try { favorites = cleanFavorites(body.favorites); }
  catch (error) { return json(req, { error: String(error?.message || error) }, 400); }
  if (!favorites.teams.length && !favorites.leagues.length)
    return json(req, { error: "Choisissez au moins une équipe ou une compétition." }, 400);
  const hour = Number(body.hour_local);
  const offset = Number(body.timezone_offset_minutes);
  if (!Number.isInteger(hour) || hour < 7 || hour > 21 ||
      !Number.isInteger(offset) || offset < -840 || offset > 720)
    return json(req, { error: "Heure ou fuseau horaire invalide" }, 400);
  const row = {
    endpoint, favorites, hour_local: hour, timezone_offset_minutes: offset,
    updated_at: new Date().toISOString(), enabled: true
  };
  const { error } = await sb.from(TABLE).upsert(row, { onConflict: "endpoint" });
  if (error) return json(req, { error: "Préférence non enregistrée" }, 500);
  return json(req, { enabled: true, hour_local: hour,
    favorite_count: favorites.teams.length + favorites.leagues.length });
}

function localClock(now, offset) {
  const local = new Date(now.getTime() - Number(offset) * 60000);
  return { day: local.toISOString().slice(0, 10), hour: local.getUTCHours() };
}
function favoriteIncludes(value, favorites) {
  const normalized = normalize(value);
  if (!normalized) return false;
  const all = [...(favorites?.teams || []), ...(favorites?.leagues || [])];
  return all.some(t => {
    const term = normalize(t);
    return term.length >= 3 && (normalized === term || normalized.includes(term));
  });
}
function selectRelevant(matches, news, favorites, day) {
  const matchesToday = [];
  const newsToday = [];
  for (const match of Array.isArray(matches) ? matches : []) {
    if (!match || match.date !== day || match.is_finished === true ||
        match.recommendation_eligible !== true || match.combo_only === true ||
        !["pro", "vip"].includes(String(match.category || "").toLowerCase()) ||
        ["finished","settlement_pending","postponed","cancelled","canceled"].includes(
          String(match.status || "").toLowerCase())) continue;
    if (!favoriteIncludes(match.home_team, favorites) &&
        !favoriteIncludes(match.away_team, favorites) &&
        !favoriteIncludes(match.league, favorites)) continue;
    if (!match.home_team || !match.away_team) continue;
    matchesToday.push(String(match.home_team).slice(0, 36) + " – " +
      String(match.away_team).slice(0, 36));
    if (matchesToday.length >= 3) break;
  }
  for (const item of Array.isArray(news) ? news : []) {
    if (!item || typeof item.published !== "string" || item.published.slice(0,10) !== day) continue;
    const names = Array.isArray(item.espn_verification?.teams) ? item.espn_verification.teams : [];
    const leagues = Array.isArray(item.espn_verification?.leagues) ? item.espn_verification.leagues : [];
    if (!favoriteIncludes(item.title, favorites) &&
        !names.some(v => favoriteIncludes(v, favorites)) &&
        !leagues.some(v => favoriteIncludes(v, favorites))) continue;
    newsToday.push(String(item.title || "").slice(0,90));
    if (newsToday.length >= 2) break;
  }
  return { matchesToday, newsToday };
}
async function feed(name) {
  const controller = new AbortController();
  const stop = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(SITE + name, { cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error("Flux inaccessible");
    return await response.json();
  } finally { clearTimeout(stop); }
}
async function deliver(req) {
  const secret = Deno.env.get("CRON_SECRET") || "";
  if (!secret || req.headers.get("Authorization") !== "Bearer " + secret)
    return json(req, { error: "Non autorisé" }, 401);

  const publicKey = Deno.env.get("VAPID_PUBLIC_KEY") || "";
  const privateKey = Deno.env.get("VAPID_PRIVATE_KEY") || "";
  const subject = Deno.env.get("VAPID_SUBJECT") ||
    (Deno.env.get("VAPID_EMAIL") ? "mailto:" + Deno.env.get("VAPID_EMAIL") : "");
  if (!publicKey || !privateKey || !subject)
    return json(req, { error: "Clés de notification non disponibles" }, 500);

  const sb = db();
  const { data, error } = await sb.from(TABLE)
    .select("endpoint,favorites,hour_local,timezone_offset_minutes,last_sent_local_day")
    .eq("enabled", true).limit(1000);
  if (error) return json(req, { error: "Préférences indisponibles" }, 500);

  const now = new Date();
  const due = (data || []).filter(p => {
    const local = localClock(now, p.timezone_offset_minutes);
    return local.hour === p.hour_local && p.last_sent_local_day !== local.day;
  });
  if (!due.length) return json(req, { due: 0, sent: 0, skipped: 0, failed: 0 });

  let snapshot, news;
  try { [snapshot, news] = await Promise.all([feed("data.json"), feed("footnews.json")]); }
  catch { return json(req, { error: "Flux publics indisponibles", sent: 0 }, 503); }
  const published = new Date(snapshot?.generated_at).getTime();
  if (!Array.isArray(snapshot?.matches) || !Array.isArray(news) ||
      !Number.isFinite(published) || published > now.getTime() + 600000 ||
      now.getTime() - published > 36 * 3600000)
    return json(req, { error: "Données trop anciennes ou invalides", sent: 0 }, 503);

  webpush.setVapidDetails(subject, publicKey, privateKey);
  let sent = 0, skipped = 0, failed = 0;
  for (const preference of due.slice(0, MAX_MESSAGES_PER_RUN)) {
    const localDay = localClock(now, preference.timezone_offset_minutes).day;
    const relevant = selectRelevant(snapshot.matches, news, preference.favorites, localDay);
    if (!relevant.matchesToday.length && !relevant.newsToday.length) { skipped++; continue; }

    // Atomic compare-and-update prevents two concurrent cron runs from sending twice.
    const { data: claimed, error: claimError } = await sb.from(TABLE)
      .update({ last_sent_local_day: localDay, updated_at: now.toISOString() })
      .eq("endpoint", preference.endpoint).eq("enabled", true)
      .or("last_sent_local_day.is.null,last_sent_local_day.lt." + localDay)
      .select("endpoint").maybeSingle();
    if (claimError || !claimed) { skipped++; continue; }

    const { data: sub, error: subError } = await sb.from("push_subscriptions")
      .select("endpoint,keys").eq("endpoint", preference.endpoint).maybeSingle();
    if (subError || !sub) { failed++; continue; }
    let keys = sub.keys;
    if (typeof keys === "string") { try { keys = JSON.parse(keys); } catch { keys = null; } }
    if (!keys?.auth || !keys?.p256dh) { failed++; continue; }

    const content = relevant.matchesToday.length ?
      "Football de vos favoris : " + relevant.matchesToday.slice(0,2).join(" ; ") :
      "À lire sur vos favoris : " + relevant.newsToday[0];
    const payload = JSON.stringify({
      title: "Mr XPRONOS · Vos favoris",
      body: content.slice(0,155),
      url: SITE + "aujourdhui.html",
      tag: "mx-favorite-" + localDay
    });
    try {
      await webpush.sendNotification({ endpoint: sub.endpoint, keys }, payload, { TTL: 3600 });
      sent++;
    } catch (e) {
      failed++;
      const code = Number(e?.statusCode || 0);
      if (code === 404 || code === 410)
        await sb.from("push_subscriptions").delete().eq("endpoint", sub.endpoint);
    }
  }
  return json(req, { due: due.length, sent, skipped, failed });
}

Deno.serve(async req => {
  if (req.method === "OPTIONS")
    return new Response(null, { status: 204, headers: cors(req) });
  if (req.method !== "POST")
    return json(req, { error: "Méthode non prise en charge" }, 405);
  let body;
  try { body = await req.json(); }
  catch { return json(req, { error: "JSON invalide" }, 400); }
  if (!body || typeof body !== "object")
    return json(req, { error: "Requête invalide" }, 400);
  try {
    if (body.action === "dispatch") return await deliver(req);
    if (["status", "save", "disable"].includes(body.action))
      return await manage(req, body);
    return json(req, { error: "Action inconnue" }, 400);
  } catch {
    return json(req, { error: "Service indisponible" }, 500);
  }
});
