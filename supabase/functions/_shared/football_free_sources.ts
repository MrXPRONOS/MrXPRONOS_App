// Free football providers used before BSD to reduce paid/quota-sensitive traffic.
// Quality authority: ESPN 100 > BSD 96 > SportScore 92 > TheSportsDB 76 > OpenLigaDB 72.
// Fetch order can differ from authority: free sources are attempted before BSD.
export const FOOTBALL_PROVIDER_QUALITY: Record<string, number> = {
  espn: 100,
  bsd: 96,
  sportscore: 92,
  thesportsdb: 76,
  openligadb: 72,
};

export const SPORTSCORE_ATTRIBUTION_URL = "https://sportscore.com/";

const SPORTSCORE_FIXTURES = "https://sportscore.com/api/v1/fixtures/";
const SPORTSCORE_MATCH = "https://sportscore.com/api/v1/match/";
const THESPORTSDB_DAY = "https://www.thesportsdb.com/api/v1/json/123/eventsday.php";
const OPENLIGA = "https://api.openligadb.de";

const cache = new Map<string, { until: number; data: any }>();
const inFlight = new Map<string, Promise<any>>();

function text(v: unknown): string {
  return String(v ?? "").replace(/\s+/g, " ").trim();
}
function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "" || v === "-") return null;
  const n = Number(String(v).replace(/%$/, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
function dateIso(v: unknown): string | null {
  if (!v) return null;
  const d = new Date(String(v));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function seasonFor(date: Date) {
  return date.getUTCMonth() >= 6 ? date.getUTCFullYear() : date.getUTCFullYear() - 1;
}
function dateKey(date: Date) {
  return date.toISOString().slice(0, 10);
}
async function getJson(url: string, params: Record<string, string>, ttlMs: number) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const key = u.toString();
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && hit.until > now) return hit.data;
  const pending = inFlight.get(key);
  if (pending) return pending;
  const promise = (async () => {
    for (let attempt = 0; attempt < 2; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 7000);
      try {
        const res = await fetch(key, {
          signal: controller.signal,
          headers: {
            Accept: "application/json,text/plain,*/*",
            "User-Agent": "MrXPRONOS-FreeSources/1.0",
          },
        });
        if ((res.status === 429 || res.status >= 500) && attempt === 0) {
          await new Promise((r) => setTimeout(r, 400));
          continue;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        cache.set(key, { until: Date.now() + ttlMs, data });
        return data;
      } catch (e) {
        if (attempt === 1) throw e;
      } finally {
        clearTimeout(timer);
      }
    }
  })();
  inFlight.set(key, promise);
  try { return await promise; }
  finally { inFlight.delete(key); }
}

function emptyStats() {
  return {
    home: {
      corner_kicks: null, fouls: null, total_shots: null, shots_on_target: null,
      ball_possession: null, yellow_cards: null, red_cards: null,
    },
    away: {
      corner_kicks: null, fouls: null, total_shots: null, shots_on_target: null,
      ball_possession: null, yellow_cards: null, red_cards: null,
    },
  };
}
function normalizeStatName(v: unknown) {
  return text(v).toLowerCase().replace(/[^a-z0-9]/g, "");
}
function normalizeStats(value: any) {
  const out = emptyStats();
  const aliases: Record<string, string[]> = {
    corner_kicks: ["corners", "cornerkicks", "woncorners"],
    fouls: ["fouls", "foulscommitted"],
    total_shots: ["shots", "totalshots", "shotstotal"],
    shots_on_target: ["shotsontarget", "shotsongoal"],
    ball_possession: ["possession", "possessionpct", "possessionpercentage"],
    yellow_cards: ["yellowcards"],
    red_cards: ["redcards"],
  };
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const side of ["home", "away"] as const) {
      const block = value?.[side];
      if (!block || typeof block !== "object") continue;
      for (const [target, names] of Object.entries(aliases)) {
        for (const [key, raw] of Object.entries(block)) {
          if (names.some((name) => normalizeStatName(key).includes(name))) {
            (out as any)[side][target] = num(raw);
            break;
          }
        }
      }
    }
  } else if (Array.isArray(value)) {
    for (const row of value) {
      if (!row || typeof row !== "object") continue;
      const label = normalizeStatName(row.name ?? row.label ?? row.type);
      for (const [target, names] of Object.entries(aliases)) {
        if (!names.some((name) => label.includes(name))) continue;
        (out as any).home[target] = num(row.home ?? row.home_value ?? row.homeValue);
        (out as any).away[target] = num(row.away ?? row.away_value ?? row.awayValue);
      }
    }
  }
  return out;
}
function providerMatch(args: any) {
  const source = String(args.source);
  const sourceId = text(args.id);
  const eventDate = dateIso(args.event_date);
  if (!args.home || !args.away || !eventDate) return null;
  const statusText = text(args.status).toLowerCase();
  const finished = args.finished === true || /finished|full time|\bft\b|ended/.test(statusText);
  const live = args.live === true || /live|in progress|1st half|2nd half|half time|halftime/.test(statusText);
  return {
    id: `${source}:${sourceId || args.slug || args.home + "-" + args.away}`,
    source_match_id: sourceId || text(args.slug),
    source_name: source,
    home_team: text(args.home),
    away_team: text(args.away),
    home_score: num(args.home_score) ?? 0,
    away_score: num(args.away_score) ?? 0,
    current_minute: num(args.minute) ?? 0,
    league_name: text(args.league) || "Football",
    league: { name: text(args.league) || "Football" },
    status: text(args.status),
    is_live: live && !finished,
    is_finished: finished,
    event_date: eventDate,
    home_team_id: null,
    away_team_id: null,
    league_id: null,
    home_logo: args.home_logo || null,
    away_logo: args.away_logo || null,
    live_stats: args.live_stats || emptyStats(),
    stats_last_updated_at: args.stats_updated_at || null,
    raw_data: {
      source,
      provider_quality: FOOTBALL_PROVIDER_QUALITY[source] || 0,
      provider_slug: text(args.slug),
      provider_payload: args.raw,
      sportscore_odds: source === "sportscore" && (args.raw?.odds || args.odds)
        ? (args.raw?.odds || args.odds)
        : null,
      live_stats: args.live_stats || emptyStats(),
      stats_sources: [source],
    },
  };
}

