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

const LIVE_PROP_ODDS_URL = Deno.env.get("LIVE_PROP_ODDS_URL") || "";
const LIVE_PROP_ODDS_TOKEN = Deno.env.get("LIVE_PROP_ODDS_TOKEN") || "";

import { richPhotoOrLegacy, richTextOrLegacy } from "../_shared/telegram_rich.ts";
import { attachLiveSponsorBanner } from "../_shared/live_sponsor_banner.ts";
const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
const TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || "";
// Deux destinations Telegram voulues : canal principal + canal secondaire.
// L'anti-doublon est géré par prediction_id + liste des canaux en échec :
// un coupon doit partir une seule fois vers chacun des deux canaux.
const TELEGRAM_CHAT_ID_SECONDARY = Deno.env.get("TELEGRAM_CHAT_ID_SECONDARY") || "@mrxpronosfr";
const SITE_URL = Deno.env.get("SITE_URL") || "https://mrxpronos.github.io/MrXPRONOS_App/";
// Telegram est de nouveau traité directement par live.ts.
// Le rendu reste borné à UN coupon par lot pour éviter les pics CPU.
const TELEGRAM_IN_REFRESH = true;

const BSD_API_BASE = "https://sports.bzzoiro.com/api/v2";
const BSD_COVERAGE_URL = "https://sports.bzzoiro.com/api/v2/coverage/?sport=football";
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

// Enrichissement des statistiques LIVE BSD.
// /events/live/ est volontairement compact chez BSD : les corners/tirs/fautes
// détaillés viennent de /events/{id}/stats/. On borne ces appels pour rester
// largement sous le quota gratuit quotidien.
const BSD_STATS_MAX_CALLS_PER_REFRESH = Math.max(
  1,
  Math.min(5, safeEnvInt("BSD_STATS_MAX_CALLS_PER_REFRESH", 2)),
);
const BSD_STATS_REFRESH_SECONDS = Math.max(
  45,
  Math.min(600, safeEnvInt("BSD_STATS_REFRESH_SECONDS", 120)),
);
const BSD_STATS_QUOTA_RESERVE = Math.max(
  250,
  Math.min(3000, safeEnvInt("BSD_STATS_QUOTA_RESERVE", 900)),
);

const T_STATS_SOURCES = "live_stats_sources";
const T_STATS_MERGED = "live_stats_merged";
const DAILY_DEFAULT_STAKE = 500_000;

if (!BSD_API_TOKEN) console.error("BSD_API_TOKEN non défini");
if (!SUPABASE_URL) console.error("SUPABASE_URL non défini");
if (!SUPABASE_SERVICE_ROLE_KEY) console.error("SUPABASE_SERVICE_ROLE_KEY non défini");

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

async function setCronRun(jobName: string, success: boolean, details: any = {}) {
  // La table cron_runs de ce projet n'a pas le schéma attendu par l'ancien code
  // (notamment pas de colonne "details"). Le suivi reste donc dans les logs Edge,
  // sans requête DB supplémentaire et sans risque de casser le refresh.
  console.log("CRON_RUN", {
    job_name: jobName,
    success,
    details,
    at: nowIso(),
  });
}


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

function nullableNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function hasCompleteStatPair(stats: any, key: string): boolean {
  return (
    nullableNumber(stats?.home?.[key]) != null &&
    nullableNumber(stats?.away?.[key]) != null
  );
}

function statPairTotal(stats: any, key: string, totalKey?: string) {
  const totals = stats?.totals || {};
  const tk = totalKey || key;
  const explicit = nullableNumber(totals?.[tk]);
  if (explicit != null) return explicit;

  const home = nullableNumber(getHomeStats(stats)?.[key]);
  const away = nullableNumber(getAwayStats(stats)?.[key]);
  if (home == null || away == null) return NaN;
  return home + away;
}

function statsCompleteness(stats: any) {
  const shots = hasCompleteStatPair(stats, "total_shots");
  const shotsOnTarget = hasCompleteStatPair(stats, "shots_on_target");
  const corners = hasCompleteStatPair(stats, "corner_kicks");
  const fouls = hasCompleteStatPair(stats, "fouls");

  const core = [shots, corners, fouls].filter(Boolean).length;
  return {
    shots,
    shots_on_target: shotsOnTarget,
    corners,
    fouls,
    core_complete: core,
    score: Math.round((core / 3) * 100),
  };
}

function ensureLiveStatsShape(stats: any) {
  const home = { ...(stats?.home || {}) };
  const away = { ...(stats?.away || {}) };
  const totals = { ...(stats?.totals || {}) };

  const pairs: Array<[string, string]> = [
    ["corner_kicks", "corners"],
    ["fouls", "fouls"],
    ["yellow_cards", "yellow_cards"],
    ["red_cards", "red_cards"],
    ["total_shots", "total_shots"],
    ["shots_on_target", "shots_on_target"],
  ];

  for (const [key, totalKey] of pairs) {
    home[key] = nullableNumber(home[key]);
    away[key] = nullableNumber(away[key]);

    const explicit = nullableNumber(totals[totalKey]);
    if (explicit != null) {
      totals[totalKey] = explicit;
    } else if (home[key] != null && away[key] != null) {
      totals[totalKey] = home[key] + away[key];
    } else {
      totals[totalKey] = null;
    }
  }

  if (home.ball_possession !== undefined) {
    home.ball_possession = nullableNumber(home.ball_possession);
  }
  if (away.ball_possession !== undefined) {
    away.ball_possession = nullableNumber(away.ball_possession);
  }

  return { ...stats, home, away, totals };
}

function applyStatPairIfBetter(base: any, extra: any, key: string, totalKey?: string) {
  const tk = totalKey || key;

  const bh = nullableNumber(base?.home?.[key]);
  const ba = nullableNumber(base?.away?.[key]);
  const eh = nullableNumber(extra?.home?.[key]);
  const ea = nullableNumber(extra?.away?.[key]);

  const baseComplete = bh != null && ba != null;
  const extraComplete = eh != null && ea != null;

  if (extraComplete) {
    const baseTotal = baseComplete ? (bh! + ba!) : -1;
    const extraTotal = eh! + ea!;

    // Une statistique cumulative ne doit jamais reculer. Une paire complète
    // remplace une paire absente ou plus ancienne.
    if (!baseComplete || extraTotal >= baseTotal) {
      base.home[key] = eh;
      base.away[key] = ea;
      base.totals[tk] = extraTotal;
    }
    return;
  }

  // Données partielles : on remplit seulement ce qui était inconnu.
  if (bh == null && eh != null) base.home[key] = eh;
  if (ba == null && ea != null) base.away[key] = ea;

  const nh = nullableNumber(base?.home?.[key]);
  const na = nullableNumber(base?.away?.[key]);
  base.totals[tk] = nh != null && na != null ? nh + na : null;
}

function mergeLiveStats(primaryStats: any, secondaryStats: any) {
  const merged = ensureLiveStatsShape(primaryStats || {});
  const extra = ensureLiveStatsShape(secondaryStats || {});

  applyStatPairIfBetter(merged, extra, "corner_kicks", "corners");
  applyStatPairIfBetter(merged, extra, "fouls", "fouls");
  applyStatPairIfBetter(merged, extra, "yellow_cards", "yellow_cards");
  applyStatPairIfBetter(merged, extra, "red_cards", "red_cards");
  applyStatPairIfBetter(merged, extra, "total_shots", "total_shots");
  applyStatPairIfBetter(merged, extra, "shots_on_target", "shots_on_target");

  // Possession n'est pas cumulative ; on prend la valeur secondaire quand elle existe.
  const hp = nullableNumber(extra?.home?.ball_possession);
  const ap = nullableNumber(extra?.away?.ball_possession);
  if (hp != null) merged.home.ball_possession = hp;
  if (ap != null) merged.away.ball_possession = ap;

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

let bsdQuotaRemaining: number | null = null;
let bsdQuotaResetSeconds: number | null = null;

function updateBsdQuotaState(res: Response) {
  const raw = res.headers.get("RateLimit") || "";
  const remainingMatch = raw.match(/(?:^|;)\s*r=(\d+)/i);
  const resetMatch = raw.match(/(?:^|;)\s*t=(\d+)/i);

  if (remainingMatch) bsdQuotaRemaining = safeNumber(remainingMatch[1], null as any);
  if (resetMatch) bsdQuotaResetSeconds = safeNumber(resetMatch[1], null as any);
}

function bsdStatsCallBudget() {
  const configured = BSD_STATS_MAX_CALLS_PER_REFRESH;
  if (bsdQuotaRemaining == null) return configured;

  const usable = bsdQuotaRemaining - BSD_STATS_QUOTA_RESERVE;
  if (usable <= 0) return 0;
  if (usable < 250) return 1;
  if (usable < 700) return Math.min(2, configured);
  return configured;
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

  updateBsdQuotaState(res);

  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    const err: any = new Error(
      `BSD API error (${res.status}): ${errorBody || res.statusText}`,
    );
    err.status = res.status;
    err.body = errorBody;
    throw err;
  }

  return res.json();
}

function isBSDQuotaError(error: any) {
  const status = safeNumber(error?.status, 0);
  const message = String(error?.message || error?.body || "").toLowerCase();
  return (
    status === 429 ||
    message.includes("taster_exhausted") ||
    message.includes("quota") ||
    message.includes("rate limit")
  );
}

function bsdResults(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}

async function fetchBSDCoverage() {
  try {
    const res = await fetch(BSD_COVERAGE_URL, {
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) return null;
    const payload = await res.json();
    if (Array.isArray(payload?.sports)) {
      return payload.sports.find((x: any) => String(x?.sport).toLowerCase() === "football") || null;
    }
    return payload;
  } catch (e) {
    console.warn("BSD coverage unavailable (ignored):", e);
    return null;
  }
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

    // IMPORTANT : pas de recherche ESPN approximative par nom ici.
    // Elle pouvait associer un club à une sélection/pays portant un nom proche
    // et afficher un drapeau incorrect. Sans identifiant/logo fiable, le coupon
    // utilise simplement les initiales de l'équipe.
  }

  console.warn("⚠️ Aucun logo exploitable pour Telegram:", {
    kind,
    team: teamNameForLogo(match, kind),
    match_id: match?.id ?? null,
    source: match?.raw_data?.source ?? match?.source_name ?? null,
  });
  return "";
}

type TelegramResvgModule = {
  initWasm: (bytes: ArrayBuffer) => Promise<void>;
  Resvg: any;
};

type TelegramRenderModules = TelegramResvgModule & {
  satori: any;
  html: any;
};

let telegramResvgModulePromise: Promise<TelegramResvgModule> | null = null;
let telegramRenderModulesPromise: Promise<TelegramRenderModules> | null = null;

async function loadTelegramResvgModule(): Promise<TelegramResvgModule> {
  if (!telegramResvgModulePromise) {
    telegramResvgModulePromise = import(
      "https://esm.sh/@resvg/resvg-wasm@2.6.2?target=deno"
    )
      .then((mod: any) => ({
        initWasm: mod.initWasm,
        Resvg: mod.Resvg,
      }))
      .catch((e) => {
        telegramResvgModulePromise = null;
        throw e;
      });
  }

  return await telegramResvgModulePromise;
}

