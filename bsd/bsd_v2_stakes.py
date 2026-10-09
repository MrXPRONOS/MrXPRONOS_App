"""Barème unique de mise indicative des coupons MR XPRONOS.

Montants théoriques pour la présentation Telegram, et NON paris enregistrés.
Les simples sont classés par cote BSD; les combinés ont une mise constante.
"""
from __future__ import annotations
from math import isfinite

MIN_SINGLE_STAKE=100_000
MAX_SINGLE_STAKE=500_000
COMBO_STAKE=250_000

# Chaque tranche inclut sa borne basse et exclut la borne haute.
# Les cotes <1.20 sont réservées aux combinés par le moteur de diffusion.
STAKES_BY_ODDS=(
    (2.00,500_000),  # 1.20 à 1.99
    (2.50,400_000),  # 2.00 à 2.49
    (3.00,300_000),  # 2.50 à 2.99
    (4.00,200_000),  # 3.00 à 3.99
    (float("inf"),100_000), # 4.00 ou plus
)

def single_stake(odds):
    """Retourne le palier en F CFA ou None si la cote est invalide.

    Toute la présentation suit le barème indépendamment du statut du ticket
    (pronostic ou marché gagné), ce qui garantit des images cohérentes.
    """
    if isinstance(odds,bool) or not isinstance(odds,(float,int)):
        return None
    if not isfinite(odds) or not (1.20 <= odds <= 100):
        return None
    for upper,stake in STAKES_BY_ODDS:
        if odds < upper:
            return stake
    raise AssertionError("Unreachable odds bucket")

def combination_stake():
    """Mise de référence fixe, quel que soit le produit des cotes."""
    return COMBO_STAKE

def gain_potentiel(stake,odds):
    """Retour indicatif BRUT, sans prétendre à un gain net/paiement réel."""
    if stake is None or isinstance(odds,bool) or not isinstance(odds,(float,int)):
        return None
    if not isfinite(odds) or odds <= 1:
        return None
    return round(stake*odds)

def money(value):
    return "—" if value is None else f"{value:,}".replace(","," ")+" F CFA"
