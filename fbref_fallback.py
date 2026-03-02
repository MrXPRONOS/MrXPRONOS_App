#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fbref_fallback.py - Scraper FBref pour récupérer les scores de matchs terminés.
Utilise Camoufox pour contourner Cloudflare.
"""

import re
import time
from datetime import datetime
from camoufox.sync_api import Camoufox

TIMEOUT_PAGE = 60000
ATTENTE_APRES_CHARGEMENT = 6000
TIMEOUT_TURNSTILE = 15000

BASE_URL = "https://fbref.com"

def contourner_cloudflare(page):
    """Tente de contourner Cloudflare sur la page."""
    try:
        iframe = page.frame_locator("iframe[title*='Cloudflare']")
        cb = iframe.locator("input[type='checkbox']")
        cb.wait_for(timeout=TIMEOUT_TURNSTILE)
        cb.click(force=True)
        print("    ✓ Cloudflare contourné (iframe)")
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT)
        return True
    except:
        try:
            page.mouse.click(210, 335)
            print("    ✓ Cloudflare contourné (coordonnées)")
            page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT)
            return True
        except:
            return False

def get_match_score(date, home_team, away_team):
    """
    Recherche le score d'un match sur FBref à partir de la date et des noms d'équipes.
    Retourne un tuple (home_score, away_score) ou None.
    """
    # Formatage de la date pour l'URL (YYYY-MM-DD)
    date_str = date.strftime("%Y-%m-%d") if isinstance(date, datetime) else date
    url = f"{BASE_URL}/en/matches/{date_str}"

    with Camoufox(headless=True, humanize=True, disable_coop=True, window=(1280,720)) as browser:
        context = browser.new_context(viewport={"width":1280,"height":720})
        page = context.new_page()

        try:
            print(f"   📡 Chargement {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
            page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT)
            contourner_cloudflare(page)

            # Attendre que le contenu des matchs apparaisse
            page.wait_for_selector("div.table_wrapper", timeout=TIMEOUT_PAGE)

            # Extraire les matchs via JavaScript (simplifié)
            # On va chercher toutes les lignes de matchs et comparer les noms
            match_rows = page.locator("table tbody tr").all()
            for row in match_rows:
                # Récupérer les équipes
                home_cell = row.locator("[data-stat='home_team']").first
                away_cell = row.locator("[data-stat='away_team']").first
                score_cell = row.locator("[data-stat='match_report']").first

                if not home_cell or not away_cell or not score_cell:
                    continue

                home = home_cell.inner_text().strip()
                away = away_cell.inner_text().strip()
                score_text = score_cell.inner_text().strip()

                # Vérifier si les équipes correspondent (tolérance)
                if (home_team.lower() in home.lower() or home.lower() in home_team.lower()) and \
                   (away_team.lower() in away.lower() or away.lower() in away_team.lower()):
                    # Extraire les scores
                    match = re.search(r'(\d+)\s*[-–]\s*(\d+)', score_text)
                    if match:
                        return int(match.group(1)), int(match.group(2))
            return None
        except Exception as e:
            print(f"   ❌ Erreur lors du scraping FBref: {e}")
            return None
        finally:
            context.close()
            browser.close()