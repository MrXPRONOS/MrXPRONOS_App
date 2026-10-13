import {
  FREE_SOURCE_QUALITY,
  providerMatchScore,
  matchProvider,
  normalizeSportScoreDetail,
  probeSportScoreOdds,
} from "../functions/_shared/football_sources.ts";

Deno.test("free source quality order is stable", () => {
  if (!(FREE_SOURCE_QUALITY.espn.overall > FREE_SOURCE_QUALITY.sportscore.overall)) {
    throw new Error("ESPN should rank above SportScore");
  }
  if (!(FREE_SOURCE_QUALITY.sportscore.overall > FREE_SOURCE_QUALITY.bsd.overall)) {
    throw new Error("SportScore should rank above BSD for general live detail");
  }
  if (FREE_SOURCE_QUALITY.sportscore.odds !== 0) {
    throw new Error("SportScore undocumented odds must never receive an automated routing score");
  }
});

Deno.test("provider fixture matching respects teams and kickoff", () => {
  const base = {
    home_team: "Paris Saint-Germain",
    away_team: "Olympique Marseille",
    event_date: "2026-10-13T19:00:00Z",
  };
  const good = {
    home_team: "Paris Saint Germain",
    away_team: "Olympique Marseille",
    event_date: "2026-10-13T19:02:00Z",
  };
  const bad = {
    home_team: "Olympique Marseille",
    away_team: "Paris Saint Germain",
    event_date: "2026-10-13T19:00:00Z",
  };
  if (providerMatchScore(base, good) < 0.68) throw new Error("good fixture rejected");
  if (providerMatchScore(base, bad) !== 0) throw new Error("reversed fixture accepted");
  if (matchProvider(base, [bad, good]) !== good) throw new Error("wrong best fixture");
});

Deno.test("SportScore detail stats normalize into LIVE stat keys", () => {
  const detail = normalizeSportScoreDetail({
    match: {
      statistics: {
        home: {
          totalShots: 14,
          shotsOnTarget: 6,
          wonCorners: 8,
          foulsCommitted: 9,
          possessionPct: "61%",
        },
        away: {
          totalShots: 8,
          shotsOnTarget: 3,
          wonCorners: 2,
          foulsCommitted: 13,
          possessionPct: "39%",
        },
      },
      timeline: [{ type: "goal", minute: 50 }],
      lineups: { home: [], away: [] },
    },
  });
  if (detail.stats.home.total_shots !== 14) throw new Error("shots missing");
  if (detail.stats.home.shots_on_target !== 6) throw new Error("shots on target missing");
  if (detail.stats.home.corner_kicks !== 8) throw new Error("corners missing");
  if (detail.stats.home.fouls !== 9) throw new Error("fouls missing");
  if (detail.stats.home.ball_possession !== 61) throw new Error("possession missing");
});

Deno.test("SportScore odds probe is diagnostic, never trusted by default", () => {
  const probe = probeSportScoreOdds({
    match: {
      markets: [{ market: "1x2", home: 1.8, draw: 3.4, away: 4.2 }],
    },
  });
  if (!probe.available) throw new Error("odds section not detected");
  if (probe.contract_verified) throw new Error("undocumented odds marked verified");
  if (probe.automation_allowed) throw new Error("undocumented odds enabled by default");
});
