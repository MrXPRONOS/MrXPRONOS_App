-- Live Value Engine V2.1 calibration observability
ALTER TABLE public.live_predictions
  ADD COLUMN IF NOT EXISTS baseline_threshold numeric(10,2),
  ADD COLUMN IF NOT EXISTS historical_uplift_cap numeric(10,2),
  ADD COLUMN IF NOT EXISTS selected_uplift numeric(10,2);

COMMENT ON COLUMN public.live_predictions.baseline_threshold IS
  'Ancienne ligne de référence calculée au moment du signal.';
COMMENT ON COLUMN public.live_predictions.historical_uplift_cap IS
  'Hausse maximale autorisée par la calibration historique pour le marché/minute.';
COMMENT ON COLUMN public.live_predictions.selected_uplift IS
  'Différence entre la ligne V2 sélectionnée et baseline_threshold.';
