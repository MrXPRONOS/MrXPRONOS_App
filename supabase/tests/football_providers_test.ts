import {
  PROVIDER_QUALITY,
  explicitSportScoreOdds,
  mergeProviderEvents,
  providerMatchScore,
  normalizeSportScore,
  normalizeTheSportsDb,
  normalizeOpenLigaDb,
} from "../functions/_shared/football_providers.ts";

Deno.test("provider quality order keeps ESPN above other free providers", () => {
  if (!(PROVIDER_QUALITY.espn > PROVIDER_QUALITY.sportscore &&
        PROVIDER_QUALITY.sportscore > PROVIDER_QUALITY.thesportsdb &&
        PROVIDER_QUALITY.thesportsdb > PROVIDER_QUALITY.openligadb)) {
    throw new Error("provider ranking changed unexpectedly");
  }
});

Deno.test("SportScore odds parser ignores AI probabilities", () => {
  const payload = {
    ai_prediction: {
      market: "double chance",
      outcome: "1X",
      probability: 0.8,
      odds: 1.25,
    },
    bookmakers: [{
      market: "Double Chance",
      selection: "1X",
      bookmaker: "Example",
      decimal_odds: 1.46,
    }],
  };
  const odds = explicitSportScoreOdds(payload);
  if (odds.length !== 1 || odds[0].odds !== 1.46) {
    throw new Error("AI probability leaked into bookmaker odds");
  }
});

Deno.test("provider event merge preserves highest quality and fills missing logo", () => {
  const espn:any = {
    id: "espn:1", source_name: "espn", provider_quality: 98,
    home_team: "Arsenal", away_team: "Chelsea",
    event_date: "2026-10-13T18:00:00Z",
    home_logo: "", away_logo: "",
    provider_ids: { espn: "1" }, provider_meta: { espn: {} }, raw_data: { source: "espn" },
  };
  const sport:any = {
    id: "sportscore:2", source_name: "sportscore", provider_quality: 91,
    home_team: "Arsenal", away_team: "Chelsea",
    event_date: "2026-10-13T18:00:00Z",
    home_logo: "https://example.com/a.png", away_logo: "",
    provider_ids: { sportscore: "2" }, provider_meta: { sportscore: { slug: "arsenal-chelsea" } },
    raw_data: { source: "sportscore" },
  };
  const out = mergeProviderEvents([sport, espn]);
  if (out.length !== 1) throw new Error("same fixture did not merge");
  if (out[0].source_name !== "espn") throw new Error("lower quality provider won");
  if (out[0].home_logo !== "https://example.com/a.png") throw new Error("missing field was not enriched");
  if (!out[0].provider_ids.sportscore) throw new Error("provider mapping lost");
});

Deno.test("normalizers produce comparable fixtures", () => {
  const sport:any = normalizeSportScore({
    id: 11,
    home: "Arsenal",
    away: "Chelsea",
    time: "2026-10-13T18:00:00Z",
    status: "scheduled",
  });
  const tsdb:any = normalizeTheSportsDb({
    idEvent: "22",
    strHomeTeam: "Arsenal",
    strAwayTeam: "Chelsea",
    strTimestamp: "2026-10-13T18:00:00Z",
    strStatus: "Not Started",
  });
  const open:any = normalizeOpenLigaDb({
    matchID: 33,
    matchDateTimeUTC: "2026-10-13T18:00:00Z",
    matchIsFinished: false,
    team1: { teamName: "Arsenal" },
    team2: { teamName: "Chelsea" },
  });
  if (!sport || !tsdb || !open) throw new Error("normalizer returned null");
  if (providerMatchScore(sport, tsdb) < 0.9 || providerMatchScore(sport, open) < 0.9) {
    throw new Error("normalized fixtures do not match");
  }
});
