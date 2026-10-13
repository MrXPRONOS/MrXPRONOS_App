// Free-first football provider mesh for Supabase Edge Functions.
// ESPN remains in _shared/espn.ts; this module adds SportScore, TheSportsDB,
// OpenLigaDB and provider ranking/normalization.
//
// SportScore attribution requirement: any public page that uses its data must
// expose a visible "Powered by SportScore" dofollow link. live.html does so.

export const PROVIDER_QUALITY: Record<string, number> = {
  espn: 98,
  bsd: 95,
  sportscore: 91,
  thesportsdb: 80,
  openligadb: 76,
};

export const CAPABILITY_PRIORITY: Record<string, string[]> = {
  live_score: ["espn", "sportscore", "bsd", "openligadb", "thesportsdb"],
  timeline: ["espn", "sportscore", "thesportsdb", "bsd", "openligadb"],
  lineups: ["espn", "sportscore", "thesportsdb", "bsd"],
  match_stats: ["espn", "sportscore", "thesportsdb", "bsd"],
  fixtures: ["sportscore", "espn", "openligadb", "thesportsdb", "bsd"],
  final_result: ["espn", "sportscore", "openligadb", "thesportsdb", "bsd"],
  standings: ["sportscore", "openligadb", "thesportsdb", "espn", "bsd"],
  scorers: ["sportscore", "openligadb", "espn", "thesportsdb", "bsd"],
  bookmaker_odds: ["sportscore_explicit_json", "bsd"],
};

const SPORT_SCORE_FIXTURES = "https://sportscore.com/api/v1/fixtures/";
const SPORT_SCORE_MATCH = "https://sportscore.com/api/widget/match/";
const SPORTS_DB = "https://www.thesportsdb.com/api/v1/json/123";
const OPEN_LIGA = "https://api.openligadb.de";

const mem = new Map<string, { until: number; data: any }>();

function plain(v: unknown) {
  return String(v ?? "").replace(/\s+/g, " ").trim();
}
function norm(v: unknown) {
  return plain(v)
    .normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
function tokens(v: unknown) {
  return new Set(norm(v).split(" ").filter((x) => x.length > 1));
}
export function providerTeamSimilarity(a: unknown, b: unknown) {
  const aa = tokens(a), bb = tokens(b);
  if (!aa.size || !bb.size) return 0;
  let common = 0;
  for (const x of aa) if (bb.has(x)) common++;
  return common / new Set([...aa, ...bb]).size;
}
function num(v: unknown): number | null {
  if (v === null || v === undefined || v === "" || typeof v === "boolean") return null;
  const n = Number(String(v).replace("%", "").trim());
  return Number.isFinite(n) && n >= 0 ? n : null;
}
function iso(v: unknown): string | null {
  if (!v) return null;
  const d = new Date(String(v));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function state(v: unknown, complete = false) {
  const s = plain(v).toLowerCase();
  if (complete || /finished|full.?time|\bfinal\b|\bft\b/.test(s)) return "finished";
  if (/live|in.?progress|in_play|1st half|2nd half|half.?time/.test(s)) return "live";
  if (/postpon|cancel|abandon|suspend/.test(s)) return s || "postponed";
  return "scheduled";
}
function slug(v: unknown) {
  return norm(v).replace(/\s+/g, "-");
}

async function getJson(
  url: string,
  params: Record<string, string> = {},
  ttlMs = 30000,
): Promise<any> {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) if (v !== "") u.searchParams.set(k, v);
  const key = u.toString();
  const cached = mem.get(key);
  if (cached && cached.until > Date.now()) return cached.data;

  let last: unknown = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const res = await fetch(key, {
        signal: controller.signal,
        headers: {
          Accept: "application/json,text/plain,*/*",
          "User-Agent": "MrXPRONOS-ProviderMesh/1.0",
        },
      });
      if (res.status === 429 && attempt === 0) {
        await new Promise((r) => setTimeout(r, 600));
        continue;
      }
      if (!res.ok) throw new Error(`Provider HTTP ${res.status}`);
      const data = await res.json();
      if (typeof data !== "object" || data === null) throw new Error("Provider non-JSON object");
      mem.set(key, { until: Date.now() + ttlMs, data });
      return data;
    } catch (e) {
      last = e;
    } finally {
      clearTimeout(timer);
    }
  }
  if (cached) return cached.data;
  throw last || new Error("Provider unavailable");
}

