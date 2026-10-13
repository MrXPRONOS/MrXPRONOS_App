import {
  normalizeSportScore,
  normalizeTsdb,
  normalizeSportScoreStats,
  normalizeTsdbStats,
  providerPolicy,
} from "../functions/_shared/free-football.ts";

Deno.test("free provider policy keeps BSD as documented odds source", () => {
  const policy = providerPolicy();
  if (policy.fetch_priority.at(-1) !== "bsd") throw new Error("BSD must be last fetch fallback");
  if (policy.odds_priority.length !== 1 || policy.odds_priority[0] !== "bsd") {
    throw new Error("Unexpected odds provider");
  }
  if (policy.sportscore_odds_api_supported !== false) throw new Error("SportScore odds must stay disabled");
});

Deno.test("SportScore normalization preserves legitimate zero score", () => {
  const match = normalizeSportScore({
    id: 1,
    home: "Arsenal",
    away: "Chelsea",
    home_score: 0,
    away_score: 0,
    status: "live",
    time: "2026-10-13T18:00:00Z",
    slug: "arsenal-chelsea",
  });
  if (!match || match.home_score !== 0 || match.away_score !== 0 || !match.is_live) {
    throw new Error("SportScore normalization failed");
  }
});

Deno.test("TheSportsDB normalization maps finished events", () => {
  const match = normalizeTsdb({
    idEvent: "9",
    strSport: "Soccer",
    strHomeTeam: "Arsenal",
    strAwayTeam: "Chelsea",
    intHomeScore: "2",
    intAwayScore: "1",
    strStatus: "Match Finished",
    strTimestamp: "2026-10-13T18:00:00Z",
  });
  if (!match || !match.is_finished || match.home_score !== 2 || match.away_score !== 1) {
    throw new Error("TSDB normalization failed");
  }
});

Deno.test("free provider stats use live engine shape", () => {
  const sport = normalizeSportScoreStats({
    statistics: [
      { name: "Corners", home: 6, away: 3 },
      { name: "Total Shots", home: 14, away: 9 },
      { name: "Fouls", home: 10, away: 12 },
    ],
  });
  if (sport.home.corner_kicks !== 6 || sport.away.total_shots !== 9 || sport.totals.fouls !== 22) {
    throw new Error("SportScore stats shape invalid");
  }

  const tsdb = normalizeTsdbStats([
    { strStat: "Shots on Target", intHome: "5", intAway: "2" },
  ]);
  if (tsdb.home.shots_on_target !== 5 || tsdb.away.shots_on_target !== 2) {
    throw new Error("TSDB stats shape invalid");
  }
});
