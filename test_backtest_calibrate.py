#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_backtest_calibrate.py 
Backtest utilisant les fonctions de generate_data.py
Permet de tester différents seuils et de calculer le taux de réussite réel.
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# Import direct des fonctions depuis generate_data.py
import generate_data as gd

# Constante manquante dans generate_data.py (à définir si absente)
HOME_ADVANTAGE = 0.1  # à ajuster si besoin

def load_all_matches(cache_file=None):
    if cache_file is None:
        cache_file = os.path.join(gd.CACHE_DIR, "all_matches_clean.json")
        if not os.path.exists(cache_file):
            cache_file = os.path.join(gd.CACHE_DIR, "all_matches.json")
    if not os.path.exists(cache_file):
        print(f"❌ Fichier cache introuvable : {cache_file}")
        return []
    with open(cache_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_match_date(match):
    if 'start_time' in match and match['start_time']:
        return match['start_time'][:10]
    if 'date' in match and match['date']:
        return match['date'][:10]
    return None

def filter_matches_by_date(matches, date):
    return [m for m in matches if get_match_date(m) == date]

def main():
    parser = argparse.ArgumentParser(description="Backtest avec calibration des seuils")
    parser.add_argument("--start-date", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--verbose", action="store_true", help="Afficher les détails")
    parser.add_argument("--cache", help="Fichier cache alternatif")
    parser.add_argument("--seuil-dominance", type=float, default=0.55, help="Seuil de dominance (défaut: 0.55)")
    parser.add_argument("--seuil-draw-rate", type=float, default=0.45, help="Seuil de draw_rate maximum (défaut: 0.45)")
    parser.add_argument("--min-h2h", type=int, default=2, help="Nombre minimum de matchs H2H (défaut: 2)")
    parser.add_argument("--min-form-matches", type=int, default=2, help="Nombre minimum de matchs de forme (défaut: 2)")
    parser.add_argument("--include-12", action="store_true", help="Inclure les pronostics 12 (matchs équilibrés)")
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    print("="*60)
    print("🚀 BACKTEST AVEC CALIBRATION")
    print(f"🔍 Test du {start} au {end}")
    print(f"Paramètres : dominance>{args.seuil_dominance}, draw_rate<{args.seuil_draw_rate}, min H2H={args.min_h2h}, min forme={args.min_form_matches}, inclure 12={args.include_12}")
    print("="*60)

    all_matches = load_all_matches(args.cache)
    if not all_matches:
        return
    print(f"📂 {len(all_matches)} matchs chargés.")

    # Construire l'historique des équipes (une seule fois)
    team_matches = gd.build_team_history(all_matches)

    results = {'simple': {'total': 0, 'correct': 0},
               'pro': {'total': 0, 'correct': 0},
               'vip': {'total': 0, 'correct': 0}}
    stats = {
        'total_matches': 0,
        'ignored_not_finished': 0,
        'ignored_h2h_insuffisant': 0,
        'ignored_draw_rate': 0,
        'ignored_form': 0,
        'ignored_double_chance_12': 0,
        'ignored_scores_manquants': 0,
        'processed': 0
    }

    current = start
    while current <= end:
        print(f"\n📅 Traitement du {current}...")
        day_matches = filter_matches_by_date(all_matches, current.isoformat())
        if not day_matches:
            print("   Aucun match trouvé pour cette date.")
            current += timedelta(days=1)
            continue

        print(f"   {len(day_matches)} matchs trouvés.")
        stats['total_matches'] += len(day_matches)

        for match in day_matches:
            if not match.get('is_finished'):
                stats['ignored_not_finished'] += 1
                if args.verbose:
                    print(f"   ⚠️ {match.get('home_team','?')} vs {match.get('away_team','?')} ignoré (non terminé)")
                continue

            home_team = match['home_team']
            away_team = match['away_team']
            home_score = match.get('home_score')
            away_score = match.get('away_score')
            if home_score is None or away_score is None:
                stats['ignored_scores_manquants'] += 1
                if args.verbose:
                    print(f"   ⚠️ {home_team} vs {away_team} ignoré (scores manquants)")
                continue

            competition = match.get('competition', '')

            # H2H avant la date (sans le match courant)
            h2h_list = gd.get_h2h(all_matches, home_team, away_team, years=2)
            h2h_before = [m for m in h2h_list if get_match_date(m) < current.isoformat()]

            if len(h2h_before) < args.min_h2h:
                stats['ignored_h2h_insuffisant'] += 1
                if args.verbose:
                    print(f"   ⚠️ {home_team} vs {away_team} ignoré (H2H insuffisant: {len(h2h_before)})")
                continue

            analysis = gd.analyze_h2h(h2h_before, home_team, away_team)

            # Forme des équipes avant la date
            home_form = gd.get_team_form(home_team, team_matches, last_games=5, max_days=365)
            away_form = gd.get_team_form(away_team, team_matches, last_games=5, max_days=365)

            # Filtre draw_rate
            if analysis['draw_rate'] > args.seuil_draw_rate:
                stats['ignored_draw_rate'] += 1
                if args.verbose:
                    print(f"   ⚠️ {home_team} vs {away_team} ignoré (draw_rate > {args.seuil_draw_rate})")
                continue

            # Vérifier que la forme est suffisante
            form_ok = True
            if home_form is None and away_form is None:
                form_ok = False
            elif home_form is None and away_form and away_form['matches_used'] < args.min_form_matches:
                form_ok = False
            elif away_form is None and home_form and home_form['matches_used'] < args.min_form_matches:
                form_ok = False
            elif home_form and home_form['matches_used'] < args.min_form_matches and away_form and away_form['matches_used'] < args.min_form_matches:
                form_ok = False

            if not form_ok:
                stats['ignored_form'] += 1
                if args.verbose:
                    print(f"   ⚠️ {home_team} vs {away_team} ignoré (forme insuffisante)")
                continue

            # Générer la prédiction avec seuil personnalisé
            def generate_prediction_local(analysis, home_form, away_form, league, h2h_list):
                home_dom = analysis["home_dominance"] + HOME_ADVANTAGE
                away_dom = analysis["away_dominance"]
                if home_dom > away_dom + args.seuil_dominance:
                    double_chance = "1X"
                elif away_dom > home_dom + args.seuil_dominance:
                    double_chance = "X2"
                else:
                    double_chance = "12"

                over_25 = analysis["over_25_prob"] > 0.6
                if league in gd.HIGH_SCORING_LEAGUES:
                    over_25 = over_25 or analysis["goals_avg"] > 2.8

                btts_prob = gd.analyze_btts(h2h_list)
                btts = btts_prob > 0.6

                combo = None
                if double_chance != "12" and btts:
                    combo = f"{double_chance} + BTTS"

                confiance = 50
                confiance += min(20, analysis["total_matches"] * 3)
                if max(home_dom, away_dom) > 0.7:
                    confiance += 10
                if home_form and away_form:
                    form_diff = abs(home_form["form_score"] - away_form["form_score"])
                    if form_diff > 0.2:
                        confiance += 5
                    if home_form["form_score"] > 0.7 and away_form["form_score"] < 0.4:
                        confiance += 5
                if analysis["draw_rate"] > 0.4:
                    confiance -= 10
                if league in gd.TRUSTED_LEAGUES:
                    confiance += 5
                else:
                    confiance -= 5
                confiance = max(0, min(100, confiance))

                return {
                    "double_chance": double_chance,
                    "over_25": over_25,
                    "btts": btts,
                    "btts_probability": round(btts_prob, 3),
                    "combo": combo,
                    "confidence": confiance
                }

            prediction = generate_prediction_local(analysis, home_form, away_form, competition, h2h_before)

            if not args.include_12 and prediction['double_chance'] == "12":
                stats['ignored_double_chance_12'] += 1
                if args.verbose:
                    print(f"   ⚠️ {home_team} vs {away_team} ignoré (double chance 12)")
                continue

            # Calcul du score et catégorie
            score = gd.calculate_xpronos_score(analysis, prediction, home_form, away_form, competition)
            category = gd.get_category(score, prediction, analysis)

            # Vérification du pronostic
            dc = prediction['double_chance']
            if dc == "1X":
                verified = (home_score > away_score) or (home_score == away_score)
            elif dc == "X2":
                verified = (home_score == away_score) or (home_score < away_score)
            else:  # "12"
                verified = (home_score > away_score) or (home_score < away_score)

            # Pour les VIP, si combo, vérifier aussi BTTS
            if category == 'vip' and prediction.get('combo'):
                verified_btts = (home_score > 0 and away_score > 0)
                verified = verified and verified_btts

            results[category]['total'] += 1
            if verified:
                results[category]['correct'] += 1
            stats['processed'] += 1
            if args.verbose:
                print(f"   {'✅' if verified else '❌'} {home_team} {home_score}-{away_score} {away_team} : {dc} -> cat {category}")

        current += timedelta(days=1)

    print("\n" + "="*60)
    print("📊 STATISTIQUES DE FILTRAGE")
    for k, v in stats.items():
        print(f"{k}: {v}")

    print("\n📊 RÉSULTATS GLOBAUX")
    for cat in ['simple', 'pro', 'vip']:
        total = results[cat]['total']
        correct = results[cat]['correct']
        pct = (correct / total * 100) if total > 0 else 0
        print(f"{cat.capitalize()}: {correct}/{total} ({pct:.1f}%)")
    total_all = sum(r['total'] for r in results.values())
    correct_all = sum(r['correct'] for r in results.values())
    pct_all = (correct_all / total_all * 100) if total_all > 0 else 0
    print(f"Total: {correct_all}/{total_all} ({pct_all:.1f}%)")
    print("="*60)

if __name__ == "__main__":
    main()