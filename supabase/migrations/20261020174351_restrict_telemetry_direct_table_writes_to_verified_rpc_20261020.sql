revoke insert,update,delete on table public.analytics from PUBLIC,anon,authenticated;
revoke insert,update,delete on table public.events from PUBLIC,anon,authenticated;
-- The RPC functions still have the required privileges through SECURITY DEFINER.
-- No public Data API caller may bypass validated inserts.
