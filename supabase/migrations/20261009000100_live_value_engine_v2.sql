-- Live value engine v2: line-specific probabilities, pricing/value metrics and historical headroom.
-- Safe to run more than once.

ALTER TABLE public.live_predictions
  ADD COLUMN IF NOT EXISTS signal_value numeric(10,2),
  ADD COLUMN IF NOT EXISTS reliability_score numeric(6,2),
  ADD COLUMN IF NOT EXISTS model_fair_odds numeric(8,3),
  ADD COLUMN IF NOT EXISTS bookmaker_odds numeric(8,3),
  ADD COLUMN IF NOT EXISTS implied_probability numeric(9,6),
  ADD COLUMN IF NOT EXISTS edge numeric(9,6),
  ADD COLUMN IF NOT EXISTS expected_value numeric(9,6),
  ADD COLUMN IF NOT EXISTS value_score numeric(6,2),
  ADD COLUMN IF NOT EXISTS data_quality_score numeric(6,2),
  ADD COLUMN IF NOT EXISTS freshness_seconds integer,
  ADD COLUMN IF NOT EXISTS source_count integer,
  ADD COLUMN IF NOT EXISTS source_confidence numeric(6,2),
  ADD COLUMN IF NOT EXISTS source_agreement_score numeric(6,2),
  ADD COLUMN IF NOT EXISTS signal_tier text,
  ADD COLUMN IF NOT EXISTS pricing_mode text,
  ADD COLUMN IF NOT EXISTS line_candidate_count integer,
  ADD COLUMN IF NOT EXISTS line_candidate_rank integer,
  ADD COLUMN IF NOT EXISTS line_candidates jsonb,
  ADD COLUMN IF NOT EXISTS model_version text,
  ADD COLUMN IF NOT EXISTS final_value numeric(10,2),
  ADD COLUMN IF NOT EXISTS headroom numeric(10,2);

COMMENT ON COLUMN public.live_predictions.signal_value IS
  'Valeur du marché au moment exact du signal; distincte de projected_value et current_value.';
COMMENT ON COLUMN public.live_predictions.projected_value IS
  'Projection finale du modèle au moment du signal.';
COMMENT ON COLUMN public.live_predictions.reliability_score IS
  'Fiabilité du modèle/données (0-100), distincte de probability.';
COMMENT ON COLUMN public.live_predictions.model_fair_odds IS
  'Cote juste du modèle = 1/probabilité, sans marge bookmaker.';
COMMENT ON COLUMN public.live_predictions.bookmaker_odds IS
  'Cote live réelle uniquement lorsqu un fournisseur externe de props live est configuré.';
COMMENT ON COLUMN public.live_predictions.expected_value IS
  'EV décimale calculée contre bookmaker_odds: p*cote-1. NULL en mode modèle seul.';
COMMENT ON COLUMN public.live_predictions.headroom IS
  'Marge finale au-dessus du seuil: final_value - threshold.';
COMMENT ON COLUMN public.live_predictions.pricing_mode IS
  'external_live lorsque la cote provient d un fournisseur live; model_only sinon.';

CREATE INDEX IF NOT EXISTS live_predictions_model_version_idx
  ON public.live_predictions(model_version, created_at DESC);

CREATE INDEX IF NOT EXISTS live_predictions_backtest_idx
  ON public.live_predictions(telegram_sent, validated, created_at DESC);


-- Les anciennes lignes validées contiennent déjà leur valeur observée dans current_value.
-- On peut donc reconstruire le headroom historique sans inventer de donnée.
UPDATE public.live_predictions
SET final_value = COALESCE(final_value, current_value),
    headroom = COALESCE(headroom, current_value - threshold)
WHERE validated = true
  AND current_value IS NOT NULL
  AND threshold IS NOT NULL
  -- Une perte ne peut être connue qu'à la fin; validation_type=final aussi.
  -- Les succès instantanés restent NULL pour être enrichis avec la vraie valeur FT.
  AND (validation_type = 'final' OR outcome = 'failure')
  AND (final_value IS NULL OR headroom IS NULL);

-- Pour les anciennes lignes, signal_value ne peut être récupéré que si projected_value
-- représentait encore la valeur au signal dans l'ancien moteur.
UPDATE public.live_predictions
SET signal_value = COALESCE(signal_value, projected_value)
WHERE signal_value IS NULL
  AND projected_value IS NOT NULL
  AND model_version IS NULL;
