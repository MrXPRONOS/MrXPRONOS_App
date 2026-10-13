import {
  FOOTBALL_PROVIDER_RANK,
  mergeFreeProviderMatches,
  normalizeSportScoreStats,
  normalizeTheSportsDbStats,
  flattenProviderStats,
} from "../functions/_shared/free_football.ts";

Deno.test("provider quality order is explicit", () => {
  if (!(FOOTBALL_PROVIDER_RANK.bsd.quality > FOOTBALL_PROVIDER_RANK.espn.quality &&
        FOOTBALL_PROVIDER_RANK.espn.quality > FOOTBALL_PROVIDER_RANK.sportscore.quality &&
        FOOTBALL_PROVIDER_RANK.sportscore.quality > FOOTBALL_PROVIDER_RANK.thesportsdb.quality &&
        FOOTBALL_PROVIDER_RANK.thesportsdb.quality > FOOTBALL_PROVIDER_RANK.openligadb.quality)) {
    throw new Error("provider quality order changed");
  }
});

Deno.test("free provider merge de-duplicates same fixture and keeps provider ids", () => {
  const rows = [
    {
      id: "sportscore:1",
      source_match_id: "1",
      home_team: "Arsenal",
      away_team: "Chelsea",
      event_date: "2026-10-13T18:00:00Z",
      home_score: 1,
      away_score: 0,
      raw_data: {
        source: "sportscore",
        provider_slug: "arsenal-vs-chelsea",
        provider_quality: 86,
      },
    },
    {
      id: "thesportsdb:9",
      source_match_id: "9",
      home_team: "Arsenal FC",
      away_team: "Chelsea FC",
      event_date: "2026-10-13T18:02:00Z",
      home_score: 1,
      away_score: 0,
      raw_data: {
        source: "thesportsdb",
        provider_quality: 78,
      },
    },
  ];
  const merged = mergeFreeProviderMatches(rows);
  if (merged.length !== 1) throw new Error("fixture was not de-duplicated");
  const sources = merged[0].raw_data.provider_sources;
  if (!sources.includes("sportscore") || !sources.includes("thesportsdb")) {
    throw new Error("provider provenance lost");
  }
  if (merged[0].raw_data.provider_ids.thesportsdb !== "9") {
    throw new Error("provider id lost");
  }
});

Deno.test("SportScore statistics normalize core live markets", () => {
  const stats = normalizeSportScoreStats({
    statistics: [
      { name: "Corners", home: 7, away: 3 },
      { name: "Shots on Target", home: 6, away: 2 },
      { name: "Fouls", home: 9, away: 12 },
      { name: "Possession", home: "58%", away: "42%" },
    ],
  });
  if (stats.home.corner_kicks !== 7 || stats.away.corner_kicks !== 3) {
    throw new Error("corners not normalized");
  }
  if (stats.home.shots_on_target !== 6 || stats.away.shots_on_target !== 2) {
    throw new Error("shots on target not normalized");
  }
  const flat = flattenProviderStats(stats);
  if (flat.corners !== 10 || flat.fouls !== 21) throw new Error("totals not flattened");
});

Deno.test("TheSportsDB statistics normalize generic event stats", () => {
  const stats = normalizeTheSportsDbStats({
    eventstats: [
      { strStat: "Corners", intHome: "5", intAway: "4" },
      { strStat: "Total Shots", intHome: "11", intAway: "9" },
    ],
  });
  if (stats.home.corner_kicks !== 5 || stats.away.total_shots !== 9) {
    throw new Error("TheSportsDB stats not normalized");
  }
});
