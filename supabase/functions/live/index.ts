// live.ts (Supabase Edge Function / Deno)
// =======================================================
// PATCHES inclus :
// - Deux canaux Telegram conservés (principal + secondaire), anti-doublon par prediction_id
// 1) Règle pronostic: on ne propose un seuil que si (seuil >= actuel + 2)
// 2) LIVE UI: /matches et /opportunities lisent la DB (matches_live + live_predictions)
// 3) Historique: INSERT only (pas d'écrasement)
// 4) "Projection" => "Au signal" stocké dans projected_value
// 5) Validation in-play: update current_value + success instant si current_value > threshold
// 6) Notifications: insertNotification() robuste (fallback minimal) + related_prediction_id
// 7) Anti-crash duplicate key (23505): savePrediction idempotent + tolérance message sans code
// 8) History + detail endpoints enrichis avec logos (via matches_live.raw_data)
// 9) Telegram LIVE: image prioritaire sur 2 canaux + retry image/WASM + fallback détaillé + retry DB
// 10) Telegram logos: fallback logos multi-source + conversion PNG si nécessaire
//    - GET /predictions/history
//    - GET /predictions/by-id?id=...
//
// IMPORTANT (DB) :
// - Le meilleur schéma est un UNIQUE INDEX PARTIEL sur (match_id,prediction_type,threshold) WHERE validated=false.
// - Si ton index unique inclut validated ou n'est pas partiel, les UPDATE validated=true peuvent aussi déclencher 23505.
// Ce fichier contient un "self-heal" (merge + delete) si ça arrive.
// =======================================================

import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// IMPORTANT CPU:
// Les dépendances lourdes Telegram (Satori / Resvg) sont chargées à la demande.
// Elles ne pénalisent donc plus chaque appel /refresh qui ne génère aucune image.

// =======================================================
// ENV
// =======================================================
const BSD_API_TOKEN = Deno.env.get("BSD_API_TOKEN") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const DEFAULT_TZ = Deno.env.get("BSD_TZ") || "Europe/Paris";

const CRON_SECRET = Deno.env.get("CRON_SECRET") || "";
const DEBUG_KEY = Deno.env.get("DEBUG_KEY") || "";

const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
const TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || "";
// Deux destinations Telegram voulues : canal principal + canal secondaire.
// L'anti-doublon est géré par prediction_id + liste des canaux en échec :
// un coupon doit partir une seule fois vers chacun des deux canaux.
const TELEGRAM_CHAT_ID_SECONDARY = Deno.env.get("TELEGRAM_CHAT_ID_SECONDARY") || "@mrxpronosfr";
const SITE_URL = Deno.env.get("SITE_URL") || "https://mrxpronos.github.io/MrXPRONOS_App/";

const BSD_API_BASE = "https://sports.bzzoiro.com/api";
const BSD_IMG_BASE = "https://sports.bzzoiro.com/img";

const ESPN_SCOREBOARD_URL =
  "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard";

// Active/désactive l’agrégation ESPN sans toucher au code.
// Par défaut : activé.
const ENABLE_ESPN_MERGE =
  String(Deno.env.get("ENABLE_ESPN_MERGE") || "true").toLowerCase() !== "false";

// Refresh par petits lots pour rester sous la limite CPU Supabase.
// Valeur choisie : 5 matchs par invocation enfant.
const LIVE_REFRESH_BATCH_SIZE = Math.max(
  1,
  Math.min(5, safeEnvInt("LIVE_REFRESH_BATCH_SIZE", 5)),
);
const LIVE_REFRESH_MAX_BATCHES = Math.max(
  1,
  Math.min(50, safeEnvInt("LIVE_REFRESH_MAX_BATCHES", 20)),
);

const T_STATS_SOURCES = "live_stats_sources";
const T_STATS_MERGED = "live_stats_merged";

if (!BSD_API_TOKEN) console.error("BSD_API_TOKEN non défini");
if (!SUPABASE_URL) console.error("SUPABASE_URL non défini");
if (!SUPABASE_SERVICE_ROLE_KEY) console.error("SUPABASE_SERVICE_ROLE_KEY non défini");

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// =======================================================
// CORS
// =======================================================
const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-cron-secret",
};

// =======================================================
// HELPERS
// =======================================================
function json(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, ...headers, "Content-Type": "application/json" },
  });
}

function safeNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function safeEnvInt(name: string, fallback: number): number {
  const n = Number(Deno.env.get(name) || "");
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

function computeFreshness(updatedAt?: string | number | null) {
  if (!updatedAt) return null;
  const ts = typeof updatedAt === "number" ? updatedAt : new Date(updatedAt).getTime();
  if (!Number.isFinite(ts)) return null;
  return Math.max(0, Math.floor((Date.now() - ts) / 1000));
}

function nowIso() {
  return new Date().toISOString();
}

function todayYYYYMMDD() {
  return new Date().toISOString().slice(0, 10).replace(/-/g, "");
}

function toDateKey(value?: unknown) {
  const raw = String(value ?? "").trim();

  if (/^\d{8}$/.test(raw)) return raw;
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10).replace(/-/g, "");

  const d = raw ? new Date(raw) : new Date();
  if (Number.isFinite(d.getTime())) return d.toISOString().slice(0, 10).replace(/-/g, "");

  return todayYYYYMMDD();
}

function stripAccents(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function normalizeTeamKey(name: unknown) {
  return stripAccents(String(name ?? ""))
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\b(fc|cf|sc|afc|club|de|da|do|the|football|soccer)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function slugTeam(name: unknown) {
  return normalizeTeamKey(name).replace(/\s+/g, "-") || "unknown";
}

function getMatchEventDate(match: any) {
  return (
    match?.event_date ??
    match?.date ??
    match?.start_time ??
    match?.startTime ??
    match?.kickoff ??
    match?.raw_data?.event_date ??
    match?.raw_data?.date ??
    null
  );
}

function getLeagueName(match: any) {
  return (
    match?.league_name ??
    match?.league?.name ??
    match?.competition?.name ??
    match?.competitionDisplayName ??
    match?.raw_data?.league?.name ??
    match?.raw_data?.competition?.name ??
    "Football"
  );
}

function buildCanonicalMatchId(match: any) {
  const dateKey = toDateKey(getMatchEventDate(match));
  const home = slugTeam(match?.home_team ?? match?.homeTeam ?? match?.home?.name);
  const away = slugTeam(match?.away_team ?? match?.awayTeam ?? match?.away?.name);
  return `${dateKey}_${home}_${away}`;
}

function tokenSet(value: unknown) {
  const clean = normalizeTeamKey(value);
  if (!clean) return new Set<string>();
  return new Set(clean.split(" ").filter(Boolean));
}

function jaccardSimilarity(a: unknown, b: unknown) {
  const A = tokenSet(a);
  const B = tokenSet(b);
  if (!A.size || !B.size) return 0;

  let intersection = 0;
  for (const x of A) {
    if (B.has(x)) intersection++;
  }

  const union = new Set([...A, ...B]).size;
  return union ? intersection / union : 0;
}

function sameMatchScore(a: any, b: any) {
  if (toDateKey(getMatchEventDate(a)) !== toDateKey(getMatchEventDate(b))) return 0;

  const sameOrder =
    (jaccardSimilarity(a?.home_team, b?.home_team) +
      jaccardSimilarity(a?.away_team, b?.away_team)) / 2;

  const reversed =
    (jaccardSimilarity(a?.home_team, b?.away_team) +
      jaccardSimilarity(a?.away_team, b?.home_team)) / 2;

  return Math.max(sameOrder, reversed);
}

function getHomeStats(stats: any) {
  return stats?.home || {};
}

function getAwayStats(stats: any) {
  return stats?.away || {};
}

function statPairTotal(stats: any, key: string, totalKey?: string) {
  const totals = stats?.totals || {};
  const tk = totalKey || key;
  const explicit = safeNumber(totals?.[tk], NaN);
  if (Number.isFinite(explicit)) return explicit;

  return safeNumber(getHomeStats(stats)?.[key], 0) + safeNumber(getAwayStats(stats)?.[key], 0);
}

function ensureLiveStatsShape(stats: any) {
  const home = { ...(stats?.home || {}) };
  const away = { ...(stats?.away || {}) };
  const totals = { ...(stats?.totals || {}) };

  if (totals.corners == null) {
    totals.corners = safeNumber(home.corner_kicks, 0) + safeNumber(away.corner_kicks, 0);
  }
  if (totals.fouls == null) {
    totals.fouls = safeNumber(home.fouls, 0) + safeNumber(away.fouls, 0);
  }
  if (totals.total_shots == null) {
    totals.total_shots = safeNumber(home.total_shots, 0) + safeNumber(away.total_shots, 0);
  }
  if (totals.shots_on_target == null) {
    totals.shots_on_target = safeNumber(home.shots_on_target, 0) + safeNumber(away.shots_on_target, 0);
  }

  return { ...stats, home, away, totals };
}

function applyStatPairIfBetter(base: any, extra: any, key: string, totalKey?: string) {
  const tk = totalKey || key;

  const baseTotal = statPairTotal(base, key, tk);
  const extraTotal = statPairTotal(extra, key, tk);

  if (extraTotal <= 0) return;
  if (baseTotal > 0 && extraTotal < baseTotal) return;

  base.home[key] = safeNumber(extra?.home?.[key], base.home[key] ?? 0);
  base.away[key] = safeNumber(extra?.away?.[key], base.away[key] ?? 0);
  base.totals[tk] = extraTotal;
}

function mergeLiveStats(primaryStats: any, secondaryStats: any) {
  const merged = ensureLiveStatsShape(primaryStats || {});
  const extra = ensureLiveStatsShape(secondaryStats || {});

  // Stats cumulatives : on prend la source qui a la valeur la plus récente/complète.
  applyStatPairIfBetter(merged, extra, "corner_kicks", "corners");
  applyStatPairIfBetter(merged, extra, "fouls", "fouls");
  applyStatPairIfBetter(merged, extra, "yellow_cards", "yellow_cards");
  applyStatPairIfBetter(merged, extra, "red_cards", "red_cards");

  // On ne remplace les tirs que si l’autre source a vraiment plus d’info.
  applyStatPairIfBetter(merged, extra, "total_shots", "total_shots");
  applyStatPairIfBetter(merged, extra, "shots_on_target", "shots_on_target");

  return ensureLiveStatsShape(merged);
}

function getMatchLiveStats(match: any) {
  return match?.live_stats || match?.raw_data?.live_stats || {};
}

function getSourceMatchId(match: any, sourceName: string) {
  if (sourceName === "espn") {
    return String(match?.source_match_id || match?.espn_id || match?.id || "");
  }
  return String(match?.id || match?.source_match_id || "");
}

function sourceRowFromMatch(match: any, sourceName: "api_original" | "espn") {
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(match));
  const canonical = buildCanonicalMatchId(match);

  return {
    canonical_match_id: canonical,
    source_name: sourceName,
    source_match_id: getSourceMatchId(match, sourceName),
    home_team: match?.home_team ?? null,
    away_team: match?.away_team ?? null,
    league_name: getLeagueName(match),
    event_date: getMatchEventDate(match) ? new Date(getMatchEventDate(match)).toISOString() : null,
    minute: safeNumber(match?.current_minute ?? match?.minute, 0),
    home_score: safeNumber(match?.home_score, 0),
    away_score: safeNumber(match?.away_score, 0),
    is_live: Boolean(match?.is_live ?? true),
    is_finished: Boolean(match?.is_finished ?? false),
    stats_json: liveStats,
    raw_json: match,
    updated_at: nowIso(),
  };
}

function mergedRowFromMatch(match: any) {
  const canonical = buildCanonicalMatchId(match);
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(match));
  const raw = match?.raw_data || {};

  return {
    canonical_match_id: canonical,
    primary_match_id: String(match?.id),
    home_team: match?.home_team ?? null,
    away_team: match?.away_team ?? null,
    league_name: getLeagueName(match),
    event_date: getMatchEventDate(match) ? new Date(getMatchEventDate(match)).toISOString() : null,
    minute: safeNumber(match?.current_minute ?? match?.minute, 0),
    home_score: safeNumber(match?.home_score, 0),
    away_score: safeNumber(match?.away_score, 0),
    is_live: Boolean(match?.is_live ?? true),
    is_finished: Boolean(match?.is_finished ?? false),
    merged_stats: liveStats,
    sources_used: raw?.merge_meta?.sources || [],
    confidence_score: safeNumber(raw?.merge_meta?.confidence_score, 0),
    merged_match_json: match,
    updated_at: nowIso(),
  };
}

async function persistStatsSourcesAndMerged(sourceRows: any[], mergedMatches: any[]) {
  const mergedRows = mergedMatches.map(mergedRowFromMatch);

  try {
    if (sourceRows.length > 0) {
      const { error } = await supabase
        .from(T_STATS_SOURCES)
        .upsert(sourceRows, { onConflict: "source_name,source_match_id" });

      if (error) throw error;
    }

    if (mergedRows.length > 0) {
      const { error } = await supabase
        .from(T_STATS_MERGED)
        .upsert(mergedRows, { onConflict: "canonical_match_id" });

      if (error) throw error;
    }
  } catch (e) {
    // Ne jamais casser le live original juste parce que la table d’agrégation n’existe pas.
    console.warn("Agrégation stats non persistée:", e);
  }
}


function extractPath(url: URL, fnName = "live") {
  const p = url.pathname;
  const needle = `/${fnName}`;
  const i = p.lastIndexOf(needle);
  if (i >= 0) {
    const rest = p.slice(i + needle.length);
    return rest === "" ? "/" : rest;
  }
  return p || "/";
}

function requireCronAuth(req: Request, url: URL) {
  if (!CRON_SECRET) return; // public si non défini
  const auth = req.headers.get("authorization") || "";
  const x = req.headers.get("x-cron-secret") || "";
  const q = url.searchParams.get("key") || "";

  const bearerOk =
    auth.toLowerCase().startsWith("bearer ") && auth.slice(7).trim() === CRON_SECRET;

  const ok = bearerOk || x === CRON_SECRET || q === CRON_SECRET;
  if (!ok) throw new Error("Unauthorized (CRON_SECRET)");
}

function requireDebugAuth(url: URL) {
  if (!DEBUG_KEY) return; // public si non défini
  const key = url.searchParams.get("key") || "";
  if (key !== DEBUG_KEY) throw new Error("Unauthorized (DEBUG_KEY)");
}

