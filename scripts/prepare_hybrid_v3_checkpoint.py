#!/usr/bin/env python3
"""Prepare authenticated past-only Hybrid V3 checkpoint, separate from publishing.

Daily training may be expensive; downstream inference does not refit models.
Never publish checkpoint, training history or 11x11 raw matrices on Pages.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from run_exact_scores_v3_daily import (
    BASE_CUTOFF, DAILY_HISTORY_SUBDIR, historical_daily_rows,
    install_research_modules)
CHECKPOINT_SUBDIR = Path("research/score_v3_model_checkpoints")


def timed(stage, start):
    print("V3_PREPARE_TIMING", json.dumps({
        "stage": stage, "seconds": round(time.monotonic() - start, 2)
    }), flush=True)


def prepare(site_root, model_root, *, now=None):
    began = time.monotonic()
    site_root = Path(site_root).resolve()
    model_root = install_research_modules(Path(model_root))
    old_cwd = Path.cwd()
    try:
        os.chdir(model_root)
        from sportdata_api import fetch_games, get_api_keys
        from single_ml_v2_git import key_from_environment, seal, open_sealed
        from single_ml_v2_multisource import certified_rows, check_ml_loader
        from single_ml_v2_data import day_snapshot
        from single_ml_v2 import load_matches, backtest
        from single_ml_v3_checkpoint import load_checkpoint
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("UTC timestamp required")
        yesterday = now.date() - timedelta(days=1)
        if yesterday < BASE_CUTOFF:
            raise ValueError("Frozen historical baseline unavailable")
        if not get_api_keys():
            raise RuntimeError("SportData keys unavailable")
        key = key_from_environment()
        path = site_root / CHECKPOINT_SUBDIR / (str(yesterday) + ".enc")
        if path.exists():
            # Do not trust a file merely because of its name.
            load_checkpoint(path, key, expected_day=yesterday)
            timed("authenticated_checkpoint_reused", began)
            return path
        step = time.monotonic()
        rows = certified_rows(key)
        history = check_ml_loader(rows)
        timed("decrypt_and_validate_historical_corpus", step)
        step = time.monotonic()
        fresh, day_counts = historical_daily_rows(
            site_root / DAILY_HISTORY_SUBDIR, yesterday,
            fetcher=fetch_games, normalizer=day_snapshot,
            sealer=seal, opener=open_sealed, key=key)
        timed("certify_incremental_history", step)
        if fresh:
            with tempfile.TemporaryDirectory(prefix="mrx-v3-certified-") as tmp:
                input_path = Path(tmp) / "verified.json"
                input_path.write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf8")
                extra = load_matches(str(input_path), yesterday)
            if len(extra) != len(fresh) or any(m.day > yesterday for m in extra):
                raise RuntimeError("Verified completed-day history rejected by native model")
            history = sorted([*history, *extra], key=lambda m: (m.day, m.key))
        if not history or history[-1].day != yesterday:
            raise RuntimeError("Latest certified day not fully covered")
        start = max(yesterday - timedelta(days=65), datetime(2026, 10, 1, tzinfo=timezone.utc).date())
        step = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="mrx-v3-train-") as tmp:
            backtest(history, start, yesterday, str(Path(tmp) / "train"),
                     max_eval=0, auto_tune=False, retrain_days=30,
                     v3_models=True, production_v3_only=True,
                     checkpoint_path=path, checkpoint_key=key)
        timed("train_native_hybrid_v3_and_seal_checkpoint", step)
        load_checkpoint(path, key, expected_day=yesterday)
        print("V3_PREPARE_COMPLETE", json.dumps({
            "cutoff": str(yesterday), "checkpoint": str(path.relative_to(site_root)),
            "incremental_days": len(day_counts),
            "duration_seconds": round(time.monotonic() - began, 2)
        }), flush=True)
        return path
    finally:
        os.chdir(old_cwd)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="site")
    p.add_argument("--model-root", default="model")
    args = p.parse_args()
    prepare(args.site_root, args.model_root)


if __name__ == "__main__":
    main()
