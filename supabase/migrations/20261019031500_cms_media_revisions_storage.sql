-- Partie 2A: public read-only CMS media with administrator-only uploads and version snapshots.
-- Existing videos bucket and existing CMS tables are deliberately untouched.
BEGIN;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
VALUES ('cms-media','cms-media',true,31457280,
 ARRAY['image/jpeg','image/png','image/webp','image/gif','video/mp4','video/webm']::text[])
ON CONFLICT(id) DO UPDATE SET
 file_size_limit=EXCLUDED.file_size_limit,
 allowed_mime_types=EXCLUDED.allowed_mime_types;

CREATE TABLE IF NOT EXISTS public.cms_media (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 bucket_id text NOT NULL DEFAULT 'cms-media' CHECK(bucket_id='cms-media'),
 storage_path text NOT NULL UNIQUE CHECK(storage_path ~ '^cms/[a-f0-9-]{36}/[a-f0-9-]{36}[.](jpe?g|png|webp|gif|mp4|webm)$'),
 kind text NOT NULL CHECK(kind IN ('image','video')),
 mime_type text NOT NULL CHECK(mime_type IN ('image/jpeg','image/png','image/webp','image/gif','video/mp4','video/webm')),
 original_name text NOT NULL CHECK(length(original_name) BETWEEN 1 AND 240),
 file_size bigint NOT NULL CHECK(file_size BETWEEN 1 AND 31457280),
 alt_text text NOT NULL DEFAULT '',
 caption text NOT NULL DEFAULT '',
 width integer CHECK(width BETWEEN 1 AND 10000),
 height integer CHECK(height BETWEEN 1 AND 10000),
 thumbnail_path text,
 created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL DEFAULT auth.uid(),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cms_media_created_idx ON public.cms_media(created_at DESC);
ALTER TABLE public.cms_media ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.cms_media FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.cms_media TO authenticated;
DROP POLICY IF EXISTS cms_media_admin ON public.cms_media;
CREATE POLICY cms_media_admin ON public.cms_media FOR ALL TO authenticated
 USING ((select public.is_admin())) WITH CHECK ((select public.is_admin()));

DROP POLICY IF EXISTS cms_media_admin_insert ON storage.objects;
DROP POLICY IF EXISTS cms_media_admin_read ON storage.objects;
DROP POLICY IF EXISTS cms_media_admin_delete ON storage.objects;
CREATE POLICY cms_media_admin_insert ON storage.objects FOR INSERT TO authenticated
 WITH CHECK (bucket_id='cms-media' AND (select public.is_admin())
    AND name ~ '^cms/[a-f0-9-]{36}/[a-f0-9-]{36}[.](jpe?g|png|webp|gif|mp4|webm)$');
CREATE POLICY cms_media_admin_read ON storage.objects FOR SELECT TO authenticated
 USING (bucket_id='cms-media' AND (select public.is_admin()));
CREATE POLICY cms_media_admin_delete ON storage.objects FOR DELETE TO authenticated
 USING (bucket_id='cms-media' AND (select public.is_admin()));

CREATE TABLE IF NOT EXISTS public.cms_revisions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 document_table text NOT NULL CHECK(document_table IN
   ('cms_articles','cms_conseils','cms_infos','cms_bonus','cms_bookmakers')),
 document_id uuid NOT NULL,
 operation text NOT NULL CHECK(operation IN ('insert','update','delete')),
 snapshot jsonb NOT NULL,
 actor_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cms_revisions_doc_idx
 ON public.cms_revisions(document_table,document_id,created_at DESC);
ALTER TABLE public.cms_revisions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.cms_revisions FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.cms_revisions TO authenticated;
DROP POLICY IF EXISTS cms_revisions_admin_read ON public.cms_revisions;
CREATE POLICY cms_revisions_admin_read ON public.cms_revisions FOR SELECT
 TO authenticated USING ((select public.is_admin()));

CREATE OR REPLACE FUNCTION public.cms_track_revision() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp
 AS $cms_revision$
 BEGIN
   INSERT INTO public.cms_revisions(document_table,document_id,operation,snapshot,actor_user_id)
   VALUES(TG_TABLE_NAME,
     CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END,
     lower(TG_OP),
     CASE WHEN TG_OP='INSERT' THEN to_jsonb(NEW) ELSE to_jsonb(OLD) END,
     auth.uid());
   RETURN NULL;
 END;
 $cms_revision$;
REVOKE ALL ON FUNCTION public.cms_track_revision() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.cms_track_revision() TO service_role;

DO $block$
DECLARE name text;
BEGIN
 FOREACH name IN ARRAY ARRAY['cms_articles','cms_conseils','cms_infos','cms_bonus','cms_bookmakers'] LOOP
  EXECUTE format('DROP TRIGGER IF EXISTS cms_revision_audit ON public.%I',name);
  EXECUTE format('CREATE TRIGGER cms_revision_audit AFTER INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.cms_track_revision()',name);
 END LOOP;
END;
$block$;

-- Editorial metadata (published JSON transformation is added in later steps).
ALTER TABLE public.cms_articles ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.cms_articles ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';
ALTER TABLE public.cms_conseils ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.cms_conseils ADD COLUMN IF NOT EXISTS difficulty text;
ALTER TABLE public.cms_conseils ADD COLUMN IF NOT EXISTS tags text[] DEFAULT '{}';
ALTER TABLE public.cms_infos ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE public.cms_infos ADD COLUMN IF NOT EXISTS image_url text;
COMMIT;