async function fetchBSD(endpoint: string, params?: Record<string, string>) {
  if (!BSD_API_TOKEN) throw new Error("BSD_API_TOKEN missing");

  const url = new URL(`${BSD_API_BASE}${endpoint}`);
  const finalParams: Record<string, string> = { ...(params || {}) };

  if (!finalParams.tz) finalParams.tz = DEFAULT_TZ;
  for (const [k, v] of Object.entries(finalParams)) {
    if (v != null && v !== "") url.searchParams.set(k, v);
  }

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Token ${BSD_API_TOKEN}` },
  });

  if (!res.ok) {
    const error = await res.text().catch(() => "");
    throw new Error(`BSD API error (${res.status}): ${error || res.statusText}`);
  }

  return res.json();
}

function isFinishedEvent(ev: any) {
  const status = String(ev?.status || "").toLowerCase();
  const period = String(ev?.period || "").toUpperCase();
  return status === "finished" || period === "FT";
}

function isDuplicateKeyError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return (
    code === "23505" ||
    msg.includes("duplicate key value violates unique constraint") ||
    msg.includes("live_predictions_unique_idx")
  );
}

function isUndefinedColumnError(err: any) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return code === "42703" || msg.toLowerCase().includes("does not exist");
}

// =======================================================
// ✅ Notifications insertion robuste + logs + fallback
// =======================================================
async function insertNotification(payload: {
  user_id?: string;
  type: string;
  title: string;
  message: string;
  priority?: string;
  read?: boolean;
  related_prediction_id?: string | number | null;
}) {
  const baseRow: any = {
    user_id: payload.user_id ?? "all",
    type: payload.type,
    title: payload.title,
    message: payload.message,
    created_at: new Date().toISOString(),
  };

  const fullRow: any = {
    ...baseRow,
    priority: payload.priority ?? "normal",
    read: payload.read ?? false,
    related_prediction_id:
      payload.related_prediction_id == null ? null : String(payload.related_prediction_id),
  };

  // 1) tentative "full"
  {
    const { error } = await supabase.from("notifications").insert(fullRow);
    if (!error) return true;

    console.error("❌ notifications insert failed (full):", error, "row=", fullRow);

    // 2) fallback minimal
    const { error: e2 } = await supabase.from("notifications").insert(baseRow);
    if (!e2) return true;

    console.error("❌ notifications insert failed (minimal):", e2, "row=", baseRow);
    return false;
  }
}


// =======================================================
// ✅ TELEGRAM LIVE COUPONS — IMAGE SATORI + LOGOS + TEXTE DANS L'IMAGE
// =======================================================
function formatLivePredictionType(type: string) {
  if (type === "total_corners") return "Corners";
  if (type === "total_shots") return "Tirs";
  if (type === "total_fouls") return "Fautes";
  return "Signal LIVE";
}

function formatThreshold(value: unknown) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

function predictionLabelForCaption(type: string) {
  if (type === "total_corners") return "corners";
  if (type === "total_shots") return "tirs";
  if (type === "total_fouls") return "fautes";
  return "";
}

function getTeamInitials(name: unknown) {
  const clean = String(name ?? "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (!clean) return "MX";

  const parts = clean.split(" ").filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}

function bytesToBase64(bytes: Uint8Array) {
  let binary = "";
  const chunkSize = 0x8000;

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

function detectImageMime(bytes: Uint8Array): string {
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return "image/png";
  }

  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return "image/jpeg";
  }

  return "";
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fitText(text: unknown, max = 32): string {
  const s = String(text ?? "").replace(/\s+/g, " ").trim();
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)).trim() + "…";
}

function confidenceFromPrediction(pred: any): number {
  const probability = safeNumber(pred?.probability, 0);
  if (probability > 0 && probability <= 1) return Math.round(probability * 100);

  const reliability = safeNumber(pred?.reliability, 0);
  if (reliability > 0) return Math.round(reliability);

  const confidence = safeNumber(pred?.confidence, 0);
  if (confidence > 0 && confidence <= 1) return Math.round(confidence * 100);
  if (confidence > 0) return Math.round(confidence);

  return 0;
}

function uniqueLogoCandidates(values: unknown[]): string[] {
  return [...new Set(
    values
      .map((value) => String(value ?? "").trim())
      .filter(Boolean),
  )];
}

function pickLogoUrls(match: any, type: "home" | "away" | "league") {
  const raw = match?.raw_data || match || {};

  if (type === "home") {
    return uniqueLogoCandidates([
      match?.home_logo,
      raw?.home_logo,
      raw?.home_team_obj?.logo,
      raw?.home_team_obj?.image,
      raw?.home_team_obj?.crest,
      raw?.home?.logo,
      raw?.home?.image,
      raw?.home?.team?.logo,
      raw?.home?.team?.image,
      raw?.home?.team?.logos?.[0]?.href,
      raw?.home?.team?.logos?.[0]?.url,
    ]);
  }

  if (type === "away") {
    return uniqueLogoCandidates([
      match?.away_logo,
      raw?.away_logo,
      raw?.away_team_obj?.logo,
      raw?.away_team_obj?.image,
      raw?.away_team_obj?.crest,
      raw?.away?.logo,
      raw?.away?.image,
      raw?.away?.team?.logo,
      raw?.away?.team?.image,
      raw?.away?.team?.logos?.[0]?.href,
      raw?.away?.team?.logos?.[0]?.url,
    ]);
  }

  return uniqueLogoCandidates([
    match?.league_logo,
    raw?.league_logo,
    raw?.league?.logo,
    raw?.league?.image,
    raw?.league?.logos?.[0]?.href,
    raw?.competition?.logo,
    raw?.competition?.image,
    raw?.competition?.logos?.[0]?.href,
  ]);
}

function pickBsdLogoIds(match: any, type: "home" | "away" | "league") {
  const raw = match?.raw_data || match || {};
  const source = String(raw?.source ?? match?.source_name ?? "").toLowerCase();
  const sources = Array.isArray(raw?.merge_meta?.sources)
    ? raw.merge_meta.sources.map((s: unknown) => String(s).toLowerCase())
    : [];

  const espnOnly = source === "espn" || (sources.length === 1 && sources[0] === "espn");
  if (espnOnly) return [];

  if (type === "home") {
    return uniqueLogoCandidates([
      match?.home_team_id,
      raw?.home_team_id,
      raw?.home_team_obj?.api_id,
      raw?.home_team_obj?.id,
      raw?.home?.team?.api_id,
      raw?.home?.team?.id,
      raw?.home?.id,
    ]);
  }

  if (type === "away") {
    return uniqueLogoCandidates([
      match?.away_team_id,
      raw?.away_team_id,
      raw?.away_team_obj?.api_id,
      raw?.away_team_obj?.id,
      raw?.away?.team?.api_id,
      raw?.away?.team?.id,
      raw?.away?.id,
    ]);
  }

  return uniqueLogoCandidates([
    match?.league_id,
    raw?.league_id,
    raw?.league?.api_id,
    raw?.league?.id,
    raw?.competition?.api_id,
    raw?.competition?.id,
  ]);
}

function pickEspnLogoId(match: any, type: "home" | "away" | "league") {
  const raw = match?.raw_data || match || {};
  const source = String(raw?.source ?? match?.source_name ?? "").toLowerCase();
  const espnOnly = source === "espn" ||
    (Array.isArray(raw?.merge_meta?.sources) && raw.merge_meta.sources.length === 1 && raw.merge_meta.sources[0] === "espn");

  if (type === "home") {
    return (
      raw?.home_team_obj?.espn_id ??
      raw?.home?.team?.espn_id ??
      (espnOnly ? (match?.home_team_id ?? raw?.home_team_id ?? raw?.home_team_obj?.id ?? raw?.home_team_obj?.api_id) : null) ??
      null
    );
  }

  if (type === "away") {
    return (
      raw?.away_team_obj?.espn_id ??
      raw?.away?.team?.espn_id ??
      (espnOnly ? (match?.away_team_id ?? raw?.away_team_id ?? raw?.away_team_obj?.id ?? raw?.away_team_obj?.api_id) : null) ??
      null
    );
  }

  return raw?.league?.espn_id ?? (espnOnly ? (match?.league_id ?? raw?.league_id ?? raw?.league?.id) : null) ?? null;
}

function teamNameForLogo(match: any, kind: "home" | "away" | "league") {
  if (kind === "home") return String(match?.home_team ?? match?.homeTeam ?? "").trim();
  if (kind === "away") return String(match?.away_team ?? match?.awayTeam ?? "").trim();
  return String(getLeagueName(match) || "").trim();
}

const telegramLogoDataCache = new Map<string, string>();

async function bytesToSupportedDataUri(bytes: Uint8Array, sourceLabel = "image") {
  if (bytes.length > 800_000) {
    console.warn("Logo trop lourd, ignoré:", sourceLabel, bytes.length);
    return "";
  }

  const mime = detectImageMime(bytes);
  if (!mime) {
    console.warn("Logo ignoré: format non supporté directement par le rendu Telegram:", sourceLabel, {
      bytes: bytes.length,
      header: Array.from(bytes.slice(0, 12)).map((b) => b.toString(16).padStart(2, "0")).join(" "),
    });
    return "";
  }

  return `data:${mime};base64,${bytesToBase64(bytes)}`;
}

function normalizeLogoUrl(url: unknown): string {
  const raw = String(url ?? "").trim();
  if (!raw) return "";
  if (raw.startsWith("data:image/")) return raw;
  if (raw.startsWith("//")) return `https:${raw}`;

  try {
    if (/^https?:\/\//i.test(raw)) return raw;
    return new URL(raw, `${BSD_API_BASE}/`).toString();
  } catch {
    return raw;
  }
}

async function fetchLogoResponse(url: string, headers: Record<string, string> = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6_000);

  try {
    return await fetch(url, {
      signal: controller.signal,
      redirect: "follow",
      headers: {
        "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
        "Accept": "image/png,image/jpeg,*/*;q=0.5",
        ...headers,
      },
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function convertPublicImageToPngDataUri(url: string): Promise<string> {
  if (!/^https?:\/\//i.test(url) || url.includes("wsrv.nl/")) return "";

  try {
    const proxy = new URL("https://wsrv.nl/");
    proxy.searchParams.set("url", url);
    proxy.searchParams.set("output", "png");
    proxy.searchParams.set("w", "256");
    proxy.searchParams.set("h", "256");
    proxy.searchParams.set("fit", "inside");

    const res = await fetchLogoResponse(proxy.toString());
    if (!res.ok) {
      console.warn("Conversion PNG logo impossible:", res.status, url);
      return "";
    }

    const bytes = new Uint8Array(await res.arrayBuffer());
    return await bytesToSupportedDataUri(bytes, `png-proxy:${url}`);
  } catch (e) {
    console.warn("Conversion PNG logo impossible:", url, e);
    return "";
  }
}

async function imageUrlToDataUri(url?: string | null): Promise<string> {
  const normalized = normalizeLogoUrl(url);
  if (!normalized) return "";
  if (normalized.startsWith("data:image/")) return normalized;

  const cacheKey = `url:${normalized}`;
  const cached = telegramLogoDataCache.get(cacheKey);
  if (cached) return cached;

  try {
    const res = await fetchLogoResponse(normalized);

    if (!res.ok) {
      console.warn("Logo impossible à charger:", res.status, normalized);
      return "";
    }

    const bytes = new Uint8Array(await res.arrayBuffer());
    const direct = await bytesToSupportedDataUri(bytes, normalized);
    if (direct) {
      telegramLogoDataCache.set(cacheKey, direct);
      return direct;
    }

    const converted = await convertPublicImageToPngDataUri(normalized);
    if (converted) telegramLogoDataCache.set(cacheKey, converted);
    return converted;
  } catch (e: any) {
    const detail = e?.name === "AbortError" ? "timeout" : (e?.message || String(e));
    console.warn("Logo impossible à convertir en data URI:", normalized, detail);
    return "";
  }
}

async function bsdImageToDataUri(type: "team" | "league", id?: string | number | null) {
  if (!id || !BSD_API_TOKEN) return "";

  const safeId = String(id).trim();
  if (!safeId) return "";

  const cacheKey = `bsd:${type}:${safeId}`;
  const cached = telegramLogoDataCache.get(cacheKey);
  if (cached) return cached;

  try {
    const url = `${BSD_IMG_BASE}/${type}/${encodeURIComponent(safeId)}/`;
    const res = await fetchLogoResponse(url, { Authorization: `Token ${BSD_API_TOKEN}` });

    if (!res.ok) {
      console.warn("Logo BSD impossible à charger:", res.status, type, safeId);
      return "";
    }

    const bytes = new Uint8Array(await res.arrayBuffer());
    const direct = await bytesToSupportedDataUri(bytes, `${type}:${safeId}`);
    if (direct) {
      telegramLogoDataCache.set(cacheKey, direct);
      return direct;
    }

    if (SUPABASE_URL) {
      const publicProxy = `${SUPABASE_URL.replace(/\/$/, "")}/functions/v1/live/img/${type}/${encodeURIComponent(safeId)}/`;
      const converted = await convertPublicImageToPngDataUri(publicProxy);
      if (converted) {
        telegramLogoDataCache.set(cacheKey, converted);
        return converted;
      }
    }

    return "";
  } catch (e: any) {
    const detail = e?.name === "AbortError" ? "timeout" : (e?.message || String(e));
    console.warn("Logo BSD impossible à convertir:", type, safeId, detail);
    return "";
  }
}

function espnTeamLogoUrl(id?: string | number | null) {
  const clean = String(id ?? "").trim();
  return clean ? `https://a.espncdn.com/i/teamlogos/soccer/500/${encodeURIComponent(clean)}.png` : "";
}

async function findEspnTeamLogoByName(teamName: string): Promise<string> {
  const wanted = normalizeTeamKey(teamName);
  if (!wanted) return "";

  try {
    const scoreboard = await fetchEspnScoreboard(todayYYYYMMDD(), false);
    let bestScore = 0;
    let bestUrl = "";

    for (const event of scoreboard?.events || []) {
      const competition = event?.competitions?.[0];
      for (const competitor of competition?.competitors || []) {
        const team = competitor?.team || {};
        const candidateName = team?.displayName || team?.name || team?.shortDisplayName || "";
        const score = jaccardSimilarity(teamName, candidateName);
        if (normalizeTeamKey(candidateName) === wanted || score > bestScore) {
          bestScore = normalizeTeamKey(candidateName) === wanted ? 1 : score;
          bestUrl = team?.logo || team?.logos?.[0]?.href || espnTeamLogoUrl(team?.id);
        }
      }
    }

    return bestScore >= 0.72 ? String(bestUrl || "") : "";
  } catch (e) {
    console.warn("Recherche logo ESPN par nom impossible:", teamName, e);
    return "";
  }
}

async function getTelegramLogoData(match: any, kind: "home" | "away" | "league") {
  for (const directUrl of pickLogoUrls(match, kind)) {
    const direct = await imageUrlToDataUri(directUrl);
    if (direct) return direct;
  }

  for (const id of pickBsdLogoIds(match, kind)) {
    const bsd = await bsdImageToDataUri(kind === "league" ? "league" : "team", id);
    if (bsd) return bsd;
  }

  if (kind !== "league") {
    const espnId = pickEspnLogoId(match, kind);
    if (espnId) {
      const espn = await imageUrlToDataUri(espnTeamLogoUrl(espnId));
      if (espn) return espn;
    }

    const name = teamNameForLogo(match, kind);
    if (name) {
      const espnByName = await findEspnTeamLogoByName(name);
      if (espnByName) {
        const converted = await imageUrlToDataUri(espnByName);
        if (converted) return converted;
      }
    }
  }

  console.warn("⚠️ Aucun logo exploitable pour Telegram:", {
    kind,
    team: teamNameForLogo(match, kind),
    match_id: match?.id ?? null,
    source: match?.raw_data?.source ?? match?.source_name ?? null,
  });
  return "";
}

type TelegramRenderModules = {
  initWasm: (bytes: ArrayBuffer) => Promise<void>;
  Resvg: any;
  satori: any;
  html: any;
};

let telegramRenderModulesPromise: Promise<TelegramRenderModules> | null = null;

async function loadTelegramRenderModules(): Promise<TelegramRenderModules> {
  if (!telegramRenderModulesPromise) {
    telegramRenderModulesPromise = (async () => {
      const [resvgMod, satoriMod, htmlMod] = await Promise.all([
        import("https://esm.sh/@resvg/resvg-wasm@2.6.2?target=deno"),
        import("npm:satori@0.12.0"),
        import("npm:satori-html@0.3.2"),
      ]);

      return {
        initWasm: resvgMod.initWasm,
        Resvg: resvgMod.Resvg,
        satori: satoriMod.default,
        html: htmlMod.html,
      };
    })().catch((e) => {
      // Une erreur de chargement ne doit pas empoisonner le worker chaud.
      telegramRenderModulesPromise = null;
      throw e;
    });
  }

  return await telegramRenderModulesPromise;
}

let resvgReady: Promise<void> | null = null;

type TelegramFonts = {
  regular: ArrayBuffer;
  bold: ArrayBuffer;
  extraBold: ArrayBuffer;
};

let cachedFontData: TelegramFonts | null = null;

// Polices Telegram : on ignore volontairement les fichiers _fonts locaux.
// Les fichiers présents dans le bundle peuvent être tronqués tout en ayant un en-tête TTF valide,
// ce qui faisait planter opentype.js/Satori avec "Offset is outside the bounds of the DataView".
// On charge donc trois fichiers Noto Sans connus et valides depuis Google Fonts, une seule fois
// par instance Edge Function, puis on les conserve en mémoire.
const REMOTE_FONT_URLS: Record<string, string[]> = {
  "NotoSans-Regular.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
  ],
  "NotoSans-Bold.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
  ],
  "NotoSans-ExtraBold.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-ExtraBold.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-ExtraBold.ttf",
  ],
};

function fontHeader(bytes: Uint8Array): string {
  return Array.from(bytes.slice(0, 16))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join(" ");
}

function isValidFontFile(bytes: Uint8Array): boolean {
  if (bytes.byteLength < 20_000) return false;
  const head = Array.from(bytes.slice(0, 4))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return head === "00010000" || head === "4f54544f" || head === "74746366" || head === "74727565";
}

function toExactArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function fetchRemoteFont(filename: string): Promise<Uint8Array> {
  const urls = REMOTE_FONT_URLS[filename] || [];
  if (!urls.length) throw new Error(`Aucune URL distante pour ${filename}`);

  const errors: string[] = [];

  for (const url of urls) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8_000);

    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: {
          "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
          "Accept": "font/ttf,application/octet-stream,*/*;q=0.8",
        },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const bytes = new Uint8Array(await res.arrayBuffer());
      if (!isValidFontFile(bytes)) {
        throw new Error(`fichier police invalide (${bytes.byteLength} octets, header=${fontHeader(bytes)})`);
      }

      console.log("✅ Police Telegram distante chargée", {
        filename,
        bytes: bytes.byteLength,
        source: url.includes("jsdelivr") ? "jsDelivr" : "GitHub",
      });
      return bytes;
    } catch (e: any) {
      const detail = e?.name === "AbortError" ? "timeout" : (e?.message || String(e));
      errors.push(`${url} => ${detail}`);
      console.warn("⚠️ Source de police indisponible", { filename, source: url, error: detail });
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new Error(`Impossible de charger ${filename}: ${errors.join(" | ")}`);
}

