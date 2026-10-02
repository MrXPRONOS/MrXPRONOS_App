-- Capture immuable du coupon au moment de la publication (aucun score/minute live ne doit l'écraser).
ALTER TABLE public.live_predictions
  ADD COLUMN IF NOT EXISTS signal_home_score integer,
  ADD COLUMN IF NOT EXISTS signal_away_score integer,
  ADD COLUMN IF NOT EXISTS signal_minute numeric(6,2),
  ADD COLUMN IF NOT EXISTS signal_half1_home integer,
  ADD COLUMN IF NOT EXISTS signal_half1_away integer,
  ADD COLUMN IF NOT EXISTS signal_half2_home integer,
  ADD COLUMN IF NOT EXISTS signal_half2_away integer,
  ADD COLUMN IF NOT EXISTS live_odds numeric(8,2),
  ADD COLUMN IF NOT EXISTS stake_fcfa bigint,
  ADD COLUMN IF NOT EXISTS potential_gain_fcfa bigint,
  ADD COLUMN IF NOT EXISTS odds_source text;
-- Backfill des anciennes données de score et minute: uniquement si présentes.
UPDATE public.live_predictions
SET signal_home_score=COALESCE(signal_home_score,home_score),
    signal_away_score=COALESCE(signal_away_score,away_score),
    signal_minute=COALESCE(signal_minute,minute),
    stake_fcfa=COALESCE(stake_fcfa,500000)
WHERE signal_home_score IS NULL OR signal_away_score IS NULL
   OR signal_minute IS NULL OR stake_fcfa IS NULL;
COMMENT ON COLUMN public.live_predictions.live_odds IS 'Cote indicative calculée figée au signal ; ne pas présenter comme cote bookmaker';
