-- Server-enforced least privilege for the existing admin role model.
-- Existing active administrator keeps access_role='owner'.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['cms_articles','cms_conseils','cms_bonus','cms_bookmakers','cms_infos']
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'admin_all_'||t,t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t||'_admin_only',t);
    EXECUTE format('CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING ((SELECT public.admin_can(''read'')))',
      t||'_role_read',t);
    EXECUTE format('CREATE POLICY %I ON public.%I FOR INSERT TO authenticated WITH CHECK ((SELECT public.admin_can(''cms'')))',
      t||'_role_insert',t);
    EXECUTE format('CREATE POLICY %I ON public.%I FOR UPDATE TO authenticated USING ((SELECT public.admin_can(''cms''))) WITH CHECK ((SELECT public.admin_can(''cms'')))',
      t||'_role_update',t);
    EXECUTE format('CREATE POLICY %I ON public.%I FOR DELETE TO authenticated USING ((SELECT public.admin_can(''cms'')))',
      t||'_role_delete',t);
  END LOOP;
END $$;
DROP POLICY IF EXISTS admin_users_admin_only ON public.admin_users;
CREATE POLICY admin_users_role_read ON public.admin_users FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY admin_users_owner_insert ON public.admin_users FOR INSERT TO authenticated
WITH CHECK ((SELECT public.admin_can('users')));
CREATE POLICY admin_users_owner_update ON public.admin_users FOR UPDATE TO authenticated
USING ((SELECT public.admin_can('users'))) WITH CHECK ((SELECT public.admin_can('users')));
CREATE POLICY admin_users_owner_delete ON public.admin_users FOR DELETE TO authenticated
USING ((SELECT public.admin_can('users')));

DROP POLICY IF EXISTS cms_media_admin ON public.cms_media;
CREATE POLICY cms_media_role_read ON public.cms_media FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY cms_media_role_insert ON public.cms_media FOR INSERT TO authenticated
WITH CHECK ((SELECT public.admin_can('media')));
CREATE POLICY cms_media_role_update ON public.cms_media FOR UPDATE TO authenticated
USING ((SELECT public.admin_can('media'))) WITH CHECK ((SELECT public.admin_can('media')));
CREATE POLICY cms_media_role_delete ON public.cms_media FOR DELETE TO authenticated
USING ((SELECT public.admin_can('media')));
DROP POLICY IF EXISTS cms_editor_drafts_owner ON public.cms_editor_drafts;
CREATE POLICY cms_editor_drafts_owner ON public.cms_editor_drafts FOR ALL TO authenticated
USING (user_id=(SELECT auth.uid()) AND (SELECT public.admin_can('cms')))
WITH CHECK (user_id=(SELECT auth.uid()) AND (SELECT public.admin_can('cms')));
DROP POLICY IF EXISTS cms_revisions_admin_read ON public.cms_revisions;
CREATE POLICY cms_revisions_admin_read ON public.cms_revisions FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));

DROP POLICY IF EXISTS admin_all_vip_access ON public.vip_access;
DROP POLICY IF EXISTS vip_access_admin_only ON public.vip_access;
CREATE POLICY vip_access_role_read ON public.vip_access FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY vip_access_role_write ON public.vip_access FOR ALL TO authenticated
USING ((SELECT public.admin_can('vip'))) WITH CHECK ((SELECT public.admin_can('vip')));

DROP POLICY IF EXISTS audit_admin_only ON public.audit_log;
DROP POLICY IF EXISTS audit_select_admin ON public.audit_log;
CREATE POLICY audit_log_role_read ON public.audit_log FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY audit_log_role_insert ON public.audit_log FOR INSERT TO authenticated
WITH CHECK ((SELECT public.admin_can('cms')) OR (SELECT public.admin_can('push')));

DROP POLICY IF EXISTS cron_runs_admin_only ON public.cron_runs;
DROP POLICY IF EXISTS cron_select_admin ON public.cron_runs;
CREATE POLICY cron_runs_role_read ON public.cron_runs FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY cron_runs_role_write ON public.cron_runs FOR ALL TO authenticated
USING ((SELECT public.admin_can('users'))) WITH CHECK ((SELECT public.admin_can('users')));

