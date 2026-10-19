"""Non-publishing live end-to-end audit of all ten Actu Crypto categories.

Real external API/RSS calls, same real validators, same Playwright renderers,
same production bot *read-only* permission check. Absolutely no sendPhoto,
no editMessageMedia and no writes to historical Telegram state.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from crypto import production_seed_v1 as seed

ROOT = Path("crypto/generated/test")
REPORT = ROOT / "live_readonly_audit_20261019.json"
DETAILS = []

def result(number: int, status: str, **details):
    record = {"number": number, "status": status, **details}
    DETAILS.append(record)
    print("ACTU_CRYPTO_LIVE_AUDIT", json.dumps(record, ensure_ascii=False), flush=True)

def verify_bot_read_only():
    try:
        d = seed.verify_production_route()  # GET getMe/getChat/getChatMember ONLY
        return {"status": "READ_ONLY_OK", "chat_type": d.get("type"),
                "channel": d.get("username"), "posting_rights": True}
    except Exception as e:
        return {"status": "ERROR", "problem": type(e).__name__ + ": " + str(e)[:200]}

def scan_n(number: int):
    try:
        output = seed.prepared(number)
        if output is None:
            if number == 4:
                data = seed.read_json(ROOT / "alerts_v2_data.json")
                result(number, "NO_REAL_ALERT", provider=data.get("provider"),
                       observation_count=len(data.get("observations", [])))
            else:
                result(number, "NO_QUALIFIED_RECENT_NEWS")
            return
        d, png = output
        seed.validated_real(number, d)  # Repeat full production validation
        seed.validate_image(png)
        from PIL import Image
        with Image.open(png) as image:
            dimensions=list(image.size)
        meta={"provider": d.get("provider") or d.get("main", {}).get("source"),
              "timestamp": d.get("timestamp") or d.get("collected_at"),
              "bytes": png.stat().st_size,"pixels":dimensions,
              "image":png.name,
              "demo":bool(d.get("is_demo")),
              "validated_real":True}
        if number in (1,3):
            row=d["rows"][0]
            meta.update(global_cap_usd=row.get("market_cap_total"),
                        global_volume_usd=row.get("global_volume_24h"))
        if number in (8,9):
            meta["original_article_url"]=d["main"].get("url")
            meta["headline_fr"]=d.get("headline_fr")
            meta["fingerprints"]=d.get("fingerprints")
        result(number,"REAL_VALIDATED_RENDERED",**meta)
    except Exception as exc:
        result(number,"ERROR",problem=type(exc).__name__+": "+str(exc)[:450],
               trace=traceback.format_exc(limit=2)[-800:])

def scan_10():
    try:
        seed.run("python","-m","crypto.export_regulation_v2")
        path=ROOT/"regulation_v2_candidate.json"
        if path.exists():
            from crypto.export_regulation_v2 import validate_candidate
            d=seed.read_json(path)
            validate_candidate(d)
            seed.run("node","scripts/render_crypto_regulation_v2.mjs")
            png=ROOT/"regulation_v2_candidate.png"
            seed.validate_image(png)
            result(10,"REAL_REVIEW_CANDIDATE_NO_PUBLICATION",
                   source=d["primary"]["source"],
                   original_url=d["primary"]["url"],
                   declared_stage=d["primary"]["stage"],
                   photo=png.name,bytes=png.stat().st_size)
        else:
            result(10,"NO_REGULATORY_CANDIDATE")
        # Explicitly exercise approval guard: empty sign-off registry should
        # never create production regulatory material.
        from crypto.regulation_10_approval import run as approved
        if approved():
            raise RuntimeError("UNEXPECTED: approved publication without human sign-off")
        public=ROOT/"regulation_v2_approved.json"
        if public.exists():
            raise RuntimeError("Approved legal JSON unexpectedly present")
    except Exception as exc:
        result(10,"ERROR",problem=type(exc).__name__+": "+str(exc)[:450],
               trace=traceback.format_exc(limit=2)[-800:])

def audit_cross_metrics():
    metrics={r["number"]:r for r in DETAILS
             if r.get("status")=="REAL_VALIDATED_RENDERED" and r["number"] in (1,3)}
    if len(metrics)<2:
        return {"status":"INCOMPLETE","reason":"One or both source posters not available"}
    one,three=metrics[1],metrics[3]
    cap1,cap3=one["global_cap_usd"],three["global_cap_usd"]
    vol1,vol3=one["global_volume_usd"],three["global_volume_usd"]
    if not all(isinstance(x,(float,int)) and x>0 for x in (cap1,cap3,vol1,vol3)):
        return {"status":"ERROR","reason":"Missing cross-poster global metric"}
    diffcap=abs(cap1-cap3)/max(cap1,cap3)
    diffvol=abs(vol1-vol3)/max(vol1,vol3)
    return {"status":"PASS" if diffcap<0.1 and diffvol<0.25 else "WARN",
            "market_cap_relative_diff":round(diffcap,5),
            "volume_relative_diff":round(diffvol,5)}

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    bot=verify_bot_read_only()
    print("ACTU_CRYPTO_LIVE_BOT_READ_ONLY",json.dumps(bot,ensure_ascii=False),flush=True)
    for number in range(1,10):
        scan_n(number)
    scan_10()
    comparison=audit_cross_metrics()
    doc={"audited_at":datetime.now(timezone.utc).isoformat(),
         "purpose":"Real API/RSS + actual production renderers, no Telegram writes",
         "telegram_preflight":bot,"cross_metrics":comparison,
         "rubrics":DETAILS}
    REPORT.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ACTU_CRYPTO_AUDIT_REPORT",REPORT,flush=True)
    failures=[r for r in DETAILS if r["status"]=="ERROR"]
    if bot["status"]=="ERROR" or failures or comparison["status"]=="ERROR":
        raise SystemExit(1)

if __name__=="__main__":
    main()
