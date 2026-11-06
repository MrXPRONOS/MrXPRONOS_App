"""Read-only adaptation of the existing BSD models and free-data connectors.

V3 never imports publishing, settlement or Telegram entrypoints.
"""
from pathlib import Path
import sys

BSD_PATH = str(Path(__file__).resolve().parent.parent / "bsd")
if BSD_PATH not in sys.path:
    sys.path.insert(0, BSD_PATH)

from bsd_v2_core import (V2History, estimate_goals, fixture_datetime,
                         score_matrix, markets_from_matrix, fit_rho_2024,
                         outcome_scores)
from bsd_markets import realized
