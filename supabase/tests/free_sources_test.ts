import {
  FOOTBALL_PROVIDER_QUALITY,
  fetchSportScoreLive,
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