async function loadFontData(): Promise<TelegramFonts> {
  if (cachedFontData) return cachedFontData;

  // Chargement séquentiel volontaire : moins de pic mémoire/CPU qu'un Promise.all
  // dans le worker Supabase.
  const regular = await fetchRemoteFont("NotoSans-Regular.ttf");
  const bold = await fetchRemoteFont("NotoSans-Bold.ttf");
  const extraBold = await fetchRemoteFont("NotoSans-ExtraBold.ttf");

  cachedFontData = {
    regular: toExactArrayBuffer(regular),
    bold: toExactArrayBuffer(bold),
    extraBold: toExactArrayBuffer(extraBold),
  };

  console.log("✅ Polices Telegram prêtes (mode léger, cache actif)");
  return cachedFontData;
}

async function fetchResvgWasm(): Promise<ArrayBuffer> {
  // Plusieurs CDN : un incident ponctuel sur jsDelivr ne doit plus bloquer
  // toutes les images Telegram jusqu'au prochain déploiement/cold start.
  const urls = [
    "https://cdn.jsdelivr.net/npm/@resvg/resvg-wasm@2.6.2/index_bg.wasm",
    "https://unpkg.com/@resvg/resvg-wasm@2.6.2/index_bg.wasm",
    "https://esm.sh/@resvg/resvg-wasm@2.6.2/index_bg.wasm",
  ];

  const errors: string[] = [];

  for (const url of urls) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);

    try {
      const res = await fetch(url, {
        signal: controller.signal,
        headers: {
          "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
          "Accept": "application/wasm,application/octet-stream,*/*;q=0.8",
        },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const bytes = await res.arrayBuffer();
      if (bytes.byteLength < 10000) {
        throw new Error(`WASM anormalement petit (${bytes.byteLength} octets)`);
      }

      console.log("✅ resvg WASM chargé", { url, bytes: bytes.byteLength });
      return bytes;
    } catch (e: any) {
      const detail = e?.name === "AbortError"
        ? "timeout 10s"
        : (e?.message || String(e));
      errors.push(`${url} => ${detail}`);
      console.warn("⚠️ Échec chargement resvg WASM, essai CDN suivant:", url, detail);
    } finally {
      clearTimeout(timeout);
    }
  }

  throw new Error(`Impossible de charger resvg WASM. ${errors.join(" | ")}`);
}

async function ensureResvgReady() {
  if (!resvgReady) {
    resvgReady = (async () => {
      const { initWasm } = await loadTelegramRenderModules();
      const wasmBytes = await fetchResvgWasm();
      await initWasm(wasmBytes);
      console.log("✅ resvg initialisé pour les images Telegram");
    })();
  }

  try {
    await resvgReady;
  } catch (e) {
    // IMPORTANT : ne jamais conserver une Promise rejetée en cache.
    // Sinon une seule panne réseau condamne toutes les images suivantes
    // au fallback texte tant que l'instance Edge reste chaude.
    resvgReady = null;
    throw e;
  }
}

async function buildTelegramCouponPng(match: any, pred: any): Promise<Uint8Array> {
  const { satori, html, Resvg } = await loadTelegramRenderModules();
  await ensureResvgReady();
  const fonts = await loadFontData();

  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;

  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const [homeLogoData, awayLogoData] = await Promise.all([
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 25);
  const awayName = fitText(match?.away_team ?? "Équipe B", 25);
  const leagueName = fitText(
    match?.league?.name ?? match?.league_name ?? match?.competition ?? "Football",
    38,
  );

  const couponText =
    rawType === "total_corners"
      ? `Total plus de ${threshold} corners`
      : rawType === "total_shots"
      ? `Total plus de ${threshold} tirs`
      : rawType === "total_fouls"
      ? `Total plus de ${threshold} fautes`
      : `Total plus de ${threshold}`;

  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));

  // Coupon LIVE inspiré de la présentation 1xBet fournie :
  // - un seul événement
  // - bandeau 1XBET + code promo XPVIP
  // - aucune cote affichée
  // - présentation compacte pour Telegram
  const markup = html(`
    <div style="width:1080px;height:860px;display:flex;flex-direction:column;background:#152D45;color:#F7FAFC;font-family:'Noto Sans';box-sizing:border-box;">

      <div style="width:1080px;height:118px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;background:#000000;padding:0 30px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;font-style:italic;font-weight:900;letter-spacing:-5px;line-height:1;">
          <div style="display:flex;font-size:70px;color:#FFFFFF;">1X</div>
          <div style="display:flex;font-size:70px;color:#1598DA;">BET</div>
        </div>

        <div style="height:72px;display:flex;flex-direction:row;align-items:center;background:#EAD03B;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;font-size:35px;font-weight:900;color:#050505;letter-spacing:-1px;">
            CODE PROMO XPVIP
          </div>
        </div>
      </div>

      <div style="width:1080px;height:150px;display:flex;flex-direction:column;background:#17314A;border-bottom:2px solid #2B4359;padding:26px 34px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
          <div style="display:flex;flex-direction:row;align-items:center;">
            <div style="width:34px;height:34px;display:flex;align-items:center;justify-content:center;margin-right:14px;color:#A8B7C6;font-size:25px;">▰</div>
            <div style="display:flex;font-size:30px;font-weight:700;color:#DCE5ED;">Événements : 1</div>
          </div>
          <div style="display:flex;font-size:29px;font-weight:500;color:#E7EEF4;">0 sur 1 terminé</div>
        </div>

        <div style="margin-top:24px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
          <div style="display:flex;font-size:28px;font-weight:500;color:#8EA2B4;">Statut:</div>
          <div style="display:flex;font-size:30px;font-weight:700;color:#4A8ED8;">Accepté</div>
        </div>
      </div>

      <div style="width:1044px;height:480px;margin:18px;display:flex;flex-direction:column;background:#142C43;border:2px solid #10263A;border-radius:28px;box-sizing:border-box;overflow:hidden;">
        <div style="height:94px;display:flex;flex-direction:row;align-items:center;padding:20px 24px 14px 24px;box-sizing:border-box;">
          <div style="width:46px;height:46px;border-radius:999px;border:3px solid #70869A;display:flex;align-items:center;justify-content:center;color:#8FA3B5;font-size:25px;margin-right:16px;">⚽</div>
          <div style="display:flex;flex-direction:column;">
            <div style="display:flex;font-size:23px;font-weight:500;color:#8FA3B5;">Football · ${escapeHtml(leagueName)}</div>
            <div style="display:flex;margin-top:5px;font-size:22px;font-weight:500;color:#8FA3B5;">LIVE · ${minute}'</div>
          </div>
        </div>

        <div style="height:190px;display:flex;flex-direction:row;align-items:center;justify-content:center;padding:0 26px;box-sizing:border-box;">
          <div style="width:370px;display:flex;flex-direction:row;align-items:center;justify-content:flex-end;">
            <div style="max-width:245px;display:flex;font-size:31px;font-weight:600;text-align:right;color:#F4F7FA;line-height:1.1;margin-right:18px;">${escapeHtml(homeName)}</div>
            ${
              homeLogoData
                ? `<img src="${homeLogoData}" width="78" height="78" style="object-fit:contain;" />`
                : `<div style="width:78px;height:78px;border-radius:999px;border:3px solid #4A8ED8;color:#4A8ED8;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;">${homeInitials}</div>`
            }
          </div>

          <div style="width:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;font-size:36px;font-weight:500;color:#F5F7FA;">VS</div>
            <div style="display:flex;margin-top:8px;font-size:25px;font-weight:700;color:#8FA3B5;">${escapeHtml(score)}</div>
          </div>

          <div style="width:370px;display:flex;flex-direction:row;align-items:center;justify-content:flex-start;">
            ${
              awayLogoData
                ? `<img src="${awayLogoData}" width="78" height="78" style="object-fit:contain;" />`
                : `<div style="width:78px;height:78px;border-radius:999px;border:3px solid #4A8ED8;color:#4A8ED8;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;">${awayInitials}</div>`
            }
            <div style="max-width:245px;display:flex;font-size:31px;font-weight:600;text-align:left;color:#F4F7FA;line-height:1.1;margin-left:18px;">${escapeHtml(awayName)}</div>
          </div>
        </div>

        <div style="height:2px;width:100%;display:flex;background:#29435A;"></div>

        <div style="height:108px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;flex-direction:column;">
            <div style="display:flex;font-size:23px;font-weight:500;color:#91A4B6;">Pronostic LIVE</div>
            <div style="display:flex;margin-top:8px;font-size:32px;font-weight:700;color:#F7FAFC;">${escapeHtml(couponText)}</div>
          </div>
        </div>

        <div style="height:2px;width:100%;display:flex;background:#29435A;"></div>

        <div style="height:84px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;font-size:26px;font-weight:500;color:#8FA3B5;">Statut:</div>
          <div style="display:flex;font-size:29px;font-weight:700;color:#4A8ED8;">Accepté</div>
        </div>
      </div>

      <div style="width:1080px;height:94px;display:flex;flex-direction:row;align-items:center;justify-content:center;background:#17314A;border-top:2px solid #2B4359;">
        <div style="display:flex;font-size:22px;font-weight:500;color:#8EA2B4;">18+ • Joue responsablement • Mr XPRONOS</div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 860,
    fonts: [
      { name: "Noto Sans", data: fonts.regular, weight: 400, style: "normal" },
      { name: "Noto Sans", data: fonts.bold, weight: 700, style: "normal" },
      { name: "Noto Sans", data: fonts.extraBold, weight: 900, style: "normal" },
    ],
    embedFont: true,
  });

  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      loadSystemFonts: false,
    },
  });

  return resvg.render().asPng();
}

function buildTelegramText(match: any, pred: any) {
  // Légende volontairement courte sous l'image, comme dans le canal Telegram.
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const label = predictionLabelForCaption(type);
  return `🔥 NOUVEAU COUPON LIVE

⚽️ Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}

function buildTelegramLiveFallbackText(match: any, pred: any) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );
  const label = predictionLabelForCaption(type);
  const typeLabel = formatLivePredictionType(type);

  const home = String(match?.home_team ?? match?.homeTeam ?? "Équipe A").trim() || "Équipe A";
  const away = String(match?.away_team ?? match?.awayTeam ?? "Équipe B").trim() || "Équipe B";
  const league = String(getLeagueName(match) || "Football").trim() || "Football";
  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const minuteLabel = minute > 0 ? `${minute}'` : "LIVE";
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;
  const confidence = confidenceFromPrediction(pred);
  const currentValue =
    pred?.projected_value ??
    pred?.current_value ??
    pred?.current ??
    pred?.signal_value ??
    pred?.value_at_signal ??
    0;
  const reason = String(pred?.message ?? pred?.reason ?? "").trim();

  return `🔥 NOUVEAU COUPON LIVE

🏆 Championnat : ${league}
⚽️ Match : ${home} vs ${away}
⏱ Minute : ${minuteLabel}
🥅 Score : ${score}

🎯 Pronostic : Total plus de ${threshold}${label ? ` ${label}` : ""}
📊 Type : ${typeLabel}
📈 Au signal : ${currentValue}
🛡 Fiabilité : ${confidence}%${reason ? `\n📝 Analyse : ${reason}` : ""}

18+ • Joue responsablement`;
}

type TelegramSendResult = {
  ok: boolean;
  sentChatIds: string[];
  failedChatIds: string[];
  error: string | null;
};

function telegramChatIds(): string[] {
  // On conserve volontairement les DEUX canaux. Set évite seulement les doublons
  // strictement identiques dans la configuration (même chaîne répétée).
  return [...new Set(
    [TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID_SECONDARY]
      .map((id) => String(id || "").trim())
      .filter(Boolean),
  )];
}

function sanitizeTelegramTargets(targetChatIds?: string[]): string[] {
  const allowed = telegramChatIds();
  if (!targetChatIds?.length) return allowed;

  const allowedSet = new Set(allowed);
  const requested = [...new Set(
    targetChatIds.map((id) => String(id || "").trim()).filter(Boolean),
  )];

  // En retry, on ne renvoie que vers les canaux qui avaient échoué.
  // Si la liste sauvegardée est devenue invalide, on revient aux deux canaux configurés.
  const filtered = requested.filter((id) => allowedSet.has(id));
  return filtered.length ? filtered : allowed;
}

async function sendTelegramPhoto(
  pngBytes: Uint8Array,
  caption: string,
  buttonUrl?: string,
  targetChatIds?: string[],
): Promise<TelegramSendResult> {
  const chatIds = sanitizeTelegramTargets(targetChatIds);

  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    const message = "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant";
    console.warn(`Telegram non configuré: ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: chatIds, error: message };
  }

  if (!chatIds.length) {
    const message = "aucun canal Telegram cible";
    console.warn(`Telegram non configuré: ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: [], error: message };
  }

  // Signature PNG : 89 50 4E 47 0D 0A 1A 0A
  const pngSignature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  const validPng = pngBytes.byteLength > 1000 &&
    pngSignature.every((value, index) => pngBytes[index] === value);

  if (!validPng) {
    const message = `PNG Telegram invalide (${pngBytes.byteLength} octets)`;
    console.error(`❌ ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: chatIds, error: message };
  }

  console.log("🖼️ Image Telegram prête", { bytes: pngBytes.byteLength, chatIds });

  const sentChatIds: string[] = [];
  const failedChatIds: string[] = [];
  const errors: string[] = [];

  for (const chatId of chatIds) {
    let sent = false;
    let lastError = "";

    // Deux tentatives IMAGE avant de passer au fallback texte.
    // Chaque tentative recrée FormData + Blob pour éviter tout problème
    // de réutilisation du corps multipart entre deux canaux.
    for (let attempt = 1; attempt <= 2; attempt++) {
      const form = new FormData();
      form.append("chat_id", chatId);
      if (caption && caption.trim()) form.append("caption", caption);

      if (buttonUrl) {
        form.append(
          "reply_markup",
          JSON.stringify({
            inline_keyboard: [
              [
                {
                  text: "Voir plus d’opportunités 🔥",
                  url: "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",
                },
              ],
              [
                {
                  text: "S’inscrire chez un bookmaker 🎯",
                  url: "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",
                },
              ],
            ],
          }),
        );
      }

      form.append(
        "photo",
        new Blob([pngBytes], { type: "image/png" }),
        `coupon-live-${Date.now()}-${attempt}.png`,
      );

      try {
        const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto`, {
          method: "POST",
          body: form,
        });

        if (res.ok) {
          sent = true;
          sentChatIds.push(chatId);
          console.log(`✅ Coupon LIVE envoyé en IMAGE vers ${chatId} (tentative ${attempt})`);
          break;
        }

        const body = await res.text().catch(() => "");
        lastError = `sendPhoto ${res.status}${body ? `: ${body}` : ""}`;
        console.error(`❌ Telegram sendPhoto failed [${chatId}] tentative ${attempt}:`, res.status, body);
      } catch (e: any) {
        lastError = e?.message || String(e);
        console.error(`❌ Telegram sendPhoto exception [${chatId}] tentative ${attempt}:`, e);
      }

      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 500));
    }

    if (!sent) {
      failedChatIds.push(chatId);
      errors.push(`${chatId} => ${lastError || "sendPhoto échoué après 2 tentatives"}`);
    }
  }

  return {
    ok: failedChatIds.length === 0 && sentChatIds.length === chatIds.length,
    sentChatIds,
    failedChatIds,
    error: errors.length ? errors.join(" | ") : null,
  };
}

async function sendTelegramMessage(
  text: string,
  buttonUrl?: string,
  targetChatIds?: string[],
): Promise<TelegramSendResult> {
  const chatIds = sanitizeTelegramTargets(targetChatIds);

  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    const message = "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant";
    return { ok: false, sentChatIds: [], failedChatIds: chatIds, error: message };
  }

  if (!chatIds.length) {
    return { ok: false, sentChatIds: [], failedChatIds: [], error: "aucun canal Telegram cible" };
  }

  const sentChatIds: string[] = [];
  const failedChatIds: string[] = [];
  const errors: string[] = [];

  for (const chatId of chatIds) {
    const form = new FormData();
    form.append("chat_id", chatId);
    form.append("text", text);

    if (buttonUrl) {
      form.append(
        "reply_markup",
        JSON.stringify({
          inline_keyboard: [
            [
              {
                text: "Voir plus d’opportunités 🔥",
                url: "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",
              },
            ],
            [
              {
                text: "S’inscrire chez un bookmaker 🎯",
                url: "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",
              },
            ],
          ],
        }),
      );
    }

    try {
      const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const body = await res.text().catch(() => "");
        const detail = `sendMessage ${res.status}${body ? `: ${body}` : ""}`;
        console.error(`❌ Telegram sendMessage failed [${chatId}]:`, res.status, body);
        failedChatIds.push(chatId);
        errors.push(`${chatId} => ${detail}`);
        continue;
      }

      sentChatIds.push(chatId);
      console.log(`✅ Message Telegram envoyé vers ${chatId}`);
    } catch (e: any) {
      const detail = e?.message || String(e);
      console.error(`❌ Telegram sendMessage exception [${chatId}]:`, e);
      failedChatIds.push(chatId);
      errors.push(`${chatId} => ${detail}`);
    }
  }

  return {
    ok: failedChatIds.length === 0 && sentChatIds.length === chatIds.length,
    sentChatIds,
    failedChatIds,
    error: errors.length ? errors.join(" | ") : null,
  };
}

