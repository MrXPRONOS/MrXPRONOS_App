create index if not exists assistant_review_queue_feedback_id_audit_idx on public.assistant_review_queue(feedback_id);
create index if not exists cms_media_created_by_audit_idx on public.cms_media(created_by);
create index if not exists cms_revisions_actor_user_id_audit_idx on public.cms_revisions(actor_user_id);
create index if not exists feedback_conversation_id_audit_idx on public.feedback(conversation_id);
create index if not exists notifications_scrape_related_prediction_id_audit_idx on public.notifications_scrape(related_prediction_id);
