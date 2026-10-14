-- Optional, quota-controlled API-Football provider for accurate in-play statistics.
-- The additional provider is populated only by the scheduled GitHub action
-- when API_FOOTBALL_KEY is configured; existing providers are unaffected.
ALTER TABLE public.live_stats_sources
  DROP CONSTRAINT IF EXISTS live_stats_sources_source_name_check;
ALTER TABLE public.live_stats_sources
  ADD CONSTRAINT live_stats_sources_source_name_check
  CHECK (source_name IN ('api_original', 'espn', 'sportscore', 'thesportsdb', 'openligadb', 'api_football'));
