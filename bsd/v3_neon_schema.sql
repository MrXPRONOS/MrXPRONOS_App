-- Mr XPRONOS experimental BSD V3 schema for Neon Postgres.
-- REVIEW-ONLY: do not execute on the existing production Neon database without
-- a dedicated development branch and explicit migration controls.
-- No Supabase dependencies. No secret values.
BEGIN;
CREATE SCHEMA IF NOT EXISTS bsd_v3_shadow;

CREATE TABLE IF NOT EXISTS bsd_v3_shadow.model_runs (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  model_version TEXT NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL,
  input_fingerprint TEXT NOT NULL,
  experimental BOOLEAN NOT NULL DEFAULT TRUE CHECK(experimental),
  published BOOLEAN NOT NULL DEFAULT FALSE CHECK(NOT published),
  diagnostics JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS bsd_v3_shadow.match_predictions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES bsd_v3_shadow.model_runs(id),
  provider TEXT NOT NULL DEFAULT 'bsd',
  external_event_id TEXT NOT NULL,
  kickoff_at TIMESTAMPTZ NOT NULL,
  feature_timestamp TIMESTAMPTZ NOT NULL,
  expected_home_goals DOUBLE PRECISION NOT NULL CHECK(expected_home_goals > 0),
  expected_away_goals DOUBLE PRECISION NOT NULL CHECK(expected_away_goals > 0),
  features JSONB NOT NULL,
  UNIQUE(run_id, external_event_id),
  CHECK(feature_timestamp < kickoff_at)
);

CREATE TABLE IF NOT EXISTS bsd_v3_shadow.market_predictions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  match_prediction_id BIGINT NOT NULL REFERENCES bsd_v3_shadow.match_predictions(id) ON DELETE CASCADE,
  market_number INTEGER NOT NULL CHECK(market_number BETWEEN 1 AND 40),
  market_key TEXT NOT NULL,
  market_family TEXT NOT NULL,
  probability DOUBLE PRECISION NOT NULL CHECK(probability BETWEEN 0 AND 1),
  push_probability DOUBLE PRECISION NOT NULL CHECK(push_probability BETWEEN 0 AND 1),
  lose_probability DOUBLE PRECISION NOT NULL CHECK(lose_probability BETWEEN 0 AND 1),
  quote_odds NUMERIC(10,4) CHECK(quote_odds > 1),
  quote_provenance JSONB,
  publication_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK(NOT publication_allowed),
  UNIQUE(match_prediction_id,market_key),
  UNIQUE(match_prediction_id,market_number),
  CHECK(ABS(probability+push_probability+lose_probability-1)<0.00001)
);

CREATE TABLE IF NOT EXISTS bsd_v3_shadow.settlements (
  market_prediction_id BIGINT PRIMARY KEY REFERENCES bsd_v3_shadow.market_predictions(id) ON DELETE CASCADE,
  verdict TEXT NOT NULL CHECK(verdict IN ('pending','win','lose','push','void')),
  final_home_goals INTEGER CHECK(final_home_goals >= 0),
  final_away_goals INTEGER CHECK(final_away_goals >= 0),
  verified_at TIMESTAMPTZ,
  source_reference TEXT,
  CHECK ((final_home_goals IS NULL) = (final_away_goals IS NULL))
);

CREATE INDEX IF NOT EXISTS market_predictions_key_idx ON bsd_v3_shadow.market_predictions(market_key);
CREATE INDEX IF NOT EXISTS match_predictions_kickoff_idx ON bsd_v3_shadow.match_predictions(kickoff_at);
COMMIT;
