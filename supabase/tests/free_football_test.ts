import {
  FREE_SOURCE_RANKING,
  normalizeProviderStatsPayload,
  providerMatchScore,
} from "../functions/_shared/free-football.ts";

Deno.test("provider ranking keeps conflict priority explicit", () => {
  if (!(FREE_SOURCE_RANKING.espn.rank < FREE_SOURCE_RANKING.bsd.rank &&
        FREE_SOURCE_RANKING.bsd.rank < FREE_SOURCE_RANKING.sportscore.rank &&
        FREE_SOURCE_RANKING.sportscore.rank < FREE_SOURCE_RANKING.thesportsdb.rank &&
        FREE_SOURCE_RANKING.thesportsdb.rank < FREE_SOURCE_RANKING.openligadb.rank)) {
    throw new Error("provider order changed");
  }
});

Deno.test("SportScore on/off target stats derive total shots", () => {
  const stats = normalizeProviderStatsPayload({
    match: {
      stats: [
        { label: "Ball Possession", home: 52, away: 48 },
        { label: "Shots on Target", home: 4, away: 3 },
        { label: "Shots off Target", home: 6, away: 3 },
      ],
    },
  });
  if (stats.home.shots_on_target !== 4 || stats.away.shots_on_target !== 3) {
    throw new Error("shots on target missing");
  }
  if (stats.home.total_shots !== 10 || stats.away.total_shots !== 6) {
    throw new Error("total shots not derived");
  }
  if (stats.totals.total_shots !== 16) throw new Error("total match shots wrong");
  if (stats.home.ball_possession !== 52 || stats.away.ball_possession !== 48) {
    throw new Error("possession missing");
  }
});

Deno.test("provider matching rejects reversed teams", () => {
  const score = providerMatchScore(
    { home_team: "Arsenal", away_team: "Chelsea", event_date: "2026-10-13T18:00:00Z" },
    { home_team: "Chelsea", away_team: "Arsenal", event_date: "2026-10-13T18:00:00Z" },
  );
  if (score >= 0.68) throw new Error("reversed fixture should not match");
});
