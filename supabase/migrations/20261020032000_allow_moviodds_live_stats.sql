-- MoviOdds supplies verified opt-in soccer statistics (stats=1).
-- Keep the existing source allow-list, adding only the audited provider.
-- Idempotent so a repeated deployment cannot block the LIVE worker.
ALTER TABLE public.live_stats_sources
  DROP CONSTRAINT IF EXISTS live_stats_sources_source_name_check;
ALTER TABLE public.live_stats_sources
  ADD CONSTRAINT live_stats_sources_source_name_check
  CHECK (source_name = ANY (ARRAY[
    'api_original'::text, 'espn'::text, 'sportscore'::text,
    'thesportsdb'::text, 'openligadb'::text, 'api_football'::text,
    'moviodds'::text
  ]));
