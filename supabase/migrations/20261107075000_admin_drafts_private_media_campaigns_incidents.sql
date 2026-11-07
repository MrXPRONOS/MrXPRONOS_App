-- Mr XPRONOS: additive admin completion (no changes to public prediction feeds).
-- Drafts remain private; notifications are never dispatched by this migration.
CREATE TABLE IF NOT EXISTS public.cms_editor_drafts (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('articles','conseils','infos','bonus','bookmakers')),
  identity text NOT NULL CHECK (length(identity) BETWEEN 1 AND 160),
  content text NOT NULL DEFAULT '' CHECK (octet_length(content) <= 250000),
  revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id,kind,identity)
);
ALTER TABLE public.cms_editor_drafts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cms_editor_drafts_owner ON public.cms_editor_drafts;
CREATE POLICY cms_editor_drafts_owner ON public.cms_editor_drafts FOR ALL
TO authenticated USING (user_id=(SELECT auth.uid()) AND (SELECT public.is_admin()))
WITH CHECK (user_id=(SELECT auth.uid()) AND (SELECT public.is_admin()));
REVOKE ALL ON public.cms_editor_drafts FROM PUBLIC, anon;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.cms_editor_drafts TO authenticated;

-- Existing published URLs remain unchanged. New uploads are private until
-- their owner explicitly promotes them to the established public bucket.
INSERT INTO storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
VALUES ('cms-drafts','cms-drafts',false,31457280,
 ARRAY['image/jpeg','image/png','image/webp','image/gif','video/mp4','video/webm'])
ON CONFLICT (id) DO NOTHING;
ALTER TABLE public.cms_media DROP CONSTRAINT IF EXISTS cms_media_bucket_id_check;
ALTER TABLE public.cms_media ADD CONSTRAINT cms_media_bucket_id_check
 CHECK (bucket_id IN ('cms-media','cms-drafts'));
DROP POLICY IF EXISTS cms_drafts_admin_read ON storage.objects;
CREATE POLICY cms_drafts_admin_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id='cms-drafts' AND (SELECT public.is_admin()));
DROP POLICY IF EXISTS cms_drafts_admin_insert ON storage.objects;
CREATE POLICY cms_drafts_admin_insert ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id='cms-drafts' AND (SELECT public.is_admin())
  AND name ~ '^cms/[a-f0-9-]{36}/[a-f0-9-]{36}[.](jpe?g|png|webp|gif|mp4|webm)$');
DROP POLICY IF EXISTS cms_drafts_admin_delete ON storage.objects;
CREATE POLICY cms_drafts_admin_delete ON storage.objects FOR DELETE TO authenticated
USING (bucket_id='cms-drafts' AND (SELECT public.is_admin()));

CREATE TABLE IF NOT EXISTS public.admin_push_campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL UNIQUE,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','processing','sent','failed','cancelled')),
  scheduled_at timestamptz NOT NULL DEFAULT now(),
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 110),
  body text NOT NULL CHECK (length(body) BETWEEN 1 AND 700),
  url text,
  tag text,
  recipient_user_id text,
  attempt_count integer NOT NULL DEFAULT 0,
  started_at timestamptz,
  completed_at timestamptz,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_push_due_idx
  ON public.admin_push_campaigns(scheduled_at,id) WHERE status='queued';
CREATE INDEX IF NOT EXISTS admin_push_created_idx
  ON public.admin_push_campaigns(created_at DESC);
ALTER TABLE public.admin_push_campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_push_campaigns_admin_read ON public.admin_push_campaigns;
CREATE POLICY admin_push_campaigns_admin_read ON public.admin_push_campaigns FOR SELECT
TO authenticated USING ((SELECT public.is_admin()));
REVOKE ALL ON public.admin_push_campaigns FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.admin_push_campaigns TO authenticated;

CREATE TABLE IF NOT EXISTS public.admin_incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
  external_key text UNIQUE,
  summary text NOT NULL CHECK (length(summary) BETWEEN 3 AND 500),
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  severity text NOT NULL DEFAULT 'medium' CHECK (severity IN ('low','medium','high')),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS admin_incidents_open_idx ON public.admin_incidents(status,created_at DESC);
ALTER TABLE public.admin_incidents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS admin_incidents_admin_all ON public.admin_incidents;
CREATE POLICY admin_incidents_admin_all ON public.admin_incidents FOR ALL
TO authenticated USING ((SELECT public.is_admin()))
WITH CHECK ((SELECT public.is_admin()));
REVOKE ALL ON public.admin_incidents FROM PUBLIC,anon;
GRANT SELECT,INSERT,UPDATE ON public.admin_incidents TO authenticated;

-- Roles are additive; the existing admin retains all permissions.
ALTER TABLE public.admin_users ADD COLUMN IF NOT EXISTS access_role text NOT NULL DEFAULT 'owner'
  CHECK (access_role IN ('owner','editor','communications','viewer'));
CREATE OR REPLACE FUNCTION public.admin_can(p_permission text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $$
SELECT EXISTS(
 SELECT 1 FROM public.admin_users a
 WHERE a.user_id=(SELECT auth.uid()) AND a.active IS TRUE
 AND (
  a.access_role='owner'
  OR (a.access_role='editor' AND p_permission IN ('read','cms','media'))
  OR (a.access_role='communications' AND p_permission IN ('read','push'))
  OR (a.access_role='viewer' AND p_permission='read')
 )
);
$$;
REVOKE ALL ON FUNCTION public.admin_can(text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_can(text) TO authenticated;
