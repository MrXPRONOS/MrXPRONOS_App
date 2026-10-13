// Free football providers used before BSD to reduce paid/quota-heavy calls.
// SportScore API free tier requires visible attribution on public surfaces.
// Public SportScore API does NOT document betting-odds endpoints (2026-10-13).

export const PROVIDER_QUALITY: Record<string, number> = {
  espn: 98,
  bsd: 96,
  sportscore: 91,
  openligadb: 84,
  thesportsdb: 80,
};

export const FETCH_PRIORITY = ["espn", "sportscore", "openligadb", "thesportsdb", "bsd"] as const;
export const ODDS_PRIORITY = ["bsd"] as const;
export const SPORTScore_ATTRIBUTION_HTML =
  '<a href="https://sportscore.com/" rel="dofollow" title="Sports data by SportScore">Powered by SportScore</a>';

const SPORTScore_BASE = "https://sportscore.com";
const TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123";

function txt(v: unknown) { return String(v ?? "").trim(); }
function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "" || v === "-") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
function stateFrom(v: unknown) {
  const s = txt(v).toLowerCase();
  if (/finished|full.?time|\bft\b|ended/.test(s)) return { is_live: false, is_finished: true };
  if (/live|in.?progress|1st|2nd|half|extra/.test(s)) return { is_live: true, is_finished: false };
  return { is_live: false, is_finished: false };
}
function iso(v: unknown) {
  const d = new Date(txt(v));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function hashString(input: string) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h >>> 0);
}
function stableTeamId(name: string) { return hashString(name.toLowerCase().replace(/\W+/g, " ")) || 1; }
function rows(payload: any, ...keys: string[]): any[] {
  if (Array.isArray(payload)) return payload.filter((x) => x && typeof x === "object");
  if (!payload || typeof payload !== "object") return [];
  for (const key of keys) if (Array.isArray(payload[key])) return payload[key];
  return [];
}
async function getJson(url: URL, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url.toString(), {
      signal: controller.signal,
      headers: { Accept: "application/json", "User-Agent": "MrXPRONOS-FreeProviders/1.0" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} ${url.hostname}`);
    return await res.json();
  } finally { clearTimeout(timer); }
}

export function normalizeSportScore(row: any) {
  if (!row || typeof row !== "object") return null;
  const home = txt(row.home || row.home_team || row.homeTeam?.name);
  const away = txt(row.away || row.away_team || row.awayTeam?.name);
  if (!home || !away) return null;
  const start = row.time || row.start_time || row.date || row.start;
  const status = txt(row.status_text || row.status);
  const state = stateFrom(status);
  const slug = txt(row.slug);
  const rawId = txt(row.id || row.match_id || slug);
  return {
    id: `sportscore:${rawId || hashString(home + "|" + away + "|" + txt(start))}`,
    event_date: iso(start) || start || null,
    home_team: home,
    away_team: away,
    home_team_id: stableTeamId(home),
    away_team_id: stableTeamId(away),
    home_logo: txt(row.home_logo),
    away_logo: txt(row.away_logo),
    home_score: num(row.home_score),
    away_score: num(row.away_score),
    current_minute: num(row.minute || row.current_minute),
    status,
    is_live: state.is_live,
    is_finished: state.is_finished,
    live_stats: {},
    raw_data: {
      source: "sportscore",
      provider_quality: PROVIDER_QUALITY.sportscore,
      sportscore_slug: slug,
      sportscore_id: rawId,
      raw_provider: row,
    },
  };
}

export function normalizeTsdb(row: any) {
  if (!row || typeof row !== "object") return null;
  const sport = txt(row.strSport).toLowerCase();
  if (sport && !["soccer", "football"].includes(sport)) return null;
  const home = txt(row.strHomeTeam), away = txt(row.strAwayTeam);
  if (!home || !away) return null;
  const start = row.strTimestamp || (row.dateEvent ? `${row.dateEvent}T${row.strTime || "00:00:00"}Z` : null);
  const status = txt(row.strStatus || row.strProgress);
  const state = stateFrom(status);
  const eventId = txt(row.idEvent);
  return {
    id: `thesportsdb:${eventId || hashString(home + "|" + away + "|" + txt(start))}`,
    event_date: iso(start) || start,
    home_team: home,
    away_team: away,
    home_team_id: num(row.idHomeTeam) || stableTeamId(home),
    away_team_id: num(row.idAwayTeam) || stableTeamId(away),
    home_logo: txt(row.strHomeTeamBadge),
    away_logo: txt(row.strAwayTeamBadge),
    home_score: num(row.intHomeScore),
    away_score: num(row.intAwayScore),
    current_minute: num(String(row.strProgress || "").match(/\d+/)?.[0]),
    status,
    is_live: state.is_live,
    is_finished: state.is_finished,
    live_stats: {},
    raw_data: {
      source: "thesportsdb",
      provider_quality: PROVIDER_QUALITY.thesportsdb,
      tsdb_event_id: eventId,
      raw_provider: row,
    },
  };
}

export async function fetchSportScoreLive() {
  try {
    const url = new URL(SPORTScore_BASE + "/api/v1/fixtures/");
    url.searchParams.set("sport", "football");
    url.searchParams.set("date", new Date().toISOString().slice(0, 10));
    url.searchParams.set("status", "live");
    url.searchParams.set("limit", "200");
    url.searchParams.set("src", "mrxpronos");
    const payload = await getJson(url);
    const matches = rows(payload, "matches", "fixtures", "results", "data")
      .map(normalizeSportScore).filter(Boolean);
    return { matches, error: null };
  } catch (e: any) {
    return { matches: [], error: e?.message || String(e) };
  }
}

export async function fetchTheSportsDbToday() {
  try {
    const url = new URL(TSDB_BASE + "/eventsday.php");
    url.searchParams.set("d", new Date().toISOString().slice(0, 10));
    url.searchParams.set("s", "Soccer");
    const payload = await getJson(url);
    const matches = rows(payload, "events").map(normalizeTsdb).filter(Boolean)
      .filter((m: any) => m.is_live || (!m.is_finished && num(m.home_score) !== null));
    return { matches, error: null };
  } catch (e: any) {
    return { matches: [], error: e?.message || String(e) };
  }
}

export async function fetchSportScoreDetail(slug: string) {
  if (!slug) return null;
  try {
    const url = new URL(SPORTScore_BASE + "/api/v1/match/");
    url.searchParams.set("sport", "football");
    url.searchParams.set("slug", slug);
    url.searchParams.set("src", "mrxpronos");
    return await getJson(url);
  } catch { return null; }
}

export async function findTsdbEvent(home: string, away: string, day: string) {
  try {
    const url = new URL(TSDB_BASE + "/searchevents.php");
    url.searchParams.set("e", `${home}_vs_${away}`.replace(/\s+/g, "_"));
    url.searchParams.set("d", day);
    const payload = await getJson(url);
    return rows(payload, "event", "events")[0] || null;
  } catch { return null; }
}

export async function fetchTsdbStats(eventId: string) {
  if (!/^\d+$/.test(eventId)) return [];
  try {
    const url = new URL(TSDB_BASE + "/lookupeventstats.php");
    url.searchParams.set("id", eventId);
    const payload = await getJson(url);
    return rows(payload, "eventstats", "stats");
  } catch { return []; }
}

const STAT_ALIASES: Record<string, string[]> = {
  corner_kicks: ["corners", "corner kicks", "won corners"],
  total_shots: ["shots", "total shots"],
  shots_on_target: ["shots on target", "shots on goal"],
  fouls: ["fouls", "fouls committed"],
  yellow_cards: ["yellow cards"],
  red_cards: ["red cards"],
};

function normalizedLabel(v: unknown) {
  return txt(v).toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}
function setPair(out: any, key: string, home: unknown, away: unknown) {
  const h = num(home), a = num(away);
  if (h === null || a === null) return;
  out.home ||= {};
  out.away ||= {};
  out.totals ||= {};
  out.home[key] = h;
  out.away[key] = a;
  const totalKey: Record<string, string> = {
    corner_kicks: "corners", total_shots: "total_shots", shots_on_target: "shots_on_target",
    fouls: "fouls", yellow_cards: "yellow_cards", red_cards: "red_cards",
  };
  if (totalKey[key]) out.totals[totalKey[key]] = h + a;
}

export function normalizeTsdbStats(rowsData: any[]) {
  const out: any = { home: {}, away: {}, totals: {} };
  for (const row of rowsData || []) {
    if (!row || typeof row !== "object") continue;
    const label = normalizedLabel(row.strStat || row.strStatistic || row.name || row.label);
    for (const [key, aliases] of Object.entries(STAT_ALIASES)) {
      if (aliases.some((alias) => label === alias || label.includes(alias))) {
        setPair(out, key,
          row.intHome ?? row.home ?? row.homeValue ?? row.home_value,
          row.intAway ?? row.away ?? row.awayValue ?? row.away_value);
      }
    }
  }
  return out;
}

export function normalizeSportScoreStats(payload: any) {
  const root = payload?.match || payload?.data || payload || {};
  const stats = root.statistics || root.stats || payload?.statistics || payload?.stats;
  const out: any = { home: {}, away: {}, totals: {} };
  if (Array.isArray(stats)) {
    for (const row of stats) {
      if (!row || typeof row !== "object") continue;
      const label = normalizedLabel(row.name || row.label || row.type);
      for (const [key, aliases] of Object.entries(STAT_ALIASES)) {
        if (aliases.some((alias) => label === alias || label.includes(alias))) {
          setPair(out, key,
            row.home ?? row.home_value ?? row.homeValue,
            row.away ?? row.away_value ?? row.awayValue);
        }
      }
    }
  } else if (stats && typeof stats === "object") {
    const home = stats.home || stats.home_team || {};
    const away = stats.away || stats.away_team || {};
    for (const [key, aliases] of Object.entries(STAT_ALIASES)) {
      for (const alias of aliases) {
        const normalized = alias.replace(/\s+/g, "_");
        const hv = home[key] ?? home[normalized] ?? home[alias];
        const av = away[key] ?? away[normalized] ?? away[alias];
        if (hv !== undefined || av !== undefined) { setPair(out, key, hv, av); break; }
      }
    }
  }
  return out;
}

export function providerPolicy() {
  return {
    quality: PROVIDER_QUALITY,
    fetch_priority: FETCH_PRIORITY,
    odds_priority: ODDS_PRIORITY,
    sportscore_odds_api_supported: false,
    sportscore_attribution_required: true,
  };
}