async function sendTelegramLiveCoupon(
  match: any,
  pred: any,
  predictionId?: string | number | null,
  targetChatIds?: string[],
): Promise<TelegramSendResult> {
  const liveUrl = "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/";
  const shortCaption = buildTelegramText(match, pred);
  const detailedFallback = buildTelegramLiveFallbackText(match, pred);

  try {
    const pngBytes = await buildTelegramCouponPng(match, pred);
    console.log("✅ PNG NOUVEAU COUPON LIVE généré", { bytes: pngBytes.byteLength });
    const photoResult = await sendTelegramPhoto(pngBytes, shortCaption, liveUrl, targetChatIds);

    if (photoResult.ok) return photoResult;

    // Si l'image n'a échoué que sur un canal, on envoie le fallback texte
    // uniquement sur ce canal pour éviter un doublon sur les canaux déjà servis.
    const fallbackTargets = photoResult.failedChatIds.length
      ? photoResult.failedChatIds
      : (targetChatIds?.length ? targetChatIds : telegramChatIds());

    console.warn("⚠️ Envoi image LIVE incomplet, fallback texte détaillé:", photoResult.error);
    const fallbackResult = await sendTelegramMessage(detailedFallback, liveUrl, fallbackTargets);

    const sentChatIds = [...new Set([...photoResult.sentChatIds, ...fallbackResult.sentChatIds])];
    const failedChatIds = [...new Set(fallbackResult.failedChatIds)];

    return {
      ok: failedChatIds.length === 0,
      sentChatIds,
      failedChatIds,
      error: failedChatIds.length
        ? [photoResult.error, fallbackResult.error].filter(Boolean).join(" | ") || "Échec Telegram"
        : null,
    };
  } catch (e: any) {
    const generationError = e?.message || String(e);
    console.error("❌ Génération image LIVE impossible, fallback texte détaillé:", e);
    const fallbackResult = await sendTelegramMessage(detailedFallback, liveUrl, targetChatIds);

    return {
      ...fallbackResult,
      error: fallbackResult.ok
        ? null
        : [generationError, fallbackResult.error].filter(Boolean).join(" | ") || "Échec Telegram",
    };
  }
}


function validationStatusMeta(outcome: "success" | "failure") {
  if (outcome === "success") {
    return {
      emoji: "✅",
      header: "COUPON VALIDÉ",
      status: "RÉUSSI",
      color: "#22C55E",
      bg: "#0f2a18",
      border: "#22C55E",
    };
  }

  return {
    emoji: "❌",
    header: "COUPON PERDU",
    status: "ÉCHOUÉ",
    color: "#EF4444",
    bg: "#2a1111",
    border: "#EF4444",
  };
}

function buildValidationCouponText(pred: any) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const label = predictionLabelForCaption(type);
  return `Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}

function splitMatchName(matchName?: string | null) {
  const text = String(matchName ?? "").trim();
  if (!text) return { home: "Équipe A", away: "Équipe B" };

  const parts = text.split(/\s+vs\s+/i);
  if (parts.length >= 2) {
    return {
      home: parts[0].trim() || "Équipe A",
      away: parts.slice(1).join(" vs ").trim() || "Équipe B",
    };
  }

  return { home: text, away: "Équipe B" };
}

async function getTelegramMatchFromCache(pred: any, ev?: any | null) {
  const { data } = await supabase
    .from("matches_live")
    .select("*")
    .eq("id", String(pred.match_id))
    .limit(1)
    .maybeSingle();

  if (data) {
    return {
      id: data.id,
      home_team: data.home_team,
      away_team: data.away_team,
      home_score: data.home_score ?? 0,
      away_score: data.away_score ?? 0,
      current_minute: data.current_minute ?? 90,
      league_name: data.league_name ?? pred.league_name ?? null,
      league: { name: data.league_name ?? pred.league_name ?? "Football" },
      raw_data: data.raw_data || {},
      home_logo: data.raw_data?.home_logo ?? null,
      away_logo: data.raw_data?.away_logo ?? null,
      league_logo: data.raw_data?.league_logo ?? null,
    };
  }

  const names = splitMatchName(pred?.match_name);

  return {
    id: pred.match_id,
    home_team: names.home,
    away_team: names.away,
    home_score: ev?.home_score ?? ev?.home?.score ?? 0,
    away_score: ev?.away_score ?? ev?.away?.score ?? 0,
    current_minute: 90,
    league_name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football",
    league: { name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football" },
    raw_data: ev || {},
  };
}

async function buildTelegramValidationPng(
  match: any,
  pred: any,
  outcome: "success" | "failure",
  currentValue: number,
  validationType: "instant" | "final",
): Promise<Uint8Array> {
  const { satori, html, Resvg } = await loadTelegramRenderModules();
  await ensureResvgReady();
  const fonts = await loadFontData();

  const meta = validationStatusMeta(outcome);
  const minute = safeNumber(
    match?.current_minute ?? match?.minute,
    validationType === "final" ? 90 : 0,
  );
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;

  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );

  const [homeLogoData, awayLogoData] = await Promise.all([
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 25);
  const awayName = fitText(match?.away_team ?? "Équipe B", 25);
  const leagueName = fitText(
    match?.league?.name ?? match?.league_name ?? match?.competition ?? "Football",
    38,
  );

  const couponText = buildValidationCouponText(pred);
  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));

  const finishedLabel = validationType === "instant"
    ? `Validé en LIVE${minute > 0 ? ` · ${minute}'` : ""}`
    : "Match terminé";

  const statusText = outcome === "success" ? "Validé" : "Perdu";
  const statusColor = outcome === "success" ? "#4A8ED8" : "#E05252";
  const resultText = outcome === "success" ? "RÉUSSI" : "ÉCHOUÉ";
  const resultColor = outcome === "success" ? "#35C76F" : "#EF5350";

  // Même identité visuelle que le nouveau coupon LIVE :
  // 1XBET + CODE PROMO XPVIP + un seul événement + aucune cote.
  const markup = html(`
    <div style="width:1080px;height:860px;display:flex;flex-direction:column;background:#152D45;color:#F7FAFC;font-family:'Noto Sans';box-sizing:border-box;">

      <div style="width:1080px;height:118px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;background:#000000;padding:0 30px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;font-style:italic;font-weight:900;letter-spacing:-5px;line-height:1;">
          <div style="display:flex;font-size:70px;color:#FFFFFF;">1X</div>
          <div style="display:flex;font-size:70px;color:#1598DA;">BET</div>
        </div>

        <div style="height:72px;display:flex;flex-direction:row;align-items:center;background:#EAD03B;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;font-size:35px;font-weight:900;color:#050505;letter-spacing:-1px;">
            CODE PROMO XPVIP
          </div>
        </div>
      </div>

      <div style="width:1080px;height:150px;display:flex;flex-direction:column;background:#17314A;border-bottom:2px solid #2B4359;padding:26px 34px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
          <div style="display:flex;flex-direction:row;align-items:center;">
            <div style="width:34px;height:34px;display:flex;align-items:center;justify-content:center;margin-right:14px;color:#A8B7C6;font-size:25px;">▰</div>
            <div style="display:flex;font-size:30px;font-weight:700;color:#DCE5ED;">Événements : 1</div>
          </div>
          <div style="display:flex;font-size:29px;font-weight:500;color:#E7EEF4;">1 sur 1 terminé</div>
        </div>

        <div style="margin-top:24px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
          <div style="display:flex;font-size:28px;font-weight:500;color:#8EA2B4;">Statut:</div>
          <div style="display:flex;font-size:30px;font-weight:800;color:${statusColor};">${escapeHtml(statusText)}</div>
        </div>
      </div>

      <div style="width:1044px;height:480px;margin:18px;display:flex;flex-direction:column;background:#142C43;border:2px solid #10263A;border-radius:28px;box-sizing:border-box;overflow:hidden;">
        <div style="height:94px;display:flex;flex-direction:row;align-items:center;padding:20px 24px 14px 24px;box-sizing:border-box;">
          <div style="width:46px;height:46px;border-radius:999px;border:3px solid #70869A;display:flex;align-items:center;justify-content:center;color:#8FA3B5;font-size:25px;margin-right:16px;">⚽</div>
          <div style="display:flex;flex-direction:column;">
            <div style="display:flex;font-size:23px;font-weight:500;color:#8FA3B5;">Football · ${escapeHtml(leagueName)}</div>
            <div style="display:flex;margin-top:5px;font-size:22px;font-weight:500;color:#8FA3B5;">${escapeHtml(finishedLabel)}</div>
          </div>
        </div>

        <div style="height:190px;display:flex;flex-direction:row;align-items:center;justify-content:center;padding:0 26px;box-sizing:border-box;">
          <div style="width:370px;display:flex;flex-direction:row;align-items:center;justify-content:flex-end;">
            <div style="max-width:245px;display:flex;font-size:31px;font-weight:600;text-align:right;color:#F4F7FA;line-height:1.1;margin-right:18px;">${escapeHtml(homeName)}</div>
            ${
              homeLogoData
                ? `<img src="${homeLogoData}" width="78" height="78" style="object-fit:contain;" />`
                : `<div style="width:78px;height:78px;border-radius:999px;border:3px solid #4A8ED8;color:#4A8ED8;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;">${homeInitials}</div>`
            }
          </div>

          <div style="width:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;font-size:50px;font-weight:800;color:#F5F7FA;">${escapeHtml(score)}</div>
            <div style="display:flex;margin-top:8px;font-size:22px;font-weight:700;color:#8FA3B5;">Score final</div>
          </div>

          <div style="width:370px;display:flex;flex-direction:row;align-items:center;justify-content:flex-start;">
            ${
              awayLogoData
                ? `<img src="${awayLogoData}" width="78" height="78" style="object-fit:contain;" />`
                : `<div style="width:78px;height:78px;border-radius:999px;border:3px solid #4A8ED8;color:#4A8ED8;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;">${awayInitials}</div>`
            }
            <div style="max-width:245px;display:flex;font-size:31px;font-weight:600;text-align:left;color:#F4F7FA;line-height:1.1;margin-left:18px;">${escapeHtml(awayName)}</div>
          </div>
        </div>

        <div style="height:2px;width:100%;display:flex;background:#29435A;"></div>

        <div style="height:108px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;flex-direction:column;max-width:780px;">
            <div style="display:flex;font-size:23px;font-weight:500;color:#91A4B6;">Résultat du coupon</div>
            <div style="display:flex;margin-top:8px;font-size:32px;font-weight:700;color:#F7FAFC;">${escapeHtml(couponText)}</div>
          </div>
          <div style="display:flex;font-size:29px;font-weight:900;color:${resultColor};">${resultText}</div>
        </div>

        <div style="height:2px;width:100%;display:flex;background:#29435A;"></div>

        <div style="height:84px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:0 28px;box-sizing:border-box;">
          <div style="display:flex;font-size:25px;font-weight:500;color:#8FA3B5;">Final : ${escapeHtml(currentValue)} · Seuil : ${escapeHtml(threshold)}</div>
          <div style="display:flex;font-size:29px;font-weight:800;color:${statusColor};">${escapeHtml(statusText)}</div>
        </div>
      </div>

      <div style="width:1080px;height:94px;display:flex;flex-direction:row;align-items:center;justify-content:center;background:#17314A;border-top:2px solid #2B4359;">
        <div style="display:flex;font-size:22px;font-weight:500;color:#8EA2B4;">18+ • Joue responsablement • Mr XPRONOS</div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 860,
    fonts: [
      { name: "Noto Sans", data: fonts.regular, weight: 400, style: "normal" },
      { name: "Noto Sans", data: fonts.bold, weight: 700, style: "normal" },
      { name: "Noto Sans", data: fonts.extraBold, weight: 900, style: "normal" },
    ],
    embedFont: true,
  });

  const resvg = new Resvg(svg, {
    fitTo: { mode: "original" },
    font: {
      loadSystemFonts: false,
    },
  });

  return resvg.render().asPng();
}

function buildTelegramValidationText(pred: any, outcome: "success" | "failure", currentValue: number) {
  const meta = validationStatusMeta(outcome);
  const couponText = buildValidationCouponText(pred);

  return `${meta.emoji} ${outcome === "success" ? "COUPON VALIDÉ" : "COUPON PERDU"}

⚽️ ${couponText}
📊 Résultat : ${currentValue}`;
}

function buildTelegramValidationFallbackText(
  match: any,
  pred: any,
  outcome: "success" | "failure",
  currentValue: number,
  validationType: "instant" | "final",
) {
  const meta = validationStatusMeta(outcome);
  const couponText = buildValidationCouponText(pred);
  const home = String(match?.home_team ?? match?.homeTeam ?? "Équipe A").trim() || "Équipe A";
  const away = String(match?.away_team ?? match?.awayTeam ?? "Équipe B").trim() || "Équipe B";
  const league = String(getLeagueName(match) || "Football").trim() || "Football";
  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const score = `${safeNumber(match?.home_score, 0)}-${safeNumber(match?.away_score, 0)}`;
  const validationLabel = validationType === "instant"
    ? `Validé en LIVE${minute > 0 ? ` à la ${minute}'` : ""}`
    : "Validation à la fin du match";

  return `${meta.emoji} ${outcome === "success" ? "COUPON VALIDÉ" : "COUPON PERDU"}

🏆 Championnat : ${league}
⚽️ Match : ${home} vs ${away}
🥅 Score : ${score}
⏱ ${validationLabel}

🎯 Pronostic : ${couponText}
📊 Résultat : ${currentValue}
📌 Statut : ${meta.status}

18+ • Joue responsablement`;
}

async function sendTelegramValidationResult(
  match: any,
  pred: any,
  outcome: "success" | "failure",
  currentValue: number,
  validationType: "instant" | "final",
  predictionId?: string | number | null,
) {
  const liveUrl = `${SITE_URL.replace(/\/$/, "")}/live.html`;
  const shortCaption = buildTelegramValidationText(pred, outcome, currentValue);
  const detailedFallback = buildTelegramValidationFallbackText(
    match,
    pred,
    outcome,
    currentValue,
    validationType,
  );

  try {
    const pngBytes = await buildTelegramValidationPng(match, pred, outcome, currentValue, validationType);
    console.log("✅ PNG VALIDATION généré", { bytes: pngBytes.byteLength, outcome, validationType });
    const photoResult = await sendTelegramPhoto(pngBytes, shortCaption, liveUrl);

    if (photoResult.ok) return true;

    const fallbackTargets = photoResult.failedChatIds.length
      ? photoResult.failedChatIds
      : telegramChatIds();

    console.warn("⚠️ Envoi image VALIDATION incomplet, fallback texte détaillé:", photoResult.error);
    const fallbackResult = await sendTelegramMessage(detailedFallback, liveUrl, fallbackTargets);
    return fallbackResult.ok;
  } catch (e) {
    console.error("❌ Génération image VALIDATION impossible, fallback texte détaillé:", e);
    const fallbackResult = await sendTelegramMessage(detailedFallback, liveUrl);
    return fallbackResult.ok;
  }
}


// =======================================================
// ✅ CRON HEALTH (cron_runs)
// =======================================================
async function setCronRun(name: string, ok: boolean, meta: any = {}) {
  try {
    await supabase.from("cron_runs").upsert({
      name,
      last_run_at: new Date().toISOString(),
      last_ok: ok,
      meta: meta ?? {},
    });
  } catch (e) {
    console.error("cron_runs upsert failed:", e);
  }
}

// =======================================================
// LIVE ENGINE
// =======================================================
function computeMomentum(stats: any) {
  const h = stats?.home || {};
  const a = stats?.away || {};

  const hm =
    safeNumber(h.total_shots) * 2 +
    safeNumber(h.shots_on_target) * 3 +
    safeNumber(h.corner_kicks) * 1.5 +
    safeNumber(h.ball_possession) * 0.15;

  const am =
    safeNumber(a.total_shots) * 2 +
    safeNumber(a.shots_on_target) * 3 +
    safeNumber(a.corner_kicks) * 1.5 +
    safeNumber(a.ball_possession) * 0.15;

  const total = hm + am;
  const homeRatio = total > 0 ? hm / total : 0.5;
  const awayRatio = 1 - homeRatio;

  let dominant = "balanced";
  if (homeRatio >= 0.58) dominant = "home";
  else if (awayRatio >= 0.58) dominant = "away";

  return {
    total: Math.round(total),
    home_ratio: Math.round(homeRatio * 100),
    away_ratio: Math.round(awayRatio * 100),
    dominant_side: dominant,
  };
}

function getTotalStats(stats: any) {
  return {
    shots: safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots),
    shotsOnTarget:
      safeNumber(stats?.home?.shots_on_target) + safeNumber(stats?.away?.shots_on_target),
    corners: safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks),
    fouls: safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls),
    possessionHome: safeNumber(stats?.home?.ball_possession),
    possessionAway: safeNumber(stats?.away?.ball_possession),
  };
}

