const fs=require("node:fs");
const assert=require("node:assert/strict");
const migration=fs.readFileSync(
  "supabase/migrations/20261018233415_remove_recursive_admin_users_policy.sql","utf8");
assert(migration.includes('DROP POLICY IF EXISTS "admin_users: admin can read" ON public.admin_users'),
  "Must remove the self-referential RLS policy");
assert(!/ALTER\s+TABLE\s+(?:public\.)?admin_users\s+DISABLE\s+ROW\s+LEVEL\s+SECURITY/i.test(migration),
  "Admin RLS must stay enabled");
assert(!/DROP\s+POLICY\s+(?:IF\s+EXISTS\s+)?["']?admin_users_admin_only/i.test(migration),
  "Preserve admin-only authorization");
assert(!/DELETE\s+FROM\s+(?:public\.)?admin_users/i.test(migration),
  "Migration must not delete admin accounts");
console.log("Admin RLS recursion regression checks passed.");
