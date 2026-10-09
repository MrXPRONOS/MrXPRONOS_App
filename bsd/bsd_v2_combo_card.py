"""Render the same light reference-style ticket as the single coupon, for two games."""
from __future__ import annotations
from bsd_v2_ticket_ui import render_combined

def render_combo(combo,path,*,now=None,session=None):
    return render_combined(combo,path,now=now,session=session)
