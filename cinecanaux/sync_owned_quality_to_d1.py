#!/usr/bin/env python3
"""Synchronize observed channel-quality facts to Cloudflare D1.
Only numeric Cine Radar listing IDs and aggregate statistics are transmitted.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests

FILE=Path(__file__).resolve().parent/"assets"/"owned_channel_quality.json"
ACCOUNT="9c86118191b804d91b5f5b2c89114999"
DATABASE="fa8b5009-bc1a-4a6e-b143-7a487c7297a5"

def run():
    token=str(os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN") or "").strip()
    if not token:
        print("QUALITY_SYNC_PENDING_TOKEN")
        return 0
    if not FILE.is_file():raise RuntimeError("quality_audit_missing")
    report=json.loads(FILE.read_text(encoding="utf8"))
    if report.get("version")!=1 or not isinstance(report.get("channels"),list):
        raise RuntimeError("invalid_quality_report")
    date=datetime.fromisoformat(report["observed_at"].replace("Z","+00:00"))
    if date.tzinfo is None or datetime.now(timezone.utc)-date>timedelta(days=3):
        raise RuntimeError("stale_quality_report")
    endpoint=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/d1/database/{DATABASE}/query"
    s=requests.Session()
    s.headers.update({"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    sql="""INSERT INTO owned_channel_quality(
 channel_id,avatar_status,avatar_checked_at,total_posts,sampled_posts,posts_7d,posts_30d,media_30d,
 last_post_at,audit_status,observed_at
 ) SELECT ?,?,?,?,?,?,?,?,?,?,?
 WHERE EXISTS(SELECT 1 FROM owned_channel_features WHERE channel_id=? AND enabled=1)
 ON CONFLICT(channel_id) DO UPDATE SET
 avatar_status=CASE WHEN excluded.avatar_status='unknown' THEN owned_channel_quality.avatar_status ELSE excluded.avatar_status END,
 avatar_checked_at=CASE WHEN excluded.avatar_status='unknown' THEN owned_channel_quality.avatar_checked_at ELSE excluded.avatar_checked_at END,
 total_posts=COALESCE(excluded.total_posts,owned_channel_quality.total_posts),
 sampled_posts=CASE WHEN excluded.audit_status='verified' THEN excluded.sampled_posts ELSE owned_channel_quality.sampled_posts END,
 posts_7d=COALESCE(excluded.posts_7d,owned_channel_quality.posts_7d),
 posts_30d=COALESCE(excluded.posts_30d,owned_channel_quality.posts_30d),
 media_30d=COALESCE(excluded.media_30d,owned_channel_quality.media_30d),
 last_post_at=COALESCE(excluded.last_post_at,owned_channel_quality.last_post_at),
 audit_status=CASE WHEN excluded.audit_status='verified' THEN 'verified' ELSE owned_channel_quality.audit_status END,
 observed_at=excluded.observed_at"""
    count=0
    for row in report["channels"]:
        id=row.get("channel_id")
        if not isinstance(id,int) or not 0<id<1_000_000_000:continue
        avatar=row.get("avatar_status")
        status=row.get("audit_status")
        if avatar not in {"real","fallback","unknown"} or status not in {"verified","unavailable","unknown"}:continue
        def count_field(name):
            value=row.get(name)
            return value if isinstance(value,int) and 0<=value<100_000_000 else None
        params=[id,avatar,row.get("observed_at"),count_field("total_posts"),
          count_field("sampled_posts") or 0,count_field("posts_7d"),
          count_field("posts_30d"),count_field("media_30d"),row.get("last_post_at"),
          status,row.get("observed_at"),id]
        r=s.post(endpoint,json={"sql":sql,"params":params},timeout=(8,25))
        if r.status_code!=200 or r.json().get("success") is not True:
            raise RuntimeError("quality_sync_failed")
        count+=1
    s.close()
    print("QUALITY_SYNC_OK",{"updated":count})
    return 0
if __name__=="__main__":
    try:sys.exit(run())
    except Exception as e:
        print("::error::QUALITY_SYNC_ERROR",type(e).__name__)
        sys.exit(1)
