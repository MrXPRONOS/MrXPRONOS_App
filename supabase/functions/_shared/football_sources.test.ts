// Regression tests for football provider adapters. All network calls are mocked.
import {
  fetchSportScoreFixtures,
  normalizeSportScoreDetail,
  fetchTheSportsDbStats,
  fetchOpenLigaDay,
  resolveTheSportsDbEvent,
} from "./football_sources.ts";

function check(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
function jsonReply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json" },
  });
}

Deno.test("SportScore: stable event id is not the match detail slug", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonReply({ matches: [{
    home: "Home United", away: "Away City",
    url: "/football/match/away-city-vs-home-united/abc123xyz/",
    status: "live", status_text: "2nd half", minute: 62,
    time: "2098-08-12T18:00:00Z", home_score: 2, away_score: 1,
  }] });
  try {
    const rows = await fetchSportScoreFixtures("2098-08-12", "live");
    check(rows.length === 1, "Expected one fixture");
    check(rows[0].id === "sportscore:abc123xyz", "Wrong stable event ID");
    check(rows[0].raw_data.sportscore_slug === "away-city-vs-home-united", "Wrong detail slug");
    check(rows[0].current_minute === 62, "Lost actual minute");
    check(rows[0].is_live === true, "Live status not recognized");
  } finally {
    globalThis.fetch = realFetch;
  }
});

Deno.test("SportScore: missing minute remains unknown (never inferred from 1st half)", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonReply({ matches: [{
    home: "A", away: "B", status: "live", status_text: "1st half",
    time: "2098-08-13T18:00:00Z", url: "/football/match/a-vs-b/fixture456/",
  }] });
  try {
    const rows = await fetchSportScoreFixtures("2098-08-13", "live");
    check(rows.length === 1 && rows[0].current_minute === 0, "Must not fabricate minutes");
    check(rows[0].is_live === true, "Missing minute is not a completed match");
  } finally {
    globalThis.fetch = realFetch;
  }
});

Deno.test("SportScore detail: use observed minute but not status-based estimates", () => {
  const valid = normalizeSportScoreDetail({
    match: { minute: 73, status_text: "2nd half", stats: {} },
  });
  check(valid.minute === 73, "Expected observed detail minute");
  const unknown = normalizeSportScoreDetail({
    match: { status_text: "2nd half", stats: {} },
  });
  check(unknown.minute === null, "Must not invent 2nd-half clock");
});

Deno.test("SportScore real payload: 45+ and labeled statistics are parsed without inventing corners", () => {
  const payload = { match: { live_minute:"45+", status:"live", stats:[
    {label:"Ball Possession",home:54,away:46,suffix:"%"},
    {label:"Shots on Target",home:3,away:2,suffix:""},
    {label:"Shots off Target",home:2,away:3,suffix:""},
    {label:"Attacks",home:54,away:51,suffix:""},
    {label:"Dangerous Attacks",home:31,away:19,suffix:""},
  ] }};
  const d = normalizeSportScoreDetail(payload);
  check(d.minute === 45, "45+ must preserve known minute floor");
  check(d.stats.home.ball_possession === 54, "Possession missing");
  check(d.stats.away.shots_on_target === 2, "Shots on target missing");
  check(d.stats.home.shots_off_target === 2, "Shots off target missing");
  check(d.stats.home.attacks === 54, "Attacks missing");
  check(d.stats.away.dangerous_attacks === 19, "Dangerous attacks missing");
  check(d.stats.home.corner_kicks === undefined, "Absent corners must never be invented");
  check(d.stats.home.total_shots === undefined, "Total shots must not be inferred without blocked shot data");
});

Deno.test("TheSportsDB: normalize real eventstats field names", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => jsonReply({ eventstats: [
    { strStat: "Total Shots", intHome: "18", intAway: "14" },
    { strStat: "Shots on Goal", intHome: "11", intAway: "8" },
    { strStat: "Corners", intHome: "7", intAway: "3" },
  ] });
  try {
    const value = await fetchTheSportsDbStats("1032723");
    check(value?.stats.home.total_shots === 18, "Home shots lost");
    check(value?.stats.away.shots_on_target === 8, "Shots-on-goal mapping failed");
    check(value?.stats.home.corner_kicks === 7, "Corners mapping failed");
  } finally {
    globalThis.fetch = realFetch;
  }
});

Deno.test("OpenLigaDB: map real match result structure to canonical feed", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const u = new URL(String(input));
    if (!u.pathname.includes("/bl1/")) return jsonReply([]);
    return jsonReply([{
      matchID: 424242,
      matchDateTimeUTC: "2098-10-10T16:00:00Z",
      matchIsFinished: true,
      team1: { teamName: "Borussia Example", teamIconUrl: "https://example.com/a.png" },
      team2: { teamName: "Union Example", teamIconUrl: "https://example.com/b.png" },
      matchResults: [
        { resultOrderID: 1, pointsTeam1: 0, pointsTeam2: 0 },
        { resultOrderID: 2, pointsTeam1: 2, pointsTeam2: 1 },
      ],
    }]);
  };
  try {
    const rows = await fetchOpenLigaDay("2098-10-10");
    check(rows.length === 1, "Expected a mapped Bundesliga fixture");
    check(rows[0].id === "openligadb:424242", "Invalid match key");
    check(rows[0].home_score === 2 && rows[0].away_score === 1, "Final result lost");
    check(rows[0].is_finished === true, "Finished status lost");
  } finally {
    globalThis.fetch = realFetch;
  }
});

Deno.test("TheSportsDB: HTTP 503 gets bounded retry and cooldown", async () => {
  const realFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => { calls++; return jsonReply({ error: "Unavailable" }, 503); };
  try {
    let rejected = false;
    try { await resolveTheSportsDbEvent("Unavailable A", "Unavailable B", "2098-12-19T19:00:00Z"); }
    catch { rejected = true; }
    check(rejected && calls === 2, "Transient HTTP 503 must retry exactly once");
    try { await resolveTheSportsDbEvent("Unavailable C", "Unavailable D", "2098-12-19T19:00:00Z"); }
    catch { /* expected endpoint-level cooldown */ }
    check(calls === 2, "Cooldown should prevent immediate retry flood");
  } finally {
    globalThis.fetch = realFetch;
  }
});
