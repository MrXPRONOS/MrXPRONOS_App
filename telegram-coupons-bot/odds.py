"""Calcul reproductible des cotes de coupons, sans produire de pronostics."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MIN_TOTAL_ODDS = Decimal('4.00')
MAX_SELECTIONS = 10


def normalize_selections(selections):
    """Une sélection: {'match': ..., 'market': ..., 'odd': '1.70'}.

    Les cotes sont décimales (non américaines); la chaîne affichée est arrondie à
    deux décimales comme l'entrée, et seul l'administrateur apporte les données.
    """
    if not isinstance(selections, list) or not 1 <= len(selections) <= MAX_SELECTIONS:
        raise ValueError('Entre 1 et 10 sélections requises.')
    normalized = []
    for entry in selections:
        if not isinstance(entry, dict):
            raise ValueError('Sélection invalide.')
        match = str(entry.get('match', '')).strip()
        market = str(entry.get('market', '')).strip()
        if not 3 <= len(match) <= 120 or not 3 <= len(market) <= 120:
            raise ValueError('Chaque match et marché doit contenir de 3 à 120 caractères.')
        raw = str(entry.get('odd', '')).strip().replace(',', '.')
        try:
            odd = Decimal(raw)
        except (InvalidOperation, ValueError):
            raise ValueError('Cote décimale invalide.') from None
        if not odd.is_finite() or odd < Decimal('1.01') or odd > 100 or odd.as_tuple().exponent < -2:
            raise ValueError('Cote requise entre 1.01 et 100, avec au plus 2 décimales.')
        normalized.append({'match': match, 'market': market, 'odd': f'{odd:.2f}'})
    return normalized


def _raw_total_odds(normalized):
    total = Decimal('1')
    for entry in normalized:
        total *= Decimal(entry['odd'])
    return total


def calculate_total_odds(selections):
    normalized = normalize_selections(selections)
    return _raw_total_odds(normalized).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def assert_minimum_odds(selections):
    normalized = normalize_selections(selections)
    exact = _raw_total_odds(normalized)
    # La vérification s'effectue AVANT l'arrondi destiné à l'affichage.
    if exact < MIN_TOTAL_ODDS:
        raise ValueError(f'Cote totale insuffisante : {exact}. Minimum : 4.00.')
    return exact.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def format_coupon(coupon):
    import json
    selections = json.loads(coupon['selections_json'])
    lines = [f'🎟️ {coupon["title"]}', f'🏷️ Catégorie : {coupon["category"]}',
             f'📈 Cote totale indicative : {coupon["total_odds"]}']
    for i, s in enumerate(selections, 1):
        lines.append(f'\n{i}. ⚽ {s["match"]}\n🎯 {s["market"]}\n📊 Cote : {s["odd"]}')
    lines.append('\n⚠️ Cotes indicatives à vérifier chez le bookmaker avant toute mise. '
                 'Aucun résultat garanti. 18+ • Pari responsable.')
    return '\n'.join(lines)
