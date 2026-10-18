-- Admin security: remove a self-referential SELECT RLS policy that causes SQLSTATE 42P17.
-- Preserve RLS and the existing admin_users_admin_only policy, which delegates
-- authorization to public.is_admin() (SECURITY DEFINER).
-- No admin accounts or other table rows are modified.
BEGIN;
DROP POLICY IF EXISTS "admin_users: admin can read" ON public.admin_users;
COMMIT;
