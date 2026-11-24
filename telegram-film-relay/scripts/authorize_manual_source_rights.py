"""Explicit, audited, rights-gated activation of owner private manual vaults.

Does NOT infer copyright permissions from Telegram ownership, video availability,
or earlier general publishing switches. Runs only after an owner confirms rights.
No content is sent by this tool; it only flips existing verified D1 source gates.
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys

from scripts.audit_remaining_manual_vaults import REMAINING,audit
from scripts.complete_remaining_manual_vaults import d1_query


def categories_for(target):
    if target=="all":
        return list(REMAINING)
    if target in REMAINING:
        return [target]
    raise ValueError("unrecognized_manual_rights_category")


def authorized_request(env,flag):
    return bool(flag and
        env.get("GITHUB_REPOSITORY")=="MrXPRONOS/MrXPRONOS_App"
        and env.get("GITHUB_ACTOR","").lower()=="mrxpronos"
        and env.get("GITHUB_REF")=="refs/heads/main")


async def activate(target,*,confirm,env=None):
    env=os.environ if env is None else env
    if not authorized_request(env,confirm):
        raise RuntimeError("explicit_owner_redistribution_rights_required")
    wanted=categories_for(target)
    current=await audit()
    verified={x.category for x in current if x.ready}
    if not set(wanted)<=verified:
        raise RuntimeError("live_telegram_source_or_bot_not_verified")
    slots=",".join("?" for _ in wanted)
    old=d1_query(
        "SELECT category,owner_approved,bot_access_verified,rights_attested,enabled "
        "FROM cine_manual_fallback_sources WHERE category IN ("+slots+")",
        wanted)
    if len(old)!=len(wanted) or {r["category"] for r in old}!=set(wanted):
        raise RuntimeError("category_source_registry_incomplete")
    if any(int(r["owner_approved"])!=1 or
           int(r["bot_access_verified"])!=1 for r in old):
        raise RuntimeError("category_source_approval_or_bot_missing")
    d1_query(
        "UPDATE cine_manual_fallback_sources "
        "SET rights_attested=1,enabled=1,verified_at=CURRENT_TIMESTAMP "
        "WHERE category IN ("+slots+") "
        "AND owner_approved=1 AND bot_access_verified=1",
        wanted)
    checked=d1_query(
        "SELECT category,rights_attested,enabled "
        "FROM cine_manual_fallback_sources WHERE category IN ("+slots+")",
        wanted)
    if (len(checked)!=len(wanted) or
        {x["category"] for x in checked}!=set(wanted) or
        any(int(x["rights_attested"])!=1 or int(x["enabled"])!=1
            for x in checked)):
        raise RuntimeError("manual_rights_d1_receipt_incomplete")
    # Never discard owner uploads received BEFORE explicit attestation.
    # Promote only items quarantined solely for missing rights, not
    # changed media, ambiguous titles, unsupported files or other reasons.
    d1_query(
        "UPDATE cine_manual_fallback_inbox "
        "SET state='indexed',review_code='',updated_at=CURRENT_TIMESTAMP "
        "WHERE category IN ("+slots+") AND state='needs_review' "
        "AND review_code='rights_not_attested' AND EXISTS ("
        "SELECT 1 FROM cine_manual_fallback_sources s "
        "WHERE s.chat_id=cine_manual_fallback_inbox.chat_id "
        "AND s.category=cine_manual_fallback_inbox.category "
        "AND s.owner_approved=1 AND s.bot_access_verified=1 "
        "AND s.rights_attested=1 AND s.enabled=1)",
        wanted)
    return wanted


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--category",choices=(*REMAINING,"all"),required=True)
    parser.add_argument("--confirm-redistribution-rights",action="store_true")
    opts=parser.parse_args()
    from scripts.check_personal_cooldown import seconds_remaining
    if seconds_remaining():
        print("CINEX_MANUAL_RIGHTS_BLOCKED_BY_FLOODWAIT")
        return 75
    try:
        categories=asyncio.run(activate(
            opts.category,confirm=opts.confirm_redistribution_rights))
    except Exception as exc:
        print("CINEX_MANUAL_RIGHTS_NOT_ACTIVATED",type(exc).__name__)
        return 1
    print("CINEX_MANUAL_RIGHTS_ACTIVATED",",".join(categories),
          "total",len(categories))
    return 0

if __name__=="__main__":
    sys.exit(main())