function getMatchFlow(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);

  const globalShotsRate = totals.shots / Math.max(minute, 1);
  const globalCornersRate = totals.corners / Math.max(minute, 1);
  const globalFoulsRate = totals.fouls / Math.max(minute, 1);

  const attackingPressure =
    totals.shotsOnTarget * 2 +
    totals.corners * 1.4 +
    Math.abs(totals.possessionHome - totals.possessionAway) * 0.08 +
    safeNumber(momentum?.total) * 0.12;

  let flow: "offensive" | "neutral" | "defensive" = "neutral";

  if (attackingPressure >= 18 || globalShotsRate >= 0.22 || globalCornersRate >= 0.09) {
    flow = "offensive";
  }

  if (
    minute >= 65 &&
    attackingPressure < 12 &&
    globalShotsRate < 0.18 &&
    globalCornersRate < 0.07
  ) {
    flow = "defensive";
  }

  return { flow, attackingPressure, globalShotsRate, globalCornersRate, globalFoulsRate };
}

function conservativeProjection(params: {
  current: number;
  minute: number;
  type: "shots" | "corners" | "fouls";
  flow: "offensive" | "neutral" | "defensive";
}) {
  const { current, minute, type, flow } = params;

  const elapsed = Math.max(1, minute);
  const remaining = Math.max(0, 90 - elapsed);
  const baseRate = current / elapsed;

  let multiplier = 0.72;
  if (flow === "offensive") multiplier = 0.82;
  if (flow === "neutral") multiplier = 0.7;
  if (flow === "defensive") multiplier = 0.52;

  if (minute >= 70) multiplier -= 0.08;
  if (minute >= 78) multiplier -= 0.1;

  multiplier = Math.max(0.35, multiplier);

  let projected = current + baseRate * remaining * multiplier;

  const maxExtra = type === "corners" ? 4 : type === "shots" ? 8 : 8;
  projected = Math.min(projected, current + maxExtra);

  return Number(projected.toFixed(1));
}

/**
 * ✅ Règle :
 * prediction seulement si seuil >= actuel + 2
 */
function getSafeThreshold(
  type: "shots" | "corners" | "fouls",
  current: number,
  projected: number,
  minGap = 2,
) {
  const thresholds =
    type === "corners"
      ? [7.5, 8.5, 9.5, 10.5, 11.5]
      : type === "shots"
        ? [17.5, 19.5, 21.5, 23.5, 25.5, 27.5, 29.5]
        : [19.5, 21.5, 23.5, 24.5, 25.5, 27.5];

  for (const t of thresholds) {
    const gapOk = (t - current) >= minGap;
    if (current < t && projected >= t + 0.5 && gapOk) return t;
  }
  return null;
}

function computeHeatLevel(match: any) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const totals = getTotalStats(stats);

  let score = 0;
  score += totals.shots * 1.2;
  score += totals.shotsOnTarget * 2;
  score += totals.corners * 1.2;
  score += totals.fouls * 0.35;
  score += minute >= 55 ? 6 : 0;
  score += minute >= 70 ? 5 : 0;

  if (score >= 38) return "explosive";
  if (score >= 26) return "hot";
  if (score >= 14) return "warming";
  return "calm";
}

