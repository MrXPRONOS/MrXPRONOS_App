create table if not exists public.threads_privacy_requests (
  id uuid primary key default gen_random_uuid(),
  request_type text not null check (request_type in ('uninstall','deletion')),
  subject_hmac text not null check (subject_hmac ~ '^[0-9a-f]{64}$'),
  confirmation_code uuid not null unique default gen_random_uuid(),
  status text not null default 'pending' check (status in ('pending','completed','needs_review')),
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  last_seen_at timestamptz not null default now(),
  unique (request_type, subject_hmac)
);
comment on table public.threads_privacy_requests is 'Meta Threads signed unlink/data-deletion callbacks. User IDs are HMAC-hashed, not stored in plaintext. Status pending until GitHub credentials are removed.';
alter table public.threads_privacy_requests enable row level security;
revoke all on public.threads_privacy_requests from public, anon, authenticated;
grant select, insert, update on public.threads_privacy_requests to service_role;
create index if not exists idx_threads_privacy_pending on public.threads_privacy_requests (status,created_at) where status='pending';
