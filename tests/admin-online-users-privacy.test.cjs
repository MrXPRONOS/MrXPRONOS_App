const fs=require("node:fs");
const assert=require("node:assert/strict");
const sql=fs.readFileSync("supabase/migrations/20261019010616_lockdown_legacy_online_users_privileges.sql","utf8");
assert(sql.includes("REVOKE ALL ON TABLE public.online_users FROM PUBLIC, anon, authenticated"),
  "Anonymous and ordinary users must not have raw online-user table permissions");
assert(sql.includes('DROP POLICY IF EXISTS "Allow anonymous upsert online_users"'),
  "Remove legacy public ALL policy");
assert(sql.includes("CREATE POLICY online_users_admin_read ON public.online_users"),
  "Preserve restricted admin review");
assert(/FOR SELECT TO authenticated USING \(\(SELECT public\.is_admin\(\)\)\)/.test(sql),
  "Admin-only read RLS must be present");
assert(!/DISABLE ROW LEVEL SECURITY|DELETE FROM public\.online_users|TRUNCATE public\.online_users/.test(sql),
  "Do not remove RLS or existing visitor rows");
const main=fs.readFileSync("assets/js/main.js","utf8");
assert(main.includes("presenceState()"),"Live online counter should rely on realtime Presence");
console.log("Online users legacy privacy and live Presence source checks passed");