function canonical(
  provider: string,
  providerId: unknown,
  home: unknown,
  away: unknown,
  kickoff: unknown,
  extra: Record<string, any> = {},
) {
  const id = plain(providerId);
  const eventDate = iso(kickoff);
  return {
    id: id ? `${provider}:${id}` : `${provider}:${slug(home)}:${slug(away)}:${eventDate || ""}`,
    source_match_id: id,
    source_name: provider,
    home_team: plain(home),
    away_team: plain(away),
    home_score: num(extra.home_score),
    away_score: num(extra.away_score),
    status: state(extra.status, extra.completed === true),
    current_minute: num(extra.minute) || 0,
    event_date: eventDate,
    league_name: plain(extra.league),
    home_logo: plain(extra.home_logo),
    away_logo: plain(extra.away_logo),
    is_live: state(extra.status, extra.completed === true) === "live",
    is_finished: state(extra.status, extra.completed === true) === "finished",
    provider_quality: PROVIDER_QUALITY[provider] || 0,
    provider_ids: id ? { [provider]: id } : {},
    provider_meta: { [provider]: extra.meta || {} },
    raw_data: {
      source: provider,
      provider_ids: id ? { [provider]: id } : {},
      provider_meta: { [provider]: extra.meta || {} },
      original_payload: extra.raw ?? null,
    },
  };
}

export function normalizeSportScore(item: any) {
  if (!item || typeof item !== "object") return null;
  const homeRaw = item.home;
  const awayRaw = item.away;
  const homeObj = item.home_team && typeof item.home_team === "object"
    ? item.home_team : homeRaw && typeof homeRaw === "object" ? homeRaw : {};
  const awayObj = item.away_team && typeof item.away_team === "object"
    ? item.away_team : awayRaw && typeof awayRaw === "object" ? awayRaw : {};
  const home = homeObj.name ?? homeObj.display_name ?? homeObj.title ??
    (typeof homeRaw === "string" ? homeRaw : null) ?? item.home_name;
  const away = awayObj.name ?? awayObj.display_name ?? awayObj.title ??
    (typeof awayRaw === "string" ? awayRaw : null) ?? item.away_name;
  if (!home || !away) return null;

  const statusRaw = item.status;
  const statusObj = statusRaw && typeof statusRaw === "object" ? statusRaw : {};
  const status = item.status_text ?? statusObj.name ?? statusObj.short_name ??
    statusObj.short ?? statusObj.state ?? (typeof statusRaw === "string" ? statusRaw : "");
  const compRaw = item.competition;
  const leagueRaw = item.league;
  const leagueObj = compRaw && typeof compRaw === "object"
    ? compRaw : leagueRaw && typeof leagueRaw === "object" ? leagueRaw : {};
  const league = leagueObj.name ?? leagueObj.title ??
    (typeof compRaw === "string" ? compRaw : null) ??
    (typeof leagueRaw === "string" ? leagueRaw : null) ?? item.competition_name;
  const matchSlug = plain(item.slug ?? item.match_slug);
  return canonical(
    "sportscore", item.id ?? matchSlug, home, away,
    item.time ?? item.start_time ?? item.kickoff ?? item.start_at ?? item.date,
    {
      home_score: item.home_score ?? item.score_home ?? homeObj.score,
      away_score: item.away_score ?? item.score_away ?? awayObj.score,
      status,
      minute: item.minute ?? item.clock ?? statusObj.minute,
      league,
      home_logo: item.home_logo ?? homeObj.logo ?? homeObj.image,
      away_logo: item.away_logo ?? awayObj.logo ?? awayObj.image,
      raw: item,
      meta: {
        slug: matchSlug,
        url: matchSlug ? `https://sportscore.com/football/match/${matchSlug}/` : "",
      },
    },
  );
}


