// Free football providers used before BSD to reduce paid/quota-limited calls.
// Conflict ranking: ESPN > BSD > SportScore > TheSportsDB > OpenLigaDB.

export const FREE_SOURCE_RANKING = {
  espn: { quality: 95, reliability: 95, rank: 1 },
  bsd: { quality: 92, reliability: 92, rank: 2 },
  sportscore: { quality: 88, reliability: 86, rank: 3 },
  thesportsdb: { quality: 78, reliability: 82, rank: 4 },
  openligadb: { quality: 72, reliability: 78, rank: 5 },
} as const;

const SPORTSSCORE = "https://sportscore.com/api/v1";
const TSDB = "https://www.thesportsdb.com/api/v1/json/123";
const OPENLIGA = "https://api.openligadb.de";

function text(v: unknown) { return String(v ?? "").trim(); }
function numberOrNull(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(String(v).replace(/%$/, ""));
  return Number.isFinite(n) ? n : null;
}
function norm(v: unknown) {
  return text(v).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, " ").trim();
}
function statusOf(v: unknown, finished?: boolean) {
  const s = norm(v);
  if (finished || /finished|final|\bft\b|ended/.test(s)) return "finished";
  if (/live|in progress|playing|half time|halftime/.test(s)) return "live";
  if (/cancel|postpon|abandon|suspend/.test(s)) return "cancelled";
  return "notstarted";
}
async function json(url: URL, timeoutMs = 7000): Promise<any> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
      headers: { Accept: "application/json", "User-Agent": "MrXPRONOS-MultiSource/1.0" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export function teamSimilarity(a: unknown, b: unknown): number {
  const aa = new Set(norm(a).split(" ").filter(Boolean));
  const bb = new Set(norm(b).split(" ").filter(Boolean));
  if (!aa.size || !bb.size) return 0;
  const common = [...aa].filter(x => bb.has(x)).length;
  return common / new Set([...aa, ...bb]).size;
}

export function providerMatchScore(a: any, b: any): number {
  const same = (teamSimilarity(a?.home_team, b?.home_team) + teamSimilarity(a?.away_team, b?.away_team)) / 2;
  if (same < 0.45) return 0;
  const ta = Date.parse(String(a?.event_date || a?.date || ""));
  const tb = Date.parse(String(b?.event_date || b?.date || ""));
  if (Number.isFinite(ta) && Number.isFinite(tb)) {
    const hours = Math.abs(ta - tb) / 3600000;
    if (hours > 6) return 0;
    return 0.82 * same + 0.18 * Math.max(0, 1 - hours / 6);
  }
  return same * 0.9;
}

export async function fetchSportScoreDay(date: string, liveOnly = false) {
  try {
    const url = new URL(SPORTSSCORE + "/fixtures/");
    url.searchParams.set("sport", "football");
    url.searchParams.set("date", date);
    url.searchParams.set("limit", "200");
    if (liveOnly) url.searchParams.set("status", "live");
    const payload = await json(url);
    let rows: any[] = [];
    if (Array.isArray(payload)) rows = payload;
    else if (Array.isArray(payload?.matches)) rows = payload.matches;
    else if (Array.isArray(payload?.fixtures)) rows = payload.fixtures;
    return rows.map((r: any) => ({
      id: "sportscore:" + text(r?.id || r?.slug),
      source_match_id: text(r?.id || r?.slug),
      source_slug: text(r?.slug),
      source_name: "sportscore",
      home_team: text(r?.home || r?.home_team || r?.home_name),
      away_team: text(r?.away || r?.away_team || r?.away_name),
      home_score: numberOrNull(r?.home_score),
      away_score: numberOrNull(r?.away_score),
      event_date: text(r?.time || r?.start_time || r?.date),
      status: statusOf(r?.status || r?.status_text),
      current_minute: numberOrNull(r?.minute ?? r?.current_minute) ?? 0,
      league_name: text(r?.competition || r?.league || r?.competition_name),
      home_logo: text(r?.home_logo),
      away_logo: text(r?.away_logo),
      raw_data: { source: "sportscore", provider_raw: r },
    })).filter((m: any) => m.home_team && m.away_team);
  } catch (e) {
    console.warn("SportScore fixtures unavailable", e);
    return [];
  }
}

function extractStatPairs(payload: any) {
  const home: any = {}, away: any = {}, totals: any = {};
  const aliases: Record<string, string> = {
    corners: "corner_kicks", corner_kicks: "corner_kicks",
    corner: "corner_kicks", fouls: "fouls", foul: "fouls",
    shots: "total_shots", total_shots: "total_shots",
    shots_on_target: "shots_on_target", shotsontarget: "shots_on_target",
    possession: "ball_possession", ball_possession: "ball_possession",
    yellow_cards: "yellow_cards", red_cards: "red_cards",
  };
  const assign = (side: any, key: string, value: any) => {
    const k = aliases[norm(key).replace(/ /g, "_")] || aliases[norm(key).replace(/ /g, "")];
    const n = numberOrNull(value);
    if (k && n != null) side[k] = n;
  };

  const candidates = [
    payload?.stats, payload?.statistics, payload?.match?.stats, payload?.match?.statistics,
    payload?.data?.stats, payload?.data?.statistics,
  ].filter(Boolean);
  for (const obj of candidates) {
    if (Array.isArray(obj)) {
      for (const row of obj) {
        if (!row || typeof row !== "object") continue;
        const key = text(row.name || row.type || row.label);
        assign(home, key, row.home ?? row.home_value ?? row.homeValue);
        assign(away, key, row.away ?? row.away_value ?? row.awayValue);
      }
    } else if (obj && typeof obj === "object") {
      const h = obj.home || obj.home_team || obj.team1;
      const a = obj.away || obj.away_team || obj.team2;
      if (h && typeof h === "object") for (const [k,v] of Object.entries(h)) assign(home, k, v);
      if (a && typeof a === "object") for (const [k,v] of Object.entries(a)) assign(away, k, v);
      for (const [k,v] of Object.entries(obj)) {
        if (v && typeof v === "object" && !Array.isArray(v)) {
          assign(home, k, (v as any).home);
          assign(away, k, (v as any).away);
        }
      }
    }
  }
  for (const key of ["corner_kicks","fouls","total_shots","shots_on_target","yellow_cards","red_cards"]) {
    if (numberOrNull(home[key]) != null && numberOrNull(away[key]) != null) totals[key === "corner_kicks" ? "corners" : key] = home[key] + away[key];
  }
  return { home, away, totals };
}

export async function fetchSportScoreMatchStats(slug: string) {
  if (!slug) return null;
  try {
    const url = new URL(SPORTSSCORE + "/match/");
    url.searchParams.set("sport", "football");
    url.searchParams.set("slug", slug);
    const payload = await json(url);
    return { payload, stats: extractStatPairs(payload) };
  } catch (e) {
    console.warn("SportScore match detail unavailable", slug, e);
    return null;
  }
}

export async function fetchTheSportsDbDay(date: string) {
  try {
    const url = new URL(TSDB + "/eventsday.php");
    url.searchParams.set("d", date);
    url.searchParams.set("s", "Soccer");
    const payload = await json(url);
    return (Array.isArray(payload?.events) ? payload.events : []).map((r: any) => ({
      id: "thesportsdb:" + text(r?.idEvent),
      source_match_id: text(r?.idEvent),
      source_name: "thesportsdb",
      home_team: text(r?.strHomeTeam),
      away_team: text(r?.strAwayTeam),
      home_score: numberOrNull(r?.intHomeScore),
      away_score: numberOrNull(r?.intAwayScore),
      event_date: text(r?.strTimestamp || (r?.dateEvent ? `${r.dateEvent}T${r.strTime || "00:00:00"}Z` : "")),
      status: statusOf(r?.strStatus || r?.strProgress),
      league_name: text(r?.strLeague),
      home_logo: text(r?.strHomeTeamBadge),
      away_logo: text(r?.strAwayTeamBadge),
      raw_data: { source: "thesportsdb", provider_raw: r },
    })).filter((m: any) => m.home_team && m.away_team);
  } catch (e) {
    console.warn("TheSportsDB day unavailable", e);
    return [];
  }
}

export async function fetchTheSportsDbStats(eventId: string) {
  if (!eventId) return null;
  try {
    const url = new URL(TSDB + "/lookupeventstats.php");
    url.searchParams.set("id", eventId);
    const payload = await json(url);
    const rows = Array.isArray(payload?.eventstats) ? payload.eventstats : [];
    const home: any = {}, away: any = {}, totals: any = {};
    const aliases: Record<string,string> = {
      "corner kicks":"corner_kicks","corners":"corner_kicks","shots":"total_shots",
      "shots on target":"shots_on_target","fouls":"fouls","possession":"ball_possession",
      "yellow cards":"yellow_cards","red cards":"red_cards",
    };
    for (const r of rows) {
      const k = aliases[norm(r?.strStat)];
      if (!k) continue;
      const hv = numberOrNull(r?.intHome ?? r?.strHome);
      const av = numberOrNull(r?.intAway ?? r?.strAway);
      if (hv != null) home[k] = hv;
      if (av != null) away[k] = av;
      if (hv != null && av != null && k !== "ball_possession") totals[k === "corner_kicks" ? "corners" : k] = hv + av;
    }
    return { payload, stats: { home, away, totals } };
  } catch (e) {
    console.warn("TheSportsDB stats unavailable", eventId, e);
    return null;
  }
}

export async function fetchOpenLigaCurrent(shortcuts = ["bl1","bl2","bl3","cl"]) {
  const out: any[] = [];
  for (const shortcut of shortcuts.slice(0, 8)) {
    try {
      const payload = await json(new URL(OPENLIGA + "/getmatchdata/" + encodeURIComponent(shortcut)));
      if (!Array.isArray(payload)) continue;
      for (const r of payload) {
        const h = r?.team1 || {}, a = r?.team2 || {};
        let hs: number|null = null, as: number|null = null;
        for (const x of Array.isArray(r?.matchResults) ? r.matchResults : []) {
          const kind = norm(x?.resultTypeKind || x?.resultName);
          if (kind.includes("after90") || kind.includes("end")) {
            hs = numberOrNull(x?.pointsTeam1); as = numberOrNull(x?.pointsTeam2);
          }
        }
        out.push({
          id: "openligadb:" + text(r?.matchID),
          source_match_id: text(r?.matchID),
          source_name: "openligadb",
          home_team: text(h?.teamName),
          away_team: text(a?.teamName),
          home_score: hs, away_score: as,
          event_date: text(r?.matchDateTimeUTC || r?.matchDateTime),
          status: statusOf("", Boolean(r?.matchIsFinished)),
          league_name: text(r?.league?.leagueName || shortcut),
          home_logo: text(h?.teamIconUrl), away_logo: text(a?.teamIconUrl),
          goals: Array.isArray(r?.goals) ? r.goals : [],
          raw_data: { source: "openligadb", provider_raw: r },
        });
      }
    } catch (e) {
      console.warn("OpenLigaDB unavailable", shortcut, e);
    }
  }
  return out.filter(m => m.home_team && m.away_team);
}

export function bestProviderMatch(base: any, rows: any[], threshold = 0.68) {
  let best: any = null, score = 0;
  for (const row of rows || []) {
    const current = providerMatchScore(base, row);
    if (current > score) { best = row; score = current; }
  }
  return score >= threshold ? { match: best, score } : null;
}