async function loadTelegramRenderModules(): Promise<TelegramRenderModules> {
  if (!telegramRenderModulesPromise) {
    telegramRenderModulesPromise = (async () => {
      const [resvgMod, satoriMod, htmlMod] = await Promise.all([
        loadTelegramResvgModule(),
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

async function readBundledTelegramFont(filename: string): Promise<Uint8Array> {
  try {
    const url = new URL(`./_fonts/${filename}`, import.meta.url);
    const bytes = await Deno.readFile(url);
    if (!isValidFontFile(bytes)) {
      throw new Error(
        `police locale invalide (${bytes.byteLength} octets, header=${fontHeader(bytes)})`,
      );
    }
    console.log("✅ Police Telegram locale chargée", {
      filename,
      bytes: bytes.byteLength,
    });
    return bytes;
  } catch (e: any) {
    console.warn(
      "⚠️ Police locale indisponible, fallback distant:",
      filename,
      e?.message || String(e),
    );
    return await fetchRemoteFont(filename);
  }
}

async function loadFontData(): Promise<TelegramFonts> {
  if (cachedFontData) return cachedFontData;

  // Les polices sont déjà packagées dans la fonction Supabase via static_files.
  // Cela évite 3 téléchargements réseau et réduit fortement le coût d'un cold start.
  const [regular, bold, extraBold] = await Promise.all([
    readBundledTelegramFont("NotoSans-Regular.ttf"),
    readBundledTelegramFont("NotoSans-Bold.ttf"),
    readBundledTelegramFont("NotoSans-ExtraBold.ttf"),
  ]);

  cachedFontData = {
    regular: toExactArrayBuffer(regular),
    bold: toExactArrayBuffer(bold),
    extraBold: toExactArrayBuffer(extraBold),
  };

  console.log("✅ Polices Telegram prêtes (bundle local + cache)");
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
      const { initWasm } = await loadTelegramResvgModule();
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

function formatTelegramSlipDateTime(match: any) {
  const raw = getMatchEventDate(match);
  const d = raw ? new Date(raw) : new Date();

  if (!Number.isFinite(d.getTime())) {
    return "--.--.---- (--:--)";
  }

  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = String(d.getFullYear());
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${day}.${month}.${year} (${hours}:${minutes})`;
}

function formatTelegramClock(value: unknown) {
  const minute = Math.max(0, safeNumber(value, 0));
  const whole = Math.floor(minute);
  let seconds = Math.round((minute - whole) * 60);
  let mins = whole;

  if (seconds >= 60) {
    mins += 1;
    seconds = 0;
  }

  return `${mins}:${String(seconds).padStart(2, "0")}`;
}

function pickTelegramNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (value == null || value === "") continue;
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function formatTelegramOdds(value: number | null) {
  if (value == null) return "—";
  return (Math.round(Math.max(0, value) * 100) / 100).toFixed(2).replace(/\.00$/, "");
}

function formatTelegramMoney(value: number | null) {
  if (value == null) return "—";
  const amount = Math.round(Math.max(0, value));
  return `${amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")} F`;
}

function buildTelegramSelectionText(pred: any) {
  const rawType = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? "",
  );
  const typeLabel = formatLivePredictionType(rawType);

  if (typeLabel && typeLabel !== "Signal LIVE") {
    return `Total. (${threshold}) Plus de. ${typeLabel}`;
  }

  return `Total. (${threshold}) Plus de`;
}

function deriveTelegramSlipStats(pred: any) {
  const oddsNumber = pickTelegramNumber(
    pred?.odd,
    pred?.odds,
    pred?.cote,
    pred?.quote,
    pred?.coefficient,
  );

  const stakeNumber = pickTelegramNumber(
    pred?.stake,
    pred?.mise,
    pred?.bet_amount,
    pred?.amount,
  );

  const explicitPotential = pickTelegramNumber(
    pred?.potential_gain,
    pred?.gains,
    pred?.gain,
    pred?.profit,
  );

  const potentialNumber = explicitPotential ??
    (oddsNumber != null && stakeNumber != null ? stakeNumber * oddsNumber : null);

  return {
    oddsNumber,
    oddsText: formatTelegramOdds(oddsNumber),
    stakeNumber,
    stakeText: formatTelegramMoney(stakeNumber),
    potentialNumber,
    potentialText: formatTelegramMoney(potentialNumber),
  };
}

async function getTelegramBookmakerBrandData() {
  // Les libellés texte 1XBET / MELBET sont déjà prévus dans le template.
  // melbet.png du dépôt contient en réalité du WEBP (header RIFF/WEBP),
  // donc on évite volontairement ces deux téléchargements ici.
  return { oneXbet: "", melbet: "" };
}

function escapeXml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function telegramMarketLabel(type: unknown) {
  const raw = String(type || "");
  if (raw === "total_corners") return "corners";
  if (raw === "total_shots") return "tirs";
  if (raw === "total_fouls") return "fautes";
  return "signal";
}

function telegramCalculatedLiveOdds(pred: any) {
  const bookmaker = pickTelegramNumber(pred?.bookmaker_odds, pred?.external_live_odds);
  if (bookmaker !== null && bookmaker > 1) return Number(bookmaker.toFixed(2));

  const modelOdds = safeNumber(
    pred?.model_fair_odds,
    estimatedModelOdds(safeNumber(pred?.probability, 0.50)),
  );
  const snap = pickTelegramNumber(pred?.live_odds);
  const odds = snap !== null && snap > 1 ? snap : modelOdds;
  return Number(Math.min(3.20, Math.max(1.05, odds)).toFixed(2));
}

function telegramSvgLogo(
  dataUri: string,
  x: number,
  y: number,
  size: number,
  initials: string,
) {
  if (dataUri) {
    return `<image href="${dataUri}" x="${x}" y="${y}" width="${size}" height="${size}" preserveAspectRatio="xMidYMid meet"/>`;
  }

  const cx = x + size / 2;
  const cy = y + size / 2;
  return `
    <circle cx="${cx}" cy="${cy}" r="${size / 2 - 2}" fill="#EAF2F8" stroke="#4A94D8" stroke-width="4"/>
    <text x="${cx}" y="${cy + 11}" text-anchor="middle" font-family="Noto Sans" font-size="28" font-weight="700" fill="#1A3B57">${escapeXml(initials)}</text>
  `;
}


/** Affichage du score de la capture. Aucun score de mi-temps n'est inventé. */
function telegramPeriodScores(match: any) {
  const raw = match?.raw_data ?? match?.raw ?? match ?? {};
  const select = (...xs: any[]) => {
    for (const x of xs) {
      if (x === null || x === undefined || x === "") continue;
      const n = Number(x);
      if (Number.isFinite(n) && n >= 0) return n;
    }
    return null;
  };
  const p1h = select(raw?.ht_home,raw?.home_ht,raw?.halftime_home,raw?.first_half_home,raw?.periods?.first?.home,raw?.periods?.[0]?.home);
  const p1a = select(raw?.ht_away,raw?.away_ht,raw?.halftime_away,raw?.first_half_away,raw?.periods?.first?.away,raw?.periods?.[0]?.away);
  const p2h = select(raw?.sh_home,raw?.home_sh,raw?.second_half_home,raw?.periods?.second?.home,raw?.periods?.[1]?.home);
  const p2a = select(raw?.sh_away,raw?.away_sh,raw?.second_half_away,raw?.periods?.second?.away,raw?.periods?.[1]?.away);
  let home = safeNumber(match?.home_score,0), away=safeNumber(match?.away_score,0);
  let detail = "";
  if([p1h,p1a,p2h,p2a].every(x=>x !== null)){
    home=p1h+p2h; away=p1a+p2a;
    detail=home+":"+away+" ("+p1h+":"+p1a+", "+p2h+":"+p2a+")";
  } else if(p1h !== null && p1a !== null && home >= p1h && away >= p1a) {
    const secondStarted=safeNumber(match?.current_minute ?? match?.minute,0)>45;
    if(secondStarted) detail=home+":"+away+" ("+p1h+":"+p1a+", "+(home-p1h)+":"+(away-p1a)+")";
    else detail=home+":"+away+" ("+p1h+":"+p1a+")";
  } else {
    const supplied=String(raw?.score_detail ?? raw?.display_score ?? "").trim();
    // Une chaîne fournie par le fournisseur uniquement, pas de score fictif.
    if(/^\d+:\d+\s*\(\d+:\d+/.test(supplied))detail=supplied.slice(0,34);
  }
  return {home,away,detail};
}

/** Dessin SVG direct : dimensions exactes de la capture, sans Satori. */
// Tracés vectoriels: aucun glyphe dépendant du moteur de polices de Resvg.
let telegramVectorFontsPromise: Promise<{regular:any;bold:any}> | null = null;
async function getTelegramVectorFonts() {
  if (!telegramVectorFontsPromise) telegramVectorFontsPromise = (async () => {
    const module:any = await import("npm:opentype.js@1.3.4");
    const op = module.default?.parse ? module.default : module;
    // Seules deux polices sont nécessaires aux coupons SVG ; ne pas charger
    // ExtraBold ou Satori (anciens chemins responsables du rendu blanc).
    const fontBytes=await Promise.all([
      readBundledTelegramFont("NotoSans-Regular.ttf"),
      readBundledTelegramFont("NotoSans-Bold.ttf")
    ]);
    const fonts={regular:toExactArrayBuffer(fontBytes[0]),bold:toExactArrayBuffer(fontBytes[1])};
    async function parse(bytes:ArrayBuffer, name:string){
      try { const f=op.parse(bytes.slice(0)); if(!f?.unitsPerEm)throw Error("no glyphs"); return f; }
      catch(e:any){
        console.warn("Police locale rejetée, récupération source distante:",name,e?.message);
        const clean=await fetchRemoteFont(name);
        return op.parse(toExactArrayBuffer(clean));
      }
    }
    const [regular,bold]=await Promise.all([
      parse(fonts.regular,"NotoSans-Regular.ttf"),parse(fonts.bold,"NotoSans-Bold.ttf")
    ]);
    return {regular,bold};
  })().catch((e:any)=>{telegramVectorFontsPromise=null;throw e;});
  return await telegramVectorFontsPromise;
}
function telegramVectorText(font:any,x:number,y:number,raw:string,size:number,color:string,anchor:string){
  const str=String(raw??"");
  const width=font.getAdvanceWidth(str,size,{kerning:true});
  const left=anchor==="end"?x-width:anchor==="middle"?x-width/2:x;
  const data=font.getPath(str,left,y,size,{kerning:true}).toPathData(2);
  return '<path fill="'+color+'" d="'+data+'"/>';
}
async function buildTelegramCouponPngDirect(match: any, pred: any): Promise<Uint8Array> {
  // Rendu 429 x 455 pixel : même ratio et placements que le coupon de référence.
  // Pas de Satori, pas de deuxième worker, et aucune cote bookmaker inventée.
  const { Resvg } = await loadTelegramResvgModule();
  await ensureResvgReady();
  const vectorFonts = await getTelegramVectorFonts();
  const esc = escapeXml;
  const dt = pred?.created_at ? new Date(pred.created_at) : new Date();
  const date = Number.isFinite(dt.getTime())
    ? dt.toLocaleDateString("fr-FR", { timeZone: "UTC" }) + " (" +
      dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + ")"
    : formatTelegramSlipDateTime(match);
  const minute = safeNumber(pred?.signal_minute ?? pred?.minute ?? match?.current_minute ?? match?.minute, 0);
  const home = fitText(match?.home_team ?? "Équipe A", 18);
  const away = fitText(match?.away_team ?? "Équipe B", 18);
  const league = fitText(getLeagueName(match), 33);
  // Les statistiques de mi-temps doivent elles aussi venir du snapshot, jamais du match actualisé.
  const raw = {signal_half1_home:pred?.signal_half1_home,signal_half1_away:pred?.signal_half1_away,signal_half2_home:pred?.signal_half2_home,signal_half2_away:pred?.signal_half2_away};
  const getNum = (...values: any[]) => {
    for (const v of values) if (v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v))) return Number(v);
    return null;
  };
  const h1 = getNum(raw?.signal_half1_home);
  const a1 = getNum(raw?.signal_half1_away);
  const h2 = getNum(raw?.signal_half2_home);
  const a2 = getNum(raw?.signal_half2_away);
  const homeScore = h1 !== null && h2 !== null ? h1 + h2 : safeNumber(pred?.signal_home_score ?? pred?.home_score ?? match?.home_score, 0);
  const awayScore = a1 !== null && a2 !== null ? a1 + a2 : safeNumber(pred?.signal_away_score ?? pred?.away_score ?? match?.away_score, 0);
  const periodText = h1 !== null && a1 !== null
    ? (h2 !== null && a2 !== null ? homeScore + ":" + awayScore + " (" + h1 + ":" + a1 + "," + h2 + ":" + a2 + ")" : homeScore + ":" + awayScore + " (" + h1 + ":" + a1 + ")")
    : "";
  const odds = pickTelegramNumber(pred?.live_odds, pred?.odds, pred?.odd, pred?.cote);
  const stake = LIVE_COUPON_STAKE_FCFA;
  const potential = odds !== null && odds > 1 ? Math.round(stake * odds) : null;
  const value = (v: number|null) => v === null ? "—" : v.toFixed(2);
  const money = (v: number|null) => v === null ? "—" : Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g," ")+" F";
  const slip = String(pred?.id ?? pred?.prediction_id ?? match?.id ?? "").replace(/[^a-zA-Z0-9]/g,"").slice(-11);
  const threshold = formatThreshold(pred?.threshold ?? pred?.pronostic ?? pred?.line ?? "");
  const type = formatLivePredictionType(String(pred?.prediction_type ?? pred?.type ?? ""));
  const selection = "Total. ("+threshold+") Plus de. "+type;
  const validationOutcome: "success"|"failure"|null = pred?.__validationOutcome??null;
  const receiptStatus=validationOutcome==="success"?"Payé":validationOutcome==="failure"?"Perdu":"Accepté";
  const slipStatus=validationOutcome==="success"?"Gain":validationOutcome==="failure"?"Perdu":"Accepté";
  const statusColor=validationOutcome==="success"?"#33a766":validationOutcome==="failure"?"#df4545":"#4f96d7";
  const [homeLogo,awayLogo] = await Promise.all([
    getTelegramLogoData(match,"home"), getTelegramLogoData(match,"away")
  ]);
  const football = (x:number,y:number,sz:number) => '<image href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAFF0lEQVR42u1VW2xUVRRd+5y5986LPqZDW8pDkFKKlacFIYApMUBi8Es7H0ZJ0AQT44/GaPTDdj410R/Dh/ERxejHHYwaYwg+QiMGQRSwUKCAUGg70NJ5dQZm7r3nnu1HLZZnSPx155yPk5ystc86e+9FuEswsyQif/L84de/NJWvFZrIEOVIPPjXtg0bKpP3AGgi4psxxJ3AO21bEpG/Z8/RyFhJbfti977v8vkrx5TyDngV94/CcOnI4f6ht0ZKvJSIfCJiZqZ7IrCZZSqR8LMlb8vKdYuPpEezH4/lxx+TgmJaawmtLa391vPpkVeVUz48WvR2MHOYiLirq+sGzFsYbduWiUTC/2DX9y821E9/zzICCAjhHeo9TpZpCmYmEoId1+PGeEzPnzNLllwlCoXC/uHC+OMvd27OAcCkXHQ78Hd2fvVE0ArtKhXHVbniYG37MpnJFXD6/AWEghZ8rSGEwPr25TjU24fc+Lgbj0+3nPLVvYVztZuADp1MEgNgOeVDqa2tjZtaHop7GrtZ+yECwTACMpMrYFHzPDAzIqEQQpaJ1vlzkR4ZRSQckp7jeJFpVc1GpJh9/aVFB2zblqlUiq/r1d3TI4mI8473XCgcme56ns9gQUTwlAIJQkO8DvHaGkyvi6F6WhRlxwERgZnBIFkpl7Wn1Svbu94PJxIJDYBoSk2SlJI/+7bn4Eg2t1L7vk+ALDsOlrQuQKXi4OiJ0wgGLfi+RjgUxNr2pTh49Dh834cQAspTOhaLyaWtCzauarvvR5tZikl5gQ34+teLC1OWgYpHxfeEohVl2NaCSC0wODmBaNwDQMhMNBlCsOBtMjaJk3B67rgZnhKaWXPNDC82bPWAEAnQAFAKB74rN5oP9ydU1NKPLw8sXI5PLQmtEYj+FwXz+U8iEtAc0a8AHLDODshUFsWr8aa9uXwfU8SCExf84sKhbG6yaFmSTgJIDmWY3ldC7j9Z48beWLJYAZV7I5NDXEcTF9GQTCxCI4rotZjQ3IjxdxrP8sTCMA11Ooi9dxY13N1RsabbJmIxGM9Z46M3wlV2DX9dhTCgNDw5BCYE5TA8ZLJbiuh3KlAiJC89zZ6D83AMf1UHZcOK5LR/pOUfrSlRMA0NPTM/ECAOjq2hsgIvX2R6mfotGqhVevFbUACcs00XfmHNqXtCESCgEEKOVjRn0co5ksiqVrCFomtNYctCwxlhkrfjN08WcA6Ojo8Ke0dYcGAMs0djhOWUkSREIwM8MIBCAEQbO+vn2tYZkmGAwiAkAqFI4IKeSnyRe2jtoTs4xv28nvfvJlMhStejOXzTi+r41HVq2ggaFhDAylYRoGmAEGo2N1O473n8Wl0TFVVVVlgHnQgF4+du7PXHd3N99CAIBsm0UiIfzUD/t3NjY0PONVyr6nlP792EkZskzSPJGxUopra6p56cIWv1ipmEqpsYuD6Y3bE5uPdjGLJJG+XkVTLaCzE7qLtXjKMLYOZ64OCSlfu5geMYxAAJpZA6yZiZghp0WjaFkwVyrPPxiPymdpzeITtm3LxBQPuWVcExEnAfaUovpq641MNr9mZmP9502N9SMkhAiGwgHLsqRpmZXW++f+qlzv+Se3PLqOiE5MSjwVL3Bbt/mnbG1muZDoNwBP7+u9UJvJlhZqz61Tksrxhtrzy1tmnp8yLMVU97vnYGZh879T9+ZUmFnezsnuaDh3IaJUKnVd0r6+Pk4mkxr/x3+NvwHWHqQSNvXFqQAAAABJRU5ErkJggg==" x="'+x+'" y="'+y+'" width="'+sz+'" height="'+sz+'"/>';
  const circle = (logo:string,x:number,name:string) => logo
    ? '<image href="'+logo+'" x="'+x+'" y="282" width="34" height="34" preserveAspectRatio="xMidYMid meet"/>'
    : '<circle cx="'+(x+17)+'" cy="299" r="16" fill="#eff2f4" stroke="#a8b6c2"/>'+telegramVectorText(vectorFonts.bold,x+17,303,getTeamInitials(name),9,"#1e3645","middle");
  const tx=(x:number,y:number,txt:string,size:number,color="#1c3242",weight=700,anchor="start") => telegramVectorText(weight>=700?vectorFonts.bold:vectorFonts.regular,x,y,txt,size,color,anchor);
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="429" height="455" viewBox="0 0 429 455">'+
    '<rect width="429" height="455" rx="9" fill="#fff" stroke="#dbe0e5"/>'+
    '<circle cx="42" cy="48" r="25" fill="#ecf1f4"/>'+football(29,35,26)+
    '<circle cx="62" cy="69" r="9" fill="#29b36c"/><path d="M58 69l3 3 5-7" fill="none" stroke="white" stroke-width="1.7"/>'+
    tx(80,34,date,12,"#8698a6")+tx(80,55,"Simple",19)+tx(80,72,"N° "+slip,10,"#24313a",600)+
    '<rect x="348" y="24" width="67" height="14" rx="3" fill="#ef4338"/>'+tx(381.5,34,"• En direct",9,"#fff",700,"middle")+
    '<path d="M0 87h429" stroke="#e4e8eb"/>'+
    tx(16,113,"Cotes:",15,"#8497a5")+tx(16,141,"Mise:",15,"#8497a5")+
    tx(16,167,"Gains potentiels:",15,"#8497a5")+tx(16,193,"Statut:",15,"#8497a5")+
    tx(414,113,value(odds),15,"#1c3242",700,"end")+tx(414,141,money(stake),15,"#1c3242",700,"end")+
    tx(414,167,money(potential),15,"#4dbb69",700,"end")+tx(414,193,receiptStatus,15,statusColor,700,"end")+
    '<path d="M0 211h429" stroke="#eff3f5" stroke-width="8"/><rect x="7" y="219" width="415" height="234" rx="11" fill="#fbfbfb" stroke="#d9e1e7"/>'+
    football(18,235,24)+tx(52,245,"Football · "+league,12,"#8599a7")+tx(52,262,date,12,"#8599a7")+
    '<rect x="352" y="226" width="67" height="13" rx="3" fill="#ef4338"/>'+tx(385.5,235,"• En direct",9,"#fff",700,"middle")+
    tx(139,304,home,13,"#20323f",700,"end")+circle(homeLogo,150,home)+
    tx(216,305,homeScore+":"+awayScore,19,"#20323f",800,"middle")+circle(awayLogo,249,away)+
    tx(292,304,away,13,"#20323f")+
    tx(216,351,periodText,12,"#879da9",400,"middle")+
    '<path d="M8 363h414" stroke="#dbe1e6"/>'+
    tx(19,383,selection,13,"#24333e",700)+tx(412,383,value(odds),14,"#24333e",700,"end")+
    tx(19,410,"EN DIRECT",13,"#869aa7")+tx(412,410,"temps écoulé : "+formatTelegramClock(minute),13,"#24333e",700,"end")+
    tx(19,439,"Statut:",13,"#869aa7")+tx(412,439,slipStatus,13,statusColor,700,"end")+
    '</svg>';
  const renderer = new Resvg(svg,{fitTo:{mode:"original"}});
  const png = renderer.render().asPng();
  if (!png || png.byteLength < 1500) throw new Error("PNG SVG Telegram invalide");
  return png;
}

async function buildTelegramCouponPng(match: any, pred: any): Promise<Uint8Array> {
  const { satori, html, Resvg } = await loadTelegramRenderModules();
  await ensureResvgReady();
  const fonts = await loadFontData();

  const minute = safeNumber(match?.current_minute ?? match?.minute, 0);
  const scoreMain = `${safeNumber(match?.home_score, 0)} : ${safeNumber(match?.away_score, 0)}`;
  const scoreSmall = `${safeNumber(match?.home_score, 0)}:${safeNumber(match?.away_score, 0)} (${safeNumber(match?.home_score, 0)}:${safeNumber(match?.away_score, 0)})`;
  const selectionText = buildTelegramSelectionText(pred);
  const stats = deriveTelegramSlipStats(pred);
  const eventDateText = formatTelegramSlipDateTime(match);
  const elapsed = formatTelegramClock(minute);
  const slipNumber = String(pred?.id ?? pred?.prediction_id ?? match?.id ?? buildCanonicalMatchId(match)).replace(/[^0-9A-Za-z]/g, "").slice(-12) || "87751503787";

  const [{ oneXbet: oneXbetLogoData, melbet: melbetLogoData }, homeLogoData, awayLogoData] = await Promise.all([
    getTelegramBookmakerBrandData(),
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 20);
  const awayName = fitText(match?.away_team ?? "Équipe B", 20);
  const leagueName = fitText(getLeagueName(match), 34);

  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));

  const markup = html(`
    <div style="width:1080px;height:1030px;display:flex;flex-direction:column;background:#eef2f6;color:#16324B;font-family:'Noto Sans';box-sizing:border-box;padding:0;">
      <div style="width:1080px;height:112px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;background:#050505;padding:0 28px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;height:74px;">
          ${oneXbetLogoData
            ? `<img src="${oneXbetLogoData}" width="210" height="68" style="object-fit:contain;" />`
            : `<div style="display:flex;font-size:45px;font-weight:900;font-style:italic;color:#FFFFFF;">1XBET</div>`}
          <div style="display:flex;font-size:22px;font-weight:800;color:#FFFFFF;margin:0 16px;">ou</div>
          ${melbetLogoData
            ? `<img src="${melbetLogoData}" width="205" height="68" style="object-fit:contain;" />`
            : `<div style="display:flex;font-size:45px;font-weight:900;font-style:italic;color:#FFFFFF;">MELBET</div>`}
        </div>
        <div style="height:68px;display:flex;flex-direction:row;align-items:center;background:#F1CF36;border-radius:8px;padding:0 24px;box-sizing:border-box;">
          <div style="display:flex;font-size:33px;font-weight:900;color:#111111;letter-spacing:-0.8px;">CODE PROMO XPVIP</div>
        </div>
      </div>

      <div style="width:100%;padding:18px 18px 26px 18px;box-sizing:border-box;display:flex;">
        <div style="width:1044px;display:flex;flex-direction:column;background:#FFFFFF;border:2px solid #cdd5dd;border-radius:18px;overflow:hidden;">
          <div style="padding:18px 22px 14px 22px;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;box-sizing:border-box;">
            <div style="display:flex;flex-direction:column;">
              <div style="display:flex;font-size:28px;font-weight:500;color:#8fa0ae;">${escapeHtml(eventDateText)}</div>
              <div style="display:flex;flex-direction:row;align-items:center;margin-top:8px;">
                <div style="display:flex;font-size:50px;font-weight:900;color:#1A3B57;line-height:1;">Simple</div>
                <div style="display:flex;font-size:33px;font-weight:500;color:#4D6881;margin-left:14px;line-height:1;">N° ${escapeHtml(slipNumber)}</div>
              </div>
            </div>
            <div style="display:flex;background:#EF3D33;color:#FFFFFF;border-radius:8px;padding:6px 12px;font-size:25px;font-weight:900;line-height:1;">• En direct</div>
          </div>

          <div style="width:100%;height:1px;background:#d8dde2;"></div>

          <div style="padding:18px 22px 16px 22px;display:flex;flex-direction:column;box-sizing:border-box;gap:10px;">
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Cote :</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:#1D3D56;">${escapeHtml(stats.oddsText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Mise :</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:#1D3D56;">${escapeHtml(stats.stakeText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Gains potentiels :</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:#1D3D56;">${escapeHtml(stats.potentialText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Statut :</div>
              <div style="display:flex;flex-direction:row;align-items:center;font-size:34px;font-weight:900;color:#4A94D8;">
                <div style="width:26px;height:26px;border-radius:999px;background:#4A94D8;color:#FFFFFF;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;margin-right:10px;">✓</div>
                Accepté
              </div>
            </div>
          </div>

          <div style="padding:0 12px 14px 12px;display:flex;">
            <div style="width:100%;display:flex;flex-direction:column;background:#FFFFFF;border:1px solid #d8dde2;border-radius:18px;overflow:hidden;">
              <div style="padding:16px 18px 10px 18px;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;">
                <div style="display:flex;flex-direction:row;align-items:flex-start;">
                  <div style="width:34px;height:34px;border-radius:999px;border:3px solid #b2bec8;display:flex;align-items:center;justify-content:center;color:#95A7B6;font-size:18px;margin-right:12px;">⚽</div>
                  <div style="display:flex;flex-direction:column;">
                    <div style="display:flex;font-size:18px;font-weight:800;color:#7e97aa;">Football . ${escapeHtml(leagueName)}</div>
                    <div style="display:flex;margin-top:2px;font-size:15px;font-weight:700;color:#7e97aa;">${escapeHtml(eventDateText)}</div>
                  </div>
                </div>
                <div style="display:flex;background:#EF3D33;color:#FFFFFF;border-radius:7px;padding:5px 10px;font-size:20px;font-weight:900;line-height:1;">• En direct</div>
              </div>

              <div style="padding:6px 24px 10px 24px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
                <div style="width:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:19px;font-weight:800;color:#1D3650;text-align:center;line-height:1.12;min-height:48px;align-items:center;justify-content:center;">${escapeHtml(homeName)}</div>
                  <div style="margin-top:10px;width:76px;height:76px;border-radius:999px;border:2px solid #cad3dc;background:#ffffff;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    ${homeLogoData ? `<img src="${homeLogoData}" width="70" height="70" style="object-fit:contain;border-radius:999px;" />` : `<div style="display:flex;font-size:28px;font-weight:900;color:#5c7389;">${homeInitials}</div>`}
                  </div>
                </div>
                <div style="width:220px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:56px;font-weight:900;color:#15344D;line-height:1;">${escapeHtml(scoreMain)}</div>
                  <div style="display:flex;margin-top:14px;font-size:17px;font-weight:700;color:#7f95a6;">${escapeHtml(scoreSmall)}</div>
                </div>
                <div style="width:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:19px;font-weight:800;color:#1D3650;text-align:center;line-height:1.12;min-height:48px;align-items:center;justify-content:center;">${escapeHtml(awayName)}</div>
                  <div style="margin-top:10px;width:76px;height:76px;border-radius:999px;border:2px solid #cad3dc;background:#ffffff;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    ${awayLogoData ? `<img src="${awayLogoData}" width="70" height="70" style="object-fit:contain;border-radius:999px;" />` : `<div style="display:flex;font-size:28px;font-weight:900;color:#5c7389;">${awayInitials}</div>`}
                  </div>
                </div>
              </div>

              <div style="width:100%;height:1px;background:#d8dde2;"></div>

              <div style="padding:14px 18px 10px 18px;display:flex;flex-direction:column;">
                <div style="display:flex;font-size:33px;font-weight:900;color:#263948;line-height:1.15;">${escapeHtml(selectionText)}</div>
                <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-top:18px;">
                  <div style="display:flex;font-size:27px;font-weight:900;color:#7c95a7;">EN DIRECT</div>
                  <div style="display:flex;font-size:27px;font-weight:900;color:#263948;">temps écoulé : ${escapeHtml(elapsed)}</div>
                </div>
                <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-top:12px;">
                  <div style="display:flex;font-size:28px;font-weight:700;color:#8da0af;">Statut :</div>
                  <div style="display:flex;font-size:31px;font-weight:900;color:#4A94D8;">Accepté</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 1030,
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


async function buildTelegramCouponPngSafe(match: any, pred: any): Promise<Uint8Array> {
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
                  text: "Voir plus de coupons 🔥",
                  url: "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",
                },
              ],
              [
                {
                  text: "S’inscrire ou réinitialiser son compte 🎯",
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
        const res = await richPhotoOrLegacy(
          TELEGRAM_BOT_TOKEN,chatId,pngBytes,caption,
          buttonUrl?[
            [{text:"Voir plus de coupons 🔥",url:"https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",style:"primary"}],
            [{text:"S’inscrire ou réinitialiser son compte 🎯",url:"https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",style:"success"}]
          ]:[],form,`coupon-live-${Date.now()}-${attempt}.png`
        );

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
                text: "Voir plus de coupons 🔥",
                url: "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",
              },
            ],
            [
              {
                text: "S’inscrire ou réinitialiser son compte 🎯",
                url: "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",
              },
            ],
          ],
        }),
      );
    }

    try {
      const res = await richTextOrLegacy(
        TELEGRAM_BOT_TOKEN,chatId,text,
        buttonUrl?[
          [{text:"Voir plus de coupons 🔥",url:"https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",style:"primary"}],
          [{text:"S’inscrire ou réinitialiser son compte 🎯",url:"https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html",style:"success"}]
        ]:[],form
      );

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
  match:any,pred:any,predictionId?:string|number|null,targetChatIds?:string[]
):Promise<TelegramSendResult>{
  try {
    const png=await attachLiveSponsorBanner(await buildTelegramCouponPngDirect(match,{
      ...pred,id:predictionId??pred?.id
    }));
    return await sendTelegramPhoto(
      png,buildTelegramText(match,pred),
      "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/",targetChatIds
    );
  } catch(e:any){
    const err=e?.stack||e?.message||String(e);
    console.error("TELEGRAM_IMAGE_ERROR",err);
    return {ok:false,sentChatIds:[],failedChatIds:sanitizeTelegramTargets(targetChatIds),error:err};
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

  const minute = safeNumber(
    match?.current_minute ?? match?.minute,
    validationType === "final" ? 90 : 0,
  );
  const scoreMain = `${safeNumber(match?.home_score, 0)}:${safeNumber(match?.away_score, 0)}`;
  const scoreSmall = `${safeNumber(match?.home_score, 0)}:${safeNumber(match?.away_score, 0)} (${safeNumber(match?.home_score, 0)}:${safeNumber(match?.away_score, 0)})`;
  const selectionText = buildTelegramSelectionText(pred);
  const baseStats = deriveTelegramSlipStats(pred);
  const eventDateText = formatTelegramSlipDateTime(match);
  const elapsed = formatTelegramClock(minute);
  const slipNumber = String(pred?.id ?? pred?.prediction_id ?? match?.id ?? buildCanonicalMatchId(match)).replace(/[^0-9A-Za-z]/g, "").slice(-12) || "87751346361";

  const [{ oneXbet: oneXbetLogoData, melbet: melbetLogoData }, homeLogoData, awayLogoData] = await Promise.all([
    getTelegramBookmakerBrandData(),
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away"),
  ]);

  const homeName = fitText(match?.home_team ?? "Équipe A", 20);
  const awayName = fitText(match?.away_team ?? "Équipe B", 20);
  const leagueName = fitText(getLeagueName(match), 34);

  const homeInitials = escapeHtml(getTeamInitials(match?.home_team ?? "Home"));
  const awayInitials = escapeHtml(getTeamInitials(match?.away_team ?? "Away"));

  const explicitPaidGain = pickTelegramNumber(
    pred?.validated_gain,
    pred?.paid_gain,
    pred?.potential_gain,
    pred?.gain,
  );
  const payoutNumber = outcome === "success"
    ? (explicitPaidGain ?? baseStats.potentialNumber)
    : (baseStats.stakeNumber != null ? 0 : null);
  const payoutText = formatTelegramMoney(payoutNumber);
  const payoutColor = outcome === "success" ? "#58B967" : "#E35A5A";
  const globalStatus = outcome === "success" ? "Payé" : "Perdu";
  const resultStatus = outcome === "success" ? "Gain" : "Perdu";
  const resultColor = outcome === "success" ? "#58B967" : "#E35A5A";
  const infoBadge = validationType === "instant" ? "• En direct" : "• Terminé";
  const scoreLabel = validationType === "instant" ? `temps écoulé : ${elapsed}` : "match terminé";

  const markup = html(`
    <div style="width:1080px;height:1030px;display:flex;flex-direction:column;background:#eef2f6;color:#16324B;font-family:'Noto Sans';box-sizing:border-box;padding:0;">
      <div style="width:1080px;height:112px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;background:#050505;padding:0 28px;box-sizing:border-box;">
        <div style="display:flex;flex-direction:row;align-items:center;height:74px;">
          ${oneXbetLogoData
            ? `<img src="${oneXbetLogoData}" width="210" height="68" style="object-fit:contain;" />`
            : `<div style="display:flex;font-size:45px;font-weight:900;font-style:italic;color:#FFFFFF;">1XBET</div>`}
          <div style="display:flex;font-size:22px;font-weight:800;color:#FFFFFF;margin:0 16px;">ou</div>
          ${melbetLogoData
            ? `<img src="${melbetLogoData}" width="205" height="68" style="object-fit:contain;" />`
            : `<div style="display:flex;font-size:45px;font-weight:900;font-style:italic;color:#FFFFFF;">MELBET</div>`}
        </div>
        <div style="height:68px;display:flex;flex-direction:row;align-items:center;background:#F1CF36;border-radius:8px;padding:0 24px;box-sizing:border-box;">
          <div style="display:flex;font-size:33px;font-weight:900;color:#111111;letter-spacing:-0.8px;">CODE PROMO XPVIP</div>
        </div>
      </div>

      <div style="width:100%;padding:18px 18px 26px 18px;box-sizing:border-box;display:flex;">
        <div style="width:1044px;display:flex;flex-direction:column;background:#FFFFFF;border:2px solid #cdd5dd;border-radius:18px;overflow:hidden;">
          <div style="padding:18px 22px 14px 22px;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;box-sizing:border-box;">
            <div style="display:flex;flex-direction:row;align-items:flex-start;">
              <div style="width:56px;height:56px;border-radius:999px;background:#eff3f6;color:#AAB8C4;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;margin-right:14px;">⚽</div>
              <div style="display:flex;flex-direction:column;">
                <div style="display:flex;font-size:28px;font-weight:500;color:#8fa0ae;">${escapeHtml(eventDateText)}</div>
                <div style="display:flex;flex-direction:row;align-items:center;margin-top:8px;">
                  <div style="display:flex;font-size:50px;font-weight:900;color:#1A3B57;line-height:1;">Simple</div>
                  <div style="display:flex;font-size:33px;font-weight:500;color:#4D6881;margin-left:14px;line-height:1;">N° ${escapeHtml(slipNumber)}</div>
                </div>
              </div>
            </div>
            <div style="display:flex;background:#EF3D33;color:#FFFFFF;border-radius:8px;padding:6px 12px;font-size:25px;font-weight:900;line-height:1;">${escapeHtml(infoBadge)}</div>
          </div>

          <div style="width:100%;height:1px;background:#d8dde2;"></div>

          <div style="padding:18px 22px 16px 22px;display:flex;flex-direction:column;box-sizing:border-box;gap:10px;">
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Cotes:</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:#1D3D56;">${escapeHtml(baseStats.oddsText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Mise:</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:#1D3D56;">${escapeHtml(baseStats.stakeText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Gains:</div>
              <div style="display:flex;font-size:35px;font-weight:900;color:${payoutColor};">${escapeHtml(payoutText)}</div>
            </div>
            <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;">
              <div style="display:flex;font-size:33px;font-weight:700;color:#8296A7;">Statut:</div>
              <div style="display:flex;font-size:34px;font-weight:900;color:${payoutColor};">${escapeHtml(globalStatus)}</div>
            </div>
          </div>

          <div style="padding:0 12px 14px 12px;display:flex;">
            <div style="width:100%;display:flex;flex-direction:column;background:#FFFFFF;border:1px solid #d8dde2;border-radius:18px;overflow:hidden;">
              <div style="padding:16px 18px 10px 18px;display:flex;flex-direction:row;align-items:flex-start;justify-content:space-between;">
                <div style="display:flex;flex-direction:row;align-items:flex-start;">
                  <div style="width:34px;height:34px;border-radius:999px;border:3px solid #b2bec8;display:flex;align-items:center;justify-content:center;color:#95A7B6;font-size:18px;margin-right:12px;">⚽</div>
                  <div style="display:flex;flex-direction:column;">
                    <div style="display:flex;font-size:18px;font-weight:800;color:#7e97aa;">Football . ${escapeHtml(leagueName)}</div>
                    <div style="display:flex;margin-top:2px;font-size:15px;font-weight:700;color:#7e97aa;">${escapeHtml(eventDateText)}</div>
                  </div>
                </div>
                <div style="display:flex;background:#EF3D33;color:#FFFFFF;border-radius:7px;padding:5px 10px;font-size:20px;font-weight:900;line-height:1;">${escapeHtml(infoBadge)}</div>
              </div>

              <div style="padding:6px 24px 10px 24px;display:flex;flex-direction:row;align-items:center;justify-content:space-between;">
                <div style="width:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:19px;font-weight:800;color:#1D3650;text-align:center;line-height:1.12;min-height:48px;align-items:center;justify-content:center;">${escapeHtml(homeName)}</div>
                  <div style="margin-top:10px;width:76px;height:76px;border-radius:999px;border:2px solid #cad3dc;background:#ffffff;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    ${homeLogoData ? `<img src="${homeLogoData}" width="70" height="70" style="object-fit:contain;border-radius:999px;" />` : `<div style="display:flex;font-size:28px;font-weight:900;color:#5c7389;">${homeInitials}</div>`}
                  </div>
                </div>
                <div style="width:220px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:56px;font-weight:900;color:#15344D;line-height:1;">${escapeHtml(scoreMain)}</div>
                  <div style="display:flex;margin-top:14px;font-size:17px;font-weight:700;color:#7f95a6;">${escapeHtml(scoreSmall)}</div>
                </div>
                <div style="width:250px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
                  <div style="display:flex;font-size:19px;font-weight:800;color:#1D3650;text-align:center;line-height:1.12;min-height:48px;align-items:center;justify-content:center;">${escapeHtml(awayName)}</div>
                  <div style="margin-top:10px;width:76px;height:76px;border-radius:999px;border:2px solid #cad3dc;background:#ffffff;display:flex;align-items:center;justify-content:center;overflow:hidden;">
                    ${awayLogoData ? `<img src="${awayLogoData}" width="70" height="70" style="object-fit:contain;border-radius:999px;" />` : `<div style="display:flex;font-size:28px;font-weight:900;color:#5c7389;">${awayInitials}</div>`}
                  </div>
                </div>
              </div>

              <div style="width:100%;height:1px;background:#d8dde2;"></div>

              <div style="padding:14px 18px 10px 18px;display:flex;flex-direction:column;">
                <div style="display:flex;font-size:33px;font-weight:900;color:#263948;line-height:1.15;">${escapeHtml(selectionText)}</div>
                <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-top:18px;">
                  <div style="display:flex;font-size:27px;font-weight:900;color:#7c95a7;">EN DIRECT</div>
                  <div style="display:flex;font-size:27px;font-weight:900;color:#263948;">${escapeHtml(scoreLabel)}</div>
                </div>
                <div style="display:flex;flex-direction:row;justify-content:space-between;align-items:center;margin-top:12px;">
                  <div style="display:flex;font-size:28px;font-weight:700;color:#8da0af;">Statut:</div>
                  <div style="display:flex;font-size:31px;font-weight:900;color:${resultColor};">${escapeHtml(resultStatus)}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `);

  const svg = await satori(markup, {
    width: 1080,
    height: 1030,
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


async function buildTelegramValidationPngSafe(
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
  outcome: "success" | "failure",  currentValue: number,
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
  match:any,pred:any,outcome:"success"|"failure",currentValue:number,
  validationType:"instant"|"final",predictionId?:string|number|null
){
  try{
    // SVG direct validé: même police que les coupons LIVE, aucun appel Satori.
    const snapshotPred={...pred,id:predictionId??pred?.id,__validationOutcome:outcome};
    const png=await buildTelegramCouponPngDirect(
      {...match,current_minute:match?.current_minute??(validationType==="final"?90:0)},
      snapshotPred
    );
    const result=await sendTelegramPhoto(png,buildTelegramValidationText(pred,outcome,currentValue),
      "https://mrxpronos.github.io/MrXPRONOS_App/prono-live/");
    if(!result.ok)console.error("TELEGRAM_VALIDATION_IMAGE_SEND_FAILED",result.error);
    return result.ok;
  }catch(e:any){
    console.error("TELEGRAM_VALIDATION_IMAGE_FAILED",e?.stack||e?.message||String(e));
    return false; // Aucun fallback texte; la validation persiste et peut être retentée.
  }
}

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


const LIVE_VALUE_MODEL_VERSION = "live-value-v2.0";

type LiveMarketKind = "shots" | "corners" | "fouls";
type LiveSignalTier = "quality" | "value" | "high_value";

const LIVE_MARKET_LINES: Record<LiveMarketKind, number[]> = {
  corners: [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5],
  shots: [15.5, 17.5, 19.5, 21.5, 23.5, 25.5, 27.5, 29.5, 31.5, 33.5],
  fouls: [17.5, 19.5, 21.5, 23.5, 24.5, 25.5, 27.5, 29.5, 31.5],
};

function poissonTail(lambda: number, atLeast: number) {
  if (atLeast <= 0) return 1;
  if (!(lambda > 0)) return 0;

  let term = Math.exp(-lambda);
  let cdf = term;
  for (let k = 1; k < atLeast; k++) {
    term *= lambda / k;
    cdf += term;
  }
  return Math.min(0.995, Math.max(0.005, 1 - cdf));
}

function marketProjectionBuffer(type: LiveMarketKind) {
  if (type === "corners") return 1.5;
  if (type === "shots") return 3.0;
  return 3.0;
}

function candidateProbability(params: {
  current: number;
  threshold: number;
  projected: number;
  heuristicProbability: number;
  reliability: number;
}) {
  const { current, threshold, projected, heuristicProbability, reliability } = params;
  const futureMean = Math.max(0.05, projected - current);
  const additionalNeeded = Math.max(0, Math.floor(threshold) + 1 - current);
  const countProbability = poissonTail(futureMean, additionalNeeded);

  const heuristic = Math.min(0.95, Math.max(0.20, heuristicProbability));
  const rel = Math.min(1, Math.max(0, reliability / 100));
  const blended =
    countProbability * 0.72 +
    heuristic * 0.18 +
    0.50 * 0.10;

  const calibrated = 0.50 + (blended - 0.50) * (0.72 + rel * 0.28);
  return Number(Math.min(0.94, Math.max(0.18, calibrated)).toFixed(4));
}

function estimatedModelOdds(probability: number) {
  const p = Math.min(0.95, Math.max(0.05, probability));
  return Number((1 / p).toFixed(2));
}

function selectMedianCandidate<T>(items: T[]) {
  if (!items.length) return null;
  // 5 éléments -> index 2 (3e). Pour un nombre pair, médiane basse.
  const index = Math.max(0, Math.floor((items.length - 1) / 2));
  return { item: items[index], index };
}

function signalTierFromModelOdds(odds: number): LiveSignalTier | null {
  if (odds >= 1.45 && odds <= 1.75) return "quality";
  if (odds > 1.75 && odds <= 2.30) return "value";
  if (odds > 2.30 && odds <= 3.20) return "high_value";
  return null;
}

function passesTierQuality(params: {
  tier: LiveSignalTier | null;
  probability: number;
  reliability: number;
  dataQuality: number;
}) {
  const { tier, probability, reliability, dataQuality } = params;
  if (!tier) return false;

  if (tier === "quality") {
    return probability >= 0.56 && reliability >= 68 && dataQuality >= 67;
  }
  if (tier === "value") {
    return probability >= 0.43 && reliability >= 72 && dataQuality >= 67;
  }
  return probability >= 0.31 && reliability >= 78 && dataQuality >= 100;
}

function getLineCandidates(params: {
  type: LiveMarketKind;
  current: number;
  projected: number;
  heuristicProbability: number;
  reliability: number;
  minGap?: number;
}) {
  const {
    type,
    current,
    projected,
    heuristicProbability,
    reliability,
    minGap = 2,
  } = params;

  const buffer = marketProjectionBuffer(type);
  const lines = LIVE_MARKET_LINES[type] || [];

  return lines
    .filter((threshold) =>
      current < threshold &&
      threshold - current >= minGap &&
      threshold <= projected + buffer
    )
    .map((threshold) => {
      const probability = candidateProbability({
        current,
        threshold,
        projected,
        heuristicProbability,
        reliability,
      });
      const modelFairOdds = estimatedModelOdds(probability);
      return {
        threshold,
        probability,
        model_fair_odds: modelFairOdds,
        signal_tier: signalTierFromModelOdds(modelFairOdds),
      };
    });
}

function predictionDataQuality(stats: any, type: LiveMarketKind) {
  const completeness = statsCompleteness(stats);
  if (type === "corners") {
    return completeness.corners
      ? (completeness.shots && completeness.shots_on_target ? 100 : 82)
      : 0;
  }
  if (type === "shots") {
    return completeness.shots
      ? (completeness.shots_on_target ? 100 : 82)
      : 0;
  }
  return completeness.fouls ? (completeness.corners || completeness.shots ? 100 : 82) : 0;
}

function buildLivePrediction(params: {
  type: LiveMarketKind;
  predictionType: string;
  titleUnit: string;
  badge: string;
  color: string;
  stats: any;
  minute: number;
  current: number;
  projectedFinal: number;
  heuristicProbability: number;
  reliability: number;
  reasons: string[];
}) {
  const {
    type,
    predictionType,
    titleUnit,
    badge,
    color,
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability,
    reliability,
    reasons,
  } = params;

  const dataQuality = predictionDataQuality(stats, type);
  const candidates = getLineCandidates({
    type,
    current,
    projected: projectedFinal,
    heuristicProbability,
    reliability,
    minGap: 2,
  });
  if (!candidates.length) return null;

  const selected = selectMedianCandidate(candidates);
  if (!selected) return null;

  const chosen: any = selected.item;
  const tier = chosen.signal_tier as LiveSignalTier | null;

  if (!passesTierQuality({
    tier,
    probability: chosen.probability,
    reliability,
    dataQuality,
  })) return null;

  return {
    type: predictionType,
    title: `Over ${chosen.threshold} ${titleUnit}`,
    badge,
    color,
    probability: chosen.probability,
    message: `${current} ${titleUnit} actuellement`,
    threshold: chosen.threshold,
    current,
    signal_value: current,
    projected_value: projectedFinal,
    reliability,
    data_quality_score: dataQuality,
    model_fair_odds: chosen.model_fair_odds,
    signal_tier: tier,
    pricing_mode: "model_only",
    line_candidate_count: candidates.length,
    line_candidate_rank: selected.index + 1,
    line_candidates: candidates,
    model_version: LIVE_VALUE_MODEL_VERSION,
    minute,
    reasons: [
      ...reasons,
      `Projection finale ${projectedFinal}`,
      `Ligne médiane ${selected.index + 1}/${candidates.length}`,
      `Cote modèle ${chosen.model_fair_odds.toFixed(2)}`,
    ],
  };
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
  if (!hasCompleteStatPair(stats, "corner_kicks")) return null;
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

  if (reliability < 63) return null;

  return buildLivePrediction({
    type: "corners",
    predictionType: "total_corners",
    titleUnit: "corners",
    badge: "Corners",
    color: "yellow",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons,
  });
}

function predictTotalShots(stats: any, minute: number, momentum: any) {
  if (!hasCompleteStatPair(stats, "total_shots")) return null;
  const totals = getTotalStats(stats);
  const current = totals.shots;

  if (minute < 15 || minute > 83) return null;
  if (current < 6) return null;

  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({ current, minute, type: "shots", flow: flowData.flow });

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

  if (reliability < 64) return null;

  return buildLivePrediction({
    type: "shots",
    predictionType: "total_shots",
    titleUnit: "tirs",
    badge: "Tirs",
    color: "green",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons,
  });
}

function predictTotalFouls(stats: any, minute: number, momentum: any) {
  if (!hasCompleteStatPair(stats, "fouls")) return null;
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

  let probability = 0.57;
  let reliability = 54;
  const reasons: string[] = [];

  if (current >= 8) { probability += 0.05; reliability += 6; reasons.push(`${current} fautes déjà sifflées`); }
  if (minute >= 25 && minute <= 75) { probability += 0.05; reliability += 5; reasons.push(`Période exploitable`); }
  if (flowData.flow === "defensive") { probability += 0.03; reliability += 3; reasons.push(`Match fermé`); }
  if (flowData.flow === "offensive") { probability -= 0.03; reliability -= 2; }

  probability = Math.min(0.88, Math.max(0.50, probability));
  reliability = Math.min(90, Math.max(40, reliability));

  if (reliability < 62) return null;

  return buildLivePrediction({
    type: "fouls",
    predictionType: "total_fouls",
    titleUnit: "fautes",
    badge: "Fautes",
    color: "orange",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons,
  });
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
  const reliability = Math.min(100, Math.max(0, safeNumber(best.reliability, 0)));
  const dataQuality = Math.min(100, Math.max(0, safeNumber(best.data_quality_score, 0)));
  const probability = Math.min(1, Math.max(0, safeNumber(best.probability, 0)));
  const modelOdds = safeNumber(best.model_fair_odds, estimatedModelOdds(probability || 0.5));
  const bookmakerOdds = safeNumber(best.bookmaker_odds, 0);
  const implied = bookmakerOdds > 1 ? 1 / bookmakerOdds : null;
  const edge = implied != null ? probability - implied : null;
  const ev = bookmakerOdds > 1 ? probability * bookmakerOdds - 1 : null;
  let score = reliability * 0.35 + dataQuality * 0.30 + Math.min(25, Math.max(0, (modelOdds - 1.30) * 20));
  if (edge != null && ev != null) score = reliability * 0.25 + dataQuality * 0.20 + Math.max(0, Math.min(25, edge * 200)) + Math.max(0, Math.min(30, ev * 120));
  return Math.max(0, Math.min(99, Math.round(score)));
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

function getEspnStatNullable(
  competitor: any,
  names: string | string[],
): number | null {
  const wanted = new Set(Array.isArray(names) ? names : [names]);
  const stats = competitor?.statistics || [];

  for (const s of stats) {
    if (wanted.has(String(s?.name || ""))) {
      return nullableNumber(s?.displayValue ?? s?.value);
    }
  }

  return null;
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

  const homeCorners = getEspnStatNullable(home, ["wonCorners", "corners"]);
  const awayCorners = getEspnStatNullable(away, ["wonCorners", "corners"]);
  const homeFouls = getEspnStatNullable(home, ["foulsCommitted", "fouls"]);
  const awayFouls = getEspnStatNullable(away, ["foulsCommitted", "fouls"]);
  const homeShots = getEspnStatNullable(home, ["totalShots", "shotsTotal"]);
  const awayShots = getEspnStatNullable(away, ["totalShots", "shotsTotal"]);
  const homeShotsOnTarget = getEspnStatNullable(home, ["shotsOnTarget", "shotsOnGoal"]);
  const awayShotsOnTarget = getEspnStatNullable(away, ["shotsOnTarget", "shotsOnGoal"]);
  const homePossession = getEspnStatNullable(home, ["possessionPct", "possession"]);
  const awayPossession = getEspnStatNullable(away, ["possessionPct", "possession"]);

  const homeCards = countEspnCards(details, homeTeamId);
  const awayCards = countEspnCards(details, awayTeamId);

  const liveStats = ensureLiveStatsShape({
    home: {
      corner_kicks: homeCorners,
      fouls: homeFouls,
      total_shots: homeShots,
      shots_on_target: homeShotsOnTarget,
      ball_possession: homePossession,
      yellow_cards: homeCards.yellow,
      red_cards: homeCards.red,
    },
    away: {
      corner_kicks: awayCorners,
      fouls: awayFouls,
      total_shots: awayShots,
      shots_on_target: awayShotsOnTarget,
      ball_possession: awayPossession,
      yellow_cards: awayCards.yellow,
      red_cards: awayCards.red,
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
    stats_last_updated_at:
      statsCompleteness(liveStats).core_complete > 0 ? nowIso() : null,
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
    stats_last_updated_at:
      espn?.stats_last_updated_at ||
      original?.stats_last_updated_at ||
      null,
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

function applyPredictionQualityContext(match: any, pred: any) {
  if (!pred) return pred;
  const mergeMeta = match?.raw_data?.merge_meta || {};
  const sourceNames = new Set<string>([
    ...((Array.isArray(mergeMeta?.sources) ? mergeMeta.sources : []) as string[]),
    ...((Array.isArray(match?.raw_data?.stats_sources) ? match.raw_data.stats_sources : []) as string[]),
  ]);
  const sourceCount = sourceNames.size || 1;
  const sourceConfidence = Math.min(100, Math.max(0, safeNumber(mergeMeta?.confidence_score, sourceCount >= 2 ? 75 : 65)));
  const age = statsAgeSeconds(match);
  const freshness = Number.isFinite(age) ? age : null;

  let reliability = safeNumber(pred.reliability, 0);
  let dataQuality = safeNumber(pred.data_quality_score, 0);

  if (sourceCount >= 2 && sourceConfidence >= 72) {
    reliability += Math.min(5, (sourceConfidence - 70) * 0.12);
    dataQuality += 5;
  } else if (sourceConfidence < 60) {
    reliability -= 6;
    dataQuality -= 8;
  }

  if (freshness != null && freshness > 180) {
    reliability -= freshness > 300 ? 12 : 8;
    dataQuality -= freshness > 300 ? 15 : 10;
  }

  reliability = Math.min(98, Math.max(35, reliability));
  dataQuality = Math.min(100, Math.max(0, dataQuality));
  const tier = pred.signal_tier as LiveSignalTier | null;
  const qualityOk = passesTierQuality({ tier, probability: safeNumber(pred.probability, 0), reliability, dataQuality });

  return {
    ...pred,
    reliability: Number(reliability.toFixed(1)),
    data_quality_score: Number(dataQuality.toFixed(1)),
    freshness_seconds: freshness,
    source_count: sourceCount,
    source_confidence: sourceConfidence,
    signal_tier: qualityOk ? tier : null,
    value_score: 0,
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
  ].filter(Boolean)
    .map((p: any) => applyPredictionQualityContext(match, p))
    .map((p: any) => ({ ...p, value_score: computeValueScore(match, [p]) }));

  allPredictions.sort((a: any, b: any) => {
    const av = safeNumber(a?.value_score, 0);
    const bv = safeNumber(b?.value_score, 0);
    if (bv !== av) return bv - av;
    if ((b.reliability || 0) !== (a.reliability || 0)) return (b.reliability || 0) - (a.reliability || 0);
    return (b.probability || 0) - (a.probability || 0);
  });

  const predictions = allPredictions.filter((p: any) => Boolean(p?.signal_tier));

  return {
    ...match,
    momentum_index: momentum,
    pressure_index: momentum,
    predictions,
    all_predictions: allPredictions,
    ai_score: computeAiScore(match, allPredictions),
    value_score: computeValueScore(match, allPredictions),
    reliability_score: allPredictions?.[0]?.reliability || 0,
    data_quality_score: statsCompleteness(stats).score,
    stats_completeness: statsCompleteness(stats),
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

async function processTelegramPredictionById(predictionId: string | number) {
  const id = String(predictionId || "").trim();
  if (!id) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      error: "prediction_id manquant",
    };
  }

  await releaseStaleTelegramClaims();

  const { data: row, error } = await supabase
    .from("live_predictions")
    .select(
      "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, confidence, validated, telegram_sent, telegram_attempts, telegram_last_error, telegram_last_attempt_at, telegram_pending_chat_ids, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa",
    )
    .eq("id", id)
    .maybeSingle();

  if (error) {
    if (isUndefinedColumnError(error)) {
      return {
        telegram_retry_enabled: false,
        telegram_retry_processed: 0,
        telegram_retry_sent: 0,
        telegram_retry_failed: 1,
        telegram_retry_skipped: 0,
        error: "colonnes Telegram retry absentes",
      };
    }
    throw error;
  }

  if (!row) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      error: "prediction introuvable",
    };
  }

  if (row.validated === true) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      error: "prediction déjà validée",
    };
  }

  if (row.telegram_sent === true && row.telegram_last_error !== "__SENDING__") {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_sent: true,
    };
  }

  const currentMatch = await getTelegramMatchFromCache(row, null);
  if (!currentMatch) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      error: "match introuvable dans le cache LIVE",
    };
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

  const claimed = await claimTelegramDelivery(row.id);
  if (!claimed) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_claimed: true,
    };
  }

  const pendingChatIds = Array.isArray(row.telegram_pending_chat_ids)
    ? row.telegram_pending_chat_ids
      .map((chatId: unknown) => String(chatId || "").trim())
      .filter(Boolean)
    : [];

  try {
    const delivery = await sendTelegramLiveCoupon(
      retryMatch,
      retryPred,
      row.id,
      pendingChatIds.length ? pendingChatIds : undefined,
    );

    await markTelegramDelivery(row.id, delivery);

    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 1,
      telegram_retry_sent: delivery.ok ? 1 : 0,
      telegram_retry_failed: delivery.ok ? 0 : 1,
      telegram_retry_skipped: 0,
      prediction_id: row.id,
      sent_chat_ids: delivery.sentChatIds,
      failed_chat_ids: delivery.failedChatIds,
      error: delivery.error,
    };
  } catch (e: any) {
    const failedTargets =
      pendingChatIds.length ? pendingChatIds : telegramChatIds();

    await markTelegramDelivery(row.id, {
      ok: false,
      sentChatIds: [],
      failedChatIds: failedTargets,
      error: e?.message || String(e),
    });

    throw e;
  }
}

async function dispatchOnePendingTelegramRetry(){
  const r=await retryPendingTelegramLiveCoupons([],1);
  return {
    telegram_worker_retry_processed:r.telegram_retry_processed,
    telegram_worker_retry_sent:r.telegram_retry_sent,
    telegram_worker_retry_failed:r.telegram_retry_failed,
    telegram_worker_retry_skipped:r.telegram_retry_skipped,
    telegram_worker_retry_error:null
  };
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
      "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, confidence, validated, telegram_sent, telegram_attempts, telegram_pending_chat_ids, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa",
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
      home_score: row.signal_home_score ?? row.home_score ?? currentMatch.home_score ?? 0,
      away_score: row.signal_away_score ?? row.away_score ?? currentMatch.away_score ?? 0,
      current_minute: row.signal_minute ?? row.minute ?? currentMatch.current_minute ?? 0,
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


const LIVE_COUPON_STAKE_FCFA = 500_000;
const formatReceiptOdds = (n:number) => n.toFixed(2);
const formatReceiptMoney = (n:number) => formatTelegramMoney(n);

// Pricing V2: une cote externe est bookmaker; sinon la cote affichée est la fair odd du modèle.
async function fetchExternalLivePropOdds(match: any, pred: any) {
  if (!LIVE_PROP_ODDS_URL) return null;
  try {
    const url = new URL(LIVE_PROP_ODDS_URL);
    url.searchParams.set("match_id", String(match?.id ?? ""));
    url.searchParams.set("market", String(pred?.type ?? pred?.prediction_type ?? ""));
    url.searchParams.set("line", String(pred?.threshold ?? ""));
    url.searchParams.set("minute", String(pred?.minute ?? match?.current_minute ?? 0));
    const headers: Record<string,string> = { Accept: "application/json" };
    if (LIVE_PROP_ODDS_TOKEN) headers.Authorization = "Bearer " + LIVE_PROP_ODDS_TOKEN;
    const res = await fetch(url.toString(), { headers });
    if (!res.ok) return null;
    const body = await res.json().catch(() => null);
    const raw = body?.odds ?? body?.price ?? body?.decimal_odds ?? body?.data?.odds ?? body?.data?.price ?? body?.data?.decimal_odds;
    const odds = Number(raw);
    if (!Number.isFinite(odds) || odds <= 1.01 || odds > 25) return null;
    return { odds: Number(odds.toFixed(2)), source: String(body?.source || body?.bookmaker || "external_live") };
  } catch (e) {
    console.warn("LIVE prop odds provider unavailable:", e);
    return null;
  }
}

async function computeLiveCouponPricing(match: any, pred: any) {
  const probability = Math.min(0.95, Math.max(0.05, safeNumber(pred?.probability, 0.50)));
  const modelFairOdds = Number(safeNumber(pred?.model_fair_odds, estimatedModelOdds(probability)).toFixed(2));
  const explicit = pickTelegramNumber(pred?.bookmaker_odds, pred?.external_live_odds);
  const external = explicit !== null && explicit > 1
    ? { odds: Number(explicit.toFixed(2)), source: "provided_bookmaker" }
    : await fetchExternalLivePropOdds(match, pred);
  const bookmakerOdds = external?.odds ?? null;
  const rawDisplayOdds = bookmakerOdds ?? modelFairOdds;
  const receiptOdds = Number(Math.min(3.20, Math.max(1.05, rawDisplayOdds)).toFixed(2));
  const impliedProbability = bookmakerOdds ? Number((1 / bookmakerOdds).toFixed(6)) : null;
  const edge = impliedProbability != null ? Number((probability - impliedProbability).toFixed(6)) : null;
  const expectedValue = bookmakerOdds ? Number((probability * bookmakerOdds - 1).toFixed(6)) : null;
  return {
    odds: receiptOdds,
    potentialGain: Math.round(LIVE_COUPON_STAKE_FCFA * receiptOdds),
    source: external ? external.source : "model_fair_odds",
    pricingMode: external ? "external_live" : "model_only",
    modelFairOdds, bookmakerOdds, impliedProbability, edge, expectedValue,
  };
}

function signalPeriodCapture(match:any){
  const raw=match?.raw_data??match?.raw??match??{};
  const first=(...vs:any[])=>{for(const v of vs)if(v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v)))return Number(v);return null};
  return {
    signal_half1_home:first(raw?.ht_home,raw?.home_ht,raw?.halftime_home,raw?.first_half_home),
    signal_half1_away:first(raw?.ht_away,raw?.away_ht,raw?.halftime_away,raw?.first_half_away),
    signal_half2_home:first(raw?.sh_home,raw?.home_sh,raw?.second_half_home,raw?.period2_home),
    signal_half2_away:first(raw?.sh_away,raw?.away_sh,raw?.second_half_away,raw?.period2_away)
  };
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

  // Snapshot du signal pour garder exactement la même cote au retry/à la validation.
  pred.minute = pred.minute ?? match.current_minute ?? 0;
  pred.projected_value = pred.projected_value ?? signalValue;
  pred.signal_value = pred.signal_value ?? signalValue;
  pred.home_score = pred.home_score ?? match.home_score ?? 0;
  pred.away_score = pred.away_score ?? match.away_score ?? 0;

  const livePricing = await computeLiveCouponPricing(match, pred);
  pred.live_odds = livePricing.odds;
  pred.model_fair_odds = livePricing.modelFairOdds;
  pred.bookmaker_odds = livePricing.bookmakerOdds;
  pred.implied_probability = livePricing.impliedProbability;
  pred.edge = livePricing.edge;
  pred.expected_value = livePricing.expectedValue;
  pred.pricing_mode = livePricing.pricingMode;
  pred.stake_fcfa = LIVE_COUPON_STAKE_FCFA;
  pred.potential_gain_fcfa = livePricing.potentialGain;

  if (livePricing.pricingMode === "external_live") {
    const minEdge = pred.signal_tier === "high_value" ? 0.12 : pred.signal_tier === "value" ? 0.08 : 0.05;
    const edge = safeNumber(livePricing.edge, -1);
    const ev = safeNumber(livePricing.expectedValue, -1);
    if (edge < minEdge || ev <= 0) {
      console.log("Value gate: signal rejected against bookmaker price", { match_id: matchId, threshold: thresholdNum, edge, ev, minEdge });
      return { created: false, id: null, skipped: "no_bookmaker_value" };
    }
  }

  const payload: any = {
    match_id: matchId,
    match_name: `${match.home_team} vs ${match.away_team}`,
    home_team: match.home_team ?? null,
    away_team: match.away_team ?? null,
    home_score: pred.home_score,
    away_score: pred.away_score,
    signal_home_score: pred.home_score,
    signal_away_score: pred.away_score,
    signal_minute: pred.minute,
    ...signalPeriodCapture(match),
    live_odds: livePricing.odds,
    stake_fcfa: LIVE_COUPON_STAKE_FCFA,
    potential_gain_fcfa: livePricing.potentialGain,
    odds_source: livePricing.source,

    minute: pred.minute,
    league_name: match.league?.name ?? match.league_name ?? null,

    prediction_type: pred.type,
    probability: pred.probability,
    message: pred.message,

    threshold: thresholdNum,
    signal_value: signalValue,
    projected_value: safeNumber(pred.projected_value, signalValue),
    current_value: signalValue,

    reliability_score: safeNumber(pred.reliability, 0),
    model_fair_odds: livePricing.modelFairOdds,
    bookmaker_odds: livePricing.bookmakerOdds,
    implied_probability: livePricing.impliedProbability,
    edge: livePricing.edge,
    expected_value: livePricing.expectedValue,
    value_score: computeValueScore(match, [{ ...pred, bookmaker_odds: livePricing.bookmakerOdds }]),
    data_quality_score: safeNumber(pred.data_quality_score, match?.data_quality_score ?? 0),
    freshness_seconds: Number.isFinite(safeNumber(pred.freshness_seconds, NaN)) ? safeNumber(pred.freshness_seconds, 0) : null,
    source_count: safeNumber(pred.source_count, 1),
    source_confidence: safeNumber(pred.source_confidence, 0),
    signal_tier: pred.signal_tier ?? null,
    pricing_mode: livePricing.pricingMode,
    line_candidate_count: safeNumber(pred.line_candidate_count, 0),
    line_candidate_rank: safeNumber(pred.line_candidate_rank, 0),
    line_candidates: pred.line_candidates ?? null,
    model_version: pred.model_version ?? LIVE_VALUE_MODEL_VERSION,

    confidence: safeNumber(pred.reliability, 0) >= 80 ? "high" : "medium",
    validated: false,
    outcome: null,

    telegram_sent: false,
    telegram_attempts: 0,
    telegram_last_attempt_at: null,
    telegram_last_error: null,
    telegram_pending_chat_ids: telegramChatIds(),

    updated_at: new Date().toISOString(),
  };

  const existingRunning = await findExistingPredictionId({
    match_id: matchId,
    prediction_type: pred.type,
    threshold: thresholdNum,
    validated: false,
  });
  if (existingRunning) return { created: false, id: existingRunning };

  let { data, error } = await supabase
    .from("live_predictions")
    .insert({ ...payload, created_at: new Date().toISOString() })
    .select("id")
    .single();

  if (error && isUndefinedColumnError(error)) {
    const legacyPayload = { ...payload };
    for (const key of ["signal_value","reliability_score","model_fair_odds","bookmaker_odds","implied_probability","edge","expected_value","value_score","data_quality_score","freshness_seconds","source_count","source_confidence","signal_tier","pricing_mode","line_candidate_count","line_candidate_rank","line_candidates","model_version","final_value","headroom"]) delete legacyPayload[key];
    const retry = await supabase.from("live_predictions").insert({ ...legacyPayload, created_at: new Date().toISOString() }).select("id").single();
    data = retry.data;
    error = retry.error;
  }

  if (error) {
    if (isDuplicateKeyError(error)) {
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

  // Une panne de notifications ne doit jamais empêcher la publication Telegram.
  try { await insertNotification({
    user_id: "all",
    type: "live_prediction",
    title: "Nouvelle opportunité LIVE",
    message:
`${payload.match_name}
Pronostic: ${pred.title}
Minute du signal: ${payload.minute}'
Pronostic (seuil): ${payload.threshold}
Au signal: ${signalValue}
Cote ${livePricing.pricingMode === "external_live" ? "bookmaker" : "modèle"}: ${formatReceiptOdds(livePricing.odds)}
Mise coupon: ${formatReceiptMoney(LIVE_COUPON_STAKE_FCFA)}`,
    priority: pred.probability >= 0.86 ? "urgent" : "normal",
    read: false,
    related_prediction_id: data.id,
  }); }catch(e:any){console.warn("Notification LIVE indisponible, Telegram continue:",e?.message||String(e));}

  let telegramAttempted = false;

  if (options.sendTelegram !== false) {
    const claimed = await claimTelegramDelivery(data.id);

    if (claimed) {
      telegramAttempted = true;
      const telegramDelivery = await sendTelegramLiveCoupon(
        match,
        pred,
        data.id,
      );
      await markTelegramDelivery(data.id, telegramDelivery);
    } else {
      console.log("⏭️ Envoi Telegram ignoré: prediction déjà claimée", {
        prediction_id: data.id,
      });
    }
  } else {
    console.log("📥 Coupon LIVE mis en file Telegram", {
      prediction_id: data.id,
    });
  }

  return {
    created: true,
    id: data.id,
    telegram_attempted: telegramAttempted,
  };
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
    delete cleaned.final_value;
    delete cleaned.headroom;
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
    final_value: params.currentValue,
    headroom: Number((params.currentValue - threshold).toFixed(2)),
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
      delete cleaned.final_value;
      delete cleaned.headroom;
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
    .select("id, match_id, match_name, prediction_type, threshold, validated, telegram_sent, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa")
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
    // Jamais valider avant la publication du coupon initial.
    if(pred.telegram_sent!==true){skipped++;continue;}
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

  const signalValue = p.signal_value ?? p.current_value ?? null;
  const reliability = Math.round(safeNumber(p.reliability_score, (Number(p.probability) || 0) * 100));

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
    projected: p.projected_value ?? null,
    projected_value: p.projected_value ?? null,

    reliability,
    model_fair_odds: p.model_fair_odds ?? null,
    bookmaker_odds: p.bookmaker_odds ?? null,
    implied_probability: p.implied_probability ?? null,
    edge: p.edge ?? null,
    expected_value: p.expected_value ?? null,
    value_score: p.value_score ?? null,
    data_quality_score: p.data_quality_score ?? null,
    freshness_seconds: p.freshness_seconds ?? null,
    source_count: p.source_count ?? null,
    source_confidence: p.source_confidence ?? null,
    signal_tier: p.signal_tier ?? null,
    pricing_mode: p.pricing_mode ?? null,
    line_candidate_count: p.line_candidate_count ?? null,
    line_candidate_rank: p.line_candidate_rank ?? null,
    model_version: p.model_version ?? null,
    final_value: p.final_value ?? null,
    headroom: p.headroom ?? null,
    reasons: [],

    confidence: p.confidence ?? null,
    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,

    created_at: p.created_at ?? null,
    signal_home_score:p.signal_home_score,signal_away_score:p.signal_away_score,
    signal_minute:p.signal_minute,signal_half1_home:p.signal_half1_home,
    signal_half1_away:p.signal_half1_away,signal_half2_home:p.signal_half2_home,
    signal_half2_away:p.signal_half2_away,
    home_score:p.signal_home_score,away_score:p.signal_away_score,
    minute:p.signal_minute,live_odds:p.live_odds,
    stake_fcfa:p.stake_fcfa,potential_gain_fcfa:p.potential_gain_fcfa,
    odds_source:p.odds_source,
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
    .select("id, match_id, prediction_type, probability, message, threshold, current_value, projected_value, confidence, validated, outcome, validation_type, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa, odds_source, signal_value, reliability_score, model_fair_odds, bookmaker_odds, implied_probability, edge, expected_value, value_score, data_quality_score, freshness_seconds, source_count, source_confidence, signal_tier, pricing_mode, line_candidate_count, line_candidate_rank, model_version, final_value, headroom")
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

    uiPreds.sort((a: any, b: any) => {
      const dv = safeNumber(b.value_score, 0) - safeNumber(a.value_score, 0);
      if (dv !== 0) return dv;
      return safeNumber(b.reliability, 0) - safeNumber(a.reliability, 0);
    });

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
    const av = safeNumber(a?.predictions?.[0]?.value_score, a?.value_score);
    const bv = safeNumber(b?.predictions?.[0]?.value_score, b?.value_score);
    if (bv !== av) return bv - av;
    const ar = safeNumber(a?.predictions?.[0]?.reliability, 0);
    const br = safeNumber(b?.predictions?.[0]?.reliability, 0);
    if (br !== ar) return br - ar;
    return safeNumber(b?.predictions?.[0]?.probability, 0) - safeNumber(a?.predictions?.[0]?.probability, 0);
  });

  return withPred.slice(0, 12);
}

// =======================================================
// ROUTES CORE
// =======================================================
function normalizeBsdStatsPayload(payload: any) {
  const raw = payload?.stats || {};
  const home = { ...(raw?.home || {}) };
  const away = { ...(raw?.away || {}) };

  // BSD recommande le shotmap comme décompte de référence des tirs.
  const shotmap = Array.isArray(payload?.shotmap)
    ? payload.shotmap.filter((s: any) => String(s?.sit || "").toLowerCase() !== "shootout")
    : [];

  if (shotmap.length) {
    const homeShots = shotmap.filter((s: any) => s?.home === true);
    const awayShots = shotmap.filter((s: any) => s?.home === false);
    const onTarget = (s: any) => ["goal", "save"].includes(String(s?.type || "").toLowerCase());

    home.total_shots = homeShots.length;
    away.total_shots = awayShots.length;
    home.shots_on_target = homeShots.filter(onTarget).length;
    away.shots_on_target = awayShots.filter(onTarget).length;
  }

  return ensureLiveStatsShape({ home, away });
}

async function loadCachedLiveMatchRows(matchIds: string[]) {
  const ids = [...new Set(matchIds.map(String).filter(Boolean))];
  const map = new Map<string, any>();
  if (!ids.length) return map;

  const { data, error } = await supabase
    .from("matches_live")
    .select("id, raw_data, updated_at")
    .in("id", ids);

  if (error) {
    console.warn("Cache LIVE stats non lisible (ignoré):", error.message);
    return map;
  }

  for (const row of data || []) map.set(String(row.id), row);
  return map;
}

async function reuseCachedStats(matches: any[]) {
  const cache = await loadCachedLiveMatchRows(
    (matches || []).map((m: any) => String(m?.id || "")),
  );

  return (matches || []).map((match: any) => {
    const row = cache.get(String(match?.id));
    const cached = row?.raw_data || null;
    if (!cached) return match;

    const mergedStats = mergeLiveStats(
      cached?.live_stats || cached?.raw_data?.live_stats || {},
      getMatchLiveStats(match),
    );

    return {
      ...match,
      live_stats: mergedStats,
      stats_last_updated_at:
        match?.stats_last_updated_at ||
        cached?.stats_last_updated_at ||
        cached?.raw_data?.stats_last_updated_at ||
        null,
      raw_data: {
        ...(match?.raw_data || {}),
        live_stats: mergedStats,
      },
    };
  });
}

function isBsdNumericEvent(match: any) {
  return /^\d+$/.test(String(match?.id || ""));
}

function statsAgeSeconds(match: any) {
  const raw =
    match?.stats_last_updated_at ||
    match?.raw_data?.stats_last_updated_at ||
    null;
  if (!raw) return Number.POSITIVE_INFINITY;
  const ts = new Date(raw).getTime();
  if (!Number.isFinite(ts)) return Number.POSITIVE_INFINITY;
  return Math.max(0, Math.floor((Date.now() - ts) / 1000));
}

async function enrichLiveMatchesWithBsdStats(matches: any[]) {
  const budget = bsdStatsCallBudget();
  if (budget <= 0) {
    return {
      matches,
      calls: 0,
      enriched: 0,
      failed: 0,
      skipped_quota: true,
    };
  }

  const candidates = (matches || [])
    .filter((m: any) => {
      if (!isBsdNumericEvent(m)) return false;
      const minute = safeNumber(m?.current_minute ?? m?.minute, 0);
      if (minute < 10 || minute > 88) return false;

      const completeness = statsCompleteness(getMatchLiveStats(m));
      return (
        completeness.core_complete < 3 ||
        statsAgeSeconds(m) >= BSD_STATS_REFRESH_SECONDS
      );
    })
    .sort((a: any, b: any) => {
      const ca = statsCompleteness(getMatchLiveStats(a)).core_complete;
      const cb = statsCompleteness(getMatchLiveStats(b)).core_complete;
      if (ca !== cb) return ca - cb; // d'abord les matchs les plus incomplets
      return statsAgeSeconds(b) - statsAgeSeconds(a); // puis les plus anciens
    })
    .slice(0, budget);

  let calls = 0;
  let enriched = 0;
  let failed = 0;

  const out = [...(matches || [])];
  const indexById = new Map(out.map((m: any, i: number) => [String(m?.id), i]));

  for (const match of candidates) {
    try {
      calls++;
      const payload = await fetchBSD(`/events/${match.id}/stats/`);
      const freshStats = normalizeBsdStatsPayload(payload);
      const mergedStats = mergeLiveStats(getMatchLiveStats(match), freshStats);
      const idx = indexById.get(String(match.id));
      if (idx == null) continue;

      out[idx] = {
        ...out[idx],
        live_stats: mergedStats,
        stats_last_updated_at: nowIso(),
        raw_data: {
          ...(out[idx]?.raw_data || {}),
          live_stats: mergedStats,
          stats_last_updated_at: nowIso(),
          stats_sources: [
            ...new Set([
              ...((out[idx]?.raw_data?.stats_sources || []) as string[]),
              "bsd_stats",
            ]),
          ],
        },
      };
      enriched++;
    } catch (e: any) {
      failed++;
      if (isBSDQuotaError(e)) {
        console.warn("⚠️ Quota BSD atteint pendant enrichissement stats; arrêt des appels stats.");
        break;
      }
      console.warn("⚠️ Stats BSD indisponibles pour le match", {
        match_id: match?.id,
        error: e?.message || String(e),
      });
    }
  }

  return {
    matches: out,
    calls,
    enriched,
    failed,
    skipped_quota: false,
  };
}

type RefreshBatchOptions = {
  cursor?: string | null;
  batchSize?: number;
  allowTelegram?: boolean;
  skipBsd?: boolean;
  useSnapshot?: boolean;
};

function stableRefreshMatchId(match: any): string {
  return String(match?.id ?? buildCanonicalMatchId(match));
}

function sortMatchesForRefresh(matches: any[]) {
  return [...(matches || [])].sort((a: any, b: any) =>
    stableRefreshMatchId(a).localeCompare(stableRefreshMatchId(b))
  );
}

async function loadRecentRefreshSnapshot(maxAgeSeconds = 150) {
  const since = new Date(Date.now() - maxAgeSeconds * 1000).toISOString();
  const { data, error } = await supabase
    .from(T_STATS_MERGED)
    .select("merged_match_json, updated_at")
    .gte("updated_at", since)
    .order("updated_at", { ascending: false })
    .limit(500);

  if (error || !data?.length) return [];

  const newest = Math.max(
    ...data.map((r: any) => new Date(r.updated_at).getTime()).filter(Number.isFinite),
  );

  // Les lignes d'un même snapshot sont écrites presque au même instant.
  // On garde uniquement le dernier groupe pour ne pas mélanger deux cycles.
  const recent = data.filter((r: any) => {
    const ts = new Date(r.updated_at).getTime();
    return Number.isFinite(ts) && newest - ts <= 15_000;
  });

  const byId = new Map<string, any>();
  for (const r of recent) {
    const m = r?.merged_match_json;
    if (!m) continue;
    if (m?.is_finished === true) continue;
    const id = stableRefreshMatchId(m);
    if (!byId.has(id)) byId.set(id, m);
  }
  return sortMatchesForRefresh([...byId.values()]);
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
  const allowTelegram = TELEGRAM_IN_REFRESH && options.allowTelegram !== false;
  const refreshAt = nowIso();

  let allRawMatches: any[] = [];
  let sourceRows: any[] = [];
  let sourceMeta: any = {
    original_source_matches: 0,
    espn_source_matches: 0,
    duplicates_merged: 0,
    espn_only_matches: 0,
    espn_enabled: ENABLE_ESPN_MERGE,
  };
  let espnError: string | null = null;
  let bsdError: string | null = null;
  let bsdRateLimited = false;
  let snapshotReused = false;
  let coverage: any = null;

  // Les lots 2+ réutilisent le snapshot complet créé par le premier lot.
  // C'est le point essentiel : un refresh = au maximum UN appel BSD /events/live/.
  if (options.useSnapshot) {
    allRawMatches = await loadRecentRefreshSnapshot();
    snapshotReused = allRawMatches.length > 0;
  }

  if (!snapshotReused) {
    let originalRawMatches: any[] = [];

    coverage = await fetchBSDCoverage();
    const liveNow = safeNumber(coverage?.live_now, -1);

    if (!options.skipBsd && liveNow !== 0) {
      try {
        const liveData = await fetchBSD("/events/live/");
        originalRawMatches = bsdResults(liveData);
      } catch (e: any) {
        bsdError = e?.message || String(e);
        bsdRateLimited = isBSDQuotaError(e);
        if (bsdRateLimited) {
          console.warn("⚠️ Quota BSD épuisé: ESPN + cache prennent le relais");
        } else {
          console.error("⚠️ BSD v2 live indisponible: ESPN prend le relais", e);
        }
      }
    }

    const espnResult = await fetchEspnLiveMatchesForMerge();
    espnError = espnResult.error;

    const merged = mergeOriginalAndEspnMatches(
      originalRawMatches,
      espnResult.matches || [],
    );

    allRawMatches = sortMatchesForRefresh(merged.mergedMatches);
    sourceRows = merged.sourceRows || [];
    sourceMeta = merged.meta || sourceMeta;

    // /events/live/ est compact et ne fournit pas les stats détaillées.
    // 1) on réutilise d'abord notre dernier snapshot connu;
    // 2) ESPN complète gratuitement ce qu'il possède;
    // 3) BSD /stats/ enrichit seulement quelques matchs prioritaires par cycle.
    allRawMatches = await reuseCachedStats(allRawMatches);

    const statsEnrichment = await enrichLiveMatchesWithBsdStats(allRawMatches);
    allRawMatches = sortMatchesForRefresh(statsEnrichment.matches);
    sourceMeta = {
      ...sourceMeta,
      bsd_stats_calls: statsEnrichment.calls,
      bsd_stats_enriched: statsEnrichment.enriched,
      bsd_stats_failed: statsEnrichment.failed,
      bsd_stats_skipped_quota: statsEnrichment.skipped_quota,
      bsd_quota_remaining: bsdQuotaRemaining,
      bsd_quota_reset_seconds: bsdQuotaResetSeconds,
    };

    // Snapshot COMPLET persistant avant de découper en lots.
    // Les invocations enfants suivantes lisent exactement ces mêmes matchs
    // sans rappeler BSD ni ESPN.
    if (allRawMatches.length) {
      await persistStatsSourcesAndMerged(sourceRows, allRawMatches);
    }
  }

  const candidates = cursor
    ? allRawMatches.filter(
      (m: any) => stableRefreshMatchId(m).localeCompare(cursor) > 0,
    )
    : allRawMatches;

  const rawMatches = candidates.slice(0, batchSize);
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
        original_source_matches: safeNumber(sourceMeta.original_source_matches, 0),
        espn_source_matches: safeNumber(sourceMeta.espn_source_matches, 0),
        bsd_stats_calls: safeNumber(sourceMeta.bsd_stats_calls, 0),
        bsd_stats_enriched: safeNumber(sourceMeta.bsd_stats_enriched, 0),
        bsd_stats_failed: safeNumber(sourceMeta.bsd_stats_failed, 0),
        bsd_quota_remaining: sourceMeta.bsd_quota_remaining ?? bsdQuotaRemaining,
        duplicates_merged: safeNumber(sourceMeta.duplicates_merged, 0),
        espn_only_matches: safeNumber(sourceMeta.espn_only_matches, 0),
        espn_enabled: ENABLE_ESPN_MERGE,
        espn_error: espnError,
        bsd_error: bsdError,
        bsd_rate_limited: bsdRateLimited,
        bsd_skipped: options.skipBsd === true || safeNumber(coverage?.live_now, -1) === 0,
        snapshot_reused: snapshotReused,
        telegram_in_refresh: allowTelegram,
        predictions_created: 0,
        predictions_existing: 0,
        predictions_failed: 0,
      },
    };
  }

  const normalizedMatches = rawMatches.map((m: any) =>
    normalizeMatch(m, refreshAt)
  );

  await cacheLiveMatches(rawMatches, refreshAt);

  let createdPreds = 0;
  let existingPreds = 0;
  let failedPreds = 0;
  const freshTelegramIds: string[] = [];

  for (const m of normalizedMatches) {
    for (const pred of m.predictions || []) {
      try {
        const res = await savePrediction(m, pred, { sendTelegram: false });
        if (res.created) { createdPreds++; if(res.id)freshTelegramIds.push(String(res.id)); }
        else existingPreds++;
      } catch (e) {
        failedPreds++;
        console.error("savePrediction failed (ignored):", e);
      }
    }
  }

  // Un nouveau coupon doit être publié avant toute validation.
  const noTelegram=()=>({telegram_retry_enabled:true,telegram_retry_processed:0,telegram_retry_sent:0,telegram_retry_failed:0,telegram_retry_skipped:0});
  let telegramRetry:any=noTelegram();
  if(allowTelegram){
    try{
      telegramRetry=freshTelegramIds.length
        ? await processTelegramPredictionById(freshTelegramIds[0])
        : await retryPendingTelegramLiveCoupons(normalizedMatches,1);
    }catch(e:any){
      console.error("Nouvelle publication Telegram prioritaire échouée:",e);
      telegramRetry={...noTelegram(),telegram_retry_failed:1};
    }
  }
  const imageBudgetRemaining=allowTelegram && telegramRetry.telegram_retry_processed===0;
  const instant=await validatePredictionsInPlay(normalizedMatches,{
    maxInstantValidations:imageBudgetRemaining?1:0,
    sendTelegram:imageBudgetRemaining,
  });

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
      original_source_matches: safeNumber(sourceMeta.original_source_matches, 0),
      espn_source_matches: safeNumber(sourceMeta.espn_source_matches, 0),
      bsd_stats_calls: safeNumber(sourceMeta.bsd_stats_calls, 0),
      bsd_stats_enriched: safeNumber(sourceMeta.bsd_stats_enriched, 0),
      bsd_stats_failed: safeNumber(sourceMeta.bsd_stats_failed, 0),
      bsd_quota_remaining: sourceMeta.bsd_quota_remaining ?? bsdQuotaRemaining,
      duplicates_merged: safeNumber(sourceMeta.duplicates_merged, 0),
      espn_only_matches: safeNumber(sourceMeta.espn_only_matches, 0),
      espn_enabled: ENABLE_ESPN_MERGE,
      espn_error: espnError,
      bsd_error: bsdError,
      bsd_rate_limited: bsdRateLimited,
      bsd_skipped: options.skipBsd === true || safeNumber(coverage?.live_now, -1) === 0,
      snapshot_reused: snapshotReused,
      telegram_in_refresh: allowTelegram,
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
  skipBsd = false,
  useSnapshot = false,
) {
  const endpoint = new URL(
    `${SUPABASE_URL.replace(/\/$/, "")}/functions/v1/live/refresh/batch`,
  );

  endpoint.searchParams.set("batch_size", String(batchSize));
  endpoint.searchParams.set("allow_telegram", allowTelegram ? "1" : "0");
  endpoint.searchParams.set("skip_bsd", skipBsd ? "1" : "0");
  endpoint.searchParams.set("use_snapshot", useSnapshot ? "1" : "0");
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
  let skipBsd = false;

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
          skipBsd,
          batchNumber > 0,
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

    // Une fois le quota BSD détecté sur un lot, les lots suivants de CE refresh
    // n'appellent plus BSD et utilisent ESPN uniquement.
    if (meta.bsd_rate_limited) skipBsd = true;

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
    aggregate.bsd_rate_limited =
      aggregate.bsd_rate_limited || Boolean(meta.bsd_rate_limited);
    if (meta.bsd_skipped) aggregate.bsd_skipped_batches++;

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
    .select("id, match_id, match_name, prediction_type, threshold, league_name, validated, created_at, telegram_sent, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa")
    .eq("validated", false)
    .order("created_at", { ascending: false });

  if (pendingError) throw pendingError;
  if (!pending?.length) return { validated: 0, skipped: 0, failed: 0 };

  let validated = 0;
  let skipped = 0;
  let failed = 0;

  for (const pred of pending) {
    // Le coupon accepté doit toujours précéder le résultat.
    if(pred.telegram_sent!==true){skipped++;continue;}
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
        user_id: "all",        type: "prediction_validated",
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
    created_at:p.created_at,
    signal_home_score:p.signal_home_score,signal_away_score:p.signal_away_score,
    signal_minute:p.signal_minute,
    signal_half1_home:p.signal_half1_home,signal_half1_away:p.signal_half1_away,
    signal_half2_home:p.signal_half2_home,signal_half2_away:p.signal_half2_away,
    home_score:p.signal_home_score??p.home_score??0,
    away_score:p.signal_away_score??p.away_score??0,
    minute:p.signal_minute??p.minute??null,
    live_odds:p.live_odds,stake_fcfa:p.stake_fcfa,
    potential_gain_fcfa:p.potential_gain_fcfa,odds_source:p.odds_source
  };
}

// =======================================================
// PRONOSTICS DU JOUR — intégré à la fonction live
// =======================================================
// Le frontend ne dépend plus d'une Edge Function "daily-pronos" séparée.
// Si daily_predictions n'existe pas encore ou est vide, on affiche
// immédiatement les pronostics de la table pronostics comme fallback.

function dailyTodayUtc() {
  return new Date().toISOString().slice(0, 10);
}

function dailyNormTeam(v: unknown) {
  return stripAccents(String(v ?? ""))
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\b(fc|cf|sc|afc|club|football|soccer|the|de|da|do)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function dailyTeamSimilarity(a: unknown, b: unknown) {
  const aa = dailyNormTeam(a);
  const bb = dailyNormTeam(b);
  if (!aa || !bb) return 0;
  if (aa === bb) return 1;
  if (aa.includes(bb) || bb.includes(aa)) return 0.92;

  const as = new Set(aa.split(" ").filter(Boolean));
  const bs = new Set(bb.split(" ").filter(Boolean));
  let intersection = 0;
  for (const x of as) if (bs.has(x)) intersection++;
  const union = new Set([...as, ...bs]).size || 1;
  return intersection / union;
}

function dailyEventHome(ev: any) {
  return ev?.home_team?.name ??
    ev?.home_team ??
    ev?.home?.name ??
    ev?.teams?.home?.name ??
    "";
}

function dailyEventAway(ev: any) {
  return ev?.away_team?.name ??
    ev?.away_team ??
    ev?.away?.name ??
    ev?.teams?.away?.name ??
    "";
}

function dailyEventLeague(ev: any) {
  return ev?.league?.name ??
    ev?.competition?.name ??
    ev?.league_name ??
    "Football";
}

function dailyEventKickoff(ev: any) {
  return ev?.event_date ??
    ev?.start_time ??
    ev?.date ??
    ev?.kickoff ??
    null;
}

function dailyEventId(ev: any) {
  return ev?.id ?? ev?.event_id ?? null;
}

function dailyEventTeamId(ev: any, side: "home" | "away") {
  const team = side === "home"
    ? (ev?.home_team_obj ?? ev?.home ?? ev?.teams?.home ?? ev?.home_team)
    : (ev?.away_team_obj ?? ev?.away ?? ev?.teams?.away ?? ev?.away_team);

  return (
    team?.id ??
    team?.api_id ??
    team?.team_id ??
    ev?.[side + "_team_id"] ??
    ev?.[side + "_id"] ??
    null
  );
}

function dailyEventLogo(ev: any, side: "home" | "away") {
  const team = side === "home"
    ? (ev?.home_team_obj ?? ev?.home ?? ev?.teams?.home ?? ev?.home_team)
    : (ev?.away_team_obj ?? ev?.away ?? ev?.teams?.away ?? ev?.away_team);

  const direct =
    team?.logo_url ??
    team?.logo ??
    team?.image_url ??
    team?.image ??
    ev?.[side + "_logo"] ??
    null;

  if (typeof direct === "string" && direct.trim()) return direct;

  const teamId = dailyEventTeamId(ev, side);
  if (teamId != null && /^\d+$/.test(String(teamId))) {
    return `${BSD_IMG_BASE}/team/${teamId}/?bg=transparent`;
  }

  return null;
}

function dailyResultRows(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}

function dailyFindEventForProno(prono: any, events: any[]) {
  const ph = prono?.home_team;
  const pa = prono?.away_team;
  let best: any = null;
  let bestScore = 0;

  for (const ev of events || []) {
    const direct =
      dailyTeamSimilarity(ph, dailyEventHome(ev)) * 0.5 +
      dailyTeamSimilarity(pa, dailyEventAway(ev)) * 0.5;

    const reverse =
      dailyTeamSimilarity(ph, dailyEventAway(ev)) * 0.5 +
      dailyTeamSimilarity(pa, dailyEventHome(ev)) * 0.5;

    const score = Math.max(direct, reverse);
    if (score > bestScore) {
      bestScore = score;
      best = ev;
    }
  }

  return bestScore >= 0.78 ? best : null;
}

function dailyCollectOddsObjects(value: any, out: any[] = [], depth = 0): any[] {
  if (depth > 8 || value == null) return out;

  if (Array.isArray(value)) {
    for (const x of value) dailyCollectOddsObjects(x, out, depth + 1);
    return out;
  }

  if (typeof value !== "object") return out;

  const hasOdds =
    value.decimal_odds != null ||
    value.odds_decimal != null ||
    value.odds != null ||
    value.price != null;

  const hasMarket =
    value.market != null ||
    value.market_type != null ||
    value.market_name != null;

  const hasOutcome =
    value.outcome != null ||
    value.selection != null ||
    value.name != null;

  if (hasOdds && hasMarket && hasOutcome) out.push(value);

  for (const x of Object.values(value)) {
    if (x && typeof x === "object") {
      dailyCollectOddsObjects(x, out, depth + 1);
    }
  }

  return out;
}

function dailyNormMarket(v: unknown) {
  return String(v ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function dailyNormOutcome(v: unknown) {
  return String(v ?? "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "");
}

function dailyOutcomeAliases(wanted: string) {
  const target = dailyNormOutcome(wanted);

  if (target === "1X") {
    return new Set([
      "1X", "HOME_DRAW", "HOMEDRAW", "HOMEORDRAW",
      "HOME_OR_DRAW", "1_X", "HD",
    ]);
  }

  if (target === "X2") {
    return new Set([
      "X2", "DRAW_AWAY", "DRAWAWAY", "DRAWORAWAY",
      "DRAW_OR_AWAY", "X_2", "DA",
    ]);
  }

  return new Set([
    "12", "HOME_AWAY", "HOMEAWAY", "HOMEORAWAY",
    "HOME_OR_AWAY", "1_2", "HA",
  ]);
}

function dailyOutcomeKey(v: unknown) {
  return String(v ?? "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function dailyExtractPrice(v: any): number | null {
  if (typeof v === "number" || typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) && n > 1.01 ? Number(n.toFixed(2)) : null;
  }

  if (!v || typeof v !== "object") return null;

  for (const key of [
    "price", "odds", "decimal_odds", "odds_decimal",
    "value", "consensus_price",
  ]) {
    const n = Number(v?.[key]);
    if (Number.isFinite(n) && n > 1.01) return Number(n.toFixed(2));
  }

  return null;
}

function dailyExtractTargetFromMap(value: any, aliases: Set<string>): number | null {
  if (!value || typeof value !== "object") return null;

  for (const [key, raw] of Object.entries(value)) {
    if (aliases.has(dailyOutcomeKey(key))) {
      const price = dailyExtractPrice(raw);
      if (price != null) return price;
    }
  }

  return null;
}

function dailyPickDoubleChanceOdds(payload: any, wanted: string) {
  const aliases = dailyOutcomeAliases(wanted);

  // Formes directes utilisées par le consensus / détail événement.
  const directContainers = [
    payload?.odds?.double_chance,
    payload?.double_chance,
    payload?.consensus?.double_chance,
    payload?.odds_consensus?.double_chance,
    payload?.markets?.double_chance,
  ];

  for (const container of directContainers) {
    const price = dailyExtractTargetFromMap(container, aliases);
    if (price != null) {
      return { odds: price, source: "consensus" };
    }
  }

  const marketCandidates: any[] = [];

  function walk(value: any, depth = 0) {
    if (depth > 8 || value == null) return;

    if (Array.isArray(value)) {
      for (const x of value) walk(x, depth + 1);
      return;
    }

    if (typeof value !== "object") return;

    const marketName = dailyNormMarket(
      value?.market ??
      value?.market_type ??
      value?.market_name ??
      value?.market_kind ??
      value?.market_family ??
      value?.kind ??
      value?.family,
    );

    const looksDc =
      marketName.includes("double_chance") ||
      marketName === "dc" ||
      marketName.startsWith("dc_") ||
      marketName.includes("doublechance");

    if (looksDc) marketCandidates.push(value);

    for (const x of Object.values(value)) {
      if (x && typeof x === "object") walk(x, depth + 1);
    }
  }

  walk(payload);

  const prices: number[] = [];

  for (const market of marketCandidates) {
    // Prix consensus directement attachés au marché.
    for (const container of [
      market?.prices,
      market?.consensus,
      market?.consensus_prices,
      market?.odds,
      market?.selections,
    ]) {
      const direct = dailyExtractTargetFromMap(container, aliases);
      if (direct != null) prices.push(direct);
    }

    // Forme flattened : { outcome: "1X", price: 1.25 }.
    const outcome = dailyOutcomeKey(
      market?.outcome ??
      market?.selection ??
      market?.name,
    );
    if (aliases.has(outcome)) {
      const p = dailyExtractPrice(market);
      if (p != null) prices.push(p);
    }

    // Forme markets[].bookmakers[].prices.{HOME_DRAW|1X|...}
    for (const book of market?.bookmakers || []) {
      const p = dailyExtractTargetFromMap(
        book?.prices ?? book?.odds ?? book,
        aliases,
      );
      if (p != null) prices.push(p);
    }
  }

  // Ancienne forme flattened conservée en dernier recours.
  for (const row of dailyCollectOddsObjects(payload)) {
    const market = dailyNormMarket(
      row?.market ?? row?.market_type ?? row?.market_name,
    );
    const outcome = dailyOutcomeKey(
      row?.outcome ?? row?.selection ?? row?.name,
    );

    if (
      (market.includes("double_chance") || market.startsWith("dc_")) &&
      aliases.has(outcome)
    ) {
      const p = dailyExtractPrice(row);
      if (p != null) prices.push(p);
    }
  }

  if (!prices.length) return null;

  // Si plusieurs bookmakers sont présents mais aucun champ consensus explicite,
  // on utilise leur moyenne comme consensus, jamais le "meilleur prix".
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  return {
    odds: Number(avg.toFixed(2)),
    source: prices.length > 1 ? "consensus_avg" : "consensus",
  };
}

function dailyTableMissing(error: any) {
  const code = String(error?.code || "");
  const message = String(error?.message || "").toLowerCase();

  return (
    code === "42P01" ||
    code === "PGRST205" ||
    message.includes("daily_predictions") &&
      (
        message.includes("could not find") ||
        message.includes("does not exist") ||
        message.includes("schema cache")
      )
  );
}

function dailySourceOdds(p: any): number | null {
  const candidates = [
    p?.odds_snapshot,
    p?.consensus_odds,
    p?.bookmaker_odds,
    p?.odds,
    p?.odd,
    p?.cote,
  ];

  for (const value of candidates) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 1.01) {
      return Number(n.toFixed(2));
    }
  }

  return null;
}

function dailyIsLikelyFootball(p: any) {
  const text = [
    p?.competition,
    p?.league_name,
    p?.league,
    p?.home_team,
    p?.away_team,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  // Le fournisseur amont a déjà renvoyé quelques rencontres d'autres sports
  // malgré l'endpoint football (ex.: NPB/baseball, Basketball). On les bloque
  // avant de les publier dans "Pronostics du jour".
  return !/\b(npb|mlb|kbo|cpbl|baseball|basketball|basket|nba|wnba|nhl|ice hockey|hockey|cricket|volleyball|handball|nfl|american football)\b/i.test(text);
}

let dailySiteDataCache: { at: number; byId: Map<string, any> } | null = null;
const DAILY_SITE_DATA_TTL_MS = 10 * 60 * 1000;

async function dailyLoadSiteDataMap() {
  const now = Date.now();
  if (
    dailySiteDataCache &&
    now - dailySiteDataCache.at < DAILY_SITE_DATA_TTL_MS
  ) {
    return dailySiteDataCache.byId;
  }

  const byId = new Map<string, any>();

  try {
    const base = SITE_URL.replace(/\/$/, "");
    const res = await fetch(`${base}/data.json`, {
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const payload = await res.json();
    for (const row of payload?.matches || []) {
      if (row?.id != null) byId.set(String(row.id), row);
    }

    dailySiteDataCache = { at: now, byId };
  } catch (e: any) {
    console.warn("data.json public indisponible pour les logos daily:", e?.message || String(e));
    dailySiteDataCache = { at: now, byId };
  }

  return byId;
}

function dailyAbsoluteSiteAsset(path: unknown) {
  const raw = String(path || "").trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return raw;

  const base = SITE_URL.replace(/\/$/, "");
  return `${base}/${raw.replace(/^\/+/, "")}`;
}

async function dailyEnrichSourceRows(sourceRows: any[]) {
  const byId = await dailyLoadSiteDataMap();

  return (sourceRows || []).map((p: any) => {
    const raw = byId.get(String(p?.match_id ?? p?.id ?? ""));
    if (!raw) return p;

    return {
      ...p,
      home_logo:
        p?.home_logo ??
        dailyAbsoluteSiteAsset(raw?.home_logo),
      away_logo:
        p?.away_logo ??
        dailyAbsoluteSiteAsset(raw?.away_logo),
      event_date:
        p?.event_date ??
        raw?.event_date ??
        null,
      competition:
        p?.competition ??
        raw?.league ??
        null,
    };
  });
}

async function dailyGetSourcePronos(date: string) {
  const { data, error } = await supabase
    .from("pronostics")
    .select("*")
    .eq("date", date)
    .order("xpronos_score", { ascending: false });

  if (error) throw error;

  return (data || []).filter((p: any) => {
    const pick = String(p?.prediction || "").toUpperCase();
    return ["1X", "X2", "12"].includes(pick) && dailyIsLikelyFootball(p);
  });
}

function dailyFallbackRows(date: string, sourceRows: any[]) {
  return (sourceRows || []).map((p: any) => {
    const outcome = String(p?.prediction || "").toUpperCase();
    const odds = dailySourceOdds(p);
    const stake = DAILY_DEFAULT_STAKE;

    return {
      id: `source-${String(p?.match_id ?? p?.id ?? crypto.randomUUID())}`,
      prediction_date: date,
      source_match_id: String(p?.match_id ?? p?.id ?? ""),
      bsd_event_id: null,
      home_team: p?.home_team ?? "Équipe domicile",
      away_team: p?.away_team ?? "Équipe extérieure",
      league_name:
        p?.competition ??
        p?.league_name ??
        p?.league ??
        "Football",
      kickoff:
        p?.event_date ??
        p?.kickoff ??
        p?.start_time ??
        date,
      home_logo: p?.home_logo ?? null,
      away_logo: p?.away_logo ?? null,
      market_type: "double_chance",
      market_label: `Double chance ${outcome}`,
      outcome,
      line: null,
      odds_snapshot: odds,
      odds_source: odds ? "source" : null,
      odds_captured_at: p?.updated_at ?? p?.created_at ?? null,
      stake,
      potential_gain: odds ? Math.round(stake * odds) : null,
      confidence: safeNumber(p?.confidence, 0),
      xpronos_score: safeNumber(p?.xpronos_score, 0),
      source_category: p?.category ?? null,
      source_badge: p?.badge ?? null,
      status: "accepted",
      validated: false,
      fallback_source: true,
    };
  });
}

async function dailyGetForUi(date: string) {
  const stored = await supabase
    .from("daily_predictions")
    .select("*")
    .eq("prediction_date", date)
    .order("kickoff", { ascending: true });

  if (!stored.error && stored.data?.length) {
    return {
      date,
      predictions: stored.data,
      count: stored.data.length,
      source: "daily_predictions",
      snapshot_available: true,
    };
  }

  if (stored.error && !dailyTableMissing(stored.error)) {
    console.warn("daily_predictions read failed; fallback pronostics:", stored.error);
  }

  let sourceRows: any[] = [];
  try {
    sourceRows = await dailyGetSourcePronos(date);
    sourceRows = await dailyEnrichSourceRows(sourceRows);
  } catch (e) {
    console.error("Fallback pronostics du jour indisponible:", e);
  }

  const fallback = dailyFallbackRows(date, sourceRows);

  return {
    date,
    predictions: fallback,
    count: fallback.length,
    source: "pronostics_fallback",
    snapshot_available: false,
    daily_predictions_table_missing:
      Boolean(stored.error && dailyTableMissing(stored.error)),
  };
}


async function dailyFetchAllEventsForDate(date: string) {
  const all: any[] = [];
  const pageSize = 200;

  for (let offset = 0; offset < 1200; offset += pageSize) {
    const payload = await fetchBSD("/events/", {
      date_from: date,
      date_to: date,
      limit: String(pageSize),
      offset: String(offset),
    });

    const rows = dailyResultRows(payload);
    all.push(...rows);

    const total = safeNumber(payload?.count, all.length);
    if (rows.length < pageSize || all.length >= total) break;
  }

  return all;
}

async function dailyFetchBsdConsensusDoubleChance(
  eventIdValue: string | number,
  outcome: string,
) {
  const target = String(outcome || "").toUpperCase();
  if (!["1X", "12", "X2"].includes(target)) return null;

  const payload = await fetchBSD("/odds/", {
    event_id: String(eventIdValue),
    market: "double_chance",
    outcome: target,
    limit: "20",
  });

  const rows = dailyResultRows(payload);
  const candidates = rows
    .map((row: any) => ({
      odds: safeNumber(
        row?.decimal_odds ??
          row?.odds_decimal ??
          row?.price ??
          row?.odds,
        0,
      ),
      bookmaker_slug: String(row?.bookmaker_slug || ""),
      bookmaker_name: String(row?.bookmaker_name || ""),
      bookmaker_count: row?.bookmaker_count ?? null,
    }))
    .filter((row: any) => row.odds > 1.01);

  if (!candidates.length) return null;

  const consensus =
    candidates.find((row: any) =>
      row.bookmaker_slug.toLowerCase() === "consensus" ||
      row.bookmaker_name.toLowerCase() === "consensus"
    ) || candidates[0];

  return {
    odds: Number(consensus.odds.toFixed(2)),
    source: "bsd_consensus",
    bookmaker_count: consensus.bookmaker_count,
  };
}

async function dailyGenerateSnapshots() {
  const date = dailyTodayUtc();
  const pronos = await dailyEnrichSourceRows(
    await dailyGetSourcePronos(date),
  );

  if (!pronos.length) {
    return {
      date,
      source_count: 0,
      inserted: 0,
      skipped: 0,
      message: "Aucun prono source pour aujourd'hui",
    };
  }

  // Vérification unique de la table avant tout appel BSD.
  const tableProbe = await supabase
    .from("daily_predictions")
    .select("id")
    .limit(1);

  if (tableProbe.error) {
    if (dailyTableMissing(tableProbe.error)) {
      return {
        date,
        source_count: pronos.length,
        inserted: 0,
        skipped: pronos.length,
        fallback_available: true,
        table_missing: true,
        message:
          "daily_predictions absente: le site utilise temporairement pronostics comme fallback",
      };
    }
    throw tableProbe.error;
  }

  let events: any[] = [];
  try {
    // Une journée peut dépasser 200 événements. On parcourt toutes les pages
    // pour éviter de rater les matchs situés après la première page.
    events = await dailyFetchAllEventsForDate(date);
  } catch (e: any) {
    const quotaExhausted = isBSDQuotaError(e);
    const nextMidnight = new Date();
    nextMidnight.setUTCDate(nextMidnight.getUTCDate() + 1);
    nextMidnight.setUTCHours(0, 0, 0, 0);

    return {
      date,
      source_count: pronos.length,
      inserted: 0,
      skipped: pronos.length,
      fallback_available: true,
      quota_exhausted: quotaExhausted,
      retry_after_utc: quotaExhausted ? nextMidnight.toISOString() : null,
      events_error: e?.message || String(e),
    };
  }

  let inserted = 0;
  let skipped = 0;
  const details: any[] = [];

  for (const p of pronos) {
    const outcome = String(p?.prediction || "").toUpperCase();

    const existing = await supabase
      .from("daily_predictions")
      .select("id")
      .eq("prediction_date", date)
      .eq("source_match_id", String(p?.match_id))
      .eq("market_type", "double_chance")
      .eq("outcome", outcome)
      .limit(1)
      .maybeSingle();

    if (existing.error) throw existing.error;

    if (existing.data?.id) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "already_snapshotted",
      });
      continue;
    }

    const ev = dailyFindEventForProno(p, events);
    if (!ev) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "bsd_event_not_found",
      });
      continue;
    }

    let picked: any = null;
    let oddsError: string | null = null;
    const bsdEventId = dailyEventId(ev);

    // Endpoint documenté pour la clé gratuite BSD:
    // /api/v2/odds/?event_id=...&market=double_chance&outcome=1X|12|X2
    // La clé gratuite renvoie une ligne de consensus.
    try {
      picked = await dailyFetchBsdConsensusDoubleChance(
        bsdEventId,
        outcome,
      );
    } catch (e: any) {
      oddsError = e?.message || String(e);
      if (isBSDQuotaError(e)) {
        details.push({
          match_id: p?.match_id,
          status: "odds_quota_exhausted",
          bsd_event_id: bsdEventId,
          error: oddsError,
        });
        break;
      }
    }

    // Secours: anciennes formes embarquées / raccourci événement.
    if (!picked) {
      picked = dailyPickDoubleChanceOdds(ev, outcome);
    }

    if (!picked && !oddsError) {
      try {
        const oddsPayload = await fetchBSD(
          `/events/${bsdEventId}/odds/`,
        );
        picked = dailyPickDoubleChanceOdds(oddsPayload, outcome);
      } catch (e: any) {
        oddsError = e?.message || String(e);
      }
    }

    if (!picked) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "consensus_odds_not_found",
        bsd_event_id: bsdEventId,
        error: oddsError,
      });
      continue;
    }

    const stake = DAILY_DEFAULT_STAKE;
    const odds = Number(picked.odds.toFixed(2));
    const gain = Math.round(stake * odds);
    const rawBsdId = dailyEventId(ev);
    const numericBsdId = Number(rawBsdId);

    const row = {
      prediction_date: date,
      source_match_id: String(p?.match_id),
      bsd_event_id:
        Number.isFinite(numericBsdId) ? numericBsdId : null,
      home_team: p?.home_team || dailyEventHome(ev),
      away_team: p?.away_team || dailyEventAway(ev),
      league_name:
        p?.competition ||
        p?.league_name ||
        dailyEventLeague(ev),
      kickoff:
        dailyEventKickoff(ev) ||
        p?.event_date ||
        null,
      home_logo:
        p?.home_logo ||
        dailyEventLogo(ev, "home"),
      away_logo:
        p?.away_logo ||
        dailyEventLogo(ev, "away"),
      market_type: "double_chance",
      market_label: `Double chance ${outcome}`,
      outcome,
      line: null,
      odds_snapshot: odds,
      odds_source: picked.source || "consensus",
      odds_captured_at: nowIso(),
      stake,
      potential_gain: gain,
      confidence: safeNumber(p?.confidence, 0),
      xpronos_score: safeNumber(p?.xpronos_score, 0),
      source_category: p?.category || null,
      source_badge: p?.badge || null,
      status: "accepted",
      validated: false,
    };

    const { error } = await supabase
      .from("daily_predictions")
      .insert(row);

    if (error) {
      if (String(error?.code || "") === "23505") {
        skipped++;
        details.push({
          match_id: p?.match_id,
          status: "duplicate",
        });
        continue;
      }
      throw error;
    }

    inserted++;
    details.push({
      match_id: p?.match_id,
      status: "inserted",
      odds,
      outcome,
    });
  }

  return {
    date,
    source_count: pronos.length,
    bsd_events_count: events.length,
    matched_events: details.filter((d: any) =>
      String(d?.status) !== "bsd_event_not_found"
    ).length,
    unmatched_events: details.filter((d: any) =>
      String(d?.status) === "bsd_event_not_found"
    ).length,
    inserted,
    skipped,
    details,
  };
}

async function dailyValidateSnapshots() {
  const today = dailyTodayUtc();
  const eligibleBefore = new Date(
    Date.now() - 105 * 60 * 1000,
  ).toISOString();

  const pending = await supabase
    .from("daily_predictions")
    .select("*")
    .eq("validated", false)
    .lte("kickoff", eligibleBefore)
    .lte("prediction_date", today)
    .order("kickoff", { ascending: true });

  if (pending.error) {
    if (dailyTableMissing(pending.error)) {
      return {
        checked: 0,
        validated: 0,
        won: 0,
        lost: 0,
        table_missing: true,
      };
    }
    throw pending.error;
  }

  if (!pending.data?.length) {
    return { checked: 0, validated: 0, won: 0, lost: 0 };
  }

  const byDate = new Map<string, any[]>();
  for (const p of pending.data) {
    const date = String(p?.prediction_date);
    if (!byDate.has(date)) byDate.set(date, []);
    byDate.get(date)!.push(p);
  }

  let checked = 0;
  let validated = 0;
  let won = 0;
  let lost = 0;

  for (const [date, preds] of byDate.entries()) {
    let events: any[] = [];

    try {
      const payload = await fetchBSD("/events/", {
        status: "finished",
        date_from: date,
        date_to: date,
        limit: "200",
      });

      events = dailyResultRows(payload).filter(isFinishedEvent);
    } catch (e) {
      console.warn("Validation daily: événements terminés indisponibles", e);
      continue;
    }

    for (const p of preds) {
      checked++;

      let ev = events.find(
        (x: any) =>
          String(dailyEventId(x)) ===
          String(p?.bsd_event_id),
      );

      if (!ev) ev = dailyFindEventForProno(p, events);
      if (!ev || !isFinishedEvent(ev)) continue;

      const hs = safeNumber(
        ev?.home_score ??
          ev?.home?.score ??
          ev?.scores?.home,
        0,
      );

      const as = safeNumber(
        ev?.away_score ??
          ev?.away?.score ??
          ev?.scores?.away,
        0,
      );

      const outcome = String(p?.outcome || "").toUpperCase();
      let ok = false;

      if (p?.market_type !== "double_chance") continue;

      if (outcome === "1X") ok = hs >= as;
      else if (outcome === "X2") ok = as >= hs;
      else if (outcome === "12") ok = hs !== as;
      else continue;

      const status = ok ? "won" : "lost";

      const { error } = await supabase
        .from("daily_predictions")
        .update({
          status,
          final_home_score: hs,
          final_away_score: as,
          validated: true,
          validated_at: nowIso(),
        })
        .eq("id", p.id)
        .eq("validated", false);

      if (error) throw error;

      validated++;
      if (ok) won++;
      else lost++;
    }
  }

  return { checked, validated, won, lost };
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
      const skipBsd =
        String(url.searchParams.get("skip_bsd") || "0") === "1";
      const useSnapshot =
        String(url.searchParams.get("use_snapshot") || "0") === "1";

      const result = await refreshLiveDataBatch({
        cursor,
        batchSize,
        allowTelegram,
        skipBsd,
        useSnapshot,
      });

      return json({
        success: true,
        ...result,
      });
    }

    if (path === "/telegram/status" && req.method === "GET") {
      requireCronAuth(req, url);

      const predictionId = String(
        url.searchParams.get("prediction_id") || "",
      ).trim();

      let q = supabase
        .from("live_predictions")
        .select(
          "id, match_name, prediction_type, threshold, created_at, telegram_sent, telegram_attempts, telegram_last_attempt_at, telegram_last_error, telegram_pending_chat_ids, telegram_sent_at",
        )
        .order("created_at", { ascending: false })
        .limit(predictionId ? 1 : 20);

      if (predictionId) q = q.eq("id", predictionId);

      const { data, error } = await q;
      if (error) throw error;

      return json({
        telegram_configured:
          Boolean(TELEGRAM_BOT_TOKEN) && telegramChatIds().length > 0,
        target_chat_count: telegramChatIds().length,
        predictions: data || [],
      });
    }

    // ===================================================
    // TELEGRAM: traitement isolé d'un seul coupon
    // ===================================================
    // Cette route est volontairement séparée du refresh LIVE afin que
    // Satori/Resvg ne consomment jamais le budget CPU du moteur de pronostics.
    if (path === "/telegram/process-one" && req.method === "POST") {
      requireCronAuth(req, url);

      const body = await req.json().catch(() => ({}));
      const predictionId =
        url.searchParams.get("prediction_id") ||
        String(body?.prediction_id || "").trim() ||
        null;

      // Traitement SYNCHRONE dans cette invocation dédiée.
      // Le caller reçoit le vrai résultat de sendPhoto au lieu d'un simple 202
      // qui pouvait masquer un crash Satori/Resvg après la réponse.
      const result = predictionId
        ? await processTelegramPredictionById(predictionId)
        : await retryPendingTelegramLiveCoupons([], 1);

      return json({
        success:
          safeNumber(result?.telegram_retry_failed, 0) === 0,
        isolated: true,
        background: false,
        prediction_id: predictionId,
        ...result,
      });
    }

    // Coordinateur compatible avec l'ancienne URL.
    // IMPORTANT : le cron externe ne doit pas attendre tous les lots.
    // On répond immédiatement (202) puis Supabase continue le refresh en arrière-plan.
    if (path === "/refresh" && req.method === "POST") {
      requireCronAuth(req, url);

      const refreshTask = (async () => {
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
        } catch (e: any) {
          await setCronRun("live_refresh", false, {
            error: e?.message || String(e),
          });
          console.error("Background live refresh failed:", e);
        }
      })();

      const edgeRuntime = (globalThis as any).EdgeRuntime;
      if (edgeRuntime?.waitUntil) {
        edgeRuntime.waitUntil(refreshTask);
        return json({
          accepted: true,
          background: true,
          message: "Refresh LIVE démarré en arrière-plan",
        }, 202);
      }

      // Fallback local/non-Supabase : un seul lot borné pour éviter les timeouts.
      const oneBatch = await refreshLiveDataBatch({
        batchSize: LIVE_REFRESH_BATCH_SIZE,
        allowTelegram: true,
      });

      return json({
        accepted: true,
        background: false,
        ...oneBatch,
      }, 200);
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
      const date = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);

      // IMPORTANT QUOTA: cette route est appelée par le site toutes les 20 s.
      // Elle ne doit donc JAMAIS consommer BSD.
      const liveMatches = await getLiveMatchesFromDb().catch(() => []);

      let events: any[] = [];
      try {
        const scoreboard = await fetchEspnScoreboard(toDateKey(date), false);
        events = (scoreboard?.events || [])
          .map(normalizeEspnEventToOriginalMatch)
          .filter(Boolean);
      } catch (e) {
        console.warn("ESPN /today unavailable:", e);
      }

      const scheduled = events.filter((m: any) => !m.is_live && !m.is_finished);
      const finished = events.filter((m: any) => m.is_finished);

      return json({
        data: {
          live: { count: liveMatches.length, matches: liveMatches },
          scheduled: { count: scheduled.length, matches: scheduled },
          finished: { count: finished.length, matches: finished.slice(0, 10) },
        },
        meta: { source: "supabase+espn", bsd_calls: 0 },
      });
    }
    // ===================================================
    // PRONOSTICS DU JOUR
    // ===================================================
    if (path === "/daily/today" && req.method === "GET") {
      const date =
        url.searchParams.get("date") ||
        dailyTodayUtc();

      // Lecture seule : cette route ne consomme jamais le quota BSD.
      // La création des snapshots est réservée au cron POST /daily/generate.
      const result = await dailyGetForUi(date);
      return json(result);
    }

    if (path === "/daily/generate" && req.method === "POST") {
      requireCronAuth(req, url);
      const result = await dailyGenerateSnapshots();

      if (result?.quota_exhausted) {
        return json({
          success: false,
          error: "BSD_DAILY_QUOTA_EXHAUSTED",
          ...result,
        }, 429);
      }

      return json({ success: true, ...result });
    }

    if (path === "/daily/validate" && req.method === "POST") {
      requireCronAuth(req, url);
      const result = await dailyValidateSnapshots();
      return json({ success: true, ...result });
    }

    // ===================================================
    // UI: history (48h) + logos
    // ===================================================
    if (path === "/predictions/history" && req.method === "GET") {
      const since = new Date(Date.now() - 48 * 3600 * 1000).toISOString();

      const { data, error } = await supabase
        .from("live_predictions")
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa, odds_source")
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
        .select("id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, validated, outcome, validation_type, validated_at, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa, odds_source")
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