function extractSportScoreRows(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  for (const key of ["matches", "fixtures", "results", "data"]) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  return [];
}
async function fetchSportScoreDetail(slug: string) {
  if (!slug) return null;
  try {
    const payload = await getJson(
      SPORTSCORE_MATCH,
      { sport: "football", slug, src: "mrxpronos" },
      30_000,
    );
    return payload?.match || payload?.data || payload || null;
  } catch {
    return null;
  }
}
export async function fetchSportScoreLive(maxDetails = 4) {
  try {
    const payload = await getJson(
      SPORTSCORE_FIXTURES,
      { sport: "football", date: dateKey(new Date()), status: "live", limit: "200", src: "mrxpronos" },
      45_000,
    );
    const rows = extractSportScoreRows(payload);
    const normalized: any[] = [];
    for (const row of rows) {
      if (!row || typeof row !== "object") continue;
      const homeObj = row.home_team && typeof row.home_team === "object" ? row.home_team
        : row.homeTeam && typeof row.homeTeam === "object" ? row.homeTeam : {};
      const awayObj = row.away_team && typeof row.away_team === "object" ? row.away_team
        : row.awayTeam && typeof row.awayTeam === "object" ? row.awayTeam : {};
      const leagueObj = row.competition && typeof row.competition === "object" ? row.competition
        : row.league && typeof row.league === "object" ? row.league : {};
      const slug = text(row.slug);
      let detail: any = null;
      if (normalized.length < maxDetails && slug) detail = await fetchSportScoreDetail(slug);
      const stats = normalizeStats(detail?.stats || detail?.statistics || row.stats || row.statistics);
      const match = providerMatch({
        source: "sportscore",
        id: row.id ?? row.match_id ?? slug,
        slug,
        home: row.home ?? homeObj.name ?? homeObj.display_name,
        away: row.away ?? awayObj.name ?? awayObj.display_name,
        home_score: row.home_score ?? row.homeScore,
        away_score: row.away_score ?? row.awayScore,
        event_date: row.time ?? row.start_time ?? row.date,
        status: row.status_text ?? row.status ?? detail?.status,
        minute: row.minute ?? row.current_minute ?? detail?.minute,
        league: leagueObj.name ?? row.competition_name ?? row.league_name,
        home_logo: row.home_logo ?? homeObj.logo,
        away_logo: row.away_logo ?? awayObj.logo,
        live_stats: stats,
        stats_updated_at: Object.values(stats.home).some((v) => v != null) ? new Date().toISOString() : null,
        raw: detail ? { ...row, detail } : row,
        odds: detail?.odds,
      });
      if (match && match.is_live && !match.is_finished) normalized.push(match);
    }
    return { matches: normalized, error: null, odds_documented: false };
  } catch (e: any) {
    return { matches: [], error: e?.message || String(e), odds_documented: false };
  }
}