function sportScoreRows(payload: any): any[] {
  if (Array.isArray(payload)) return payload.filter((x) => x && typeof x === "object");
  if (!payload || typeof payload !== "object") return [];
  for (const key of ["matches", "fixtures", "results", "data"]) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  if (payload.home || payload.away || payload.home_team || payload.away_team) return [payload];
  return [];
}

export async function fetchSportScoreDay(date: string, status = "") {
  const payload = await getJson(
    SPORT_SCORE_FIXTURES,
    {
      sport: "football", date, status, limit: "200", src: "mrxpronos",
    },
    status === "live" ? 45000 : 60000,
  );
  return sportScoreRows(payload).map(normalizeSportScore).filter(Boolean);
}

export async function fetchSportScoreLive() {
  return fetchSportScoreDay(new Date().toISOString().slice(0, 10), "live");
}

export async function fetchSportScoreDetail(matchSlug: string, live = false) {
  if (!matchSlug) return null;
  return getJson(
    SPORT_SCORE_MATCH,
    { sport: "football", slug: matchSlug, src: "mrxpronos" },
    live ? 20000 : 120000,
  );
}

export function normalizeTheSportsDb(item: any) {
  if (!item || typeof item !== "object" || !item.strHomeTeam || !item.strAwayTeam) return null;
  const kickoff = item.strTimestamp ||
    (item.dateEvent ? `${item.dateEvent}T${item.strTime || "00:00:00"}Z` : null);
  return canonical("thesportsdb", item.idEvent, item.strHomeTeam, item.strAwayTeam, kickoff, {
    home_score: item.intHomeScore,
    away_score: item.intAwayScore,
    status: item.strStatus ?? item.strProgress,
    league: item.strLeague,
    home_logo: item.strHomeTeamBadge,
    away_logo: item.strAwayTeamBadge,
    minute: item.strProgress,
    raw: item,
  });
}

export async function fetchTheSportsDbDay(date: string) {
  const payload = await getJson(
    `${SPORTS_DB}/eventsday.php`,
    { d: date, s: "Soccer" },
    180000,
  );
  const rows = Array.isArray(payload?.events) ? payload.events : [];
  return rows.map(normalizeTheSportsDb).filter(Boolean);
}

export async function searchTheSportsDbMatch(home: string, away: string, date: string) {
  const title = `${home}_vs_${away}`.replace(/\s+/g, "_");
  const payload = await getJson(
    `${SPORTS_DB}/searchevents.php`,
    { e: title, d: date },
    300000,
  );
  const rows = Array.isArray(payload?.event) ? payload.event : Array.isArray(payload?.events) ? payload.events : [];
  return rows.map(normalizeTheSportsDb).filter(Boolean);
}


export async function fetchTheSportsDbEvent(eventId: string) {
  if (!/^\d+$/.test(String(eventId || ""))) return null;
  const payload = await getJson(`${SPORTS_DB}/lookupevent.php`, { id: String(eventId) }, 120000);
  const rows = Array.isArray(payload?.events) ? payload.events : [];
  return rows.length ? normalizeTheSportsDb(rows[0]) : null;
}

export async function fetchTheSportsDbEventStats(eventId: string) {
  if (!/^\d+$/.test(String(eventId || ""))) return null;
  return getJson(`${SPORTS_DB}/lookupeventstats.php`, { id: String(eventId) }, 60000);
}

export async function fetchTheSportsDbTimeline(eventId: string) {
  if (!/^\d+$/.test(String(eventId || ""))) return null;
  return getJson(`${SPORTS_DB}/lookuptimeline.php`, { id: String(eventId) }, 60000);
}

export async function fetchTheSportsDbLineup(eventId: string) {
  if (!/^\d+$/.test(String(eventId || ""))) return null;
  return getJson(`${SPORTS_DB}/lookuplineup.php`, { id: String(eventId) }, 120000);
}

