const fs=require("node:fs");
const assert=require("node:assert/strict");
const sql=fs.readFileSync("supabase/migrations/20261019010035_harden_public_telemetry_rpc_search_path.sql","utf8");
for (const signature of [
  "public.increment_counter(text)",
  "public.insert_analytics(text,text,text)",
  "public.record_event(text,text,text)"
]) {
  const statement="ALTER FUNCTION "+signature;
  const location=sql.indexOf(statement);
  assert(location>=0,"Missing telemetry RPC: "+signature);
  const suffix=sql.slice(location,sql.indexOf(";",location)+1);
  assert(/SET search_path TO pg_catalog, public, pg_temp/.test(suffix),
    "Privileged functions must not resolve caller temporary tables before public schema: "+signature);
}
assert(!/REVOKE EXECUTE|DROP FUNCTION|DELETE FROM|TRUNCATE/i.test(sql),
  "Public tracking must not be disabled by the search_path migration");
console.log("Public telemetry SECURITY DEFINER search-path hardening checks passed");
