import {
  FOOTBALL_PROVIDER_QUALITY,
  fetchFreeFixturesForDate,
  fetchSportScoreLive,
  fetchTheSportsDbToday,
} from "../functions/_shared/football_free_sources.ts";

Deno.test("provider quality order keeps ESPN and BSD above free fallbacks", () => {
  if (!(FOOTBALL_PROVIDER_QUALITY.espn > FOOTBALL_PROVIDER_QUALITY.bsd)) {
    throw new Error("ESPN must outrank BSD");
  }
  if (!(FOOTBALL_PROVIDER_QUALITY.bsd > FOOTBALL_PROVIDER_QUALITY.sportscore)) {
    throw new Error("BSD must outrank SportScore");
  }
  if (!(FOOTBALL_PROVIDER_QUALITY.sportscore > FOOTBALL_PROVIDER_QUALITY.openligadb)) {
    throw new Error("SportScore must outrank OpenLigaDB");
  }
  if (!(FOOTBALL_PROVIDER_QUALITY.openligadb > FOOTBALL_PROVIDER_QUALITY.thesportsdb)) {
    throw new Error("OpenLigaDB must outrank TheSportsDB");
  }
});

Deno.test("SportScore live adapter normalizes match and stats without assuming documented odds", async () => {
  const previous = globalThis.fetch;
  const now = new Date().toISOString();
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/fixtures/")) {
      return new Response(JSON.stringify({
        matches: [{
          id: "ss1",
          slug: "arsenal-chelsea",
          home: "Arsenal",
          away: "Chelsea",
          home_score: 1,
          away_score: 0,
          time: now,
          status: "live",
          minute: 33,
          league_name: "Premier League",
        }],
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (url.includes("/match/")) {
      return new Response(JSON.stringify({
        match: {
          stats: {
            home: { corners: 4, "shots on target": 5, fouls: 6 },
            away: { corners: 2, "shots on target": 2, fouls: 7 },
          },
        },
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    throw new Error("unexpected fetch " + url);
  }) as typeof fetch;

  try {
    const result = await fetchSportScoreLive(1);
    if (result.odds_documented !== false) {
      throw new Error("SportScore odds must remain undocumented");
    }
    if (result.matches.length !== 1) throw new Error("expected one live match");
    const match = result.matches[0];
    if (match.source_name !== "sportscore") throw new Error("wrong provider");
    if (match.current_minute !== 33) throw new Error("minute not normalized");
    if (match.live_stats.home.corner_kicks !== 4) throw new Error("corners not normalized");
    if (match.live_stats.away.shots_on_target !== 2) throw new Error("shots on target not normalized");
    if (match.raw_data.sportscore_odds !== null) {
      throw new Error("adapter exposed undocumented SportScore odds");
    }
    if (match.raw_data.sportscore_odds_api_documented !== false) {
      throw new Error("SportScore odds contract must remain marked undocumented");
    }
  } finally {
    globalThis.fetch = previous;
  }
});


Deno.test("TheSportsDB live adapter fetches event stats before BSD fallback", async () => {
  const previous = globalThis.fetch;
  const now = new Date();
  const date = now.toISOString().slice(0, 10);
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("eventsday.php")) {
      return new Response(JSON.stringify({
        events: [{
          idEvent: "9991",
          strHomeTeam: "Arsenal",
          strAwayTeam: "Chelsea",
          intHomeScore: "1",
          intAwayScore: "0",
          strTimestamp: now.toISOString(),
          strStatus: "2nd Half",
          strLeague: "Premier League",
        }],
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    if (url.includes("lookupeventstats.php")) {
      return new Response(JSON.stringify({
        eventstats: [
          { strStat: "Corners", intHome: "5", intAway: "2" },
          { strStat: "Shots on Target", intHome: "6", intAway: "3" },
          { strStat: "Possession", strHome: "58%", strAway: "42%" },
        ],
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    throw new Error("unexpected fetch " + url + " date=" + date);
  }) as typeof fetch;
  try {
    const result = await fetchTheSportsDbToday(1);
    if (result.matches.length !== 1) throw new Error("expected one TSDB live match");
    const stats = result.matches[0].live_stats;
    if (stats.home.corner_kicks !== 5 || stats.away.corner_kicks !== 2) {
      throw new Error("TSDB corners not normalized");
    }
    if (stats.home.shots_on_target !== 6) throw new Error("TSDB SOT not normalized");
    if (stats.home.ball_possession !== 58) throw new Error("TSDB possession not normalized");
  } finally {
    globalThis.fetch = previous;
  }
});

Deno.test("free fixture calendar queries multiple high-quality OpenLigaDB competitions", async () => {
  const previous = globalThis.fetch;
  const requested: string[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    if (url.includes("sportscore.com")) {
      return new Response(JSON.stringify({ matches: [] }), {
        status: 200, headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("eventsday.php")) {
      return new Response(JSON.stringify({ events: [] }), {
        status: 200, headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("api.openligadb.de/getmatchdata/")) {
      return new Response(JSON.stringify([]), {
        status: 200, headers: { "content-type": "application/json" },
      });
    }
    throw new Error("unexpected fetch " + url);
  }) as typeof fetch;
  try {
    const result = await fetchFreeFixturesForDate("2026-10-13");
    const openLigaCalls = requested.filter((url) =>
      url.includes("api.openligadb.de/getmatchdata/")
    );
    for (const shortcut of ["bl1", "bl2", "bl3", "ucl", "dfb", "ffb1", "uel2026", "uecl2026", "nla", "wm26"]) {
      if (!openLigaCalls.some((url) => url.includes("/" + shortcut + "/2026"))) {
        throw new Error("missing OpenLigaDB competition " + shortcut);
      }
    }
    if (result.meta.openligadb_competitions_checked !== 10) {
      throw new Error("unexpected OpenLiga competition count");
    }
  } finally {
    globalThis.fetch = previous;
  }
});
