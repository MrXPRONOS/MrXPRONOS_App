import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const BSD_API_TOKEN = Deno.env.get("BSD_API_TOKEN") || "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const CRON_SECRET = Deno.env.get("CRON_SECRET") || "";
const BSD_API_BASE = "https://sports.bzzoiro.com/api/v2";
const DEFAULT_STAKE = 500_000;

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

const corsHeaders: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-cron-secret",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function safeNumber(v: unknown, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function todayUtc() {
  return new Date().toISOString().slice(0, 10);
}

function requireCronAuth(req: Request) {
  if (!CRON_SECRET) return;
  const x = req.headers.get("x-cron-secret") || "";
  const auth = req.headers.get("authorization") || "";
  const bearer =
    auth.toLowerCase().startsWith("bearer ") &&
    auth.slice(7).trim() === CRON_SECRET;
  if (x !== CRON_SECRET && !bearer) throw new Error("Unauthorized");
}

function stripAccents(v: string) {
  return v.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function normTeam(v: unknown) {
  return stripAccents(String(v ?? ""))
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\b(fc|cf|sc|afc|club|football|soccer|the|de|da|do)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function teamSimilarity(a: unknown, b: unknown) {
  const aa = normTeam(a);
  const bb = normTeam(b);
  if (!aa || !bb) return 0;
  if (aa === bb) return 1;
  if (aa.includes(bb) || bb.includes(aa)) return 0.92;
  const as = new Set(aa.split(" ").filter(Boolean));
  const bs = new Set(bb.split(" ").filter(Boolean));
  const inter = [...as].filter((x) => bs.has(x)).length;
  const union = new Set([...as, ...bs]).size || 1;
  return inter / union;
}

function eventHome(ev: any) {
  return ev?.home_team?.name ?? ev?.home_team ?? ev?.home?.name ?? ev?.teams?.home?.name ?? "";
}

function eventAway(ev: any) {
  return ev?.away_team?.name ?? ev?.away_team ?? ev?.away?.name ?? ev?.teams?.away?.name ?? "";
}

function eventLeague(ev: any) {
  return ev?.league?.name ?? ev?.competition?.name ?? ev?.league_name ?? "Football";
}

function eventKickoff(ev: any) {
  return ev?.event_date ?? ev?.start_time ?? ev?.date ?? ev?.kickoff ?? null;
}

function eventId(ev: any) {
  return ev?.id ?? ev?.event_id ?? null;
}

function eventLogo(ev: any, side: "home" | "away") {
  const team = side === "home"
    ? (ev?.home_team_obj ?? ev?.home ?? ev?.teams?.home ?? ev?.home_team)
    : (ev?.away_team_obj ?? ev?.away ?? ev?.teams?.away ?? ev?.away_team);
  return (
    team?.logo_url ??
    team?.logo ??
    team?.image_url ??
    team?.image ??
    ev?.[side + "_logo"] ??
    null
  );
}

function eventScore(ev: any, side: "home" | "away") {
  return safeNumber(
    side === "home"
      ? (ev?.home_score ?? ev?.home?.score ?? ev?.scores?.home)
      : (ev?.away_score ?? ev?.away?.score ?? ev?.scores?.away),
    0,
  );
}

function isFinished(ev: any) {
  const status = String(ev?.status ?? ev?.state ?? "").toLowerCase();
  const period = String(ev?.period ?? "").toUpperCase();
  return (
    status === "finished" ||
    status === "ft" ||
    status.includes("finished") ||
    status.includes("full time") ||
    period === "FT"
  );
}

async function bsd(endpoint: string, params: Record<string, string> = {}) {
  if (!BSD_API_TOKEN) throw new Error("BSD_API_TOKEN missing");
  const url = new URL(BSD_API_BASE + endpoint);
  for (const [k, v] of Object.entries(params)) {
    if (v !== "") url.searchParams.set(k, v);
  }
  const res = await fetch(url.toString(), {
    headers: { Authorization: `Token ${BSD_API_TOKEN}` },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    const err: any = new Error(`BSD HTTP ${res.status}: ${body || res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function resultRows(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}

function findEventForProno(prono: any, events: any[]) {
  const ph = prono?.home_team;
  const pa = prono?.away_team;
  let best: any = null;
  let bestScore = 0;

  for (const ev of events) {
    const direct =
      teamSimilarity(ph, eventHome(ev)) * 0.5 +
      teamSimilarity(pa, eventAway(ev)) * 0.5;

    const reverse =
      teamSimilarity(ph, eventAway(ev)) * 0.5 +
      teamSimilarity(pa, eventHome(ev)) * 0.5;

    const score = Math.max(direct, reverse);
    if (score > bestScore) {
      bestScore = score;
      best = ev;
    }
  }

  return bestScore >= 0.78 ? best : null;
}

function collectOddsObjects(value: any, out: any[] = [], depth = 0): any[] {
  if (depth > 8 || value == null) return out;
  if (Array.isArray(value)) {
    for (const x of value) collectOddsObjects(x, out, depth + 1);
    return out;
  }
  if (typeof value !== "object") return out;

  const hasOdds =
    value.decimal_odds != null ||
    value.odds_decimal != null ||
    value.odds != null ||
    value.price != null;

  const hasMarket = value.market != null || value.market_type != null || value.market_name != null;
  const hasOutcome = value.outcome != null || value.selection != null || value.name != null;

  if (hasOdds && hasMarket && hasOutcome) out.push(value);

  for (const x of Object.values(value)) {
    if (x && typeof x === "object") collectOddsObjects(x, out, depth + 1);
  }
  return out;
}

function normMarket(v: unknown) {
  return String(v ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normOutcome(v: unknown) {
  return String(v ?? "").trim().toUpperCase().replace(/\s+/g, "");
}

function pickDoubleChanceOdds(payload: any, wanted: string) {
  const rows = collectOddsObjects(payload);
  const target = normOutcome(wanted);

  const candidates = rows.filter((r) => {
    const market = normMarket(r.market ?? r.market_type ?? r.market_name);
    const outcome = normOutcome(r.outcome ?? r.selection ?? r.name);
    return (
      (market === "double_chance" || market.includes("double_chance")) &&
      outcome === target
    );
  });

  const parsed = candidates
    .map((r) => ({
      odds: safeNumber(r.decimal_odds ?? r.odds_decimal ?? r.odds ?? r.price, 0),
      source: String(r.bookmaker_name ?? r.bookmaker_slug ?? "Consensus"),
    }))
    .filter((x) => x.odds > 1.01)
    .sort((a, b) => b.odds - a.odds);

  return parsed[0] ?? null;
}

async function fetchTodayEvents(date: string) {
  const data = await bsd("/events/", {
    date_from: date,
    date_to: date,
    limit: "200",
  });
  return resultRows(data);
}

async function generateDailySnapshots() {
  const date = todayUtc();

  const { data: sourceRows, error: sourceError } = await supabase
    .from("pronostics")
    .select("*")
    .eq("date", date)
    .order("xpronos_score", { ascending: false });

  if (sourceError) throw sourceError;

  const pronos = (sourceRows || []).filter((p: any) => {
    const pick = String(p?.prediction || "").toUpperCase();
    return ["1X", "X2", "12"].includes(pick);
  });

  if (!pronos.length) {
    return { date, source_count: 0, inserted: 0, skipped: 0, message: "Aucun prono source pour aujourd'hui" };
  }

  const events = await fetchTodayEvents(date);

  let inserted = 0;
  let skipped = 0;
  const details: any[] = [];

  for (const p of pronos) {
    const existing = await supabase
      .from("daily_predictions")
      .select("id")
      .eq("prediction_date", date)
      .eq("source_match_id", String(p.match_id))
      .eq("market_type", "double_chance")
      .eq("outcome", String(p.prediction).toUpperCase())
      .limit(1)
      .maybeSingle();

    if (existing.data?.id) {
      skipped++;
      details.push({ match_id: p.match_id, status: "already_snapshotted" });
      continue;
    }

    const ev = findEventForProno(p, events);
    if (!ev) {
      skipped++;
      details.push({ match_id: p.match_id, status: "bsd_event_not_found" });
      continue;
    }

    let oddsPayload: any;
    try {
      oddsPayload = await bsd(`/events/${eventId(ev)}/odds/`);
    } catch (e: any) {
      skipped++;
      details.push({ match_id: p.match_id, status: "odds_error", error: e?.message || String(e) });
      continue;
    }

    const picked = pickDoubleChanceOdds(oddsPayload, String(p.prediction));
    if (!picked) {
      skipped++;
      details.push({ match_id: p.match_id, status: "consensus_odds_not_found" });
      continue;
    }

    const stake = DEFAULT_STAKE;
    const odds = Number(picked.odds.toFixed(2));
    const gain = Math.round(stake * odds);
    const bsdId = eventId(ev);

    const row = {
      prediction_date: date,
      source_match_id: String(p.match_id),
      bsd_event_id: bsdId == null ? null : Number(bsdId),
      home_team: p.home_team || eventHome(ev),
      away_team: p.away_team || eventAway(ev),
      league_name: p.competition || eventLeague(ev),
      kickoff: eventKickoff(ev) || p.event_date || null,
      home_logo: p.home_logo || eventLogo(ev, "home"),
      away_logo: p.away_logo || eventLogo(ev, "away"),
      market_type: "double_chance",
      market_label: `Double chance ${String(p.prediction).toUpperCase()}`,
      outcome: String(p.prediction).toUpperCase(),
      line: null,
      odds_snapshot: odds,
      odds_source: "consensus",
      odds_captured_at: new Date().toISOString(),
      stake,
      potential_gain: gain,
      confidence: safeNumber(p.confidence, 0),
      xpronos_score: safeNumber(p.xpronos_score, 0),
      source_category: p.category || null,
      source_badge: p.badge || null,
      status: "accepted",
      validated: false,
    };

    const { error } = await supabase.from("daily_predictions").insert(row);
    if (error) {
      if (String(error.code) === "23505") {
        skipped++;
        details.push({ match_id: p.match_id, status: "duplicate" });
        continue;
      }
      throw error;
    }

    inserted++;
    details.push({
      match_id: p.match_id,
      status: "inserted",
      odds,
      outcome: row.outcome,
    });
  }

  return {
    date,
    source_count: pronos.length,
    bsd_events_count: events.length,
    inserted,
    skipped,
    details,
  };
}

async function validateDailyPredictions() {
  const now = new Date();
  const today = todayUtc();
  const eligibleBefore = new Date(now.getTime() - 105 * 60 * 1000).toISOString();

  const { data: pending, error } = await supabase
    .from("daily_predictions")
    .select("*")
    .eq("validated", false)
    .lte("kickoff", eligibleBefore)
    .lte("prediction_date", today)
    .order("kickoff", { ascending: true });

  if (error) throw error;
  if (!pending?.length) return { checked: 0, validated: 0, won: 0, lost: 0 };

  const byDate = new Map<string, any[]>();
  for (const p of pending) {
    const d = String(p.prediction_date);
    if (!byDate.has(d)) byDate.set(d, []);
    byDate.get(d)!.push(p);
  }

  let checked = 0;
  let validated = 0;
  let won = 0;
  let lost = 0;

  for (const [date, preds] of byDate.entries()) {
    let finishedEvents: any[] = [];
    try {
      const payload = await bsd("/events/", {
        status: "finished",
        date_from: date,
        date_to: date,
        limit: "200",
      });
      finishedEvents = resultRows(payload).filter(isFinished);
    } catch (e) {
      console.warn("Validation daily: liste finished indisponible", e);
      continue;
    }

    for (const p of preds) {
      checked++;
      let ev = finishedEvents.find((x) => String(eventId(x)) === String(p.bsd_event_id));
      if (!ev) ev = findEventForProno(p, finishedEvents);
      if (!ev || !isFinished(ev)) continue;

      const hs = eventScore(ev, "home");
      const as = eventScore(ev, "away");
      const outcome = String(p.outcome || "").toUpperCase();

      let ok = false;
      if (p.market_type === "double_chance") {
        if (outcome === "1X") ok = hs >= as;
        else if (outcome === "X2") ok = as >= hs;
        else if (outcome === "12") ok = hs !== as;
        else continue;
      } else {
        continue;
      }

      const status = ok ? "won" : "lost";
      const { error: upErr } = await supabase
        .from("daily_predictions")
        .update({
          status,
          final_home_score: hs,
          final_away_score: as,
          validated: true,
          validated_at: new Date().toISOString(),
        })
        .eq("id", p.id)
        .eq("validated", false);

      if (upErr) throw upErr;

      validated++;
      if (ok) won++;
      else lost++;
    }
  }

  return { checked, validated, won, lost };
}

async function getDaily(date: string) {
  const { data, error } = await supabase
    .from("daily_predictions")
    .select("*")
    .eq("prediction_date", date)
    .order("kickoff", { ascending: true });

  if (error) throw error;
  return data || [];
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const path = url.pathname.replace(/^.*\/daily-pronos/, "") || "/";

  try {
    if ((path === "/" || path === "/today") && req.method === "GET") {
      const date = url.searchParams.get("date") || todayUtc();
      const predictions = await getDaily(date);
      return json({ date, predictions, count: predictions.length });
    }

    if (path === "/generate" && req.method === "POST") {
      requireCronAuth(req);
      const result = await generateDailySnapshots();
      return json({ success: true, ...result });
    }

    if (path === "/validate" && req.method === "POST") {
      requireCronAuth(req);
      const result = await validateDailyPredictions();
      return json({ success: true, ...result });
    }

    return json({ error: "Not found" }, 404);
  } catch (e: any) {
    console.error("daily-pronos error:", e);
    return json({ error: e?.message || "Erreur serveur" }, 500);
  }
});
