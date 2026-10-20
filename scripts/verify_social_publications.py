#!/usr/bin/env python3
"""Strict per-platform publication audit; no external API calls or credentials."""
import argparse
import json
from pathlib import Path

KNOWN = frozenset({"facebook", "instagram", "threads", "tiktok", "youtube"})

def validate(expected_csv, report):
    expected = [p.strip().lower() for p in expected_csv.split(",") if p.strip()]
    if not expected or len(expected) != len(set(expected)) or not set(expected) <= KNOWN:
        raise ValueError("Invalid or duplicate expected publishing platforms")
    if not isinstance(report,list):
        raise ValueError("Social report must be a JSON array")
    rows={}
    for row in report:
        if not isinstance(row,dict):
            raise ValueError("Invalid social provider entry")
        platform=row.get("platform")
        if platform in rows or platform not in KNOWN:
            raise ValueError("Unexpected or duplicate social platform result")
        rows[platform]=row
    if set(rows) != set(expected):
        raise ValueError("SOCIAL_PARTIAL_FAILURE: missing/unexpected platforms: " +
                         str(sorted(set(expected)^set(rows))))
    failed=[name for name in expected if rows[name].get("ok") is not True]
    if failed:
        raise ValueError("SOCIAL_PARTIAL_FAILURE: providers failed: "+",".join(failed))
    for name in expected:
        data=rows[name].get("data")
        if not isinstance(data,dict):
            raise ValueError("SOCIAL_UNVERIFIED_PROVIDER_RESULT: "+name)
        identity = data.get("id")
        if not isinstance(identity,(str,int)) or not str(identity).strip():
            raise ValueError("SOCIAL_MISSING_PROVIDER_ID: "+name)
    return {"checked":len(rows),"verified_platforms":expected,"failed":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",default="social_post_results.json")
    p.add_argument("--expected",required=True)
    args=p.parse_args()
    report=json.loads(Path(args.report).read_text(encoding="utf-8"))
    print("SOCIAL_PUBLICATION_AUDIT",json.dumps(validate(args.expected,report)))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
