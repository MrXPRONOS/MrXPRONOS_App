"""
SCRIPT FBREF – PRONOSTICS BASÉS SUR LES H2H RÉCENTS
Version 6.4 – Export JSON avec date automatique
Auteur : Assistant IA
Date : 2026-02-27
"""

from camoufox.sync_api import Camoufox
from bs4 import BeautifulSoup
import pandas as pd
import time
from io import StringIO
import re
import json
from datetime import datetime

###############################################################################
# 1. CONFIGURATION GÉNÉRALE
###############################################################################

# Si aucune date n'est spécifiée, on prend la date du jour
DATE_ANALYSE = ""  # Laissez vide pour utiliser la date du jour

if not DATE_ANALYSE:
    DATE_ANALYSE = datetime.now().strftime("%Y-%m-%d")

# Années courante et précédente automatiques
ANNEE_ACTUELLE = datetime.now().year
ANNEE_PRECEDENTE = ANNEE_ACTUELLE - 1

MODE_SILENCIEUX = False
DELAI_REQUETE = 5.0

BASE_URL = "https://fbref.com"
URL_MATCHS_DU_JOUR = f"{BASE_URL}/en/matches/{DATE_ANALYSE}"
URL_RECHERCHE_EQUIPE = f"{BASE_URL}/en/search/search.fcgi?search="

TIMEOUT_PAGE = 60000
ATTENTE_APRES_CHARGEMENT = 6000
TIMEOUT_TURNSTILE = 15000

# Seuils pour les catégories de pronostics
SEUIL_HAUT = 5
SEUIL_MOYEN = 4
SEUIL_BAS = 3

###############################################################################
# 2. SÉLECTEURS HTML
###############################################################################

SELECTEURS_PAGE_MATCHS = {
    "conteneur_tableau": "div.table_wrapper",
    "legende_tableau": "caption",
    "titre_section": "div.section_heading h2",
    "lignes_match": "tbody tr",
    "equipe_domicile": "[data-stat='home_team']",
    "equipe_exterieur": "[data-stat='away_team']",
    "score_match": "[data-stat='match_report']",
    "heure_match": "[data-stat='start_time']",
    "ligne_vide": "tr.spacer",
}

SELECTEURS_PAGE_MATCH = {
    "tableau_h2h": "table#games_history_all",
    "conteneur_h2h": "div.table_container[id*='head2head']",
    "lien_rapport": "a",
    "iframe_cloudflare": "iframe[title*='Cloudflare']",
}

SELECTEURS_PAGE_EQUIPE = {
    "resultats_recherche": "div.search-item",
    "tableau_matchs": "table#matchlogs_for",  # ID spécifique pour les scores & fixtures
    "logo": "img.teamlogo",
}

NOMS_COLONNES = {
    "DATE": "Date",
    "DOMICILE": "Home",
    "EXTERIEUR": "Away",
    "SCORE": "Score",
    "COMPETITION": "Comp",
    "RESULTAT": "Result",  # Attention : dans le tableau, c'est "Result" (pas "result")
    "BUTS_POUR": "GF",      # Goals For
    "BUTS_CONTRE": "GA",     # Goals Against
    "ADVERSAIRE": "Opponent",
    "LIEU": "Venue",
}

###############################################################################
# 3. FONCTIONS UTILITAIRES
###############################################################################

def extraire_score(texte):
    if not texte or pd.isna(texte):
        return None, None
    match = re.search(r'(\d+)\s*[-–]\s*(\d+)', str(texte))
    if match:
        try:
            return int(match.group(1)), int(match.group(2))
        except:
            return None, None
    return None, None

def filtrer_par_annee(liste_matchs_dict):
    gardes = []
    for m in liste_matchs_dict:
        date_str = m.get(NOMS_COLONNES["DATE"], "")
        if not date_str:
            continue
        annee = None
        match_annee = re.search(r'\b(20\d{2})\b', str(date_str))
        if match_annee:
            annee = int(match_annee.group(1))
        if annee and (annee == ANNEE_ACTUELLE or annee == ANNEE_PRECEDENTE):
            gardes.append(m)
    return gardes

