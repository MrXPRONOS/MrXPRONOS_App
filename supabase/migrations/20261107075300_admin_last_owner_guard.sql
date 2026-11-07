-- Prevent accidental lockout of the only active owner even via direct PostgREST.
CREATE OR REPLACE FUNCTION public.admin_protect_last_owner()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $$
DECLARE
  v_active_owners integer;
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.active IS TRUE AND OLD.access_role='owner'
     AND (NEW.active IS DISTINCT FROM TRUE OR NEW.access_role <> 'owner') THEN
    SELECT count(*) INTO v_active_owners FROM public.admin_users
    WHERE active IS TRUE AND access_role='owner' AND user_id<>OLD.user_id;
    IF v_active_owners=0 THEN
      RAISE EXCEPTION 'Impossible de retirer le dernier propriétaire actif'
        USING ERRCODE='42501';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS admin_protect_last_owner ON public.admin_users;
CREATE TRIGGER admin_protect_last_owner
BEFORE UPDATE ON public.admin_users
FOR EACH ROW EXECUTE FUNCTION public.admin_protect_last_owner();

-- A deleted row must not silently remove the last owner either.
CREATE OR REPLACE FUNCTION public.admin_protect_last_owner_delete()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $$
DECLARE
  v_active_owners integer;
BEGIN
  IF OLD.active IS TRUE AND OLD.access_role='owner' THEN
    SELECT count(*) INTO v_active_owners FROM public.admin_users
    WHERE active IS TRUE AND access_role='owner' AND user_id<>OLD.user_id;
    IF v_active_owners=0 THEN
      RAISE EXCEPTION 'Impossible de supprimer le dernier propriétaire actif'
        USING ERRCODE='42501';
    END IF;
  END IF;
  RETURN OLD;
END;
$$;
DROP TRIGGER IF EXISTS admin_protect_last_owner_delete ON public.admin_users;
CREATE TRIGGER admin_protect_last_owner_delete
BEFORE DELETE ON public.admin_users
FOR EACH ROW EXECUTE FUNCTION public.admin_protect_last_owner_delete();

-- Workers with read-only permissions must not see the administrator email roster.
DROP POLICY IF EXISTS admin_users_role_read ON public.admin_users;
CREATE POLICY admin_users_role_read ON public.admin_users FOR SELECT TO authenticated
USING ((SELECT public.admin_can('users')));
