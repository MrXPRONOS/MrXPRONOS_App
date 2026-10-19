-- Prevent any authenticated non-administrator from reading visitor event logs.
-- The previous policy evaluated only auth.role()='authenticated', leaking all rows.
-- Preserve event INSERT policies for public telemetry and RLS on the table.
BEGIN;
DROP POLICY IF EXISTS "Allow authenticated select" ON public.events;
DROP POLICY IF EXISTS events_select_admin ON public.events;
CREATE POLICY events_select_admin ON public.events FOR SELECT TO authenticated
  USING ((SELECT public.is_admin()));
REVOKE SELECT ON TABLE public.events FROM PUBLIC, anon;
GRANT SELECT ON TABLE public.events TO authenticated;
COMMIT;