function statName(v: unknown) {
  return norm(v).replace(/\s+/g, "");
}
function statValue(v: any): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "string") {
    const n = Number(v.replace("%", "").replace(",", ".").trim());
    return Number.isFinite(n) ? n : null;
  }
  return num(v);
}
function assignStat(target: any, label: unknown, value: any) {
  const key = statName(label);
  const n = statValue(value);
  if (n == null) return;
  const aliases: Record<string,string> = {
    corners: "corner_kicks", cornerkicks: "corner_kicks", woncorners: "corner_kicks",
    fouls: "fouls", foulscommitted: "fouls",
    yellowcards: "yellow_cards", yellowcard: "yellow_cards",
    redcards: "red_cards", redcard: "red_cards",
    shots: "total_shots", totalshots: "total_shots", shotstotal: "total_shots",
    shotsontarget: "shots_on_target", shotsongoal: "shots_on_target",
    possession: "ball_possession", possessionpct: "ball_possession", possessionpercentage: "ball_possession",
  };
  const out = aliases[key];
  if (out) target[out] = n;
}

/** Parse generic provider stats into the live engine's home/away schema. */
export function normalizeProviderStats(payload: any) {
  const result:any = { home: {}, away: {} };
  if (!payload || typeof payload !== "object") return result;

  const ingestObject = (obj:any, side:"home"|"away") => {
    if (!obj || typeof obj !== "object") return;
    for (const [k,v] of Object.entries(obj)) {
      if (typeof v !== "object") assignStat(result[side], k, v);
    }
  };

  for (const rootKey of ["stats","statistics","team_stats","match_stats","data"]) {
    const root = payload?.[rootKey];
    if (root && typeof root === "object" && !Array.isArray(root)) {
      ingestObject(root.home, "home");
      ingestObject(root.away, "away");
    }
  }
  ingestObject(payload.home_stats, "home");
  ingestObject(payload.away_stats, "away");

  const arrays:any[][] = [];
  for (const key of ["stats","statistics","eventstats","results","data"]) {
    if (Array.isArray(payload?.[key])) arrays.push(payload[key]);
  }
  if (Array.isArray(payload)) arrays.push(payload);

  for (const rows of arrays) {
    for (const row of rows) {
      if (!row || typeof row !== "object") continue;
      const label = row.name ?? row.label ?? row.stat ?? row.strStat ?? row.strStatName;
      const side = String(row.homeAway ?? row.side ?? "").toLowerCase();
      if (side === "home") assignStat(result.home, label, row.value ?? row.displayValue ?? row.strHome);
      else if (side === "away") assignStat(result.away, label, row.value ?? row.displayValue ?? row.strAway);
      else {
        const hv = row.home ?? row.homeValue ?? row.strHome ?? row.intHome;
        const av = row.away ?? row.awayValue ?? row.strAway ?? row.intAway;
        assignStat(result.home, label, hv);
        assignStat(result.away, label, av);
      }
    }
  }

  // TheSportsDB sometimes returns rows with strStat + strHome/strAway in eventstats.
  const eventRows = Array.isArray(payload?.eventstats) ? payload.eventstats :
    Array.isArray(payload?.eventstats?.eventstats) ? payload.eventstats.eventstats : [];
  for (const row of eventRows) {
    assignStat(result.home, row?.strStat ?? row?.strStatName, row?.strHome ?? row?.intHome);
    assignStat(result.away, row?.strStat ?? row?.strStatName, row?.strAway ?? row?.intAway);
  }
  return result;
}