function predictTotalCorners(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.corners;

  if (minute < 18 || minute > 82) return null;
  if (current < 3) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "corners",
    flow: flowData.flow,
  });

  const threshold = getSafeThreshold("corners", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.58;
  let reliability = 52;
  const reasons: string[] = [];

  if (current >= 4) { probability += 0.06; reliability += 6; reasons.push(`${current} corners déjà obtenus`); }
  if (totals.shots >= 10) { probability += 0.06; reliability += 5; reasons.push(`${totals.shots} tirs cumulés`); }
  if (totals.shotsOnTarget >= 4) { probability += 0.04; reliability += 4; reasons.push(`${totals.shotsOnTarget} tirs cadrés`); }
  if (flowData.flow === "offensive") { probability += 0.07; reliability += 7; reasons.push(`Match offensif`); }
  if (flowData.flow === "defensive") { probability -= 0.08; reliability -= 8; reasons.push(`Rythme défensif`); }
  if (minute >= 25 && minute <= 70) { probability += 0.05; reliability += 6; reasons.push(`Fenêtre (${minute}')`); }

  probability = Math.min(0.90, Math.max(0.50, probability));
  reliability = Math.min(92, Math.max(40, reliability));

  if (probability < 0.76 || reliability < 63) return null;

  return {
    type: "total_corners",
    title: `Over ${threshold} corners`,
    badge: "Corners",
    color: "yellow",
    probability,
    message: `${current} corners actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function predictTotalShots(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.shots;

  if (minute < 15 || minute > 83) return null;
  if (current < 6) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({ current, minute, type: "shots", flow: flowData.flow });

  const threshold = getSafeThreshold("shots", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.60;
  let reliability = 55;
  const reasons: string[] = [];

  if (current >= 8) { probability += 0.06; reliability += 6; reasons.push(`${current} tirs déjà enregistrés`); }
  if (totals.shotsOnTarget >= 3) { probability += 0.06; reliability += 5; reasons.push(`${totals.shotsOnTarget} tirs cadrés`); }
  if (flowData.flow === "offensive") { probability += 0.08; reliability += 7; reasons.push(`Match offensif`); }
  if (flowData.flow === "defensive") { probability -= 0.10; reliability -= 8; reasons.push(`Rythme baisse`); }
  if (minute >= 20 && minute <= 72) { probability += 0.05; reliability += 5; reasons.push(`Minute (${minute}')`); }

  probability = Math.min(0.91, Math.max(0.50, probability));
  reliability = Math.min(93, Math.max(40, reliability));

  if (probability < 0.77 || reliability < 64) return null;

  return {
    type: "total_shots",
    title: `Over ${threshold} tirs`,
    badge: "Tirs",
    color: "green",
    probability,
    message: `${current} tirs actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function predictTotalFouls(stats: any, minute: number, momentum: any) {
  const totals = getTotalStats(stats);
  const current = totals.fouls;

  if (minute < 18 || minute > 84) return null;
  if (current < 6) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "fouls",
    flow: flowData.flow === "offensive" ? "neutral" : flowData.flow,
  });

  const threshold = getSafeThreshold("fouls", current, projectedFinal, 2);
  if (!threshold) return null;

  let probability = 0.57;
  let reliability = 54;
  const reasons: string[] = [];

  if (current >= 8) { probability += 0.05; reliability += 6; reasons.push(`${current} fautes déjà sifflées`); }
  if (minute >= 25 && minute <= 75) { probability += 0.05; reliability += 5; reasons.push(`Période exploitable`); }
  if (flowData.flow === "defensive") { probability += 0.03; reliability += 3; reasons.push(`Match fermé`); }
  if (flowData.flow === "offensive") { probability -= 0.03; reliability -= 2; }

  probability = Math.min(0.88, Math.max(0.50, probability));  reliability = Math.min(90, Math.max(40, reliability));

  if (probability < 0.75 || reliability < 62) return null;

  return {
    type: "total_fouls",
    title: `Over ${threshold} fautes`,
    badge: "Fautes",
    color: "orange",
    probability,
    message: `${current} fautes actuellement`,
    threshold,
    current,
    signal_value: current,
    reliability,
    reasons,
  };
}

function computeAiScore(match: any, predictions: any[]) {
  const best = predictions?.[0];
  if (!best) return 0;

  const momentum = computeMomentum(match?.live_stats || {});
  let score = 0;
  score += Math.round((best.probability || 0) * 50);
  score += Math.round((best.reliability || 0) * 0.35);
  score += Math.round((momentum.total || 0) * 0.2);

  return Math.min(99, score);
}

function computeValueScore(match: any, predictions: any[]) {
  const best = predictions?.[0];
  if (!best) return 0;

  const minute = safeNumber(match?.current_minute, 0);
  let score = 0;
  score += Math.round((best.probability || 0) * 40);
  score += Math.round((best.reliability || 0) * 0.25);
  score += minute >= 25 ? 10 : 0;
  score += minute >= 45 ? 10 : 0;
  score += minute >= 60 ? 8 : 0;

  return Math.min(99, score);
}


// =======================================================
// ESPN SCRAPING SOURCE — Normalisation vers le format du live original
// =======================================================
let espnMemCache: { at: number; date: string; data: any } | null = null;
const ESPN_CACHE_TTL_MS = 15_000;

async function fetchEspnScoreboard(dateYYYYMMDD: string, force = false) {
  const now = Date.now();

  if (
    !force &&
    espnMemCache &&
    espnMemCache.date === dateYYYYMMDD &&
    now - espnMemCache.at < ESPN_CACHE_TTL_MS
  ) {
    return espnMemCache.data;
  }

  const url = new URL(ESPN_SCOREBOARD_URL);
  url.searchParams.set("dates", dateYYYYMMDD);
  url.searchParams.set("limit", "500");

  const res = await fetch(url.toString(), {
    headers: {
      "User-Agent": "Mozilla/5.0 MrXPRONOS-ESPN-Merge/1.0",
      "Accept": "application/json,text/plain,*/*",
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`ESPN HTTP ${res.status}: ${body || res.statusText}`);
  }

  const data = await res.json();
  espnMemCache = { at: now, date: dateYYYYMMDD, data };
  return data;
}

function extractEspnMinute(status: any): number {
  const displayClock = status?.displayClock || "";

  if (displayClock) {
    const found = String(displayClock).match(/(\d+)/);
    if (found) return safeNumber(found[1], 0);
  }

  const clock = status?.clock;
  if (clock) return Math.floor(safeNumber(clock, 0) / 60);

  return 0;
}

function getEspnStat(competitor: any, statName: string, fallback = 0): number {
  const stats = competitor?.statistics || [];

  for (const s of stats) {
    if (s?.name === statName) {
      return safeNumber(s?.displayValue ?? s?.value, fallback);
    }
  }

  return fallback;
}

function countEspnCards(details: any[], teamId: string | number | undefined) {
  let yellow = 0;
  let red = 0;

  for (const d of details || []) {
    const tid = String(d?.team?.id || "");
    if (!teamId || tid !== String(teamId)) continue;

    if (d?.yellowCard === true) yellow += 1;
    if (d?.redCard === true) red += 1;
  }

  return { yellow, red };
}

function normalizeEspnEventToOriginalMatch(event: any) {
  const competition = event?.competitions?.[0];
  if (!competition) return null;

  const status = competition?.status || {};
  const statusType = status?.type || {};
  const state = statusType?.state || "";

  const isLive = state === "in";
  const isFinished = Boolean(statusType?.completed);

  const competitors = competition?.competitors || [];
  const home = competitors.find((c: any) => c?.homeAway === "home");
  const away = competitors.find((c: any) => c?.homeAway === "away");

  if (!home || !away) return null;

  const homeTeam = home?.team || {};
  const awayTeam = away?.team || {};
  const leagueObj = event?.league || {};
  const seasonObj = event?.season || {};
  const details = competition?.details || [];

  const leagueName =
    leagueObj?.name ||
    leagueObj?.abbreviation ||
    seasonObj?.slug ||
    "Football";

  const leagueId = String(leagueObj?.id || leagueObj?.abbreviation || leagueName);
  const minute = extractEspnMinute(status);

  const homeTeamId = String(homeTeam?.id || "");
  const awayTeamId = String(awayTeam?.id || "");

  const homeCorners = getEspnStat(home, "wonCorners");
  const awayCorners = getEspnStat(away, "wonCorners");
  const homeFouls = getEspnStat(home, "foulsCommitted");
  const awayFouls = getEspnStat(away, "foulsCommitted");

  const homeCards = countEspnCards(details, homeTeamId);
  const awayCards = countEspnCards(details, awayTeamId);

  const liveStats = ensureLiveStatsShape({
    home: {
      corner_kicks: homeCorners,
      fouls: homeFouls,
      yellow_cards: homeCards.yellow,
      red_cards: homeCards.red,
    },
    away: {
      corner_kicks: awayCorners,
      fouls: awayFouls,
      yellow_cards: awayCards.yellow,
      red_cards: awayCards.red,
    },
    totals: {
      corners: homeCorners + awayCorners,
      fouls: homeFouls + awayFouls,
      yellow_cards: homeCards.yellow + awayCards.yellow,
      red_cards: homeCards.red + awayCards.red,
    },
  });

  const homeLogo = homeTeam?.logo || homeTeam?.logos?.[0]?.href || null;
  const awayLogo = awayTeam?.logo || awayTeam?.logos?.[0]?.href || null;
  const leagueLogo = leagueObj?.logos?.[0]?.href || leagueObj?.logo || null;

  const eventDate = event?.date ? new Date(event.date).toISOString() : nowIso();
  const eventId = String(event?.id || crypto.randomUUID());

  return {
    id: `espn:${eventId}`,
    source_match_id: eventId,
    source_name: "espn",
    home_team: homeTeam?.displayName || homeTeam?.name || "Home",
    away_team: awayTeam?.displayName || awayTeam?.name || "Away",
    home_score: safeNumber(home?.score, 0),
    away_score: safeNumber(away?.score, 0),
    current_minute: minute,
    league_name: leagueName,
    league: { name: leagueName, id: leagueId, api_id: leagueId },
    status: statusType?.name || statusType?.detail || state || "",
    is_live: isLive,
    is_finished: isFinished,
    event_date: eventDate,
    home_team_id: homeTeamId || null,
    away_team_id: awayTeamId || null,
    league_id: leagueId || null,
    home_logo: homeLogo,
    away_logo: awayLogo,
    league_logo: leagueLogo,
    live_stats: liveStats,
    raw_data: {
      source: "espn",
      event_id: eventId,
      state,
      display_clock: status?.displayClock || "",
      status_detail: statusType?.detail || statusType?.description || "",
      home_team_obj: { api_id: homeTeamId, id: homeTeamId, logo: homeLogo },
      away_team_obj: { api_id: awayTeamId, id: awayTeamId, logo: awayLogo },
      league: { name: leagueName, api_id: leagueId, id: leagueId, logo: leagueLogo },
      live_stats: liveStats,
    },
  };
}

async function fetchEspnLiveMatchesForMerge() {
  if (!ENABLE_ESPN_MERGE) {
    return { matches: [], error: null };
  }

  try {
    // Réutilise le cache mémoire 15 s si le worker reste chaud entre deux lots.
    const scoreboard = await fetchEspnScoreboard(todayYYYYMMDD(), false);
    const events = scoreboard?.events || [];

    const matches = events
      .map(normalizeEspnEventToOriginalMatch)
      .filter(Boolean)
      .filter((m: any) => m.is_live && !m.is_finished);

    return { matches, error: null };
  } catch (e: any) {
    console.error("ESPN merge source failed:", e);
    return { matches: [], error: e?.message || String(e) };
  }
}

function mergeOneOriginalWithEspn(original: any, espn: any) {
  const originalStats = getMatchLiveStats(original);
  const espnStats = getMatchLiveStats(espn);
  const mergedStats = mergeLiveStats(originalStats, espnStats);

  const originalMinute = safeNumber(original?.current_minute ?? original?.minute, 0);
  const espnMinute = safeNumber(espn?.current_minute ?? espn?.minute, 0);

  const merged: any = {
    ...original,
    current_minute: Math.max(originalMinute, espnMinute),
    live_stats: mergedStats,
    home_logo: original?.home_logo || espn?.home_logo || original?.raw_data?.home_logo || espn?.raw_data?.home_logo || null,
    away_logo: original?.away_logo || espn?.away_logo || original?.raw_data?.away_logo || espn?.raw_data?.away_logo || null,
    league_logo: original?.league_logo || espn?.league_logo || original?.raw_data?.league_logo || espn?.raw_data?.league_logo || null,
  };

  if (original?.home_score == null) merged.home_score = safeNumber(espn?.home_score, 0);
  if (original?.away_score == null) merged.away_score = safeNumber(espn?.away_score, 0);

  merged.raw_data = {
    ...(original?.raw_data || {}),
    source: "merged",
    merge_meta: {
      canonical_match_id: buildCanonicalMatchId(original),
      sources: ["api_original", "espn"],
      confidence_score: Math.round(sameMatchScore(original, espn) * 100),
      espn_match_id: espn?.source_match_id || espn?.id || null,
      primary_source: "api_original",
      merged_at: nowIso(),
    },
    live_stats: mergedStats,
    home_logo: merged.home_logo,
    away_logo: merged.away_logo,
    league_logo: merged.league_logo,
    home_team_obj: {
      ...(original?.raw_data?.home_team_obj || {}),
      logo: merged.home_logo,
      espn_id: espn?.home_team_id || espn?.raw_data?.home_team_obj?.id || null,
    },
    away_team_obj: {
      ...(original?.raw_data?.away_team_obj || {}),
      logo: merged.away_logo,
      espn_id: espn?.away_team_id || espn?.raw_data?.away_team_obj?.id || null,
    },
    league: {
      ...(original?.raw_data?.league || original?.league || {}),
      name: getLeagueName(original),
      logo: merged.league_logo,
      espn_id: espn?.league_id || espn?.raw_data?.league?.id || null,
    },
  };

  return merged;
}

function prepareEspnOnlyMatch(espn: any) {
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(espn));

  return {
    ...espn,
    live_stats: liveStats,
    raw_data: {
      ...(espn?.raw_data || {}),
      source: "merged",
      merge_meta: {
        canonical_match_id: buildCanonicalMatchId(espn),
        sources: ["espn"],
        confidence_score: 80,
        espn_match_id: espn?.source_match_id || espn?.id || null,
        primary_source: "espn",
        merged_at: nowIso(),
      },
      live_stats: liveStats,
      home_logo: espn?.home_logo || espn?.raw_data?.home_logo || null,
      away_logo: espn?.away_logo || espn?.raw_data?.away_logo || null,
      league_logo: espn?.league_logo || espn?.raw_data?.league_logo || null,
    },
  };
}

function mergeOriginalAndEspnMatches(originalMatches: any[], espnMatches: any[]) {
  const sourceRows: any[] = [];
  const entries: Array<{
    key: string;
    match: any;
    source: "api_original" | "espn" | "merged";
  }> = [];

  for (const original of originalMatches || []) {
    const key = buildCanonicalMatchId(original);
    const match = {
      ...original,
      raw_data: {
        ...(original?.raw_data || {}),
        merge_meta: {
          canonical_match_id: key,
          sources: ["api_original"],
          confidence_score: 70,
          primary_source: "api_original",
          merged_at: nowIso(),
        },
      },
    };

    entries.push({ key, match, source: "api_original" });
    sourceRows.push(sourceRowFromMatch(original, "api_original"));
  }

  let duplicatesMerged = 0;
  let espnOnly = 0;

  for (const espn of espnMatches || []) {
    sourceRows.push(sourceRowFromMatch(espn, "espn"));

    let bestIndex = -1;
    let bestScore = 0;

    for (let i = 0; i < entries.length; i++) {
      const score = sameMatchScore(entries[i].match, espn);

      if (score > bestScore) {
        bestScore = score;
        bestIndex = i;
      }
    }

    if (bestIndex >= 0 && bestScore >= 0.72) {
      entries[bestIndex].match = mergeOneOriginalWithEspn(entries[bestIndex].match, espn);
      entries[bestIndex].source = "merged";
      duplicatesMerged++;
    } else {
      const key = buildCanonicalMatchId(espn);
      entries.push({ key, match: prepareEspnOnlyMatch(espn), source: "espn" });
      espnOnly++;
    }
  }

  const mergedMatches = entries.map((e) => e.match);

  return {
    mergedMatches,
    sourceRows,
    meta: {
      original_source_matches: originalMatches.length,
      espn_source_matches: espnMatches.length,
      merged_matches: mergedMatches.length,
      duplicates_merged: duplicatesMerged,
      espn_only_matches: espnOnly,
      espn_enabled: ENABLE_ESPN_MERGE,
    },
  };
}

function normalizeMatch(match: any, updatedAt?: string) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const momentum = computeMomentum(stats);

  const allPredictions = [
    predictTotalShots(stats, minute, momentum),
    predictTotalCorners(stats, minute, momentum),
    predictTotalFouls(stats, minute, momentum),
  ].filter(Boolean);

  allPredictions.sort((a: any, b: any) => {
    if ((b.probability || 0) !== (a.probability || 0)) return (b.probability || 0) - (a.probability || 0);
    return (b.reliability || 0) - (a.reliability || 0);
  });

  const predictions = allPredictions.filter((p: any) => (p.probability || 0) >= 0.80);

  return {
    ...match,
    momentum_index: momentum,
    pressure_index: momentum,
    predictions,
    all_predictions: allPredictions,
    ai_score: computeAiScore(match, allPredictions),
    value_score: computeValueScore(match, allPredictions),
    reliability_score: allPredictions?.[0]?.reliability || 0,
    data_quality_score: 90,
    heat_level: computeHeatLevel(match),
    freshness_seconds: computeFreshness(updatedAt || new Date().toISOString()),
  };
}

// =======================================================
// DB - matches cache
// =======================================================
async function cacheLiveMatches(rawMatches: any[], updatedAt = nowIso()) {
  if (!rawMatches?.length) return;

  // Une seule écriture DB pour tout le lot au lieu d'un UPSERT par match.
  // Cela réduit fortement les allers-retours et la sérialisation répétée.
  const rows = rawMatches.map((m: any) => {
    const normalized = normalizeMatch(m, updatedAt);

    return {
      id: String(m.id),
      home_team: m.home_team ?? null,
      away_team: m.away_team ?? null,
      home_score: m.home_score ?? 0,
      away_score: m.away_score ?? 0,
      current_minute: m.current_minute ?? 0,
      league_name: m.league?.name ?? m.league_name ?? null,
      status: m.status ?? null,
      raw_data: normalized,
      momentum: normalized.momentum_index ?? null,
      updated_at: updatedAt,
    };
  });

  const { error } = await supabase.from("matches_live").upsert(rows);
  if (error) throw error;
}

// =======================================================
// DB - predictions helpers (idempotence)
// =======================================================
async function findExistingPredictionId(params: {
  match_id: string;
  prediction_type: string;
  threshold: number;
  validated?: boolean | null; // null => ignore filter
}) {
  let q = supabase
    .from("live_predictions")
    .select("id")
    .eq("match_id", params.match_id)
    .eq("prediction_type", params.prediction_type)
    .eq("threshold", params.threshold)
    .order("created_at", { ascending: false })
    .limit(1);

  if (params.validated === true || params.validated === false) {
    q = q.eq("validated", params.validated);
  }

  const { data, error } = await q.maybeSingle();
  if (error) throw error;
  return data?.id ?? null;
}

// =======================================================
// ✅ TELEGRAM DELIVERY TRACKING + RETRY
// =======================================================
// Verrou distribué anti-doublon Telegram.
// On utilise telegram_sent=true comme état provisoire de CLAIM avant l'envoi.
// Une seule invocation concurrente peut faire passer false/null -> true.
// En cas d'échec d'envoi, markTelegramDelivery remet telegram_sent=false.
async function claimTelegramDelivery(predictionId: string | number) {
  const id = String(predictionId);
  const claimedAt = nowIso();

  const { data, error } = await supabase
    .from("live_predictions")
    .update({
      telegram_sent: true,
      telegram_last_attempt_at: claimedAt,
      telegram_last_error: "__SENDING__",
    })
    .eq("id", id)
    .or("telegram_sent.is.null,telegram_sent.eq.false")
    .select("id")
    .maybeSingle();

  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("⚠️ Verrou Telegram indisponible: colonnes retry absentes.");
      return false;
    }
    console.error("⚠️ Claim Telegram impossible:", id, error);
    return false;
  }

  return Boolean(data?.id);
}

// Si une invocation meurt après le CLAIM mais avant l'envoi/retour DB,
// on libère les claims restés bloqués depuis plus de 5 minutes.
async function releaseStaleTelegramClaims() {
  const staleBefore = new Date(Date.now() - 5 * 60 * 1000).toISOString();

  const { error } = await supabase
    .from("live_predictions")
    .update({
      telegram_sent: false,
      telegram_last_error: "Claim Telegram expiré, nouvel essai autorisé",
    })
    .eq("telegram_sent", true)
    .eq("telegram_last_error", "__SENDING__")
    .lt("telegram_last_attempt_at", staleBefore);

  if (error && !isUndefinedColumnError(error)) {
    console.warn("⚠️ Nettoyage claims Telegram impossible:", error);
  }
}

async function markTelegramDelivery(
  predictionId: string | number,
  delivery: TelegramSendResult,
) {
  const id = String(predictionId);

  const { data: row, error: readError } = await supabase
    .from("live_predictions")
    .select("telegram_attempts")
    .eq("id", id)
    .maybeSingle();

  if (readError) {
    if (isUndefinedColumnError(readError)) {
      console.warn("⚠️ Colonnes Telegram retry absentes. Exécute telegram_retry_migration.sql.");
      return false;
    }
    console.error("⚠️ Lecture telegram_attempts impossible:", readError);
    return false;
  }

  const attemptAt = nowIso();
  const values: any = {
    telegram_sent: delivery.ok,
    telegram_attempts: safeNumber(row?.telegram_attempts, 0) + 1,
    telegram_last_attempt_at: attemptAt,
    telegram_last_error: delivery.ok ? null : (delivery.error || "Échec de l'envoi Telegram"),
    telegram_pending_chat_ids: delivery.ok ? [] : delivery.failedChatIds,
  };

  if (delivery.ok) values.telegram_sent_at = attemptAt;

  const { error } = await supabase
    .from("live_predictions")
    .update(values)
    .eq("id", id);

  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("⚠️ Colonnes Telegram retry absentes. Exécute telegram_retry_migration.sql.");
      return false;
    }
    console.error("⚠️ Mise à jour du statut Telegram impossible:", error);
    return false;
  }

  return true;
}

async function retryPendingTelegramLiveCoupons(
  liveMatchesNormalized: any[],
  maxToProcess = 1,
) {
  const emptyResult = {
    telegram_retry_enabled: true,
    telegram_retry_processed: 0,
    telegram_retry_sent: 0,
    telegram_retry_failed: 0,
    telegram_retry_skipped: 0,
  };

  if (maxToProcess <= 0) return emptyResult;

  await releaseStaleTelegramClaims();

  // On prend une petite fenêtre puis on filtre en JS.
  // Cela tolère telegram_sent / telegram_attempts à NULL sur d'anciennes lignes.
  const { data: pending, error } = await supabase
    .from("live_predictions")
    .select(
      "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, confidence, validated, telegram_sent, telegram_attempts, telegram_pending_chat_ids, created_at",
    )
    .eq("validated", false)
    .order("created_at", { ascending: true })
    .limit(50);

  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("⚠️ Retry Telegram désactivé: migration SQL non appliquée.");
      return { ...emptyResult, telegram_retry_enabled: false };
    }
    console.error("⚠️ Lecture des envois Telegram à retenter impossible:", error);
    return { ...emptyResult, telegram_retry_failed: 1 };
  }

  const eligible = (pending || []).filter(
    (row: any) =>
      row?.telegram_sent !== true &&
      safeNumber(row?.telegram_attempts, 0) < 5,
  );

  if (!eligible.length) return emptyResult;

  const liveMap = new Map<string, any>();
  for (const match of liveMatchesNormalized || []) {
    liveMap.set(String(match.id), match);
  }

  let processed = 0;

  for (const row of eligible) {
    if (processed >= maxToProcess) break;

    let currentMatch = liveMap.get(String(row.match_id));

    // Le coupon peut appartenir à un autre lot déjà mis en cache.
    // On le reconstruit alors depuis matches_live plutôt que de le perdre.
    if (!currentMatch) {
      currentMatch = await getTelegramMatchFromCache(row, null);
    }

    if (!currentMatch) {
      emptyResult.telegram_retry_skipped++;
      continue;
    }

    const retryMatch = {
      ...currentMatch,
      home_team: row.home_team ?? currentMatch.home_team,
      away_team: row.away_team ?? currentMatch.away_team,
      home_score: row.home_score ?? currentMatch.home_score ?? 0,
      away_score: row.away_score ?? currentMatch.away_score ?? 0,
      current_minute: row.minute ?? currentMatch.current_minute ?? 0,
      league_name: row.league_name ?? currentMatch.league_name ?? currentMatch?.league?.name,
      league: {
        ...(currentMatch?.league || {}),
        name: row.league_name ?? currentMatch?.league?.name ?? "Football",
      },
    };

    const retryPred = {
      ...row,
      type: row.prediction_type,
      prediction_type: row.prediction_type,
      pronostic: row.threshold,
      signal_value: row.projected_value ?? row.current_value ?? 0,
      current: row.projected_value ?? row.current_value ?? 0,
    };

    // CLAIM atomique avant tout appel Telegram. Si une autre invocation a déjà
    // pris ce prediction_id, on ne l'envoie surtout pas une seconde fois.
    const claimed = await claimTelegramDelivery(row.id);
    if (!claimed) {
      emptyResult.telegram_retry_skipped++;
      continue;
    }

    processed++;
    emptyResult.telegram_retry_processed++;

    try {
      const pendingChatIds = Array.isArray(row.telegram_pending_chat_ids)
        ? row.telegram_pending_chat_ids
          .map((id: unknown) => String(id || "").trim())
          .filter(Boolean)
        : [];

      const delivery = await sendTelegramLiveCoupon(
        retryMatch,
        retryPred,
        row.id,
        pendingChatIds.length ? pendingChatIds : undefined,
      );
      await markTelegramDelivery(row.id, delivery);

      if (delivery.ok) emptyResult.telegram_retry_sent++;
      else emptyResult.telegram_retry_failed++;
    } catch (e: any) {
      emptyResult.telegram_retry_failed++;
      const failedTargets =
        Array.isArray(row.telegram_pending_chat_ids) && row.telegram_pending_chat_ids.length
          ? row.telegram_pending_chat_ids.map(String)
          : telegramChatIds();

      await markTelegramDelivery(row.id, {
        ok: false,
        sentChatIds: [],
        failedChatIds: failedTargets,
        error: e?.message || String(e),
      });

      console.error("❌ Retry Telegram LIVE impossible:", row.id, e);
    }
  }

  return emptyResult;
}


/**
 * ✅ savePrediction :
 * - INSERT only
 * - idempotent (catch duplicate key)
 */
async function savePrediction(
  match: any,
  pred: any,
  options: { sendTelegram?: boolean } = {},
) {
  const matchId = String(match.id);
  const thresholdNum = Number(safeNumber(pred.threshold, 0).toFixed(1));
  const signalValue = safeNumber(pred.signal_value ?? pred.current, 0);

  const payload: any = {
    match_id: matchId,
    match_name: `${match.home_team} vs ${match.away_team}`,
    home_team: match.home_team ?? null,
    away_team: match.away_team ?? null,
    home_score: match.home_score ?? 0,
    away_score: match.away_score ?? 0,

    minute: match.current_minute ?? 0,
    league_name: match.league?.name ?? null,

    prediction_type: pred.type,
    probability: pred.probability,
    message: pred.message,

    threshold: thresholdNum,
    projected_value: signalValue,
    current_value: signalValue,

    confidence: pred.probability >= 0.84 ? "high" : "medium",
    validated: false,
    outcome: null,

    // Etat Telegram explicite : évite les NULL ambigus et facilite le CLAIM atomique.
    telegram_sent: false,
    telegram_attempts: 0,
    telegram_last_attempt_at: null,
    telegram_last_error: null,
    telegram_pending_chat_ids: telegramChatIds(),

    updated_at: new Date().toISOString(),
  };

  // pré-check : d'abord validated=false (si index partiel), sinon fallback sans filtre
  const existingRunning = await findExistingPredictionId({
    match_id: matchId,
    prediction_type: pred.type,
    threshold: thresholdNum,
    validated: false,
  });
  if (existingRunning) return { created: false, id: existingRunning };

  // INSERT
  const { data, error } = await supabase
    .from("live_predictions")
    .insert({ ...payload, created_at: new Date().toISOString() })
    .select("id")
    .single();

  if (error) {
    if (isDuplicateKeyError(error)) {
      // race condition: quelqu’un a insert entre temps
      const id2 =
        (await findExistingPredictionId({
          match_id: matchId,
          prediction_type: pred.type,
          threshold: thresholdNum,
          validated: false,
        })) ??
        (await findExistingPredictionId({
          match_id: matchId,
          prediction_type: pred.type,
          threshold: thresholdNum,
          validated: null,
        }));
      return { created: false, id: id2 };
    }
    throw error;
  }

  await insertNotification({
    user_id: "all",
    type: "live_prediction",
    title: "Nouvelle opportunité LIVE",
    message:
`${payload.match_name}
Pronostic: ${pred.title}
Minute du signal: ${payload.minute}'
Pronostic (seuil): ${payload.threshold}
Au signal: ${signalValue}`,
    priority: pred.probability >= 0.86 ? "urgent" : "normal",
    read: false,
    related_prediction_id: data.id,
  });

  // En mode refresh par lots, l'image Telegram est mise en file et traitée
  // après les calculs. Cela empêche plusieurs rendus Satori/Resvg dans la même
  // invocation, principale cause possible de pics CPU.
  let telegramAttempted = false;

  if (options.sendTelegram !== false) {
    const claimed = await claimTelegramDelivery(data.id);
    if (claimed) {
      telegramAttempted = true;
      const telegramDelivery = await sendTelegramLiveCoupon(match, pred, data.id);
      await markTelegramDelivery(data.id, telegramDelivery);
    } else {
      console.log("⏭️ Envoi Telegram ignoré: prediction déjà claimée", { prediction_id: data.id });
    }
  } else {
    console.log("📥 Coupon LIVE mis en file Telegram", { prediction_id: data.id });
  }

  return { created: true, id: data.id, telegram_attempted: telegramAttempted };
}

async function getCachedLiveStats(matchId: string) {
  const { data, error } = await supabase
    .from("matches_live")
    .select("raw_data")
    .eq("id", String(matchId))
    .limit(1)
    .maybeSingle();

  if (error || !data) return null;
  return data?.raw_data?.live_stats || null;
}

// =======================================================
// ✅ Safe update helper (tolerates missing columns like validation_type)
// =======================================================
async function updatePredictionSafe(predId: string, values: any) {
  const { error } = await supabase.from("live_predictions").update(values).eq("id", predId);
  if (!error) return true;

  // if schema doesn't have some columns, retry without them
  if (isUndefinedColumnError(error)) {
    const cleaned = { ...values };
    delete cleaned.validation_type;
    delete cleaned.validated_at; // if missing
    const { error: e2 } = await supabase.from("live_predictions").update(cleaned).eq("id", predId);
    if (!e2) return true;
    throw e2;
  }

  throw error;
}

// =======================================================
// ✅ Validation "merge" self-heal on duplicate unique index
// If UPDATE validated=true fails with 23505:
// - find existing validated=true row with same key
// - update that row with finalValue/outcome
// - delete the current row
// returns the "kept" prediction id
// =======================================================
async function validatePredictionWithMerge(params: {
  predRow: any;
  outcome: "success" | "failure";
  currentValue: number;
  validation_type: "instant" | "final";
}): Promise<{ id: string; transitioned: boolean }> {
  const predId = String(params.predRow.id);
  const matchId = String(params.predRow.match_id);
  const pType = String(params.predRow.prediction_type);
  const threshold = Number(safeNumber(params.predRow.threshold, 0).toFixed(1));
  const values: any = {
    validated: true,
    outcome: params.outcome,
    current_value: params.currentValue,
    validated_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    validation_type: params.validation_type,
  };

  try {
    // Transition atomique false -> true. Deux workers peuvent lire la même ligne,
    // mais un seul obtiendra une ligne dans .select(). Le second n'enverra rien.
    let { data, error } = await supabase
      .from("live_predictions")
      .update(values)
      .eq("id", predId)
      .eq("validated", false)
      .select("id")
      .maybeSingle();

    // Compatibilité si validation_type / validated_at n'existent pas encore.
    if (error && isUndefinedColumnError(error)) {
      const cleaned = { ...values };
      delete cleaned.validation_type;
      delete cleaned.validated_at;
      const retry = await supabase
        .from("live_predictions")
        .update(cleaned)
        .eq("id", predId)
        .eq("validated", false)
        .select("id")
        .maybeSingle();
      data = retry.data;
      error = retry.error;
    }

    if (!error) {
      if (data?.id) return { id: String(data.id), transitioned: true };
      // Déjà validé par une autre invocation : surtout ne pas renvoyer Telegram.
      return { id: predId, transitioned: false };
    }

    if (!isDuplicateKeyError(error)) throw error;

    // Self-heal ancien index unique : s'il existe déjà une ligne validée équivalente,
    // on la garde, on supprime la pending conflictuelle, mais on ne renvoie pas Telegram.
    const existingValidatedId = await findExistingPredictionId({
      match_id: matchId,
      prediction_type: pType,
      threshold,
      validated: true,
    });

    if (existingValidatedId) {
      await updatePredictionSafe(String(existingValidatedId), values);
      const { error: delErr } = await supabase
        .from("live_predictions")
        .delete()
        .eq("id", predId);
      if (delErr) console.error("⚠️ delete duplicate pending pred failed:", delErr);
      return { id: String(existingValidatedId), transitioned: false };
    }

    console.error("⚠️ duplicate on validate but no existing validated row found. predId=", predId);
    return { id: predId, transitioned: false };
  } catch (e) {
    throw e;
  }
}

// =======================================================
// ✅ IN-PLAY VALIDATION
// =======================================================
function computeCurrentValueFromStats(predType: string, stats: any) {
  if (!stats) return null;

  if (predType === "total_shots") {
    return safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
  }
  if (predType === "total_corners") {
    return safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
  }
  if (predType === "total_fouls") {
    return safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
  }  return null;
}

async function validatePredictionsInPlay(
  liveMatchesNormalized: any[],
  options: { maxInstantValidations?: number; sendTelegram?: boolean } = {},
) {
  const liveMap = new Map<string, any>();
  for (const m of liveMatchesNormalized || []) liveMap.set(String(m.id), m);

  const { data: pending, error } = await supabase
    .from("live_predictions")
    .select("id, match_id, match_name, prediction_type, threshold, validated")
    .eq("validated", false);

  if (error) throw error;
  if (!pending?.length) {
    return {
      instant_validated: 0,
      instant_validation_deferred: 0,
      updated_running: 0,
      skipped: 0,
    };
  }

  const maxInstantValidations = Math.max(
    0,
    Math.floor(options.maxInstantValidations ?? 1),
  );

  let instantValidated = 0;
  let instantValidationDeferred = 0;
  let updatedRunning = 0;
  let skipped = 0;

  for (const pred of pending) {
    const match = liveMap.get(String(pred.match_id));
    if (!match) {
      skipped++;
      continue;
    }

    const stats = match?.live_stats || null;
    const currentValue = computeCurrentValueFromStats(pred.prediction_type, stats);
    if (currentValue == null) {
      skipped++;
      continue;
    }

    // Toujours mettre à jour la valeur courante.
    await updatePredictionSafe(String(pred.id), {
      current_value: currentValue,
      updated_at: new Date().toISOString(),
    });
    updatedRunning++;

    const threshold = safeNumber(pred.threshold, 0);
    const reached = currentValue > threshold;
    if (!reached) continue;

    // On borne les validations avec rendu Telegram dans une même invocation.
    // Les autres restent pending et seront prises au passage suivant.
    if (instantValidated >= maxInstantValidations) {
      instantValidationDeferred++;
      continue;
    }

    const validation = await validatePredictionWithMerge({
      predRow: pred,
      outcome: "success",
      currentValue,
      validation_type: "instant",
    });

    if (!validation.transitioned) {
      // Une autre invocation a déjà validé et envoyé ce coupon.
      continue;
    }

    const keptId = validation.id;

    await insertNotification({
      user_id: "all",
      type: "prediction_reached",
      title: "Pronostic atteint en LIVE",
      message:
`${match.home_team} vs ${match.away_team}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Actuel: ${currentValue}
Minute: ${match.current_minute ?? "-"}'`,
      priority: "normal",
      read: false,
      related_prediction_id: keptId,
    });

    if (options.sendTelegram !== false) {
      await sendTelegramValidationResult(
        match,
        pred,
        "success",
        currentValue,
        "instant",
        keptId,
      );
    }

    instantValidated++;
  }

  return {
    instant_validated: instantValidated,
    instant_validation_deferred: instantValidationDeferred,
    updated_running: updatedRunning,
    skipped,
  };
}


