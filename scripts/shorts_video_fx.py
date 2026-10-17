#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared zero-cost motion/audio helpers for Mr XPRONOS Shorts."""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

LOOP_TAIL_SECONDS = 0.18


def scene_duration(total: int, index: int) -> float:
    """Exact pacing for 1..5 coupons, with a longer final card."""
    base = {
        1: 4.50,
        2: 3.55,
        3: 3.05,
        4: 2.80,
        5: 2.60,
    }.get(max(1, min(5, int(total))), 2.60)
    return base + (0.55 if index == total - 1 else 0.0)


def card_zoom(t: float, duration: float) -> float:
    """Subtle 100 -> 101.2% breathing zoom during the readable hold."""
    if duration <= 0:
        return 1.0
    start = 0.34
    end = max(start + 0.01, duration - 0.34)
    p = max(0.0, min(1.0, (t - start) / (end - start)))
    # Smoothstep prevents a mechanical zoom.
    p = p * p * (3.0 - 2.0 * p)
    return 1.0 + 0.012 * p


def synthesize_soundtrack(durations, out: Path, *, results: bool = False) -> float:
    """Generate a subtle royalty-free ambience + transition SFX locally."""
    durations = [float(x) for x in durations]
    total = sum(durations) + LOOP_TAIL_SECONDS
    sr = 44100
    n = max(1, int(round(total * sr)))
    t = np.arange(n, dtype=np.float32) / sr

    # Very low stadium/broadcast bed: deterministic noise + warm tones.
    rng = np.random.default_rng(228)
    noise = rng.normal(0.0, 1.0, n).astype(np.float32)
    # Cheap smoothing gives a soft crowd-like texture, not harsh white noise.
    kernel = np.ones(180, dtype=np.float32) / 180.0
    smooth_noise = np.convolve(noise, kernel, mode="same")
    base_freq = 58.0 if not results else 62.0
    ambient = (
        0.0060 * smooth_noise
        + 0.0024 * np.sin(2 * np.pi * base_freq * t)
        + 0.0014 * np.sin(2 * np.pi * (base_freq * 1.5) * t)
    )
    y = ambient.astype(np.float32)

    starts = []
    cursor = 0.0
    for duration in durations:
        starts.append(cursor)
        cursor += duration

    # Short impact at each coupon landing.
    for start in starts:
        rel = t - (start + 0.34)
        mask = (rel >= 0) & (rel < 0.22)
        r = rel[mask]
        y[mask] += (
            0.042 * np.sin(2 * np.pi * 115 * r) * np.exp(-17 * r)
            + 0.014 * np.sin(2 * np.pi * 410 * r) * np.exp(-22 * r)
        )

    # Soft whoosh before every card change.
    for start in starts[1:]:
        rel = t - (start - 0.28)
        mask = (rel >= 0) & (rel < 0.42)
        r = rel[mask]
        env = np.sin(np.pi * np.clip(r / 0.42, 0, 1)) ** 2
        chirp = np.sin(2 * np.pi * (260 + 1100 * r) * r)
        y[mask] += 0.020 * chirp * env

    # Keep it comfortably below speech/music loudness.
    y = np.clip(y, -0.16, 0.16)
    pcm = np.int16(y * 32767)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return total