/** Free stats lookup: SportScore first, then TheSportsDB; no BSD. */
export async function fetchFreeMatchStats(match:any) {
  const meta = match?.provider_meta || match?.raw_data?.provider_meta || {};
  const sport = meta?.sportscore || match?.raw_data?.provider_meta?.sportscore || {};
  const sportSlug = String(sport?.slug || "");
  if (sportSlug) {
    try {
      const payload = await fetchSportScoreDetail(sportSlug, Boolean(match?.is_live));
      const stats = normalizeProviderStats(payload);
      return { stats, source: "sportscore", payload };
    } catch {}
  }

  const tsdbId = String(
    match?.provider_ids?.thesportsdb ||
    match?.raw_data?.provider_ids?.thesportsdb ||
    ""
  );
  if (/^\d+$/.test(tsdbId)) {
    try {
      const payload = await fetchTheSportsDbEventStats(tsdbId);
      const stats = normalizeProviderStats(payload);
      return { stats, source: "thesportsdb", payload };
    } catch {}
  }

  // Locate a free provider match if this row came from ESPN/BSD only.
  try {
    const found = await findFreeProviderMatch(match);
    if (found) {
      const foundMeta = found?.provider_meta || found?.raw_data?.provider_meta || {};
      const slug = String(foundMeta?.sportscore?.slug || "");
      if (slug) {
        const payload = await fetchSportScoreDetail(slug, Boolean(match?.is_live));
        return { stats: normalizeProviderStats(payload), source: "sportscore", payload, match: found };
      }
      const id = String(found?.provider_ids?.thesportsdb || found?.source_match_id || "");
      if (String(found?.source_name) === "thesportsdb" && /^\d+$/.test(id)) {
        const payload = await fetchTheSportsDbEventStats(id);
        return { stats: normalizeProviderStats(payload), source: "thesportsdb", payload, match: found };
      }
    }
  } catch {}
  return null;
}

export function normalizeOpenLigaDb(item: any) {
  if (!item || typeof item !== "object") return null;
  const home = item.team1?.teamName;
  const away = item.team2?.teamName;
  if (!home || !away) return null;
  const results = Array.isArray(item.matchResults) ? item.matchResults : [];
  let final: any = null;
  for (const result of results) {
    if (!result || typeof result !== "object") continue;
    const name = norm(result.resultName);
    const order = num(result.resultOrderID) || 0;
    if (name.includes("endergebnis") || name.includes("full") || order >= 2) final = result;
  }
  return canonical(
    "openligadb", item.matchID ?? item.matchId, home, away,
    item.matchDateTimeUTC ?? item.matchDateTime,
    {
      home_score: final?.pointsTeam1,
      away_score: final?.pointsTeam2,
      status: item.matchIsFinished ? "finished" : "scheduled",
      league: item.leagueName,
      home_logo: item.team1?.teamIconUrl,
      away_logo: item.team2?.teamIconUrl,
      raw: item,
      meta: {
        leagueShortcut: item.leagueShortcut,
        leagueSeason: item.leagueSeason,
        goals: Array.isArray(item.goals) ? item.goals : [],
      },
    },
  );
}

export async function fetchOpenLigaDbForTeam(teamName: string) {
  if (!plain(teamName)) return [];
  const safe = encodeURIComponent(plain(teamName));
  const payload = await getJson(
    `${OPEN_LIGA}/getmatchesbyteam/${safe}/1/1`,
    {},
    300000,
  );
  const rows = Array.isArray(payload) ? payload : [];
  return rows.map(normalizeOpenLigaDb).filter(Boolean);
}

export function providerMatchScore(a: any, b: any) {
  const h = providerTeamSimilarity(a?.home_team, b?.home_team);
  const aw = providerTeamSimilarity(a?.away_team, b?.away_team);
  if (Math.min(h, aw) < 0.35) return 0;
  let score = (h + aw) / 2;
  const at = Date.parse(String(a?.event_date || ""));
  const bt = Date.parse(String(b?.event_date || ""));
  if (Number.isFinite(at) && Number.isFinite(bt)) {
    const hours = Math.abs(at - bt) / 3600000;
    if (hours > 8) return 0;
    score += Math.max(0, 0.2 - hours * 0.025);
  }
  return score;
}

