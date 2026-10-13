-- Allow all configured MrXPRONOS football providers in persisted LIVE source data.
ALTER TABLE public.live_stats_sources
  DROP CONSTRAINT IF EXISTS live_stats_sources_source_name_check;
ALTER TABLE public.live_stats_sources
  ADD CONSTRAINT live_stats_sources_source_name_check
  CHECK (source_name IN ('api_original', 'espn', 'sportscore', 'thesportsdb', 'openligadb'));
