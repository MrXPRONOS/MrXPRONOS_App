// Free football providers used before quota-constrained BSD calls.
//
// Quality/reliability ranking (intrinsic data quality, not request order):
// BSD 96 > ESPN 94 > SportScore 86 > TheSportsDB 78 > OpenLigaDB 72.
// Fetch order is intentionally free-first; BSD remains the final fallback and
// the authoritative provider for bookmaker odds in this project.

export const FOOTBALL_PROVIDER_RANK = {
  bsd: { quality: 96, reliability: 95, cost: "quota" },
  espn: { quality: 94, reliability: 89, cost: "free" },
  sportscore: { quality: 86, reliability: 84, cost: "free" },
  thesportsdb: { quality: 78, reliability: 82, cost: "free_limited" },
  openligadb: { quality: 72, reliability: 76, cost: "free" },
} as const;

const SPORT_SCORE_BASE = "https://sportscore.com";
const TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123";
const OPENLIGA_BASE = "https://api.openligadb.de";

const mem = new Map<string, { until: number; data: any }>();
const pending = new Map<string, Promise<any>>();

function text(value: unknown) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}
function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "" || value === "-") return null;
  const n = Number(String(value).replace(/%$/, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
function minuteFromStatus(value: unknown) {
  const raw = text(value);
  const match = raw.match(/(\d+)(?:\D*\+\D*(\d+))?/);
  if (!match) return 0;
  return Math.max(0, Number(match[1] || 0) + Number(match[2] || 0));
}
function safeDate(value: unknown): string | null {
  if (!value) return null;
  const d = new Date(String(value));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function norm(value: unknown) {
  return text(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}
function similarity(a: unknown, b: unknown) {
  const aa = new Set(norm(a).split(" ").filter(Boolean));
  const bb = new Set(norm(b).split(" ").filter(Boolean));
  if (!aa.size || !bb.size) return 0;
  let common = 0;
  for (const token of aa) if (bb.has(token)) common++;
  return common / new Set([...aa, ...bb]).size;
}

async function fetchJson(
  url: URL,
  ttlMs: number,
  timeoutMs = 8500,
): Promise<any> {
  const key = url.toString();
  const cached = mem.get(key);
  if (cached && cached.until > Date.now()) return cached.data;
  const existing = pending.get(key);
  if (existing) return existing;

  const task = (async () => {
    let last: unknown = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(url.toString(), {
          signal: controller.signal,
          headers: {
            Accept: "application/json",
            "User-Agent": "MrXPRONOS-FreeFootball/1.0",
          },
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        mem.set(key, { until: Date.now() + ttlMs, data });
        return data;
      } catch (error) {
        last = error;
        if (attempt === 0) await new Promise((r) => setTimeout(r, 350));
      } finally {
        clearTimeout(timer);
      }
    }
    if (cached) return cached.data;
    throw last instanceof Error ? last : new Error(String(last));
  })();

  pending.set(key, task);
  try {
    return await task;
  } finally {
    pending.delete(key);
  }
}

function canonical(args: {
  source: "sportscore" | "thesportsdb" | "openligadb";
  sourceId?: unknown;
  home?: unknown;
  away?: unknown;
  eventDate?: unknown;
  homeScore?: unknown;
  awayScore?: unknown;
  status?: unknown;
  league?: unknown;
  homeLogo?: unknown;
  awayLogo?: unknown;
  slug?: unknown;
  raw?: any;
}) {
  const home = text(args.home);
  const away = text(args.away);
  if (!home || !away) return null;
  const statusText = text(args.status);
  const nstatus = norm(statusText);
  let state = "pre";
  if (/(finished|full time|after penalties|\bft\b)/.test(nstatus)) state = "post";
  else if (/(live|in progress|1st half|2nd half|half time|halftime)/.test(nstatus)) state = "in";

  const sourceId = text(args.sourceId);
  const slug = text(args.slug);
  const id = `${args.source}:${sourceId || slug || norm(home + "-" + away)}`;
  const eventDate = safeDate(args.eventDate);
  return {
    id,
    source_match_id: sourceId,
    home_team: home,
    away_team: away,
    home_score: numberOrNull(args.homeScore),
    away_score: numberOrNull(args.awayScore),
    status: state === "post" ? "finished" : state === "in" ? "live" : "scheduled",
    state,
    minute: minuteFromStatus(statusText),
    current_minute: minuteFromStatus(statusText),
    is_live: state === "in",
    is_finished: state === "post",
    event_date: eventDate,
    start_time: eventDate,
    league_name: text(args.league),
    home_logo: text(args.homeLogo) || null,
    away_logo: text(args.awayLogo) || null,
    live_stats: {},
    stats_last_updated_at: null,
    raw_data: {
      source: args.source,
      source_match_id: sourceId,
      provider_slug: slug || null,
      provider_quality: FOOTBALL_PROVIDER_RANK[args.source].quality,
      original: args.raw || {},
      live_stats: {},
    },
  };
}

function rowsOf(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  for (const key of ["matches", "fixtures", "results", "data", "events"]) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

export async function fetchSportScoreFixtures(
  date: string,
  status?: "live" | "finished" | "upcoming",
) {
  const url = new URL(`${SPORT_SCORE_BASE}/api/v1/fixtures/`);
  url.searchParams.set("sport", "football");
  url.searchParams.set("date", date);
  url.searchParams.set("limit", "200");
  url.searchParams.set("src", "mrxpronos");
  if (status) url.searchParams.set("status", status);
  const payload = await fetchJson(url, date === new Date().toISOString().slice(0, 10) ? 55_000 : 900_000);
  return rowsOf(payload)
    .map((item: any) => {
      const home = item?.home_team && typeof item.home_team === "object" ? item.home_team : {};
      const away = item?.away_team && typeof item.away_team === "object" ? item.away_team : {};
      const competition = item?.competition && typeof item.competition === "object" ? item.competition : {};
      return canonical({
        source: "sportscore",
        sourceId: item?.id ?? item?.match_id,
        home: item?.home ?? item?.home_name ?? home?.name,
        away: item?.away ?? item?.away_name ?? away?.name,
        eventDate: item?.time ?? item?.start_time ?? item?.kickoff ?? item?.date,
        homeScore: item?.home_score ?? item?.score_home,
        awayScore: item?.away_score ?? item?.score_away,
        status: item?.status_text ?? item?.status,
        league: item?.league ?? item?.competition_name ?? competition?.name,
        homeLogo: item?.home_logo ?? home?.logo,
        awayLogo: item?.away_logo ?? away?.logo,
        slug: item?.slug,
        raw: item,
      });
    })
    .filter(Boolean) as any[];
}

export async function fetchSportScoreDetail(slug: string) {
  if (!slug) return null;
  const url = new URL(`${SPORT_SCORE_BASE}/api/v1/match/`);
  url.searchParams.set("sport", "football");
  url.searchParams.set("slug", slug);
  url.searchParams.set("src", "mrxpronos");
  const payload = await fetchJson(url, 55_000);
  if (!payload || typeof payload !== "object") return null;
  return payload?.match && typeof payload.match === "object" ? payload.match : payload;
}

export async function fetchTheSportsDbDay(date: string) {
  const url = new URL(`${TSDB_BASE}/eventsday.php`);
  url.searchParams.set("d", date);
  url.searchParams.set("s", "Soccer");
  const payload = await fetchJson(url, date === new Date().toISOString().slice(0, 10) ? 120_000 : 1_800_000);
  return rowsOf(payload)
    .map((item: any) => {
      const eventDate =
        item?.strTimestamp ||
        (item?.dateEvent ? `${item.dateEvent}T${item.strTime || "00:00:00"}Z` : null);
      return canonical({
        source: "thesportsdb",
        sourceId: item?.idEvent,
        home: item?.strHomeTeam,
        away: item?.strAwayTeam,
        eventDate,
        homeScore: item?.intHomeScore,
        awayScore: item?.intAwayScore,
        status: item?.strStatus ?? item?.strProgress,
        league: item?.strLeague,
        homeLogo: item?.strHomeTeamBadge ?? item?.strHomeTeamLogo,
        awayLogo: item?.strAwayTeamBadge ?? item?.strAwayTeamLogo,
        raw: item,
      });
    })
    .filter(Boolean) as any[];
}

async function fetchTsdbEndpoint(endpoint: string, eventId: string) {
  if (!/^\d+$/.test(String(eventId || ""))) return null;
  const url = new URL(`${TSDB_BASE}/${endpoint}`);
  url.searchParams.set("id", eventId);
  return await fetchJson(url, 120_000);
}

export async function fetchTheSportsDbDetails(eventId: string) {
  const [event, stats, timeline, lineup] = await Promise.all([
    fetchTsdbEndpoint("lookupevent.php", eventId),
    fetchTsdbEndpoint("lookupeventstats.php", eventId),
    fetchTsdbEndpoint("lookuptimeline.php", eventId),
    fetchTsdbEndpoint("lookuplineup.php", eventId),
  ]);
  return { event, stats, timeline, lineup };
}

function openLigaSeason(date: string) {
  const d = new Date(`${date}T12:00:00Z`);
  return String(d.getUTCMonth() >= 6 ? d.getUTCFullYear() : d.getUTCFullYear() - 1);
}

export async function fetchOpenLigaDbDay(date: string, maxLeagues = 8) {
  const season = openLigaSeason(date);
  const leaguesUrl = new URL(`${OPENLIGA_BASE}/getavailableleagues/${season}`);
  const leagues = await fetchJson(leaguesUrl, 6 * 3600_000);
  if (!Array.isArray(leagues)) return [];

  const wanted = [
    "bundesliga", "premier league", "champions league", "europa league",
    "conference league", "laliga", "la liga", "dfb", "nations league",
    "world cup", "weltmeister",
  ];
  const selected = leagues
    .filter((x: any) => {
      const name = norm(x?.leagueName ?? x?.name);
      const quality = numberOrNull(x?.leagueQuality ?? x?.qualityIndex) ?? 0;
      return text(x?.leagueShortcut) && quality >= 90 && wanted.some((term) => name.includes(term));
    })
    .sort((a: any, b: any) =>
      (numberOrNull(b?.leagueQuality ?? b?.qualityIndex) ?? 0) -
      (numberOrNull(a?.leagueQuality ?? a?.qualityIndex) ?? 0)
    )
    .slice(0, maxLeagues);

  const all: any[] = [];
  for (const league of selected) {
    try {
      const url = new URL(
        `${OPENLIGA_BASE}/getmatchdata/${encodeURIComponent(league.leagueShortcut)}/${season}`,
      );
      const payload = await fetchJson(url, 300_000);
      if (!Array.isArray(payload)) continue;
      for (const item of payload) {
        const eventDate = safeDate(item?.matchDateTimeUTC ?? item?.matchDateTime);
        if (!eventDate || eventDate.slice(0, 10) !== date) continue;
        const team1 = item?.team1 && typeof item.team1 === "object" ? item.team1 : {};
        const team2 = item?.team2 && typeof item.team2 === "object" ? item.team2 : {};
        const resultRows = Array.isArray(item?.matchResults) ? item.matchResults : [];
        const final =
          resultRows.find((x: any) => Number(x?.resultOrderID) === 2) ||
          resultRows[resultRows.length - 1] ||
          {};
        const row = canonical({
          source: "openligadb",
          sourceId: item?.matchID,
          home: team1?.teamName,
          away: team2?.teamName,
          eventDate,
          homeScore: final?.pointsTeam1,
          awayScore: final?.pointsTeam2,
          status: item?.matchIsFinished ? "finished" : "scheduled",
          league: league?.leagueName,
          homeLogo: team1?.teamIconUrl,
          awayLogo: team2?.teamIconUrl,
          raw: item,
        });
        if (row) all.push(row);
      }
    } catch (error) {
      console.warn("OpenLigaDB league fetch failed", league?.leagueShortcut, error);
    }
  }
  return all;
}

function matchTime(value: any) {
  const t = Date.parse(String(value?.event_date ?? value?.start_time ?? ""));
  return Number.isFinite(t) ? t : null;
}

export function sameFreeProviderMatch(a: any, b: any) {
  const ta = matchTime(a);
  const tb = matchTime(b);
  if (ta != null && tb != null && Math.abs(ta - tb) > 4 * 3600_000) return 0;
  return (
    similarity(a?.home_team, b?.home_team) +
    similarity(a?.away_team, b?.away_team)
  ) / 2;
}

export function mergeFreeProviderMatches(matches: any[]) {
  const sorted = [...(matches || [])].sort((a, b) => {
    const qa = Number(a?.raw_data?.provider_quality ?? FOOTBALL_PROVIDER_RANK[a?.raw_data?.source as keyof typeof FOOTBALL_PROVIDER_RANK]?.quality ?? 0);
    const qb = Number(b?.raw_data?.provider_quality ?? FOOTBALL_PROVIDER_RANK[b?.raw_data?.source as keyof typeof FOOTBALL_PROVIDER_RANK]?.quality ?? 0);
    return qb - qa;
  });
  const result: any[] = [];
  for (const row of sorted) {
    let best = -1;
    let score = 0;
    for (let i = 0; i < result.length; i++) {
      const current = sameFreeProviderMatch(row, result[i]);
      if (current > score) {
        score = current;
        best = i;
      }
    }
    if (best < 0 || score < 0.68) {
      result.push({
        ...row,
        raw_data: {
          ...(row.raw_data || {}),
          provider_sources: [row?.raw_data?.source].filter(Boolean),
          provider_ids: row?.raw_data?.source && row?.source_match_id
            ? { [row.raw_data.source]: row.source_match_id }
            : {},
        },
      });
      continue;
    }
    const current = result[best];
    const source = row?.raw_data?.source;
    const sources = [...new Set([
      ...(current?.raw_data?.provider_sources || []),
      ...(source ? [source] : []),
    ])];
    const providerIds = { ...(current?.raw_data?.provider_ids || {}) };
    if (source && row?.source_match_id) providerIds[source] = row.source_match_id;
    const slugs = { ...(current?.raw_data?.provider_slugs || {}) };
    if (source && row?.raw_data?.provider_slug) slugs[source] = row.raw_data.provider_slug;

    result[best] = {
      ...current,
      home_score: current.home_score ?? row.home_score,
      away_score: current.away_score ?? row.away_score,
      home_logo: current.home_logo || row.home_logo,
      away_logo: current.away_logo || row.away_logo,
      league_name: current.league_name || row.league_name,
      event_date: current.event_date || row.event_date,
      start_time: current.start_time || row.start_time,
      is_live: Boolean(current.is_live || row.is_live),
      is_finished: Boolean(current.is_finished || row.is_finished),
      raw_data: {
        ...(current.raw_data || {}),
        provider_sources: sources,
        provider_ids: providerIds,
        provider_slugs: slugs,
      },
    };
  }
  return result;
}

export async function collectFreeMatchesForDate(
  date: string,
  status?: "live" | "finished" | "upcoming",
) {
  const jobs = await Promise.allSettled([
    fetchSportScoreFixtures(date, status),
    fetchTheSportsDbDay(date),
    fetchOpenLigaDbDay(date),
  ]);
  const rows: any[] = [];
  const meta: Record<string, any> = {};
  const names = ["sportscore", "thesportsdb", "openligadb"];
  jobs.forEach((job, i) => {
    if (job.status === "fulfilled") {
      rows.push(...job.value);
      meta[names[i]] = { ok: true, count: job.value.length };
    } else {
      meta[names[i]] = { ok: false, error: String(job.reason) };
    }
  });
  const merged = mergeFreeProviderMatches(rows);
  return { matches: merged, meta };
}

function statName(value: unknown) {
  return norm(value).replace(/ /g, "");
}
const STAT_ALIASES: Record<string, string[]> = {
  corner_kicks: ["corners", "cornerkicks", "woncorners"],
  total_shots: ["shots", "totalshots", "shotstotal"],
  shots_on_target: ["shotsontarget", "shotsongoal", "shotstarget"],
  fouls: ["fouls", "foulscommitted"],
  possession: ["possession", "possessionpct", "ballpossession"],
  offsides: ["offsides", "offside"],
  saves: ["saves", "goalkeepersaves"],
  yellow_cards: ["yellowcards", "yellowcard"],
  red_cards: ["redcards", "redcard"],
};

function emptyStats() {
  return {
    home: {} as Record<string, number | null>,
    away: {} as Record<string, number | null>,
  };
}

function assignStat(out: any, side: "home" | "away", name: unknown, value: unknown) {
  const key = statName(name);
  const n = numberOrNull(value);
  if (n == null) return;
  for (const [target, aliases] of Object.entries(STAT_ALIASES)) {
    if (aliases.includes(key)) {
      out[side][target] = n;
      return;
    }
  }
}

export function normalizeSportScoreStats(detail: any) {
  const out = emptyStats();
  const stats =
    detail?.statistics ?? detail?.stats ?? detail?.match_statistics ??
    detail?.match?.statistics ?? detail?.match?.stats;

  if (Array.isArray(stats)) {
    for (const row of stats) {
      if (!row || typeof row !== "object") continue;
      const name = row?.name ?? row?.label ?? row?.type ?? row?.stat;
      assignStat(out, "home", name, row?.home ?? row?.home_value ?? row?.homeValue ?? row?.value_home);
      assignStat(out, "away", name, row?.away ?? row?.away_value ?? row?.awayValue ?? row?.value_away);
    }
  } else if (stats && typeof stats === "object") {
    const home = stats?.home ?? stats?.home_team ?? {};
    const away = stats?.away ?? stats?.away_team ?? {};
    for (const [name, value] of Object.entries(home || {})) assignStat(out, "home", name, value);
    for (const [name, value] of Object.entries(away || {})) assignStat(out, "away", name, value);
    for (const [name, row] of Object.entries(stats)) {
      if (!row || typeof row !== "object" || Array.isArray(row)) continue;
      assignStat(out, "home", name, (row as any).home);
      assignStat(out, "away", name, (row as any).away);
    }
  }
  return out;
}

export function normalizeTheSportsDbStats(payload: any) {
  const out = emptyStats();
  const rows = rowsOf(payload);
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const name = row?.strStat ?? row?.strStatistic ?? row?.strType ?? row?.name;
    assignStat(out, "home", name, row?.intHome ?? row?.strHome ?? row?.home ?? row?.homeValue);
    assignStat(out, "away", name, row?.intAway ?? row?.strAway ?? row?.away ?? row?.awayValue);
  }
  return out;
}

function completeness(stats: any) {
  const keys = ["corner_kicks", "total_shots", "shots_on_target", "fouls"];
  return keys.reduce((sum, key) =>
    sum + (numberOrNull(stats?.home?.[key]) != null && numberOrNull(stats?.away?.[key]) != null ? 1 : 0), 0);
}

export function flattenProviderStats(pair: any) {
  const home = pair?.home || {};
  const away = pair?.away || {};
  const out: any = {};
  for (const key of Object.keys(STAT_ALIASES)) {
    if (home[key] != null) out[`home_${key}`] = home[key];
    if (away[key] != null) out[`away_${key}`] = away[key];
    const a = numberOrNull(home[key]);
    const b = numberOrNull(away[key]);
    if (a != null && b != null && key !== "possession") {
      const totalKey = key === "corner_kicks" ? "corners" : key;
      out[totalKey] = a + b;
    }
  }
  return out;
}

export async function enrichMatchWithFreeStats(match: any) {
  const date = safeDate(match?.event_date ?? match?.start_time)?.slice(0, 10);
  if (!date) return { match, source: null, score: 0, calls: 0 };
  let calls = 0;
  let bestStats: any = null;
  let bestSource: string | null = null;
  let bestScore = 0;

  let sportSlug =
    match?.raw_data?.provider_slug ||
    match?.raw_data?.provider_slugs?.sportscore ||
    null;

  if (!sportSlug) {
    try {
      calls++;
      const sportRows = await fetchSportScoreFixtures(date);
      let best: any = null;
      let bestMatchScore = 0;
      for (const row of sportRows) {
        const score = sameFreeProviderMatch(match, row);
        if (score > bestMatchScore) {
          best = row;
          bestMatchScore = score;
        }
      }
      if (best && bestMatchScore >= 0.68) sportSlug = best?.raw_data?.provider_slug;
    } catch {}
  }

  if (sportSlug) {
    try {
      calls++;
      const detail = await fetchSportScoreDetail(String(sportSlug));
      const stats = normalizeSportScoreStats(detail);
      const score = completeness(stats);
      if (score > bestScore) {
        bestStats = stats;
        bestSource = "sportscore";
        bestScore = score;
      }
    } catch {}
  }

  let tsdbId = match?.raw_data?.provider_ids?.thesportsdb || null;
  if (!tsdbId && bestScore < 4) {
    try {
      calls++;
      const dayRows = await fetchTheSportsDbDay(date);
      let best: any = null;
      let bestMatchScore = 0;
      for (const row of dayRows) {
        const score = sameFreeProviderMatch(match, row);
        if (score > bestMatchScore) {
          best = row;
          bestMatchScore = score;
        }
      }
      if (best && bestMatchScore >= 0.68) tsdbId = best.source_match_id;
    } catch {}
  }

  if (tsdbId && bestScore < 4) {
    try {
      calls++;
      const details = await fetchTheSportsDbDetails(String(tsdbId));
      const stats = normalizeTheSportsDbStats(details?.stats);
      const score = completeness(stats);
      if (score > bestScore) {
        bestStats = stats;
        bestSource = "thesportsdb";
        bestScore = score;
      }
    } catch {}
  }

  if (!bestStats || bestScore === 0) return { match, source: null, score: 0, calls };

  const flat = flattenProviderStats(bestStats);
  return {
    match: {
      ...match,
      live_stats: { ...(match?.live_stats || {}), ...flat },
      stats_last_updated_at: new Date().toISOString(),
      raw_data: {
        ...(match?.raw_data || {}),
        live_stats: { ...(match?.raw_data?.live_stats || {}), ...flat },
        stats_last_updated_at: new Date().toISOString(),
        stats_sources: [...new Set([
          ...((match?.raw_data?.stats_sources || []) as string[]),
          bestSource,
        ])],
        stats_authority: bestSource,
      },
    },
    source: bestSource,
    score: bestScore,
    calls,
  };
}
