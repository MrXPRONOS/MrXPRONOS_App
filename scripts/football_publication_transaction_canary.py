#!/usr/bin/env python3
"""Offline BSD publication transaction/deduplication/rollback canary.

Uses ONE actually published historical BSD selection and authentic source
ledger, never fictional clubs, odds, bookmaker codes or live API responses.
Runs in a temporary private sandbox only. No Telegram/network/file mutation
outside the sandbox and aggregate-only report. A historical specimen is not
a new prematch coupon eligible for live public distribution.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/"bsd"):
    if str(p) not in sys.path:sys.path.insert(0,str(p))

from bsd_v2_audit import SCHEMA, _identity
from bsd_v2_guardrails import v21_accept_priced,post_price_value_guard,v21_signal_tier
from bsd_v2_estimated_odds import valid_standalone_prediction

ALLOWED=frozenset(("bsd_consensus","bsd_bookmaker"))
STATE_SCHEMA="bsd-offline-delivery-canary-v1"

def choose_historical_specimen(feed,ledger):
    """Find an AUTHENTIC already-public selection with a current-style V2.1 price guard.

    The historic publication confidence is NOT an independently proven current
    conservative forecast; specimen is never claimed to be a live GO signal.
    """
    if (not isinstance(feed,dict) or feed.get("source")!="bsd"
        or not isinstance(feed.get("matches"),list)
        or not isinstance(ledger,dict) or ledger.get("schema")!=SCHEMA):
        raise ValueError("Invalid real BSD feed/append-only publication ledger")
    old={entry.get("key"):entry for entry in ledger.get("entries",[])
         if isinstance(entry,dict) and isinstance(entry.get("key"),str)}
    for row in sorted(feed["matches"],key=lambda m:str(m.get("event_date") or "") if isinstance(m,dict) else ""):
        if not isinstance(row,dict) or row.get("source")!="bsd":
            continue
        key=_identity(row)
        old_row=old.get(key)
        if not old_row or old_row.get("origin")!="site_feed":
            continue
        pick=row.get("prediction")
        first=old_row.get("original_pick")
        if not isinstance(pick,dict) or not isinstance(first,dict):
            continue
        source=pick.get("odds_source")
        if source not in ALLOWED or source!=first.get("odds_source"):
            continue
        if pick.get("selection_key")!=first.get("selection_key"):
            continue
        if type(pick.get("odds")) not in (float,int):
            continue
        if abs(float(pick["odds"])-float(first.get("odds") or 0))>0.00001:
            continue
        if not valid_standalone_prediction(pick,row.get("combo_only",False)):
            continue
        # Existing site feed reports 'confidence' in PERCENT, not
        # 'conservative_probability' in [0, 1].
        confidence=pick.get("confidence")
        if type(confidence) not in (int,float) or not 0<confidence<100:
            continue
        choice={
            "key":pick.get("selection_key"),
            "market":pick.get("market"),
            "bookmaker_odds":float(pick["odds"]),
            "odds_source":source,
            "conservative_probability":float(confidence)/100,
        }
        gate,reason=v21_accept_priced(choice,tracker={},league_market=None)
        guard=post_price_value_guard(choice)
        if not gate or not guard.get("passed") or v21_signal_tier(choice)=="OBSERVATION":
            continue
        if choice["bookmaker_odds"]<1.20:
            continue
        return deepcopy(row),choice
    raise ValueError("No historical already-published, ledger-backed specimen meets replayed price safeguards")

def immutable_key(row):
    ident=_identity(row)
    pick=row.get("prediction") or {}
    if not ident or not pick.get("selection_key"):
        raise ValueError("Bad event+kickoff+selection identity")
    return sha256((ident+"|"+str(pick["selection_key"])).encode("utf-8")).hexdigest()

def apply_local_transaction(workdir:Path,row:dict,*,fault=None):
    """One-pointer immutable revision transaction; never contacts transport."""
    if fault not in (None,"after_prepare","after_activation"):
        raise ValueError("Unsupported fault injection")
    workdir=Path(workdir)
    if workdir.is_symlink() or not workdir.is_dir():
        raise ValueError("Sandbox directory is required")
    active=workdir/"ACTIVE.json"
    previous=active.read_bytes() if active.exists() else None
    original=json.loads(previous.decode("utf-8")) if previous is not None else {
        "schema":STATE_SCHEMA,"revision":0,"receipts":[],
    }
    if original.get("schema")!=STATE_SCHEMA or not isinstance(original.get("receipts"),list):
        raise ValueError("Invalid isolated delivery ledger")
    fingerprint=immutable_key(row)
    already={x["key"] for x in original["receipts"] if isinstance(x,dict) and "key" in x}
    if fingerprint in already:
        return {"reserved_new":0,"deduplicated":1,"transaction_committed":False,
                "simulated_transport_calls":0}
    # Only the stable fingerprint enters the local receipt ledger. No
    # team names, quote amounts or IDs leave the process/sandbox.
    state={
        "schema":STATE_SCHEMA,"revision":int(original["revision"])+1,
        "receipts":original["receipts"]+[{"key":fingerprint,"transport":"OFFLINE_ONLY"}],
    }
    temp=workdir/"ACTIVE.staged"
    staged=json.dumps(state,sort_keys=True,separators=(",",":")).encode("utf-8")
    try:
        with temp.open("wb") as output:
            output.write(staged)
            output.flush()
            os.fsync(output.fileno())
        if fault=="after_prepare":
            raise RuntimeError("Injected failure before activation")
        temp.replace(active)
        if fault=="after_activation":
            raise RuntimeError("Injected failure after activation")
        assert active.read_bytes()==staged
        return {"reserved_new":1,"deduplicated":0,"transaction_committed":True,
                "simulated_transport_calls":1}
    except Exception:
        # A durable external message cannot be unsent; THIS canary never sends
        # any. Only the sandbox's pointer state is restored byte for byte.
        if previous is None:
            active.unlink(missing_ok=True)
        else:
            recover=workdir/"ACTIVE.rollback"
            recover.write_bytes(previous)
            recover.replace(active)
        raise
    finally:
        temp.unlink(missing_ok=True)

def run_real_historical_canary(feed:dict,ledger:dict)->dict:
    before_feed=json.dumps(feed,sort_keys=True,ensure_ascii=False)
    before_ledger=json.dumps(ledger,sort_keys=True,ensure_ascii=False)
    specimen,choice=choose_historical_specimen(feed,ledger)
    key=immutable_key(specimen)
    historical={sha256((e.get("key") or "").encode()).hexdigest()
                for e in ledger.get("entries",[]) if isinstance(e,dict)}
    if not historical:
        raise AssertionError("Empty historical publication registry")
    with tempfile.TemporaryDirectory(prefix="mrxpronos-delivery-canary-") as tmp:
        root=Path(tmp)
        rollback_verified=0
        for phase in ("after_prepare","after_activation"):
            baseline=(root/"ACTIVE.json").read_bytes() if (root/"ACTIVE.json").exists() else None
            try:
                apply_local_transaction(root,specimen,fault=phase)
            except RuntimeError as exc:
                if "Injected failure" not in str(exc):
                    raise
            else:
                raise AssertionError("Fault-injected local delivery should not commit")
            after=(root/"ACTIVE.json").read_bytes() if (root/"ACTIVE.json").exists() else None
            if after!=baseline:
                raise AssertionError("Rollback failed to restore exact pointer bytes")
            rollback_verified+=1
        first=apply_local_transaction(root,specimen)
        second=apply_local_transaction(root,specimen)
        third=apply_local_transaction(root,specimen)
        committed=json.loads((root/"ACTIVE.json").read_text(encoding="utf-8"))
        if (first["reserved_new"]!=1 or first["simulated_transport_calls"]!=1
            or second["deduplicated"]!=1 or third["deduplicated"]!=1
            or len(committed["receipts"])!=1):
            raise AssertionError("Idempotency failed across consecutive attempts")
        if key!=committed["receipts"][0]["key"]:
            raise AssertionError("Receipt fingerprint mismatch")
    if before_feed!=json.dumps(feed,sort_keys=True,ensure_ascii=False):
        raise AssertionError("Original public feed mutated")
    if before_ledger!=json.dumps(ledger,sort_keys=True,ensure_ascii=False):
        raise AssertionError("Historical publication ledger mutated")
    return {
        "research_only":True,"historic_selection_authentic_from_feed_and_ledger":True,
        "specimen_had_real_independent_consensus_or_bsd_price":True,
        "historic_confidence_replayed_through_v21_and_value_guard":True,
        "specimen_is_historical_not_new_live_eligible_fixture":True,
        "new_qualified_prematch_selection_observed":False,
        "simulated_publication_attempts":3,
        "simulated_transport_dispatches":1,
        "duplicate_dispatches_suppressed":2,
        "transaction_rollbacks_byte_identical":rollback_verified,
        "original_data_json_or_ledger_modified":False,
        "external_telegram_messages_sent":0,
        "external_bookmaker_api_requests":0,
        "fixture_identifiers_or_quotes_exported":False,
        "production_publication_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--feed",required=True)
    p.add_argument("--ledger",required=True)
    p.add_argument("--report",required=True)
    a=p.parse_args()
    output=Path(a.report).resolve()
    if output in ((ROOT/"data.json").resolve(),(ROOT/"bsd"/"publication_ledger.json").resolve()):
        p.error("Do not overwrite any production data")
    feed=json.loads(Path(a.feed).read_text(encoding="utf-8"))
    ledger=json.loads(Path(a.ledger).read_text(encoding="utf-8"))
    report=run_real_historical_canary(feed,ledger)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BSD_PUBLICATION_TRANSACTION_CANARY",json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    main()
