-- Private backend-only tables. The service_role is not restricted by RLS.
alter table public.conversations enable row level security;
alter table public.vip_login_attempts enable row level security;
alter table public.worker_locks enable row level security;
-- Explicitly prevent broad direct API roles from reading private logs
revoke all on public.conversations from anon, authenticated;
revoke all on public.vip_login_attempts from anon, authenticated;
revoke all on public.worker_locks from anon, authenticated;