// =======================================================
// ✅ LIVE (DB) : /matches + /opportunities depuis Supabase
// =======================================================
function predictionMeta(type: string, threshold: number) {
  if (type === "total_corners") return { badge: "Corners", color: "yellow", title: `Over ${threshold} corners` };
  if (type === "total_shots") return { badge: "Tirs", color: "green", title: `Over ${threshold} tirs` };
  if (type === "total_fouls") return { badge: "Fautes", color: "orange", title: `Over ${threshold} fautes` };
  return { badge: "Signal", color: "gold", title: `Over ${threshold}` };
}

function predictionRowToUi(p: any) {
  const threshold = safeNumber(p.threshold, 0);
  const meta = predictionMeta(p.prediction_type, threshold);

  const signalValue = p.projected_value ?? null;
  const reliability = Math.round((Number(p.probability) || 0) * 100);

  return {
    id: p.id,
    type: p.prediction_type,
    title: meta.title,
    badge: meta.badge,
    color: meta.color,
    probability: Number(p.probability) || 0,
    message: p.message,

    threshold,
    pronostic: threshold,

    current: p.current_value ?? null,

    signal_value: signalValue,
    projected: signalValue, // compat UI

    reliability,
    reasons: [],

    confidence: p.confidence ?? null,
    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,

    created_at: p.created_at ?? null,
  };
}

async function getLiveMatchesFromDb(maxAgeSeconds = 240) {
  const since = new Date(Date.now() - maxAgeSeconds * 1000).toISOString();

  const { data: rows, error } = await supabase
    .from("matches_live")
    .select("id, raw_data, updated_at")
    .gte("updated_at", since)
    .order("updated_at", { ascending: false });

  if (error) throw error;

  const matchesRows = rows || [];
  const ids = matchesRows.map((r: any) => String(r.id));
  if (!ids.length) return [];

  const { data: preds, error: predErr } = await supabase
    .from("live_predictions")
    .select("id, match_id, prediction_type, probability, message, threshold, current_value, projected_value, confidence, validated, outcome, validation_type, created_at")
    .in("match_id", ids)
    .eq("validated", false)
    .order("created_at", { ascending: false });

  if (predErr) throw predErr;

  const byMatch = new Map<string, any[]>();
  for (const p of preds || []) {
    const k = String(p.match_id);
    if (!byMatch.has(k)) byMatch.set(k, []);
    byMatch.get(k)!.push(p);
  }

  const out = matchesRows.map((r: any) => {
    const base = r.raw_data || {};
    const pRows = byMatch.get(String(r.id)) || [];
    const uiPreds = pRows.map(predictionRowToUi);

    uiPreds.sort((a: any, b: any) => safeNumber(b.probability) - safeNumber(a.probability));

    return {
      ...base,
      predictions: uiPreds,
      all_predictions: uiPreds,
      freshness_seconds: computeFreshness(r.updated_at),
      updated_at: r.updated_at,
    };
  });

  out.sort((a: any, b: any) => safeNumber(b.value_score) - safeNumber(a.value_score));
  return out;
}

async function getLiveOpportunitiesFromDb() {
  const matches = await getLiveMatchesFromDb();
  const withPred = matches.filter((m: any) => Array.isArray(m.predictions) && m.predictions.length > 0);

  withPred.sort((a: any, b: any) => {
    const ap = safeNumber(a?.predictions?.[0]?.probability, 0);
    const bp = safeNumber(b?.predictions?.[0]?.probability, 0);
    if (bp !== ap) return bp - ap;
    return safeNumber(b.value_score) - safeNumber(a.value_score);
  });

  return withPred.slice(0, 12);
}

// =======================================================
// ROUTES CORE
// =======================================================
type RefreshBatchOptions = {
  cursor?: string | null;
  batchSize?: number;
  allowTelegram?: boolean;
};

function stableRefreshMatchId(match: any): string {
  return String(match?.id ?? buildCanonicalMatchId(match));
}

function sortMatchesForRefresh(matches: any[]) {
  return [...(matches || [])].sort((a: any, b: any) =>
    stableRefreshMatchId(a).localeCompare(stableRefreshMatchId(b))
  );
}

/**
 * Traite UN SEUL lot.
 * Important : cette fonction doit rester sous la limite CPU d'une invocation Edge.
 */
async function refreshLiveDataBatch(options: RefreshBatchOptions = {}) {
  const batchSize = Math.max(
    1,
    Math.min(5, Math.floor(options.batchSize ?? LIVE_REFRESH_BATCH_SIZE)),
  );
  const cursor = String(options.cursor || "");
  const allowTelegram = options.allowTelegram !== false;

  // 1) Sources.
  const liveData = await fetchBSD("/live/");
  const originalRawMatches = liveData.results || [];

  const espnResult = await fetchEspnLiveMatchesForMerge();

  // 2) Fusion des sources.
  const merged = mergeOriginalAndEspnMatches(
    originalRawMatches,
    espnResult.matches || [],
  );

  // Ordre stable indispensable pour ne jamais retraiter le même match
  // dans la chaîne de lots.
  const allRawMatches = sortMatchesForRefresh(merged.mergedMatches);

  const candidates = cursor
    ? allRawMatches.filter(
      (m: any) => stableRefreshMatchId(m).localeCompare(cursor) > 0,
    )
    : allRawMatches;

  const rawMatches = candidates.slice(0, batchSize);
  const refreshAt = nowIso();

  const nextCursor = rawMatches.length
    ? stableRefreshMatchId(rawMatches[rawMatches.length - 1])
    : cursor || null;

  const hasMore = candidates.length > rawMatches.length;

  if (!rawMatches.length) {
    return {
      matches: [],
      has_more: false,
      next_cursor: nextCursor,
      meta: {
        total_live_matches: allRawMatches.length,
        batch_size: batchSize,
        batch_count: 0,
        cursor: cursor || null,
        next_cursor: nextCursor,
        original_source_matches: merged.meta.original_source_matches,
        espn_source_matches: merged.meta.espn_source_matches,
        duplicates_merged: merged.meta.duplicates_merged,
        espn_only_matches: merged.meta.espn_only_matches,
        espn_enabled: merged.meta.espn_enabled,
        espn_error: espnResult.error,
        predictions_created: 0,
        predictions_existing: 0,
        predictions_failed: 0,
      },
    };
  }

  // 3) Audit uniquement pour les matchs de CE lot.
  // Avant, tout était persisté à chaque refresh.
  const batchCanonicalIds = new Set(
    rawMatches.map((m: any) => buildCanonicalMatchId(m)),
  );

  const batchSourceRows = (merged.sourceRows || []).filter((row: any) =>
    batchCanonicalIds.has(String(row?.canonical_match_id || ""))
  );

  await persistStatsSourcesAndMerged(batchSourceRows, rawMatches);

  // 4) Calcul uniquement sur 5 matchs maximum.
  const normalizedMatches = rawMatches.map((m: any) =>
    normalizeMatch(m, refreshAt)
  );

  // 5) Un seul UPSERT Supabase pour le lot.
  await cacheLiveMatches(rawMatches, refreshAt);

  // 6) Sauvegarde des nouveaux pronostics SANS rendre immédiatement toutes
  // les images Telegram. Ils entrent dans la file telegram_sent=false.
  let createdPreds = 0;
  let existingPreds = 0;
  let failedPreds = 0;

  for (const m of normalizedMatches) {
    for (const pred of m.predictions || []) {
      try {
        const res = await savePrediction(m, pred, { sendTelegram: false });
        if (res.created) createdPreds++;
        else existingPreds++;
      } catch (e) {
        failedPreds++;
        console.error("savePrediction failed (ignored):", e);
      }
    }
  }

  // 7) Au maximum UNE validation instantanée par lot.
  // Cela borne également le nombre de rendus d'image.
  const instant = await validatePredictionsInPlay(normalizedMatches, {
    // En fallback CPU sans Telegram, on ne valide pas encore le coupon :
    // il reste pending et pourra être validé + envoyé au prochain passage.
    maxInstantValidations: allowTelegram ? 1 : 0,
    sendTelegram: allowTelegram,
  });

  // 8) Si aucune image de validation n'a été rendue dans ce lot,
  // on traite au maximum UN coupon Telegram en attente.
  const telegramRetry =
    allowTelegram && safeNumber(instant.instant_validated, 0) === 0
      ? await retryPendingTelegramLiveCoupons(normalizedMatches, 1)
      : {
        telegram_retry_enabled: true,
        telegram_retry_processed: 0,
        telegram_retry_sent: 0,
        telegram_retry_failed: 0,
        telegram_retry_skipped: 0,
      };

  return {
    matches: normalizedMatches,
    has_more: hasMore,
    next_cursor: nextCursor,
    meta: {
      total_live_matches: allRawMatches.length,
      matches_live: rawMatches.length,
      batch_size: batchSize,
      batch_count: rawMatches.length,
      cursor: cursor || null,
      next_cursor: nextCursor,
      has_more: hasMore,

      original_source_matches: merged.meta.original_source_matches,
      espn_source_matches: merged.meta.espn_source_matches,
      duplicates_merged: merged.meta.duplicates_merged,
      espn_only_matches: merged.meta.espn_only_matches,
      espn_enabled: merged.meta.espn_enabled,
      espn_error: espnResult.error,

      predictions_created: createdPreds,
      predictions_existing: existingPreds,
      predictions_failed: failedPreds,

      ...telegramRetry,
      ...instant,
    },
  };
}

async function invokeRefreshBatch(
  cursor: string | null,
  batchSize: number,
  allowTelegram = true,
) {
  const endpoint = new URL(
    `${SUPABASE_URL.replace(/\/$/, "")}/functions/v1/live/refresh/batch`,
  );

  endpoint.searchParams.set("batch_size", String(batchSize));
  endpoint.searchParams.set("allow_telegram", allowTelegram ? "1" : "0");
  if (cursor) endpoint.searchParams.set("cursor", cursor);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
  };

  if (CRON_SECRET) headers["x-cron-secret"] = CRON_SECRET;

  const res = await fetch(endpoint.toString(), {
    method: "POST",
    headers,
  });

  const rawBody = await res.text().catch(() => "");
  let body: any = {};

  try {
    body = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    body = { raw: rawBody };
  }

  if (!res.ok) {
    const err: any = new Error(
      `refresh batch HTTP ${res.status}: ${
        body?.message || body?.error || rawBody || res.statusText
      }`,
    );
    err.status = res.status;
    err.body = body;
    throw err;
  }

  return body;
}