export function mergeProviderEvents(rows: any[]) {
  const merged: any[] = [];
  const sorted = [...rows].sort((a, b) =>
    (PROVIDER_QUALITY[String(b?.source_name || b?.raw_data?.source || "")] || b?.provider_quality || 0) -
    (PROVIDER_QUALITY[String(a?.source_name || a?.raw_data?.source || "")] || a?.provider_quality || 0)
  );
  for (const incoming of sorted) {
    let best = -1, bestScore = 0;
    for (let i = 0; i < merged.length; i++) {
      const s = providerMatchScore(merged[i], incoming);
      if (s > bestScore) { bestScore = s; best = i; }
    }
    if (best < 0 || bestScore < 0.72) {
      merged.push({ ...incoming });
      continue;
    }
    const current = merged[best];
    const cq = current?.provider_quality || PROVIDER_QUALITY[String(current?.source_name || "")] || 0;
    const iq = incoming?.provider_quality || PROVIDER_QUALITY[String(incoming?.source_name || "")] || 0;
    const preferred = iq > cq ? incoming : current;
    const other = iq > cq ? current : incoming;
    const out = { ...preferred };
    for (const k of [
      "event_date", "home_team", "away_team", "home_score", "away_score",
      "league_name", "home_logo", "away_logo", "current_minute",
    ]) {
      if ((out[k] === null || out[k] === undefined || out[k] === "" || out[k] === 0) &&
          other[k] !== null && other[k] !== undefined && other[k] !== "") out[k] = other[k];
    }
    const sources = Array.from(new Set([
      ...(current?.raw_data?.sources || [current?.source_name].filter(Boolean)),
      ...(incoming?.raw_data?.sources || [incoming?.source_name].filter(Boolean)),
    ]));
    out.provider_ids = { ...(current?.provider_ids || {}), ...(incoming?.provider_ids || {}) };
    out.provider_meta = { ...(current?.provider_meta || {}), ...(incoming?.provider_meta || {}) };
    out.raw_data = {
      ...(out.raw_data || {}),
      source: out.source_name || out.raw_data?.source,
      sources,
      provider_ids: out.provider_ids,
      provider_meta: out.provider_meta,
    };
    merged[best] = out;
  }
  return merged;
}

export async function findFreeProviderMatch(probe: any) {
  const date = String(probe?.event_date || "").slice(0, 10) || new Date().toISOString().slice(0, 10);
  const pools: any[] = [];
  try { pools.push(...await fetchSportScoreDay(date)); } catch {}
  try { pools.push(...await searchTheSportsDbMatch(probe?.home_team || "", probe?.away_team || "", date)); } catch {}
  try { pools.push(...await fetchOpenLigaDbForTeam(probe?.home_team || "")); } catch {}
  let best: any = null, score = 0;
  for (const row of pools) {
    const s = providerMatchScore(probe, row);
    if (s > score) { best = row; score = s; }
  }
  return score >= 0.72 ? best : null;
}

export function explicitSportScoreOdds(payload: any) {
  const found: any[] = [];
  const seen = new Set<string>();
  const walk = (value: any, path: string[] = []) => {
    if (Array.isArray(value)) {
      for (const child of value) walk(child, path);
      return;
    }
    if (!value || typeof value !== "object") return;
    const pathText = path.join("/").toLowerCase();
    const forbidden = /prediction|probability|confidence|ai/.test(pathText);
    const keys = Object.keys(value);
    const context = keys.some((k) => /odds|bookmaker|market|price/i.test(k)) ||
      /odds|bookmaker|market/.test(pathText);
    if (context && !forbidden) {
      const lower = Object.fromEntries(keys.map((k) => [k.toLowerCase(), k]));
      const market = value[lower.market] ?? value[lower.market_name] ?? "";
      const outcome = value[lower.outcome] ?? value[lower.selection] ?? "";
      const bookmaker = value[lower.bookmaker] ?? value[lower.bookmaker_name] ?? "";
      const rawOdds = value[lower.decimal_odds] ?? value[lower.odds_decimal] ??
        value[lower.odds] ?? value[lower.price];
      const odds = Number(rawOdds);
      if (Number.isFinite(odds) && odds > 1) {
        const key = JSON.stringify([market, outcome, bookmaker, odds]);
        if (!seen.has(key)) {
          seen.add(key);
          found.push({
            market: plain(market),
            outcome: plain(outcome),
            bookmaker: plain(bookmaker),
            odds,
            source: "sportscore_explicit_json",
          });
        }
      }
    }
    for (const [k, child] of Object.entries(value)) walk(child, [...path, k]);
  };
  walk(payload);
  return found;
}
