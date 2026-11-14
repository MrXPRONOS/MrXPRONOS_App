-- Migration already applied to Supabase production on 2026-11-14.
-- Commit the exact remote migration version so CI history remains synchronized.
CREATE TABLE IF NOT EXISTS public.dixon_score_push_optins (
  endpoint_digest text PRIMARY KEY CHECK (endpoint_digest ~ '^[a-f0-9]{64}$'),
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.dixon_score_push_optins ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.dixon_score_push_optins FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS public.dixon_score_push_dispatches (
  match_date date PRIMARY KEY,
  video_sha256 text NOT NULL CHECK (video_sha256 ~ '^[a-f0-9]{64}$'),
  total_count integer NOT NULL CHECK (total_count BETWEEN 1 AND 10),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  delivered integer NOT NULL DEFAULT 0
);
ALTER TABLE public.dixon_score_push_dispatches ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.dixon_score_push_dispatches FROM PUBLIC, anon, authenticated;