DROP POLICY IF EXISTS admin_incidents_admin_all ON public.admin_incidents;
CREATE POLICY admin_incidents_role_read ON public.admin_incidents FOR SELECT TO authenticated
USING ((SELECT public.admin_can('read')));
CREATE POLICY admin_incidents_role_insert ON public.admin_incidents FOR INSERT TO authenticated
WITH CHECK ((SELECT public.admin_can('cms')) OR (SELECT public.admin_can('push')));
CREATE POLICY admin_incidents_role_update ON public.admin_incidents FOR UPDATE TO authenticated
USING ((SELECT public.admin_can('cms')) OR (SELECT public.admin_can('push')))
WITH CHECK ((SELECT public.admin_can('cms')) OR (SELECT public.admin_can('push')));

DROP POLICY IF EXISTS cms_media_admin_insert ON storage.objects;
CREATE POLICY cms_media_admin_insert ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id='cms-media' AND (SELECT public.admin_can('media'))
  AND name ~ '^cms/[a-f0-9-]{36}/[a-f0-9-]{36}[.](jpe?g|png|webp|gif|mp4|webm)$');
DROP POLICY IF EXISTS cms_media_admin_read ON storage.objects;
CREATE POLICY cms_media_admin_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id='cms-media' AND (SELECT public.admin_can('media')));
DROP POLICY IF EXISTS cms_media_admin_delete ON storage.objects;
CREATE POLICY cms_media_admin_delete ON storage.objects FOR DELETE TO authenticated
USING (bucket_id='cms-media' AND (SELECT public.admin_can('media')));
DROP POLICY IF EXISTS cms_drafts_admin_read ON storage.objects;
CREATE POLICY cms_drafts_admin_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id='cms-drafts' AND (SELECT public.admin_can('media')));
DROP POLICY IF EXISTS cms_drafts_admin_insert ON storage.objects;
CREATE POLICY cms_drafts_admin_insert ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id='cms-drafts' AND (SELECT public.admin_can('media'))
  AND name ~ '^cms/[a-f0-9-]{36}/[a-f0-9-]{36}[.](jpe?g|png|webp|gif|mp4|webm)$');
DROP POLICY IF EXISTS cms_drafts_admin_delete ON storage.objects;
CREATE POLICY cms_drafts_admin_delete ON storage.objects FOR DELETE TO authenticated
USING (bucket_id='cms-drafts' AND (SELECT public.admin_can('media')));

CREATE OR REPLACE FUNCTION public.admin_reset_vip(p_user_id text,p_ip text,p_duration_days integer)
RETURNS TABLE(code text, expires_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=''
AS $function$
DECLARE
  new_code text := 'VIP-' || upper(substr(replace(gen_random_uuid()::text,'-',''),1,10));
  new_expires timestamptz := now() + make_interval(days => p_duration_days);
BEGIN
  IF NOT public.admin_can('vip') THEN RAISE EXCEPTION 'Droit VIP requis' USING ERRCODE='42501'; END IF;
  IF coalesce(trim(p_user_id),'')='' OR p_duration_days NOT BETWEEN 1 AND 365 THEN
    RAISE EXCEPTION 'Identifiant ou durée invalide';
  END IF;
  INSERT INTO public.vip_access(user_id,code,ip_address,active,created_at,expires_at)
  VALUES(trim(p_user_id),new_code,nullif(trim(p_ip),''),true,now(),new_expires)
  ON CONFLICT(user_id) DO UPDATE SET code=excluded.code,ip_address=excluded.ip_address,
    active=true,created_at=now(),expires_at=excluded.expires_at;
  INSERT INTO public.audit_log(actor_user_id,action,details)
    VALUES(auth.uid(),'vip_reset',jsonb_build_object('user_id',trim(p_user_id),'duration_days',p_duration_days));
  RETURN QUERY SELECT new_code,new_expires;
END;
$function$;
CREATE OR REPLACE FUNCTION public.admin_revoke_vip(p_user_id text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=''
AS $function$
BEGIN
  IF NOT public.admin_can('vip') THEN RAISE EXCEPTION 'Droit VIP requis' USING ERRCODE='42501'; END IF;
  IF coalesce(trim(p_user_id),'')='' THEN RAISE EXCEPTION 'Identifiant vide'; END IF;
  UPDATE public.vip_access SET active=false WHERE user_id=trim(p_user_id);
  INSERT INTO public.audit_log(actor_user_id,action,details)
    VALUES(auth.uid(),'vip_revoke',jsonb_build_object('user_id',trim(p_user_id)));
  RETURN true;
END;
$function$;
REVOKE ALL ON FUNCTION public.admin_reset_vip(text,text,integer) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_reset_vip(text,text,integer) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_revoke_vip(text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_revoke_vip(text) TO authenticated;
