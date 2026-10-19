#!/usr/bin/env python3
"""Read-only social posting-time audit (Mr XPRONOS).

Uses GitHub Secrets in Actions; never posts, modifies tokens or prints credentials.
Metrics are measured at different ages; results are descriptive, not causal.
"""
from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

UTC = timezone.utc
NOW = datetime.now(UTC)
SINCE = NOW - timedelta(days=90)
MATURE = NOW - timedelta(hours=72)
GRAPH = "https://graph.facebook.com/v25.0"
THREADS = "https://graph.threads.net/v1.0"
UA = "MrXPRONOS-Audience-Timing-Audit/1.0"
BUCKETS = ((0, 6, "00-05"), (6, 10, "06-09"), (10, 14, "10-13"),
           (14, 18, "14-17"), (18, 22, "18-21"), (22, 24, "22-23"))


def env(name):
    return (os.getenv(name) or "").strip()


def parse_date(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def daypart(h):
    return next(label for a, b, label in BUCKETS if a <= h < b)


def http_get(base, path, token, params=None):
    if not token:
        raise ValueError("missing_credentials")
    url = base + path
    # Use Authorization header; never put access tokens into URLs/logs.
    try:
        r = requests.get(url, headers={"Authorization": "Bearer " + token,
                                      "User-Agent": UA},
                         params=params or {}, timeout=25)
    except requests.RequestException as exc:
        raise RuntimeError("network_" + type(exc).__name__) from None
    if r.status_code >= 400:
        try:
            code = str((r.json().get("error") or {}).get("code") or "")
        except (ValueError, AttributeError):
            code = ""
        raise RuntimeError(f"HTTP_{r.status_code}" + ("_code_" + code if code else ""))
    try:
        payload = r.json()
    except ValueError:
        raise RuntimeError("invalid_json") from None
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_object")
    return payload


def pages(base, path, token, params, max_pages=4):
    """Bound page reads (next cursor supplied by API, never arbitrary URL redirects)."""
    out = []
    after = None
    for _ in range(max_pages):
        pp = dict(params)
        if after:
            pp["after"] = after
        data = http_get(base, path, token, pp)
        out.extend(x for x in data.get("data", []) if isinstance(x, dict))
        after = (data.get("paging") or {}).get("cursors", {}).get("after")
        if not after or len(data.get("data", [])) < int(pp.get("limit") or 25):
            break
    return out


def insight_value(data, desired):
    for r in data.get("data", []):
        if r.get("name") == desired:
            v = r.get("total_value", {}).get("value")
            if v is None:
                values = r.get("values") or []
                v = values[-1].get("value") if values else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
    return None


def add(items, published, views, interactions=0, kind="video"):
    dt = parse_date(published)
    if not dt or dt < SINCE or dt > MATURE:
        return
    items.append({"hour_utc": dt.hour, "weekday": dt.weekday(),
                  "day": dt.date().isoformat(), "kind": kind,
                  "views": views if isinstance(views, (int, float)) else None,
                  "engagements": interactions if isinstance(interactions, (int, float)) else None})


def metric_groups(items, key):
    groups = defaultdict(list)
    for x in items:
        if x.get(key) is not None:
            groups[daypart(x["hour_utc"])].append(x)
    result = []
    for start, end, label in BUCKETS:
        vv = groups[label]
        values = [float(x[key]) for x in vv]
        result.append({
            "hour_slot_utc": label, "posts": len(vv),
            "distinct_days": len({x["day"] for x in vv}),
            "median": round(statistics.median(values), 1) if values else None,
            "mean": round(statistics.mean(values), 1) if values else None,
        })
    return result


def finish(name, rows, info=None, errors=None):
    views = sum(x["views"] is not None for x in rows)
    engagements = sum(x["engagements"] is not None for x in rows)
    result = {
        "platform": name, "posts_mature": len(rows), "posts_with_views": views,
        "posts_with_engagements": engagements,
        "views_by_slot": metric_groups(rows, "views"),
        "engagements_by_slot": metric_groups(rows, "engagements"),
        "age_threshold_hours": 72,
        "data_window_days": 90, "diagnostic": info or {}, "errors": errors or [],
    }
    return result


def audit_facebook():
    token, pageid = env("META_PAGE_ACCESS_TOKEN"), env("META_PAGE_ID")
    if not token or not pageid:
        return finish("facebook", [], {"status": "missing_credentials"})
    items, errors = [], []
    try:
        rows = pages(GRAPH, "/" + pageid + "/videos", token,
                     {"fields": "id,created_time,description", "limit": "25"})
        for row in rows[:65]:
            created = row.get("created_time")
            if not parse_date(created) or not SINCE <= parse_date(created) <= MATURE:
                continue
            metric = None
            try:
                d = http_get(GRAPH, "/" + row["id"] + "/video_insights", token,
                             {"metric": "total_video_views"})
                metric = insight_value(d, "total_video_views")
            except (ValueError, RuntimeError) as e:
                if len(errors) < 2: errors.append("video_insights:" + str(e))
            # Count views only when official per-video insights are accessible.
            add(items, created, metric, None, "video")
        return finish("facebook", items, {"status": "ok", "videos_examined": len(rows)}, errors)
    except (ValueError, RuntimeError) as e:
        return finish("facebook", items, {"status": "read_failed", "reason": str(e)}, errors)


def audit_instagram():
    token, uid = env("META_ACCESS_TOKEN") or env("META_PAGE_ACCESS_TOKEN"), env("IG_USER_ID")
    if not token or not uid:
        return finish("instagram", [], {"status": "missing_credentials"})
    items, errors = [], []
    try:
        rows = pages(GRAPH, "/" + uid + "/media", token,
                     {"fields": "id,timestamp,media_type,media_product_type,like_count,comments_count", "limit": "25"})
        for row in rows[:65]:
            dt = parse_date(row.get("timestamp"))
            if not dt or not SINCE <= dt <= MATURE:
                continue
            typ = str(row.get("media_product_type") or row.get("media_type") or "")
            views = None
            if typ.upper() in ("REELS", "VIDEO"):
                for candidate in ("views", "plays"):
                    try:
                        insight = http_get(GRAPH, "/" + row["id"] + "/insights", token,
                                           {"metric": candidate})
                        views = insight_value(insight, candidate)
                        if views is not None:
                            break
                    except (ValueError, RuntimeError) as exc:
                        if len(errors) < 3: errors.append("media_insights:" + str(exc))
            engagements = (row.get("like_count") or 0) + (row.get("comments_count") or 0)
            add(items, row.get("timestamp"), views, engagements, typ)
        return finish("instagram", items, {"status": "ok", "media_examined": len(rows)}, errors)
    except (ValueError, RuntimeError) as e:
        return finish("instagram", items, {"status": "read_failed", "reason": str(e)}, errors)


def audit_threads():
    token = env("THREADS_ACCESS_TOKEN")
    if not token:
        return finish("threads", [], {"status": "missing_credentials"})
    items, errors = [], []
    try:
        rows = pages(THREADS, "/me/threads", token,
                     {"fields": "id,timestamp,media_type,text", "limit": "25"})
        for row in rows[:65]:
            dt = parse_date(row.get("timestamp"))
            if not dt or not SINCE <= dt <= MATURE:
                continue
            insight = {}
            for metric in ("views", "likes", "replies", "reposts"):
                try:
                    d = http_get(THREADS, "/" + row["id"] + "/insights", token,
                                 {"metric": metric})
                    insight[metric] = insight_value(d, metric)
                except (ValueError, RuntimeError) as e:
                    if len(errors) < 3: errors.append("threads_insights:" + str(e))
            actions = sum(v or 0 for k,v in insight.items() if k in ("likes","replies","reposts"))
            add(items, row.get("timestamp"), insight.get("views"), actions, row.get("media_type", ""))
        return finish("threads", items, {"status": "ok", "media_examined": len(rows)}, errors)
    except (ValueError, RuntimeError) as e:
        return finish("threads", items, {"status": "read_failed", "reason": str(e)}, errors)


def audit_youtube():
    client, secret, refresh = [env(x) for x in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")]
    if not all((client, secret, refresh)):
        return finish("youtube", [], {"status": "missing_credentials"})
    try:
        r = requests.post("https://oauth2.googleapis.com/token",
                          data={"client_id": client, "client_secret": secret,
                                "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=25)
        if r.status_code != 200:
            return finish("youtube", [], {"status": "oauth_failed", "http": r.status_code})
        token = r.json().get("access_token", "")
        if not token:
            return finish("youtube", [], {"status": "oauth_missing_access_token"})
        api = "https://www.googleapis.com/youtube/v3"
        channel = http_get(api, "/channels", token, {"mine": "true", "part": "contentDetails", "maxResults": 1})
        if not channel.get("items"):
            return finish("youtube", [], {"status": "channel_not_readable"})
        playlist = (channel["items"][0].get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
        if not playlist:
            return finish("youtube", [], {"status": "uploads_playlist_absent"})
        entries, page_token = [], None
        for _ in range(3):
            params = {"part": "snippet,contentDetails", "playlistId": playlist, "maxResults": 50}
            if page_token:
                params["pageToken"] = page_token
            page = http_get(api, "/playlistItems", token, params)
            entries.extend(page.get("items") or [])
            page_token = page.get("nextPageToken")
            if not page_token:
                break
        ids, dates = [], {}
        for v in entries:
            vid = (v.get("contentDetails") or {}).get("videoId")
            published = (v.get("contentDetails") or {}).get("videoPublishedAt") or (v.get("snippet") or {}).get("publishedAt")
            if vid and parse_date(published) and SINCE <= parse_date(published) <= MATURE:
                ids.append(vid)
                dates[vid] = published
        items = []
        for i in range(0, min(len(ids), 100), 50):
            vids = http_get(api, "/videos", token,
                            {"part": "statistics,snippet", "id": ",".join(ids[i:i+50]), "maxResults": "50"})
            for v in vids.get("items", []):
                stats = v.get("statistics") or {}
                views = stats.get("viewCount")
                likes = stats.get("likeCount")
                comments = stats.get("commentCount")
                add(items, dates.get(v["id"]), int(views) if views is not None else None,
                    (int(likes or 0) + int(comments or 0)), "video")
        return finish("youtube", items, {"status": "ok", "videos_examined": len(ids)})
    except (ValueError, RuntimeError, requests.RequestException) as e:
        # Status-only / abbreviated error: no tokens or HTTP request parameters.
        return finish("youtube", [], {"status": "read_failed", "reason": str(e)[:100]})


def audit_tiktok():
    # TikTok posts list requires video.list scope and app review.
    if not env("TIKTOK_ACCESS_TOKEN"):
        return finish("tiktok", [], {"status": "missing_access_token"})
    try:
        token = env("TIKTOK_ACCESS_TOKEN")
        r = requests.post("https://open.tiktokapis.com/v2/video/list/",
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                          params={"fields": "id,create_time,view_count,like_count,comment_count"},
                          json={"max_count": 20}, timeout=25)
        if r.status_code != 200:
            return finish("tiktok", [], {"status": "http_failed", "http": r.status_code})
        data = r.json()
        status = (data.get("error") or {}).get("code")
        if status and status != "ok":
            return finish("tiktok", [], {"status": "api_failed", "error_code": str(status)[:80]})
        items = []
        for v in (data.get("data") or {}).get("videos") or []:
            dt = datetime.fromtimestamp(int(v["create_time"]), UTC).isoformat()
            add(items, dt, v.get("view_count"),
                (v.get("like_count") or 0) + (v.get("comment_count") or 0))
        return finish("tiktok", items, {"status": "ok", "videos_examined": len(items)})
    except (ValueError, RuntimeError, requests.RequestException, KeyError) as e:
        return finish("tiktok", [], {"status": "read_failed", "reason_type": type(e).__name__})


def main():
    result = {
        "collected_at": NOW.isoformat(), "timezone": "Africa/Lome (UTC+0 year-round)",
        "note": ("Read-only snapshot. Post metrics are lifetime totals at differing ages, "
                 "not first-24h views; slot comparisons are descriptive, not a causal test."),
        "platforms": {}
    }
    for name, fn in [("facebook", audit_facebook), ("instagram", audit_instagram),
                     ("youtube", audit_youtube), ("threads", audit_threads), ("tiktok", audit_tiktok)]:
        try:
            data = fn()
        except Exception as exc:
            # Avoid API response bodies / token values even if accidentally thrown.
            data = finish(name, [], {"status": "unexpected_error", "type": type(exc).__name__})
        result["platforms"][name] = data
        brief = data["diagnostic"]
        print("AUDIT", name, "status", brief.get("status"), "posts", data["posts_mature"],
              "with_views", data["posts_with_views"], "diagnostic", json.dumps(brief, ensure_ascii=False),
              "errors", ",".join(data.get("errors") or []), flush=True)
    path = Path("social_timing_audit.json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SOCIAL_TIMING_AUDIT_READY", str(path.resolve()), flush=True)


if __name__ == "__main__":
    main()
