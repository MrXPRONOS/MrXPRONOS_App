"""Authenticated Hybrid V3 production checkpoint and fast pre-match inference.

The checkpoint is AES-256-GCM authenticated with the existing ML history secret.
Only decrypt an Actions-generated trusted checkpoint; pickle is never loaded
from unverified bytes. No raw results, model or matrices are deployed to Pages.
"""
from __future__ import annotations

import gzip
import os
import pickle
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import numpy as np

MAGIC = b"MRXV3C01"
VERSION = 1
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_RAW_BYTES = 200 * 1024 * 1024


def _aad(day):
    return ("mrx-v3-trained-past-only:" + str(day)).encode("ascii")


def save_checkpoint(path, key, *, state, hist_model, eleven_history,
                    hybrid_history, hybrid_weight, dc_rho, history_day, fit_day):
    """Persist only the fitted Hybrid V3 necessities, never other candidates."""
    from single_ml_v3 import VERSION as V3_VERSION
    if not isinstance(history_day, date) or not isinstance(fit_day, date):
        raise ValueError("Checkpoint dates are mandatory")
    if fit_day > history_day or state.last_ingested_day != history_day or hist_model is None:
        raise ValueError("Incomplete V3 checkpoint; refusing to persist")
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Invalid checkpoint encryption key")
    doc = {
        "checkpoint_version": VERSION, "v3_version": V3_VERSION,
        "history_day": history_day, "fit_day": fit_day,
        "state": state, "hist_model": hist_model,
        "eleven_history": eleven_history, "hybrid_history": hybrid_history,
        "hybrid_weight": hybrid_weight, "dc_rho": dc_rho,
    }
    raw = pickle.dumps(doc, protocol=5)
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("Trained V3 state exceeds size bound")
    blob = gzip.compress(raw, compresslevel=3, mtime=0)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, blob, _aad(history_day))
    sealed = MAGIC + nonce + ciphertext
    if len(sealed) > MAX_FILE_BYTES:
        raise ValueError("Sealed V3 state exceeds size bound")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    try:
        tmp.write_bytes(sealed)
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    return output


def load_checkpoint(path, key, *, expected_day):
    """Authenticate ciphertext and cutoff BEFORE any deserialization."""
    from single_ml_v3 import VERSION as V3_VERSION
    if not isinstance(expected_day, date):
        raise ValueError("Expected historical cutoff date is required")
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Invalid checkpoint encryption key")
    input_path = Path(path)
    if input_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Oversized model checkpoint")
    sealed = input_path.read_bytes()
    if len(sealed) < len(MAGIC) + 12 + 16 or not sealed.startswith(MAGIC):
        raise ValueError("Invalid checkpoint header")
    decrypted = AESGCM(key).decrypt(
        sealed[len(MAGIC):len(MAGIC)+12], sealed[len(MAGIC)+12:],
        _aad(expected_day))
    # Bound decompression before invoking pickle. AEAD ensures this is
    # an authenticated checkpoint, not a third-party-supplied pickle.
    import zlib
    inflator = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = inflator.decompress(decrypted, MAX_RAW_BYTES + 1)
    if len(raw) > MAX_RAW_BYTES or not inflator.eof or inflator.unconsumed_tail:
        raise ValueError("Invalid checkpoint compression")
    raw += inflator.flush()
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("Checkpoint exceeds raw size limit")
    data = pickle.loads(raw)
    if not isinstance(data, dict) or data.get("checkpoint_version") != VERSION:
        raise ValueError("Incompatible model checkpoint")
    if data.get("v3_version") != V3_VERSION or data.get("history_day") != expected_day:
        raise ValueError("Out-of-date model/checkpoint cutoff")
    fit_day = data.get("fit_day")
    if not isinstance(fit_day, date) or fit_day > expected_day:
        raise ValueError("Invalid trained model cutoff")
    state = data.get("state")
    if getattr(state, "last_ingested_day", None) != expected_day or data.get("hist_model") is None:
        raise ValueError("Incomplete verified form history")
    return data


def forecast_from_checkpoint(checkpoint, fixtures, *, now=None):
    """The same native Hybrid V3 grid (HistGB + DC), without retraining."""
    from single_ml_v2 import Match, poisson_grid, dixon_coles
    from single_ml_v3 import (
        HYBRID_NAME, hist_v3_grid, calibrate_eleven_cell, hybrid_v3_grid,
        eleven_multiplier, hybrid_v3_weight)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("Publication requires explicit UTC clock")
    asof = now.replace(microsecond=0)
    history_day = checkpoint["history_day"]
    fit_day = checkpoint["fit_day"]
    if history_day >= asof.date() or (asof.date()-history_day).days > 3:
        raise ValueError("Stale or future historical checkpoint")
    p11factor = eleven_multiplier(checkpoint["eleven_history"], asof=asof.date())
    weight, setting = hybrid_v3_weight(checkpoint["hybrid_history"],
                    asof=asof.date(), previous=checkpoint["hybrid_weight"])
    state = checkpoint["state"]
    model = checkpoint["hist_model"]
    rho = checkpoint["dc_rho"]
    published = []
    ids = set()
    for future in fixtures:
        if not isinstance(future, dict):
            raise ValueError("Invalid prospective fixture")
        forbidden = {"actual_score","home_score","away_score","hit","result",
                     "is_finished","final_score","win","grid"}
        if forbidden.intersection(future):
            raise ValueError("Postmatch field in prospective fixture")
        ident = future.get("id")
        try:
            kickoff = datetime.fromisoformat(str(future.get("kickoff_utc")).replace("Z","+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid verified kickoff time") from exc
        if (kickoff.tzinfo is None or kickoff.utcoffset()!=timedelta(0)
            or kickoff.date() not in (asof.date(),asof.date()+timedelta(days=1))
            or kickoff <= asof):
            continue
        if not isinstance(ident,str) or not ident or ident in ids:
            raise ValueError("Duplicate or missing prospective match ID")
        ids.add(ident)
        league, home, away = (future.get(k) for k in ("league","home","away"))
        if not all(isinstance(x,str) and x.strip() for x in (league,home,away)) or home==away:
            raise ValueError("Invalid team/competition identity")
        features = state.features(Match(ident,kickoff.date(),league,home,away,0,0))
        base = poisson_grid(features["h"],features["a"])
        dc = dixon_coles(features["h"],features["a"],rho)
        hist = hist_v3_grid(model,features["vector"],base,
                   form_samples=features["form_samples"],p11_factor=1.)
        if hist is None:
            raise ValueError("Untrained authentic HistGB V3")
        corrected = calibrate_eleven_cell(hist,p11factor)
        hybrid = hybrid_v3_grid(corrected,dc,dc_weight=weight)
        if hybrid.shape!=(11,11) or not np.isfinite(hybrid).all():
            raise ValueError("Invalid trained Hybrid V3 grid")
        published.append({
            "id":ident, "model":HYBRID_NAME,
            "league":league,"home":home,"away":away,
            "kickoff_utc":kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model_fit_latest_day":str(fit_day),
            "history_latest_day":str(history_day),
            "grid":hybrid.tolist(),
        })
    return {
        "origin":"prospective_prematch",
        "model":HYBRID_NAME,
        "generated_at":asof.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fixtures":published,
    }