export async function fetchTheSportsDbToday() {
  try {
    const payload = await getJson(
      THESPORTSDB_DAY,
      { d: dateKey(new Date()), s: "Soccer" },
      180_000,
    );
    const events = Array.isArray(payload?.events) ? payload.events : [];
    const matches = events.map((row: any) => providerMatch({
      source: "thesportsdb",
      id: row.idEvent,
      home: row.strHomeTeam,
      away: row.strAwayTeam,
      home_score: row.intHomeScore,
      away_score: row.intAwayScore,
      event_date: row.strTimestamp || `${row.dateEvent || ""}T${row.strTime || "00:00:00"}Z`,
      status: row.strStatus || row.strProgress,
      minute: row.intTime,
      league: row.strLeague,
      home_logo: row.strHomeTeamBadge,
      away_logo: row.strAwayTeamBadge,
      raw: row,
    })).filter(Boolean).filter((m: any) => m.is_live && !m.is_finished);
    return { matches, error: null };
  } catch (e: any) {
    return { matches: [], error: e?.message || String(e) };
  }
}

export async function fetchOpenLigaToday() {
  const now = new Date();
  try {
    const payload = await getJson(
      `${OPENLIGA}/getmatchdata/bl1/${seasonFor(now)}`,
      {},
      600_000,
    );
    const today = dateKey(now);
    const matches = (Array.isArray(payload) ? payload : []).map((row: any) => {
      const eventDate = dateIso(row.matchDateTimeUTC || row.matchDateTime);
      if (!eventDate || eventDate.slice(0, 10) !== today) return null;
      const results = Array.isArray(row.matchResults) ? row.matchResults : [];
      const latest = [...results].sort((a: any, b: any) =>
        Number(b?.resultOrderID || 0) - Number(a?.resultOrderID || 0)
      )[0] || {};
      return providerMatch({
        source: "openligadb",
        id: row.matchID,
        home: row.team1?.teamName,
        away: row.team2?.teamName,
        home_score: latest.pointsTeam1,
        away_score: latest.pointsTeam2,
        event_date: eventDate,
        status: row.matchIsFinished ? "finished" : "scheduled",
        finished: Boolean(row.matchIsFinished),
        league: "Bundesliga",
        home_logo: row.team1?.teamIconUrl,
        away_logo: row.team2?.teamIconUrl,
        raw: row,
      });
    }).filter(Boolean).filter((m: any) => m.is_live && !m.is_finished);
    // OpenLigaDB peut ne pas marquer explicitement "live"; les lignes du jour
    // restent surtout une corroboration de calendrier/résultat.
    return { matches, error: null };
  } catch (e: any) {
    return { matches: [], error: e?.message || String(e) };
  }
}

