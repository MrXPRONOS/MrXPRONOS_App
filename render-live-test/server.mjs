// Mr XPRONOS — prototype isolé pour Render gratuit.
// Source des données : ESPN, SportScore, TheSportsDB.
// Aucune prédiction n'est publiée et aucune base Supabase n'est modifiée.
import http from "node:http";
import { pathToFileURL } from "node:url";

const PORT = Number(process.env.PORT || 10000);
const INTERVAL_MS = 60_000;
const CONCURRENCY = Math.min(20, Math.max(1, Number(process.env.DETAIL_CONCURRENCY || 10)));
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/all";
const SPORT = "https://sportscore.com/api/v1";
const TSDB = "https://www.thesportsdb.com/api/v1/json/123";
const TRACKED = ["corner_kicks", "total_shots", "shots_on_target", "fouls", "yellow_cards", "red_cards", "ball_possession", "attacks", "dangerous_attacks"];
const cache = new Map();
const blocked = new Map();
const state = { busy: false, cycle: 0, started_at: null, completed_at: null, matches: [], diagnostics: {}, error: null };
const asText = v => String(v ?? "").trim();
const num = v => v === null || v === undefined || v === "" || v === "-" ? null : (Number.isFinite(Number(String(v).replace("%", "").replace(",", "."))) ? Number(String(v).replace("%", "").replace(",", ".")) : null);
const label = s => asText(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\b(fc|cf|sc|afc|club|football|soccer)\b/g, " ").replace(/[^a-z0-9]/g, " ").replace(/\s+/g, " ").trim();
const iso = s => { const d = new Date(s || ""); return Number.isFinite(d.getTime()) ? d.toISOString() : null; };
const pair = (home, away) => label(home) + "|" + label(away);
const statKey = s => asText(s).toLowerCase().replace(/[^a-z0-9]/g, "");
function mappedKey(s) {
  const k = statKey(s);
  if (["corners","cornerkicks","woncorners"].includes(k)) return "corner_kicks";
  if (["totalshots","shotstotal","shots"].includes(k)) return "total_shots";
  if (["shotsontarget","shotsongoal"].includes(k)) return "shots_on_target";
  if (["fouls","foulscommitted"].includes(k)) return "fouls";
  if (["yellowcards"].includes(k)) return "yellow_cards";
  if (["redcards"].includes(k)) return "red_cards";
  if (["possession","possessionpct","possessionpercentage","ballpossession"].includes(k)) return "ball_possession";
  if (["attacks","totalattacks"].includes(k)) return "attacks";
  if (["dangerousattacks"].includes(k)) return "dangerous_attacks";
  return null;
}
function isLive(s) {
  const value = asText(s).toLowerCase();
  return value === "in" || /live|in.?progress|1st.?half|2nd.?half|half.?time|1h|2h|halftime/.test(value);
}
function currentDateKeys() {
  const now = new Date();
  return [...new Set([new Date(now.getTime() - 86400000), now].map(d => d.toISOString().slice(0, 10)))];
}
async function getJson(url, ttlMs = 50_000) {
  const now = Date.now();
  const old = cache.get(url);
  if (old && old.until > now) return old.data;
  const path = new URL(url);
  const endpoint = path.origin + path.pathname;
  if ((blocked.get(endpoint) || 0) > now) throw new Error("Provider cooldown " + endpoint);
  let last;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(url, { headers: { "Accept": "application/json", "User-Agent": "MrXPRONOS-Render-Test/1.0" }, signal: AbortSignal.timeout(8500) });
      if (!res.ok) {
        if (res.status === 429 || res.status >= 500) {
          blocked.set(endpoint, Date.now() + (res.status === 429 ? 120_000 : 45_000));
        }
        throw new Error("HTTP " + res.status + " " + endpoint);
      }
      if (!(res.headers.get("content-type") || "").includes("json")) throw new Error("JSON expected from " + endpoint);
      const data = await res.json();
      cache.set(url, { data, until: Date.now() + ttlMs });
      blocked.delete(endpoint);
      return data;
    } catch (e) {
      last = e;
      if (attempt === 0 && !(blocked.get(endpoint) > Date.now())) await new Promise(r => setTimeout(r, 250));
      else break;
    }
  }
  throw last;
}
function fixture({ source, id, home, away, date, minute = null, status = "live", league = "", home_score = null, away_score = null, ref = {} }) {
  return { id: source + ":" + asText(id), home_team: asText(home), away_team: asText(away),
    event_date: iso(date), current_minute: num(minute), status: asText(status), league_name: asText(league),
    home_score: num(home_score), away_score: num(away_score), providers: [source], refs: { [source]: ref },
    live_stats: { home: {}, away: {} }, stats_observed_at: null, stats_sources: [], detail_errors: [] };
}
function parseESPN(data) {
  const matches = [];
  for (const e of data?.events || []) {
    const competition = e?.competitions?.[0] || {};
    const competitors = competition.competitors || [];
    const h = competitors.find(x => x?.homeAway === "home");
    const a = competitors.find(x => x?.homeAway === "away");
    const status = e?.status?.type?.state || competition?.status?.type?.state || "";
    if (!h || !a || !isLive(status)) continue;
    matches.push(fixture({ source: "espn", id: e.id, home: h.team?.displayName || h.team?.name,
      away: a.team?.displayName || a.team?.name, date: e.date, status,
      minute: e.status?.displayClock, league: e.league?.name || data?.leagues?.[0]?.name,
      home_score: h.score, away_score: a.score,
      ref: { event_id: asText(e.id), home_id: asText(h.team?.id), away_id: asText(a.team?.id) } }));
  }
  return matches;
}
function sportSlug(x, home, away) {
  const m = asText(x?.url || x?.match_url).match(/\/match\/([^/?#]+)\/([^/?#]+)/);
  return asText(x?.slug || x?.match_slug || x?.url_slug || m?.[1]) ||
    label(home + "-vs-" + away).replace(/\s+/g, "-");
}
function parseSportScore(data) {
  const rows = data?.matches || data?.fixtures || data?.results || [];
  const out = [];
  for (const x of Array.isArray(rows) ? rows : []) {
    const status = x?.status_text || x?.status || "";
    if (!isLive(status)) continue;
    const home = typeof x.home === "object" ? x.home?.name : x.home;
    const away = typeof x.away === "object" ? x.away?.name : x.away;
    if (!home || !away) continue;
    out.push(fixture({ source: "sportscore", id: x.id || x.match_id || sportSlug(x,home,away),
      home, away, date: x.time || x.date || x.start_time,
      status, minute: x.live_minute ?? x.minute ?? x.elapsed, home_score: x.home_score ?? x.score_home,
      away_score: x.away_score ?? x.score_away,
      league: typeof x.competition === "object" ? x.competition?.name : x.competition || x.league,
      ref: { slug: sportSlug(x,home,away) } }));
  }
  return out;
}
function parseTSDB(data) {
  const out = [];
  for (const x of data?.events || []) {
    if (!isLive(x?.strStatus)) continue;
    if (!x.strHomeTeam || !x.strAwayTeam) continue;
    out.push(fixture({ source: "thesportsdb", id: x.idEvent, home: x.strHomeTeam,
      away: x.strAwayTeam, status: x.strStatus, date: x.strTimestamp || (x.dateEvent + "T" + (x.strTime || "00:00:00Z")),
      league: x.strLeague, home_score: x.intHomeScore, away_score: x.intAwayScore,
      ref: { event_id: asText(x.idEvent) } }));
  }
  return out;
}
function sameFixture(a, b) {
  if (pair(a.home_team,a.away_team) !== pair(b.home_team,b.away_team)) return false;
  const aT = Date.parse(a.event_date || ""), bT = Date.parse(b.event_date || "");
  if (Number.isFinite(aT) && Number.isFinite(bT) && Math.abs(aT-bT) > 4*3600000) return false;
  return true;
}
export function mergeFixtures(rows) {
  const merged = [];
  for (const row of rows) {
    const match = merged.find(existing => sameFixture(existing,row));
    if (!match) { merged.push(structuredClone(row)); continue; }
    match.providers = [...new Set([...match.providers,...row.providers])];
    match.refs = { ...match.refs,...row.refs };
    if (!match.current_minute && row.current_minute) match.current_minute = row.current_minute;
    if (match.home_score == null) match.home_score = row.home_score;
    if (match.away_score == null) match.away_score = row.away_score;
  }
  return merged;
}
function emptyStats() { return { home: {}, away: {} }; }
function addSide(stats, side, data) {
  if (Array.isArray(data)) {
    for (const x of data) { const k = mappedKey(x?.name || x?.label || x?.type || x?.strStat);
      const v = num(x?.displayValue ?? x?.value ?? x?.total); if (k && v !== null) stats[side][k] = v; }
  } else if (data && typeof data === "object") {
    for (const [key,value] of Object.entries(data)) {
      const k = mappedKey(key);
      const v = num(value && typeof value === "object" ? value.value ?? value.displayValue : value);
      if (k && v !== null) stats[side][k] = v;
    }
  }
}
function normalizeDetail(input) {
  const stats = emptyStats();
  const env = input?.data || input || {};
  const root = env?.match || env;
  for (const set of [root?.stats,root?.statistics,root?.team_stats,root?.teamStats,root?.match_statistics,env?.stats,env?.statistics]) {
    if (!set) continue;
    addSide(stats,"home",set.home || set.home_team || set.homeTeam);
    addSide(stats,"away",set.away || set.away_team || set.awayTeam);
    if (Array.isArray(set)) for (const x of set) {
      const k = mappedKey(x?.label || x?.name || x?.type || x?.stat);
      const h = num(x?.home ?? x?.homeValue), a = num(x?.away ?? x?.awayValue);
      if (k && h !== null) stats.home[k] = h;
      if (k && a !== null) stats.away[k] = a;
    }
  }
  return stats;
}
function normalizeEspnSummary(data, refs) {
  const teams = data?.boxscore?.teams || [];
  const h = teams.find(x => asText(x?.team?.id) === refs.home_id);
  const a = teams.find(x => asText(x?.team?.id) === refs.away_id);
  if (!h || !a || refs.home_id === refs.away_id) return emptyStats();
  const stats = emptyStats();
  addSide(stats,"home",h.statistics);
  addSide(stats,"away",a.statistics);
  return stats;
}
function normalizeTsdbStats(data) {
  const stats = emptyStats();
  for (const x of data?.eventstats || data?.statistics || []) {
    const k = mappedKey(x?.strStat || x?.name || x?.type);
    const h = num(x?.intHome ?? x?.home ?? x?.homeValue);
    const a = num(x?.intAway ?? x?.away ?? x?.awayValue);
    if (k && h !== null) stats.home[k] = h;
    if (k && a !== null) stats.away[k] = a;
  }
  return stats;
}
export function hasPair(stats, k) { return num(stats?.home?.[k]) !== null && num(stats?.away?.[k]) !== null; }
export function mergeStats(base, extra) {
  const out = structuredClone(base || emptyStats());
  for (const k of TRACKED) {
    if (hasPair(extra, k) && !hasPair(out, k)) {
      out.home[k] = extra.home[k]; out.away[k] = extra.away[k];
    }
  }
  return out;
}
export async function mapConcurrent(items, limit, func) {
  let next = 0;
  const out = Array(items.length);
  await Promise.all(Array.from({ length: Math.min(items.length,Math.max(1,limit)) }, async () => {
    while (next < items.length) {
      const at = next++;
      try { out[at] = await func(items[at],at); }
      catch (error) { out[at] = { ...items[at], detail_errors: [...(items[at]?.detail_errors || []), String(error)] }; }
    }
  }));
  return out;
}
async function loadFixtures() {
  const tasks = [];
  for (const day of currentDateKeys()) {
    const espnDay = day.replaceAll("-","");
    tasks.push({ provider: "espn", url: ESPN + "/scoreboard?dates=" + espnDay + "&limit=500", parse: parseESPN });
    tasks.push({ provider: "sportscore", url: SPORT + "/fixtures/?sport=football&date=" + day + "&status=live&limit=200", parse: parseSportScore });
    tasks.push({ provider: "thesportsdb", url: TSDB + "/eventsday.php?d=" + day + "&s=Soccer", parse: parseTSDB });
  }
  const results = await Promise.allSettled(tasks.map(t => getJson(t.url)));
  const errors = [];
  const rows = [];
  const counts = {};
  for (let i = 0; i < tasks.length; i++) {
    const t = tasks[i], r = results[i];
    if (r.status !== "fulfilled") { errors.push(t.provider + ": " + String(r.reason)); continue; }
    const parsed = t.parse(r.value);
    rows.push(...parsed);
    counts[t.provider] = (counts[t.provider] || 0) + parsed.length;
    if (t.provider === "sportscore" && (r.value?.matches || r.value?.fixtures || []).length >= 200)
      errors.push("SportScore returned 200 fixtures: verify pagination; coverage may be incomplete");
    if (t.provider === "espn" && (r.value?.events || []).length >= 500)
      errors.push("ESPN returned 500 fixtures: verify pagination; coverage may be incomplete");
  }
  return { matches: mergeFixtures(rows), errors, counts };
}
async function enrichOne(match) {
  const calls = [];
  const er = match.refs?.espn;
  if (er?.event_id) calls.push({ name: "espn", run: async () => normalizeEspnSummary(
    await getJson(ESPN + "/summary?event=" + encodeURIComponent(er.event_id),60_000),er) });
  const sr = match.refs?.sportscore;
  if (sr?.slug) calls.push({ name: "sportscore", run: async () => normalizeDetail(
    await getJson(SPORT + "/match/?sport=football&slug=" + encodeURIComponent(sr.slug),60_000)) });
  const tr = match.refs?.thesportsdb;
  if (tr?.event_id) calls.push({ name: "thesportsdb", run: async () => normalizeTsdbStats(
    await getJson(TSDB + "/lookupeventstats.php?id=" + encodeURIComponent(tr.event_id),90_000)) });
  let stats = emptyStats(), sources = [], errors = [];
  const parts = await Promise.allSettled(calls.map(c => c.run()));
  for (let i = 0; i < parts.length; i++) {
    if (parts[i].status === "fulfilled") {
      const before = TRACKED.filter(k => hasPair(stats,k)).length;
      stats = mergeStats(stats,parts[i].value);
      if (TRACKED.filter(k => hasPair(stats,k)).length > before) sources.push(calls[i].name);
    } else errors.push(calls[i].name + ": " + String(parts[i].reason));
  }
  return { ...match, live_stats: stats, stats_sources: sources,
    stats_observed_at: sources.length ? new Date().toISOString() : null,
    detail_errors: errors, missing_stats: TRACKED.filter(k => !hasPair(stats,k)) };
}
export function coverage(matches) {
  const byMarket = Object.fromEntries(TRACKED.map(k => [k, matches.filter(m => hasPair(m.live_stats,k)).length]));
  return { total_matches: matches.length, detail_attempted: matches.length,
    complete_core: matches.filter(m => ["corner_kicks","total_shots","fouls"].every(k => hasPair(m.live_stats,k))).length,
    with_any_core: matches.filter(m => ["corner_kicks","total_shots","fouls"].some(k => hasPair(m.live_stats,k))).length,
    detail_errors: matches.filter(m => (m.detail_errors || []).length).length, by_market: byMarket };
}
async function refresh() {
  if (state.busy) return { skipped: "previous_cycle_running" };
  state.busy = true; state.started_at = new Date().toISOString(); state.error = null;
  const started = Date.now();
  try {
    const feeds = await loadFixtures();
    const updated = await mapConcurrent(feeds.matches, CONCURRENCY, enrichOne);
    const diag = { ...coverage(updated), raw_source_counts: feeds.counts,
      source_errors: feeds.errors, elapsed_ms: Date.now() - started,
      longer_than_minute: Date.now() - started > 60_000 };
    state.matches = updated; state.diagnostics = diag; state.completed_at = new Date().toISOString(); state.cycle++;
    console.log(JSON.stringify({ tag:"render_live_cycle", cycle:state.cycle, ...diag }));
    return diag;
  } catch (e) {
    state.error = String(e);
    console.error("render_live_cycle_failed",String(e));
    return { error:String(e) };
  } finally { state.busy = false; }
}
function respond(res, status, data) {
  res.writeHead(status, { "content-type":"application/json; charset=utf-8",
    "cache-control":"no-store", "access-control-allow-origin":"*" });
  res.end(JSON.stringify(data));
}
function serve() {
  http.createServer((req,res) => {
    const path = new URL(req.url || "/", "http://localhost").pathname;
    if (req.method === "GET" && path === "/health") {
      return respond(res,200,{ service:"MrXPRONOS Render LIVE test", uptime_seconds:Math.floor(process.uptime()),
        busy:state.busy, cycle:state.cycle, started_at:state.started_at, completed_at:state.completed_at,
        total_matches:state.matches.length, diagnostics:state.diagnostics, error:state.error });
    }
    if (req.method === "GET" && path === "/matches") {
      return respond(res,200,{ updated_at:state.completed_at, count:state.matches.length, matches:state.matches });
    }
    if (req.method === "POST" && path === "/refresh") {
      const token = process.env.REFRESH_TOKEN || "";
      if (!token || req.headers["x-refresh-token"] !== token) return respond(res,401,{ error:"Unauthorized; configure REFRESH_TOKEN" });
      refresh().catch(e => console.error(e));
      return respond(res,202,{ accepted:true, already_running:state.busy });
    }
    respond(res,404,{ error:"Not found", endpoints:["GET /health","GET /matches","POST /refresh"] });
  }).listen(PORT,"0.0.0.0",() => console.log("MrXPRONOS Render LIVE test listening on "+PORT));
  refresh().catch(e => console.error(e));
  setInterval(() => refresh().catch(e => console.error(e)), INTERVAL_MS);
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) serve();