def contourner_cloudflare(page):
    try:
        iframe = page.frame_locator(SELECTEURS_PAGE_MATCH["iframe_cloudflare"])
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
            print("    ℹ Aucun Cloudflare détecté")
            return False

def nettoyer_nom_equipe(nom):
    codes_pays = r'^(de|it|eng|es|ca|mx|uy|ec|br|ar|co|sa|ch|nl|au|pt|ro|tr|ve|pe|ir)'
    nom = re.sub(codes_pays, '', nom).strip()
    nom = re.sub(r'\s*\([^)]*\)', '', nom).strip()
    return nom

def trouver_url_equipe(page, nom_equipe):
    nom_nettoye = nettoyer_nom_equipe(nom_equipe)
    try:
        search = nom_nettoye.replace(" ", "+")
        page.goto(f"{URL_RECHERCHE_EQUIPE}{search}", wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT//2)
        html = page.content().replace("<!--","").replace("-->","")
        soup = BeautifulSoup(html, "html.parser")
        for result in soup.select(SELECTEURS_PAGE_EQUIPE["resultats_recherche"]):
            if "teams" in str(result) and nom_nettoye.lower() in str(result).lower():
                liens = result.find_all("a", href=True)
                for lien in liens:
                    if "/en/squads/" in lien["href"]:
                        return BASE_URL + lien["href"]
        return None
    except:
        return None

def recuperer_logo_equipe(page, nom_equipe):
    url_equipe = trouver_url_equipe(page, nom_equipe)
    if not url_equipe:
        return None
    try:
        page.goto(url_equipe, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT//2)
        html = page.content().replace("<!--","").replace("-->","")
        soup = BeautifulSoup(html, "html.parser")
        img = soup.select_one(SELECTEURS_PAGE_EQUIPE["logo"])
        if img and img.get("src"):
            return BASE_URL + img["src"] if img["src"].startswith("/") else img["src"]
        return None
    except:
        return None

def recuperer_forme_equipe(page, nom_equipe):
    """
    Récupère la forme récente (5 derniers matchs) d'une équipe.
    Retourne une chaîne comme "V V N D V".
    """
    url_equipe = trouver_url_equipe(page, nom_equipe)
    if not url_equipe:
        return None
    try:
        page.goto(url_equipe, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT//2)
        html = page.content().replace("<!--","").replace("-->","")
        soup = BeautifulSoup(html, "html.parser")
        tableau = soup.select_one(SELECTEURS_PAGE_EQUIPE["tableau_matchs"])
        if not tableau:
            print(f"      ⚠️ Tableau matchlogs_for non trouvé pour {nom_equipe}")
            return None
        df = pd.read_html(StringIO(str(tableau)))[0]
        # Identifier la colonne "Result" (peut être différente selon le tableau)
        # On va chercher une colonne contenant "Result" dans son nom
        col_result = None
        for col in df.columns:
            if "Result" in str(col):
                col_result = col
                break
        if col_result is None:
            # Fallback : on suppose que c'est la 6ème colonne
            col_result = df.columns[5] if len(df.columns) > 5 else None
        if col_result is None:
            return None

        # Filtrer par année en utilisant la première colonne (date)
        matchs_filtres = []
        for idx, row in df.iterrows():
            date_str = str(row.iloc[0])
            annee = None
            ma = re.search(r'(\d{4})', date_str)
            if ma:
                annee = int(ma.group(1))
            if annee and (annee == ANNEE_ACTUELLE or annee == ANNEE_PRECEDENTE):
                matchs_filtres.append(row)

        # Prendre les 5 derniers (les plus récents sont en haut du tableau normalement)
        matchs_recents = matchs_filtres[:5]
        forme = []
        for match in matchs_recents:
            res = str(match.get(col_result, "")).strip()
            if res == "W":
                forme.append("V")
            elif res == "D":
                forme.append("N")
            elif res == "L":
                forme.append("D")
            else:
                forme.append("?")
        return " ".join(forme) if forme else None
    except Exception as e:
        print(f"      ⚠️ Erreur forme équipe: {str(e)}")
        return None

###############################################################################
# 4. EXTRACTION DES MATCHS DU JOUR
###############################################################################

def recuperer_matchs_du_jour(page):
    print(f"\n📅 RÉCUPÉRATION DES MATCHS DU {DATE_ANALYSE}")
    print(f"   URL: {URL_MATCHS_DU_JOUR}")
    try:
        page.goto(URL_MATCHS_DU_JOUR, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT)
        contourner_cloudflare(page)
        page.wait_for_selector(SELECTEURS_PAGE_MATCHS["conteneur_tableau"], timeout=TIMEOUT_PAGE)
        print("   ✓ Page chargée")

        html = page.content().replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(html, "html.parser")
        conteneurs = soup.select(SELECTEURS_PAGE_MATCHS["conteneur_tableau"])
        print(f"   ✓ {len(conteneurs)} compétitions trouvées")

        matchs = []
        for conteneur in conteneurs:
            competition = "Compétition inconnue"
            legende = conteneur.select_one(SELECTEURS_PAGE_MATCHS["legende_tableau"])
            if legende:
                competition = legende.get_text(strip=True)
                competition = competition.replace(" Schedule Table", "").replace("Table", "").strip()
            if competition == "Compétition inconnue":
                heading = conteneur.find_previous("div", class_="section_heading")
                if heading:
                    h2 = heading.select_one("h2")
                    if h2:
                        competition = h2.get_text(strip=True)

            tableau = conteneur.find("table")
            if not tableau:
                continue
            tbody = tableau.find("tbody")
            if not tbody:
                continue

            lignes = []
            for row in tbody.select(SELECTEURS_PAGE_MATCHS["lignes_match"]):
                if not row.select(SELECTEURS_PAGE_MATCHS["ligne_vide"]):
                    lignes.append(row)

            print(f"   • {competition}: {len(lignes)} matchs")

            for row in lignes:
                dom = row.select_one(SELECTEURS_PAGE_MATCHS["equipe_domicile"])
                ext = row.select_one(SELECTEURS_PAGE_MATCHS["equipe_exterieur"])
                score_cell = row.select_one(SELECTEURS_PAGE_MATCHS["score_match"])
                heure_cell = row.select_one(SELECTEURS_PAGE_MATCHS["heure_match"])

                if not dom or not ext:
                    continue

                equipe_domicile = dom.get_text(strip=True)
                equipe_exterieur = ext.get_text(strip=True)
                score = "(à venir)"
                if score_cell:
                    texte_score = score_cell.get_text(strip=True)
                    score = texte_score if texte_score.strip() else "(à venir)"
                heure = heure_cell.get_text(strip=True) if heure_cell else ""
                url_match = ""
                if score_cell:
                    lien = score_cell.find("a")
                    if lien and lien.get("href"):
                        url_match = BASE_URL + lien["href"]

                matchs.append({
                    "competition": competition,
                    "heure": heure,
                    "equipe_domicile": equipe_domicile,
                    "equipe_exterieur": equipe_exterieur,
                    "score": score,
                    "url_match": url_match
                })

        print(f"\n✅ {len(matchs)} matchs récupérés")
        return matchs
    except Exception as e:
        print(f"\n❌ ERREUR: {str(e)}")
        return []

###############################################################################
# 5. ANALYSE H2H D'UN MATCH (CORRIGÉE)
###############################################################################

def analyser_h2h(df_h2h, nom_domicile_actuel, nom_exterieur_actuel):
    if df_h2h is None or df_h2h.empty:
        return None

    matchs_bruts = df_h2h.to_dict('records')
    matchs_filtres = filtrer_par_annee(matchs_bruts)
    if not matchs_filtres:
        return None

    matchs_valides = []
    for m in matchs_filtres:
        bd, be = extraire_score(m.get(NOMS_COLONNES["SCORE"], ""))
        if bd is not None:
            matchs_valides.append(m)

    if not matchs_valides:
        return None

    matchs_valides.sort(key=lambda x: x.get(NOMS_COLONNES["DATE"], ""), reverse=True)

    victoires_equipe_domicile = 0
    victoires_equipe_exterieur = 0
    nuls = 0
    buts_equipe_domicile = 0
    buts_equipe_exterieur = 0
    matchs_btg = 0
    matchs_over_2_5 = 0

    def correspond(nom_actuel, nom_h2h):
        n1 = nom_actuel.lower().replace('fc', '').replace('united', '').replace('city', '').replace('afc', '').strip()
        n2 = nom_h2h.lower().replace('fc', '').replace('united', '').replace('city', '').replace('afc', '').strip()
        return n1 in n2 or n2 in n1

    for match in matchs_valides:
        home = str(match.get(NOMS_COLONNES["DOMICILE"], "")).strip()
        away = str(match.get(NOMS_COLONNES["EXTERIEUR"], "")).strip()
        bd, be = extraire_score(match.get(NOMS_COLONNES["SCORE"], ""))

        # Cas 1 : l'équipe actuelle domicile est à domicile
        if correspond(nom_domicile_actuel, home):
            buts_equipe_domicile += bd
            buts_equipe_exterieur += be
            if bd > be:
                victoires_equipe_domicile += 1
            elif be > bd:
                victoires_equipe_exterieur += 1
            else:
                nuls += 1
        # Cas 2 : l'équipe actuelle domicile est à l'extérieur
        elif correspond(nom_domicile_actuel, away):
            buts_equipe_domicile += be
            buts_equipe_exterieur += bd
            if be > bd:
                victoires_equipe_domicile += 1
            elif bd > be:
                victoires_equipe_exterieur += 1
            else:
                nuls += 1
        # Cas 3 : l'équipe actuelle extérieur est à domicile
        elif correspond(nom_exterieur_actuel, home):
            buts_equipe_exterieur += bd
            buts_equipe_domicile += be
            if bd > be:
                victoires_equipe_exterieur += 1
            elif be > bd:
                victoires_equipe_domicile += 1
            else:
                nuls += 1
        # Cas 4 : l'équipe actuelle extérieur est à l'extérieur
        elif correspond(nom_exterieur_actuel, away):
            buts_equipe_exterieur += be
            buts_equipe_domicile += bd
            if be > bd:
                victoires_equipe_exterieur += 1
            elif bd > be:
                victoires_equipe_domicile += 1
            else:
                nuls += 1
        else:
            continue

        total_buts = bd + be
        if bd > 0 and be > 0:
            matchs_btg += 1
        if total_buts > 2.5:
            matchs_over_2_5 += 1

    total_matchs = len(matchs_valides)
    stats = {
        "total_matchs": total_matchs,
        "victoires_equipe_domicile": victoires_equipe_domicile,
        "victoires_equipe_exterieur": victoires_equipe_exterieur,
        "nuls": nuls,
        "buts_equipe_domicile": buts_equipe_domicile,
        "buts_equipe_exterieur": buts_equipe_exterieur,
        "matchs_btg": matchs_btg,
        "matchs_over_2_5": matchs_over_2_5,
    }

    if total_matchs > 0:
        stats["pct_victoires_domicile"] = round((victoires_equipe_domicile/total_matchs)*100, 1)
        stats["pct_victoires_exterieur"] = round((victoires_equipe_exterieur/total_matchs)*100, 1)
        stats["pct_nuls"] = round((nuls/total_matchs)*100, 1)
        stats["pct_btg"] = round((matchs_btg/total_matchs)*100, 1)
        stats["pct_over_2_5"] = round((matchs_over_2_5/total_matchs)*100, 1)
        stats["moy_buts_domicile"] = round(buts_equipe_domicile/total_matchs, 2)
        stats["moy_buts_exterieur"] = round(buts_equipe_exterieur/total_matchs, 2)
        stats["moy_buts_total"] = round((buts_equipe_domicile+buts_equipe_exterieur)/total_matchs, 2)

    return stats

def obtenir_donnees_h2h_match(page, url_match, nom_domicile, nom_exterieur):
    print(f"    🎯 Extraction H2H...")
    try:
        page.goto(url_match, wait_until="domcontentloaded", timeout=TIMEOUT_PAGE)
        page.wait_for_timeout(ATTENTE_APRES_CHARGEMENT)
        contourner_cloudflare(page)

        html = page.content().replace("<!--", "").replace("-->", "")
        soup = BeautifulSoup(html, "html.parser")

        tableau_h2h = soup.select_one(SELECTEURS_PAGE_MATCH["tableau_h2h"])
        if not tableau_h2h:
            conteneur = soup.select_one(SELECTEURS_PAGE_MATCH["conteneur_h2h"])
            if conteneur:
                tableau_h2h = conteneur.find("table")
        if not tableau_h2h:
            print("    ⚠️  Tableau H2H introuvable")
            return None

        df = pd.read_html(StringIO(str(tableau_h2h)))[0]
        print(f"    ✓ {len(df)} matchs H2H trouvés")

        stats_h2h = analyser_h2h(df, nom_domicile, nom_exterieur)
        if not stats_h2h:
            print("    ⚠️  Aucun match H2H des années 2025-2026 avec score trouvé")
            return None

        return stats_h2h

    except Exception as e:
        print(f"    ✗ Erreur H2H: {str(e)}")
        return None

###############################################################################
# 6. PRONOSTICS
###############################################################################

def pronostiquer(stats_h2h, seuil_categorie):
    if not stats_h2h:
        return None

    total = stats_h2h["total_matchs"]
    victoires_dom = stats_h2h["victoires_equipe_domicile"]
    victoires_ext = stats_h2h["victoires_equipe_exterieur"]
    nuls = stats_h2h["nuls"]
    pct_btg = stats_h2h["pct_btg"]
    pct_over = stats_h2h["pct_over_2_5"]
    moy_buts_total = stats_h2h["moy_buts_total"]

    if victoires_dom > victoires_ext:
        dominant = "domicile"
        nb_victoires_dominant = victoires_dom
        nb_victoires_autre = victoires_ext
        nom_dominant = "Domicile"
        nom_autre = "Extérieur"
    elif victoires_ext > victoires_dom:
        dominant = "exterieur"
        nb_victoires_dominant = victoires_ext
        nb_victoires_autre = victoires_dom
        nom_dominant = "Extérieur"
        nom_autre = "Domicile"
    else:
        dominant = "equilibre"
        nb_victoires_dominant = victoires_dom
        nb_victoires_autre = victoires_ext
        nom_dominant = "Domicile/Extérieur (équilibré)"
        nom_autre = ""

    condition_remplie = False
    if seuil_categorie == "5+":
        if nb_victoires_dominant >= 4:
            condition_remplie = True
    elif seuil_categorie == "4":
        if nb_victoires_dominant >= 3:
            condition_remplie = True
    elif seuil_categorie == "3":
        if nb_victoires_dominant >= 2:
            condition_remplie = True

    if not condition_remplie:
        return None

    pronos = {}

    if dominant != "equilibre":
        prob_dc = round((nb_victoires_dominant + nuls) / total * 100, 1)
        pronos["double_chance"] = {
            "type": f"{nom_dominant} ou Nul",
            "probabilite": prob_dc,
            "fiabilite": None
        }
    else:
        prob_dom_ou_nul = round((victoires_dom + nuls) / total * 100, 1)
        prob_ext_ou_nul = round((victoires_ext + nuls) / total * 100, 1)
        pronos["double_chance"] = [
            {"type": "Domicile ou Nul", "probabilite": prob_dom_ou_nul},
            {"type": "Extérieur ou Nul", "probabilite": prob_ext_ou_nul}
        ]

    if pct_over >= 50:
        pronos["over_under"] = {"type": "Over 2.5", "probabilite": pct_over}
    else:
        pronos["over_under"] = {"type": "Under 2.5", "probabilite": 100 - pct_over}

    diff_moy = stats_h2h["moy_buts_domicile"] - stats_h2h["moy_buts_exterieur"]
    if abs(diff_moy) >= 1.5:
        handicap = f"{nom_dominant} -1.5" if dominant != "equilibre" else "Pas de handicap clair"
    elif abs(diff_moy) >= 0.8:
        handicap = f"{nom_dominant} -1" if dominant != "equilibre" else "Pas de handicap clair"
    else:
        handicap = "Handicap nul (0) ou pas de tendance"
    pronos["handicap"] = handicap

    if seuil_categorie == "5+":
        fiabilite_dc = "80-90%"
    elif seuil_categorie == "4":
        fiabilite_dc = "60-70%"
    else:
        fiabilite_dc = "50-55%"

    if "double_chance" in pronos:
        if isinstance(pronos["double_chance"], list):
            for p in pronos["double_chance"]:
                p["fiabilite"] = fiabilite_dc
        else:
            pronos["double_chance"]["fiabilite"] = fiabilite_dc

    return pronos

###############################################################################
# 7. FONCTIONS D'AFFICHAGE
###############################################################################

def afficher_en_tete_match(m, logo_dom=None, logo_ext=None, forme_dom=None, forme_ext=None):
    print(f"\n{'='*100}")
    print(f"⚽ MATCH: {m['equipe_domicile']} vs {m['equipe_exterieur']}")
    if logo_dom:
        print(f"   Logo domicile : {logo_dom}")
    if logo_ext:
        print(f"   Logo extérieur : {logo_ext}")
    if forme_dom:
        print(f"   Forme {m['equipe_domicile']} (5 derniers) : {forme_dom}")
    if forme_ext:
        print(f"   Forme {m['equipe_exterieur']} (5 derniers) : {forme_ext}")
    print(f"🏆 Compétition: {m['competition']} | ⏰ {m['heure']} | 📊 {m['score']}")
    print(f"{'='*100}")

def afficher_stats_h2h(stats):
    if not stats:
        print("\n📊 H2H: Aucune donnée disponible")
        return
    print(f"\n📈 STATISTIQUES H2H ({ANNEE_PRECEDENTE}-{ANNEE_ACTUELLE})")
    print(f"   {'─'*50}")
    print(f"   Total matchs analysés: {stats['total_matchs']}")
    print(f"\n   🏆 RÉSULTATS:")
    print(f"      • Victoires équipe domicile : {stats['victoires_equipe_domicile']} ({stats['pct_victoires_domicile']}%)")
    print(f"      • Victoires équipe extérieur : {stats['victoires_equipe_exterieur']} ({stats['pct_victoires_exterieur']}%)")
    print(f"      • Nuls                      : {stats['nuls']} ({stats['pct_nuls']}%)")
    print(f"\n   ⚽ BUTS:")
    print(f"      • Total: {stats['buts_equipe_domicile']}-{stats['buts_equipe_exterieur']}")
    print(f"      • Moyenne/match: {stats['moy_buts_domicile']} - {stats['moy_buts_exterieur']} (total {stats['moy_buts_total']})")
    print(f"\n   📊 STATISTIQUES AVANCÉES:")
    print(f"      • Les deux équipes marquent: {stats['matchs_btg']}/{stats['total_matchs']} ({stats['pct_btg']}%)")
    print(f"      • Over 2.5 buts: {stats['matchs_over_2_5']}/{stats['total_matchs']} ({stats['pct_over_2_5']}%)")

def afficher_pronostics(pronos, categorie):
    if not pronos:
        return
    print(f"\n🔮 PRONOSTICS (catégorie {categorie})")
    print(f"   {'─'*50}")
    if "double_chance" in pronos:
        dc = pronos["double_chance"]
        if isinstance(dc, list):
            for p in dc:
                print(f"   • Double chance : {p['type']} – probabilité {p['probabilite']}% (fiabilité {p['fiabilite']})")
        else:
            print(f"   • Double chance : {dc['type']} – probabilité {dc['probabilite']}% (fiabilité {dc['fiabilite']})")
    if "over_under" in pronos:
        ou = pronos["over_under"]
        print(f"   • {ou['type']} – probabilité {ou['probabilite']}%")
    if "handicap" in pronos:
        print(f"   • Handicap suggéré : {pronos['handicap']}")

def exporter_json(resultats, nom_fichier="pronostics.json"):
    """
    Exporte les résultats au format JSON avec date et catégories.
    """
    data = {
        "date": DATE_ANALYSE,
        "categories": {}
    }
    for cat, liste in resultats.items():
        data["categories"][cat] = []
        for match in liste:
            stats = match['stats_h2h']
            pronos = match['pronostics']
            # Construire l'objet match
            match_obj = {
                "competition": match['competition'],
                "heure": match['heure'],
                "equipe_domicile": match['equipe_domicile'],
                "equipe_exterieur": match['equipe_exterieur'],
                "score": match['score'],
                "url_match": match['url_match'],
                "logo_domicile": match.get('logo_domicile'),
                "logo_exterieur": match.get('logo_exterieur'),
                "forme_domicile": match.get('forme_domicile'),
                "forme_exterieur": match.get('forme_exterieur'),
                "stats_h2h": stats,
                "pronostics": pronos
            }
            data["categories"][cat].append(match_obj)

    with open(nom_fichier, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 {nom_fichier} généré avec succès !")

###############################################################################
# 8. FONCTION PRINCIPALE
###############################################################################

def main():
    print("\n" + "="*80)
    print("FBREF PRONOSTICS – ANALYSE H2H AVEC FIABILITÉ")
    print(f"Date: {DATE_ANALYSE} | Période H2H: {ANNEE_PRECEDENTE}-{ANNEE_ACTUELLE}")
    print("="*80)

    with Camoufox(headless=MODE_SILENCIEUX, humanize=True, disable_coop=True, window=(1280,720)) as browser:
        context = browser.new_context(viewport={"width":1280,"height":720})
        page = context.new_page()

        try:
            # ÉTAPE 1: Récupération des matchs du jour
            print("\n📥 ÉTAPE 1: Récupération des matchs du jour...")
            tous_matchs = recuperer_matchs_du_jour(page)
            if not tous_matchs:
                print("❌ Aucun match trouvé.")
                return

            # ÉTAPE 2: Pour chaque match, récupérer les H2H
            print("\n🔍 ÉTAPE 2: Récupération des H2H...")
            matchs_avec_h2h = []
            for i, m in enumerate(tous_matchs, 1):
                if m['url_match']:
                    print(f"   {i:3}. {m['equipe_domicile'][:20]} vs {m['equipe_exterieur'][:20]} ", end="")
                    stats = obtenir_donnees_h2h_match(page, m['url_match'], m['equipe_domicile'], m['equipe_exterieur'])
                    if stats:
                        m['stats_h2h'] = stats
                        m['nb_h2h'] = stats['total_matchs']
                        matchs_avec_h2h.append(m)
                        print(f"✓ {stats['total_matchs']} H2H")
                    else:
                        print("✗ Pas de H2H récent")
                    time.sleep(DELAI_REQUETE)

            # ÉTAPE 3: Classer et filtrer selon les critères
            print("\n📊 ÉTAPE 3: Application des filtres et pronostics...")
            resultats = {"5+": [], "4": [], "3": []}

            for match in matchs_avec_h2h:
                nb = match['nb_h2h']
                stats = match['stats_h2h']
                if nb >= SEUIL_HAUT:
                    pronos = pronostiquer(stats, "5+")
                    if pronos:
                        match['pronostics'] = pronos
                        resultats["5+"].append(match)
                elif nb == SEUIL_MOYEN:
                    pronos = pronostiquer(stats, "4")
                    if pronos:
                        match['pronostics'] = pronos
                        resultats["4"].append(match)
                elif nb == SEUIL_BAS:
                    pronos = pronostiquer(stats, "3")
                    if pronos:
                        match['pronostics'] = pronos
                        resultats["3"].append(match)

            # ÉTAPE 4: Récupération des logos et formes pour les matchs sélectionnés
            print("\n🖼️ ÉTAPE 4: Récupération des logos et formes récentes...")
            for cat, liste in resultats.items():
                for match in liste:
                    print(f"   • {match['equipe_domicile']} vs {match['equipe_exterieur']}")
                    match['logo_domicile'] = recuperer_logo_equipe(page, match['equipe_domicile'])
                    time.sleep(DELAI_REQUETE/2)
                    match['logo_exterieur'] = recuperer_logo_equipe(page, match['equipe_exterieur'])
                    time.sleep(DELAI_REQUETE/2)
                    match['forme_domicile'] = recuperer_forme_equipe(page, match['equipe_domicile'])
                    time.sleep(DELAI_REQUETE/2)
                    match['forme_exterieur'] = recuperer_forme_equipe(page, match['equipe_exterieur'])
                    time.sleep(DELAI_REQUETE/2)

            # ÉTAPE 5: Affichage des résultats par catégorie
            print("\n📈 ÉTAPE 5: Résultats")
            for cat, liste in resultats.items():
                if liste:
                    print(f"\n{'='*80}")
                    print(f"CATÉGORIE {cat} H2H ({len(liste)} matchs)")
                    print(f"{'='*80}")
                    for idx, match in enumerate(liste, 1):
                        afficher_en_tete_match(
                            match,
                            logo_dom=match.get('logo_domicile'),
                            logo_ext=match.get('logo_exterieur'),
                            forme_dom=match.get('forme_domicile'),
                            forme_ext=match.get('forme_exterieur')
                        )
                        afficher_stats_h2h(match['stats_h2h'])
                        afficher_pronostics(match['pronostics'], cat)
                        if idx < len(liste):
                            print(f"\n⏳ ---")
                else:
                    print(f"\n📭 Aucun match dans la catégorie {cat} H2H répondant aux critères.")

            # ÉTAPE 6: Export JSON
            exporter_json(resultats)

            # Résumé final
            total_filtres = sum(len(lst) for lst in resultats.values())
            print(f"\n{'='*80}")
            print("✅ ANALYSE TERMINÉE")
            print(f"{'='*80}")
            print(f"   • Matchs du jour         : {len(tous_matchs)}")
            print(f"   • Matchs avec H2H récents : {len(matchs_avec_h2h)}")
            print(f"   • Matchs avec pronostics  : {total_filtres}")
            print(f"   • Répartition : 5+ H2H: {len(resultats['5+'])}  |  4 H2H: {len(resultats['4'])}  |  3 H2H: {len(resultats['3'])}")

        except KeyboardInterrupt:
            print("\n⏹️ Interruption utilisateur")
        except Exception as e:
            print(f"\n❌ Erreur critique: {str(e)}")
        finally:
            context.close()
            browser.close()
            print("\n🧹 Navigateur fermé")

###############################################################################
# 9. EXÉCUTION
###############################################################################

if __name__ == "__main__":
    debut = time.time()
    main()
    duree = time.time() - debut
    print(f"\n⏱️  Durée totale : {int(duree//60)}min {int(duree%60)}sec")