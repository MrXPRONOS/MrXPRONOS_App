ALTER TABLE public.admin_push_campaigns ADD COLUMN IF NOT EXISTS retry_of uuid
  REFERENCES public.admin_push_campaigns(id) ON DELETE SET NULL;
ALTER TABLE public.admin_push_campaigns ADD COLUMN IF NOT EXISTS endpoint_digest text
  CHECK (endpoint_digest IS NULL OR length(endpoint_digest)=64);
CREATE UNIQUE INDEX IF NOT EXISTS admin_push_unique_device_retry
 ON public.admin_push_campaigns(retry_of,endpoint_digest)
 WHERE retry_of IS NOT NULL AND endpoint_digest IS NOT NULL;
CREATE INDEX IF NOT EXISTS admin_push_delivery_error_idx
 ON public.admin_push_delivery_logs(result,http_status)
 WHERE result='failed';