/**
 * Coordinateur.
 *
 * /refresh reste compatible avec ton cron actuel :
 * un seul appel externe suffit.
 *
 * Le coordinateur appelle /refresh/batch plusieurs fois. Chaque lot est donc
 * une NOUVELLE invocation Edge avec son propre budget CPU.
 */
async function refreshLiveDataInBatches(batchSize = LIVE_REFRESH_BATCH_SIZE) {
  let cursor: string | null = null;
  let batchNumber = 0;
  let processedMatches = 0;
  let hasMore = true;
  let lastTotalLiveMatches = 0;

  const aggregate: any = {
    batches_completed: 0,
    predictions_created: 0,
    predictions_existing: 0,
    predictions_failed: 0,
    telegram_retry_processed: 0,
    telegram_retry_sent: 0,
    telegram_retry_failed: 0,
    instant_validated: 0,
    instant_validation_deferred: 0,
    updated_running: 0,
  };

  while (hasMore && batchNumber < LIVE_REFRESH_MAX_BATCHES) {
    let effectiveBatchSize = Math.max(1, Math.min(5, batchSize));
    let allowTelegram = true;
    let result: any = null;

    // Protection supplémentaire :
    // - si un lot de 5 reçoit encore un 546, on retente 2 puis 1;
    // - si même 1 échoue, on retente sans rendu Telegram pour sauver les données.
    while (!result) {
      try {
        result = await invokeRefreshBatch(
          cursor,
          effectiveBatchSize,
          allowTelegram,
        );
      } catch (e: any) {
        if (safeNumber(e?.status, 0) === 546 && effectiveBatchSize > 1) {
          const previousSize = effectiveBatchSize;
          effectiveBatchSize = Math.max(1, Math.floor(effectiveBatchSize / 2));
          console.warn(
            `⚠️ CPU 546 sur lot ${previousSize}; retry avec ${effectiveBatchSize} match(s)`,
          );
          continue;
        }

        if (
          safeNumber(e?.status, 0) === 546 &&
          effectiveBatchSize === 1 &&
          allowTelegram
        ) {
          allowTelegram = false;
          console.warn(
            "⚠️ CPU 546 même avec 1 match; retry du lot sans rendu Telegram",
          );
          continue;
        }

        throw e;
      }
    }

    const meta = result?.meta || {};

    processedMatches += safeNumber(meta.batch_count, 0);
    lastTotalLiveMatches = safeNumber(
      meta.total_live_matches,
      lastTotalLiveMatches,
    );

    aggregate.batches_completed++;
    aggregate.predictions_created += safeNumber(meta.predictions_created, 0);
    aggregate.predictions_existing += safeNumber(meta.predictions_existing, 0);
    aggregate.predictions_failed += safeNumber(meta.predictions_failed, 0);
    aggregate.telegram_retry_processed += safeNumber(
      meta.telegram_retry_processed,
      0,
    );
    aggregate.telegram_retry_sent += safeNumber(meta.telegram_retry_sent, 0);
    aggregate.telegram_retry_failed += safeNumber(
      meta.telegram_retry_failed,
      0,
    );
    aggregate.instant_validated += safeNumber(meta.instant_validated, 0);
    aggregate.instant_validation_deferred += safeNumber(
      meta.instant_validation_deferred,
      0,
    );
    aggregate.updated_running += safeNumber(meta.updated_running, 0);

    hasMore = Boolean(result?.has_more);
    const nextCursor =
      result?.next_cursor == null ? null : String(result.next_cursor);

    if (hasMore && (!nextCursor || nextCursor === cursor)) {
      throw new Error(
        `Refresh batch bloqué: cursor n'avance pas (${String(cursor)})`,
      );
    }

    cursor = nextCursor;
    batchNumber++;
  }

  return {
    processed_matches: processedMatches,
    total_live_matches: lastTotalLiveMatches,
    has_more: hasMore,
    next_cursor: cursor,
    meta: {
      ...aggregate,
      requested_batch_size: batchSize,
      max_batches: LIVE_REFRESH_MAX_BATCHES,
      truncated: hasMore,
    },
  };
}


async function validatePredictionsNow() {
  const { data: pending, error: pendingError } = await supabase
    .from("live_predictions")
    .select("id, match_id, match_name, prediction_type, threshold, league_name, validated, created_at")
    .eq("validated", false)
    .order("created_at", { ascending: false });

  if (pendingError) throw pendingError;
  if (!pending?.length) return { validated: 0, skipped: 0, failed: 0 };

  let validated = 0;
  let skipped = 0;
  let failed = 0;

  for (const pred of pending) {
    let ev: any = null;
    try {
      ev = await fetchBSD(`/events/${pred.match_id}/`);
    } catch {
      skipped++;
      continue;
    }

    if (!isFinishedEvent(ev)) continue;

    let stats = ev.live_stats || null;
    if (!stats) stats = await getCachedLiveStats(String(pred.match_id));
    if (!stats) { skipped++; continue; }

    const threshold = safeNumber(pred.threshold, 0);
    let finalValue = 0;
    let ok = false;

    if (pred.prediction_type === "total_shots") {
      finalValue = safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_corners") {
      finalValue = safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_fouls") {
      finalValue = safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
      ok = finalValue > threshold;
    } else {
      skipped++;
      continue;
    }

    try {
      const validation = await validatePredictionWithMerge({
        predRow: pred,
        outcome: ok ? "success" : "failure",
        currentValue: finalValue,
        validation_type: "final",
      });

      if (!validation.transitioned) {
        skipped++;
        continue;
      }

      const keptId = validation.id;

      await insertNotification({
        user_id: "all",
        type: "prediction_validated",
        title: "Prédiction validée",
        message:
`${pred.match_name}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Valeur finale: ${finalValue}
Résultat: ${ok ? "✅ réussi" : "❌ échoué"}`,
        priority: "normal",
        read: false,
        related_prediction_id: keptId,
      });

      // ✅ Envoi Telegram résultat final : coupon validé ou perdu.
      const telegramMatch = await getTelegramMatchFromCache(pred, ev);
      await sendTelegramValidationResult(
        telegramMatch,
        pred,
        ok ? "success" : "failure",
        finalValue,
        "final",
        keptId,
      );

      validated++;
    } catch (e) {
      failed++;
      console.error("validatePredictionsNow failed (ignored):", e);
    }
  }

  return { validated, skipped, failed };
}

// =======================================================
// ✅ Helpers UI history/detail (logos via matches_live.raw_data)
// =======================================================
async function getRawMatchMap(matchIds: string[]) {
  const ids = [...new Set((matchIds || []).map(String).filter(Boolean))];
  const matchMap = new Map<string, any>();
  if (!ids.length) return matchMap;

  const { data: mrows, error: mErr } = await supabase
    .from("matches_live")
    .select("id, raw_data")
    .in("id", ids);

  if (mErr) {
    console.error("matches_live fetch failed:", mErr);
    return matchMap;
  }

  for (const r of mrows || []) matchMap.set(String(r.id), r.raw_data || {});
  return matchMap;
}

function enrichPredictionForUi(p: any, raw: any) {
  return {
    id: p.id,
    match_id: String(p.match_id),

    home_team: p.home_team ?? raw.home_team ?? null,
    away_team: p.away_team ?? raw.away_team ?? null,
    home_score: p.home_score ?? raw.home_score ?? 0,
    away_score: p.away_score ?? raw.away_score ?? 0,
    current_minute: p.minute ?? null, // minute du signal (fixe historique)

    league: raw.league ?? { name: p.league_name ?? null },
    league_id: raw.league_id ?? null,
    home_team_id: raw.home_team_id ?? null,
    away_team_id: raw.away_team_id ?? null,
    home_team_obj: raw.home_team_obj ?? null,
    away_team_obj: raw.away_team_obj ?? null,

    match: p.match_name,
    type: p.prediction_type,
    probability: Number(p.probability),

    message: p.message,

    pronostic: p.threshold,
    threshold: p.threshold,

    signal_value: p.projected_value,
    projected: p.projected_value,
    current: p.current_value,

    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,
    validated_at: p.validated_at ?? null,

    timestamp: new Date(p.created_at).getTime(),
  };
}

// =======================================================
// SERVER
// =======================================================
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const path = extractPath(url, "live");

  try {
    // ===================================================
    // IMG PROXY
    // ===================================================
    const imgMatch = path.match(/^\/img\/(team|league|player)\/(\d+)\/?$/);
    if (imgMatch && req.method === "GET") {
      const type = imgMatch[1];
      const apiId = imgMatch[2];

      const upstream = await fetch(`${BSD_IMG_BASE}/${type}/${apiId}/`, {
        headers: { Authorization: `Token ${BSD_API_TOKEN}` },
      });

      if (!upstream.ok) {
        const t = await upstream.text().catch(() => "");
        return new Response(t || "Image not found", {
          status: upstream.status,
          headers: { ...corsHeaders, "Content-Type": upstream.headers.get("content-type") || "text/plain" },
        });
      }

      return new Response(upstream.body, {
        status: 200,
        headers: {
          ...corsHeaders,
          "Content-Type": upstream.headers.get("content-type") || "image/png",
          "Cache-Control": "public, max-age=31536000",
        },
      });
    }

    // ===================================================
    // DEBUG finished events
    // ===================================================
    if (path === "/debug/events-finished" && req.method === "GET") {
      requireDebugAuth(url);

      const date = url.searchParams.get("date") || "2026-03-29";
      const tz = url.searchParams.get("tz") || DEFAULT_TZ;
      const raw = url.searchParams.get("raw") === "1";

      const data = await fetchBSD("/events/", {
        status: "finished",
        date_from: date,
        date_to: date,
        tz,
      });

      if (raw) return json(data);

      const compact = (data?.results || []).map((m: any) => ({
        id: m.id,
        event_date: m.event_date,
        status: m.status,
        period: m.period ?? null,
        home_team: m.home_team,
        away_team: m.away_team,
        score: `${m.home_score ?? "-"}-${m.away_score ?? "-"}`,
        has_live_stats: !!m.live_stats,
      }));

      return json({
        query: { status: "finished", date_from: date, date_to: date, tz },
        count: data?.count ?? compact.length,
        results: compact,
      });
    }

    // ===================================================
    // CRON: refresh
    // ===================================================

    if (path === "/stats/sources" && req.method === "GET") {
      requireDebugAuth(url);
      const limit = Math.min(safeNumber(url.searchParams.get("limit"), 100), 500);

      const { data, error } = await supabase
        .from(T_STATS_SOURCES)
        .select("*")
        .order("updated_at", { ascending: false })
        .limit(limit);

      if (error) throw error;
      return json({ sources: data || [] });
    }

    if (path === "/stats/merged" && req.method === "GET") {
      requireDebugAuth(url);
      const limit = Math.min(safeNumber(url.searchParams.get("limit"), 100), 500);

      const { data, error } = await supabase
        .from(T_STATS_MERGED)
        .select("*")
        .order("updated_at", { ascending: false })
        .limit(limit);

      if (error) throw error;
      return json({ merged: data || [] });
    }

    // Un lot interne : maximum 5 matchs.
    // Cette route est appelée par le coordinateur /refresh.
    if (path === "/refresh/batch" && req.method === "POST") {
      requireCronAuth(req, url);

      const requestedBatchSize = Math.floor(
        safeNumber(
          url.searchParams.get("batch_size"),
          LIVE_REFRESH_BATCH_SIZE,
        ),
      );

      const batchSize = Math.max(1, Math.min(5, requestedBatchSize));
      const cursor = url.searchParams.get("cursor") || null;
      const allowTelegram =
        String(url.searchParams.get("allow_telegram") || "1") !== "0";

      const result = await refreshLiveDataBatch({
        cursor,
        batchSize,
        allowTelegram,
      });

      return json({
        success: true,
        ...result,
      });
    }

    // Coordinateur compatible avec l'ancienne URL.
    // Le cron continue d'appeler exactement POST /live/refresh.
    if (path === "/refresh" && req.method === "POST") {
      requireCronAuth(req, url);

      try {
        const result = await refreshLiveDataInBatches(
          LIVE_REFRESH_BATCH_SIZE,
        );

        await setCronRun("live_refresh", !result.has_more, {
          processed_matches: result.processed_matches,
          total_live_matches: result.total_live_matches,
          next_cursor: result.next_cursor,
          ...result.meta,
        });

        return json({
          success: !result.has_more,
          count: result.processed_matches,
          total_live_matches: result.total_live_matches,
          has_more: result.has_more,
          next_cursor: result.next_cursor,
          meta: result.meta,
        });
      } catch (e: any) {
        await setCronRun("live_refresh", false, {
          error: e?.message || String(e),
        });
        throw e;
      }
    }

    // ===================================================
    // CRON: validate (final)
    // ===================================================
    if (path === "/validate" && req.method === "POST") {
      requireCronAuth(req, url);

      try {
        const result = await validatePredictionsNow();
        await setCronRun("live_validate", true, result);
        return json({ success: true, ...result });
      } catch (e: any) {
        await setCronRun("live_validate", false, { error: e?.message || String(e) });
        throw e;
      }
    }

    // ===================================================
    // UI: matches (DB)
    // ===================================================
    if (path === "/matches" && req.method === "GET") {
      const matches = await getLiveMatchesFromDb();
      return json({ matches });
    }

    // ===================================================
    // UI: opportunities (DB)
    // ===================================================
    if (path === "/opportunities" && req.method === "GET") {
      const opportunities = await getLiveOpportunitiesFromDb();
      return json({ opportunities });
    }

    // ===================================================
    // UI: today (BSD direct)
    // ===================================================
    if (path === "/today" && req.method === "GET") {
      const today = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);

      const liveData = await fetchBSD("/live/");
      const liveMatches = liveData.results || [];

      const eventsData = await fetchBSD("/events/", { date_from: today, date_to: today });
      const allEvents = eventsData.results || [];

      const scheduled: any[] = [];
      const finished: any[] = [];

      allEvents.forEach((ev: any) => {
        if (isFinishedEvent(ev)) finished.push(ev);
        else {
          const isLive = liveMatches.some((l: any) => String(l.id) === String(ev.id));
          if (!isLive) scheduled.push(ev);
        }
      });

      return json({
        data: {
          live: { count: liveMatches.length, matches: liveMatches },
          scheduled: { count: scheduled.length, matches: scheduled },
          finished: { count: finished.length, matches: finished.slice(0, 10) },
        },
      });
    }

    // ===================================================
    // UI: history (48h) + logos
    // ===================================================
    if (path === "/predictions/history" && req.method === "GET") {
      const since = new Date(Date.now() - 48 * 3600 * 1000).toISOString();

      const { data, error } = await supabase
        .from("live_predictions")
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at")
        .gte("created_at", since)
        .order("created_at", { ascending: false });

      if (error) throw error;

      const preds = data || [];
      const rawMap = await getRawMatchMap(preds.map((p: any) => String(p.match_id)));

      return json({
        history: preds.map((p: any) =>
          enrichPredictionForUi(p, rawMap.get(String(p.match_id)) || {})
        ),
      });    }

    // ===================================================
    // UI: prediction detail by id (pour clic notif)
    // ===================================================
    if (path === "/predictions/by-id" && req.method === "GET") {
      const id = url.searchParams.get("id") || "";
      if (!id) return json({ error: "id required" }, 400);

      const { data: p, error } = await supabase
        .from("live_predictions")
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at")
        .eq("id", id)
        .maybeSingle();

      if (error) throw error;
      if (!p) return json({ error: "not found" }, 404);

      const { data: mrow, error: mErr } = await supabase
        .from("matches_live")
        .select("raw_data")
        .eq("id", String(p.match_id))
        .maybeSingle();

      if (mErr) console.error("matches_live by-id failed:", mErr);

      return json({ prediction: enrichPredictionForUi(p, mrow?.raw_data || {}) });
    }

    // ===================================================
    // UI: notifications
    // ===================================================
    if (path === "/notifications" && req.method === "GET") {
      const userId = url.searchParams.get("user_id") || "all";
      const ids = userId === "all" ? ["all"] : ["all", userId];

      const { data, error } = await supabase
        .from("notifications")
        .select("*")
        .in("user_id", ids)
        .order("created_at", { ascending: false })
        .limit(50);

      if (error) throw error;

      return json({
        notifications: (data || []).map((n: any) => ({
          ...n,
          timestamp: new Date(n.created_at).getTime(),
        })),
      });
    }

    if (path === "/notifications/mark-read" && req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      const ids = Array.isArray(body.notification_ids) ? body.notification_ids : [];

      if (!ids.length) return json({ success: true, updated: 0 });

      const { error } = await supabase
        .from("notifications")
        .update({ read: true })
        .in("id", ids);

      if (error) throw error;

      return json({ success: true, updated: ids.length });
    }

    return json({ error: "Not found" }, 404);
  } catch (e: any) {
    console.error("live.ts error:", e);
    return json({ error: e?.message || "Erreur serveur" }, 500);
  }
});