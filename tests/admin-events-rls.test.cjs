const fs=require("node:fs");
const assert=require("node:assert/strict");
const sql=fs.readFileSync("supabase/migrations/20261019005600_events_admin_only_read_privacy.sql","utf8");
assert(sql.includes('DROP POLICY IF EXISTS "Allow authenticated select" ON public.events'));
assert(/CREATE POLICY events_select_admin ON public\.events FOR SELECT TO authenticated/.test(sql));
assert(sql.includes("USING ((SELECT public.is_admin()))"));
assert(sql.includes("REVOKE SELECT ON TABLE public.events FROM PUBLIC, anon"));
assert(sql.includes("GRANT SELECT ON TABLE public.events TO authenticated"));
assert(!/DISABLE ROW LEVEL SECURITY/i.test(sql));
assert(!/REVOKE (?:ALL|INSERT) ON TABLE public\.events/i.test(sql),
  "Event tracking INSERT permissions must remain untouched");
assert(!/DELETE FROM public\.events/i.test(sql));
console.log("Visitor events RLS: only admins can read, public INSERT retained");