export async function fetchFreeFixturesForDate(date: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return { matches: [], meta: { error: "invalid_date" } };
  }

  const targetDate = new Date(date + "T12:00:00Z");
  const [sportscoreResult, tsdbResult, openligaResult] = await Promise.allSettled([
    getJson(
      SPORTSCORE_FIXTURES,
      { sport: "football", date, limit: "300", src: "mrxpronos" },
      180_000,
    ),
    getJson(
      THESPORTSDB_DAY,
      { d: date, s: "Soccer" },
      300_000,
    ),
    getJson(
      `${OPENLIGA}/getmatchdata/bl1/${seasonFor(targetDate)}`,
      {},
      900_000,
    ),
  ]);

  const matches: any[] = [];
  let sportscoreCount = 0;
  let tsdbCount = 0;
  let openligaCount = 0;

  if (sportscoreResult.status === "fulfilled") {
    for (const row of extractSportScoreRows(sportscoreResult.value)) {
      if (!row || typeof row !== "object") continue;
      const homeObj = row.home_team && typeof row.home_team === "object" ? row.home_team
        : row.homeTeam && typeof row.homeTeam === "object" ? row.homeTeam : {};
      const awayObj = row.away_team && typeof row.away_team === "object" ? row.away_team
        : row.awayTeam && typeof row.awayTeam === "object" ? row.awayTeam : {};
      const leagueObj = row.competition && typeof row.competition === "object" ? row.competition
        : row.league && typeof row.league === "object" ? row.league : {};
      const match = providerMatch({
        source: "sportscore",
        id: row.id ?? row.match_id ?? row.slug,
        slug: row.slug,
        home: row.home ?? homeObj.name ?? homeObj.display_name,
        away: row.away ?? awayObj.name ?? awayObj.display_name,
        home_score: row.home_score ?? row.homeScore,
        away_score: row.away_score ?? row.awayScore,
        event_date: row.time ?? row.start_time ?? row.date,
        status: row.status_text ?? row.status,
        minute: row.minute ?? row.current_minute,
        league: leagueObj.name ?? row.competition_name ?? row.league_name,
        home_logo: row.home_logo ?? homeObj.logo,
        away_logo: row.away_logo ?? awayObj.logo,
        raw: row,
      });
      if (match && match.event_date.slice(0, 10) === date) {
        matches.push(match);
        sportscoreCount++;
      }
    }
  }

  if (tsdbResult.status === "fulfilled") {
    const events = Array.isArray(tsdbResult.value?.events) ? tsdbResult.value.events : [];
    for (const row of events) {
      const match = providerMatch({
        source: "thesportsdb",
        id: row.idEvent,
        home: row.strHomeTeam,
        away: row.strAwayTeam,
        home_score: row.intHomeScore,
        away_score: row.intAwayScore,
        event_date: row.strTimestamp || `${row.dateEvent || ""}T${row.strTime || "00:00:00"}Z`,
        status: row.strStatus || row.strProgress,
        league: row.strLeague,
        home_logo: row.strHomeTeamBadge,
        away_logo: row.strAwayTeamBadge,
        raw: row,
      });
      if (match && match.event_date.slice(0, 10) === date) {
        matches.push(match);
        tsdbCount++;
      }
    }
  }

  if (openligaResult.status === "fulfilled") {
    for (const row of Array.isArray(openligaResult.value) ? openligaResult.value : []) {
      const eventDate = dateIso(row.matchDateTimeUTC || row.matchDateTime);
      if (!eventDate || eventDate.slice(0, 10) !== date) continue;
      const results = Array.isArray(row.matchResults) ? row.matchResults : [];
      const latest = [...results].sort((a: any, b: any) =>
        Number(b?.resultOrderID || 0) - Number(a?.resultOrderID || 0)
      )[0] || {};
      const match = providerMatch({
        source: "openligadb",
        id: row.matchID,
        home: row.team1?.teamName,
        away: row.team2?.teamName,
        home_score: latest.pointsTeam1,
        away_score: latest.pointsTeam2,
        event_date: eventDate,
        status: row.matchIsFinished ? "finished" : "scheduled",
        finished: Boolean(row.matchIsFinished),
        league: "Bundesliga",
        home_logo: row.team1?.teamIconUrl,
        away_logo: row.team2?.teamIconUrl,
        raw: row,
      });
      if (match) {
        matches.push(match);
        openligaCount++;
      }
    }
  }

  return {
    matches,
    meta: {
      sportscore_matches: sportscoreCount,
      thesportsdb_matches: tsdbCount,
      openligadb_matches: openligaCount,
      sportscore_error: sportscoreResult.status === "rejected"
        ? String(sportscoreResult.reason?.message || sportscoreResult.reason) : null,
      thesportsdb_error: tsdbResult.status === "rejected"
        ? String(tsdbResult.reason?.message || tsdbResult.reason) : null,
      openligadb_error: openligaResult.status === "rejected"
        ? String(openligaResult.reason?.message || openligaResult.reason) : null,
    },
  };
}


export async function fetchFreeLiveProviders() {
  const [sportscore, thesportsdb, openligadb] = await Promise.all([
    fetchSportScoreLive(),
    fetchTheSportsDbToday(),
    fetchOpenLigaToday(),
  ]);
  return {
    matches: [...sportscore.matches, ...thesportsdb.matches, ...openligadb.matches],
    meta: {
      sportscore_matches: sportscore.matches.length,
      thesportsdb_matches: thesportsdb.matches.length,
      openligadb_matches: openligadb.matches.length,
      sportscore_error: sportscore.error,
      thesportsdb_error: thesportsdb.error,
      openligadb_error: openligadb.error,
      // SportScore's public API docs do not expose an odds endpoint.
      sportscore_odds_api_documented: false,
      sportscore_attribution_required: true,
    },
  };
}
