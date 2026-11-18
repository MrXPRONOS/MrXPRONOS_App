-- Mr XPRONOS Telegram assistant v2 — private server-only tables.
-- Already applied to Supabase via migration telegram_assistant_sessions_metrics_receipts_20261117.
-- This reference is idempotent; do not expose these tables to anon/authenticated.
CREATE TABLE IF NOT EXISTS public.mx_telegram_assistant_sessions (
 chat_key text PRIMARY KEY REFERENCES public.mx_telegram_assistant_chats(chat_key) ON DELETE CASCADE,
 mode text NOT NULL DEFAULT 'idle' CHECK (mode IN ('idle','guided','awaiting_clarification')),
 goal text NOT NULL DEFAULT '',
 bookmaker text NOT NULL DEFAULT '',
 step_number integer NOT NULL DEFAULT 0 CHECK (step_number BETWEEN 0 AND 50),
 step_text text NOT NULL DEFAULT '',
 last_input text NOT NULL DEFAULT '',
 summary text NOT NULL DEFAULT '',
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mx_ta_sessions_updated_idx ON public.mx_telegram_assistant_sessions(updated_at);
ALTER TABLE public.mx_telegram_assistant_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mx_telegram_assistant_sessions FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mx_telegram_assistant_sessions TO service_role;

CREATE TABLE IF NOT EXISTS public.mx_telegram_assistant_model_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 model text NOT NULL,
 status text NOT NULL,
 duration_ms integer NOT NULL DEFAULT 0 CHECK (duration_ms >= 0 AND duration_ms < 300000),
 source text NOT NULL DEFAULT 'chat' CHECK (source IN ('chat','vision','speech')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS mx_ta_model_events_recent_idx ON public.mx_telegram_assistant_model_events(created_at DESC, model);
ALTER TABLE public.mx_telegram_assistant_model_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mx_telegram_assistant_model_events FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mx_telegram_assistant_model_events TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public.mx_telegram_assistant_model_events_id_seq TO service_role;

CREATE TABLE IF NOT EXISTS public.mx_telegram_assistant_delivery_receipts (
 update_id bigint NOT NULL,
 part_index smallint NOT NULL CHECK (part_index BETWEEN 0 AND 5),
 telegram_message_id bigint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(update_id,part_index)
);
ALTER TABLE public.mx_telegram_assistant_delivery_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mx_telegram_assistant_delivery_receipts FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mx_telegram_assistant_delivery_receipts TO service_role;


-- At-most-once Telegram delivery reservation. Applied with the new server migration.
CREATE TABLE IF NOT EXISTS public.mx_telegram_assistant_delivery_claims (
  update_id bigint NOT NULL,
  part_index smallint NOT NULL CHECK (part_index BETWEEN 0 AND 5),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','delivered')),
  telegram_message_id bigint,
  claimed_at timestamptz NOT NULL DEFAULT now(),
  delivered_at timestamptz,
  PRIMARY KEY (update_id,part_index)
);
CREATE INDEX IF NOT EXISTS mx_ta_delivery_claims_issued_idx
 ON public.mx_telegram_assistant_delivery_claims(claimed_at DESC);
ALTER TABLE public.mx_telegram_assistant_delivery_claims ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.mx_telegram_assistant_delivery_claims FROM anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mx_telegram_assistant_delivery_claims TO service_role;
