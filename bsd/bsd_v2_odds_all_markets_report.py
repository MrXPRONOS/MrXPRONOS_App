"""Render all-25-markets odds quality audit to complete CSV + human report."""
import argparse,csv,json
from pathlib import Path

PAIR_FIELDS=[
 'event_id','kickoff','home_team','away_team','market_key','market_code',
 'family','model_status','model_pricing_method','model_probability',
 'model_price','external_price','provider','source','bookmaker',
 'absolute_difference','relative_difference_pct','abs_relative_pct',
 'implied_prob_model_pct','implied_prob_external_pct',
 'implied_probability_difference_points',
 'external_updated_at','external_captured_at','timestamp_type',
 'external_no_vig_probability_pct','external_market_overround_pct',
 'model_probability_pct','no_vig_probability_gap_pp','no_vig_unavailable_reason']
MARKET_FIELDS=[
 'event_id','kickoff','home_team','away_team','league','key','family','market_code',
 'probability','raw_probability','refund_probability','indicative_odds',
 'pricing_status','odds_method','model_status','native_site_price_allowed',
 'provider','external_status','external_odds','difference','relative_pct',
 'bookmaker','updated_at']
def pct(p):
    return '—' if p is None else str(p)+' %'
def val(n):
    return '—' if n is None else str(n)
def create_markdown(r):
    c=r['coverage']
    lines=[
      '# Audit des cotes indicatives — 25 marchés par match',
      '',
      'Observation UTC : **'+str(r.get('captured_at'))+'**.',
      '',
      'Tous les matchs à venir de la fenêtre sont examinés, indépendamment du',
      'marché que BSD V2 aurait retenu pour publication.',
      '',
      '**Plage de probabilité du calcul indicatif : 0,10 ≤ p ≤ 0,99**',
      '(soit de 10 % à 99 %, bornes incluses). Les probabilités en dehors',
      'de cette plage restent enregistrées sans cote indicative de recherche.',
      '',
      '## Périmètre',
      '',
      '| Élément | Nombre |',
      '|---|---:|',
      '| Rencontres futures dans la fenêtre | '+val(c.get('fixture_candidates_in_horizon'))+' |',
      '| Rencontres prises en compte | '+val(c.get('fixtures_scanned'))+' |',
      '| Rencontre × marché examinés | '+val(c.get('market_observations'))+' |',
      '| Probabilités et cotes modèle disponibles | '+val(c.get('model_price_available'))+' |',
      '| Paires avec une cote externe valide | '+val(c.get('valid_pairs'))+' |',
      '| Probabilités hors plage 10 %–99 % | '+val(c.get('outside_research_probability_range'))+' |',
      '| Paires avec probabilité externe corrigée de marge | '+val(c.get('pairs_with_fair_external_probability'))+' |',
      '| Rencontres avec au moins une paire | '+val(c.get('fixtures_with_at_least_one_pair'))+' |',
      '| Marchés/rencontres sans adaptateur externe existant | '+val(c.get('market_codes_without_existing_provider_adapter'))+' |',
      '',
      '**Couverture tronquée par limite configurée :** '+('oui' if c.get('truncated_due_to_max_fixtures') else 'non')+'.',
      '',
      '## Résultats par marché (y compris les marchés sans cote externe)',
      '',
      '| Marché | Observations | Cote indicative disponible | Paires externes | Écart médian absolu | Écart médian relatif |',
      '|---|---:|---:|---:|---:|---:|',
    ]
    for key,info in r['by_market'].items():
        m=info['comparison']
        lines.append('| '+key+' | '+val(info['observations'])+' | '+
           val(info['with_model_price'])+' | '+val(m['n'])+' | '+
           val(m['median_abs_price_delta'])+' | '+pct(m['median_abs_relative_pct'])+' |')
    n=r.get('no_vig_summary') or {}
    lines+=['',
        '## Comparaison des probabilités après retrait de la marge',
        '',
        'Paires avec des issues complémentaires complètes chez la même source : **'+str(n.get('pairs_with_complete_market',0))+'**.',
        'Écart absolu moyen des probabilités : **'+val(n.get('mean_absolute_probability_gap_pp'))+' points**.',
        '',
        'Seuls 1X2, BTTS et Over/Under sont normalisés quand toutes leurs issues sont présentes.',
        'Aucun retrait de marge n’est inventé pour un marché isolé ou plusieurs bookmakers mélangés.',
        '',
        '## Résultats par fournisseur','','| Fournisseur | Paires | Écart moyen | Écart médian absolu |',
            '|---|---:|---:|---:|']
    for source,info in r['by_source'].items():
        m=info['comparison']
        lines.append('| '+source+' | '+val(m['n'])+' | '+
            val(m['mean_price_delta'])+' | '+val(m['median_abs_price_delta'])+' |')
    lines+=['','## Signification du contrôle','','Une cote indicative calculée par le modèle et une cote',
            'externe ne sont comparables que si elles concernent le même match,',
            'la même issue et le même temps de jeu. Une différence ne prouve',
            '**ni une erreur de notre modèle ni une opportunité rentable** :',
            'la probabilité implicite externe inclut généralement une marge.',
            '',
            'Les marchés sans adaptateur externe restent dans le rapport.',
            'Les marchés dont la probabilité ne peut être calculée (notamment',
            'une mi-temps sans historique mi-temps entraîné) restent signalés.',
            'Le Draw No Bet est une estimation expérimentale tenant compte',
            'du remboursement sur match nul.',
            '',
            'Les cotes de diagnostic inférieures à **1,20** ne constituent',
            'pas des cotes autorisées à publication par le site.',
            'Une vérification supplémentaire sur les résultats après les',
            'matchs sera nécessaire pour mesurer calibration et score de Brier.',
            '','## Fichiers associés',
            '','- Comparaisons exactes : `odds_all_markets_external_pairs.csv`.',
            '- Toutes les observations y compris sans fournisseurs : `odds_all_markets_external_observations.csv`.',
            '- Informations et motifs détaillés : `odds_all_markets_external_report.json`.',
            '']
    return '\n'.join(lines)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='bsd/odds_all_markets_external_report.json')
    ap.add_argument('--md',default='bsd/odds_all_markets_external_resume.md')
    ap.add_argument('--pairs-csv',default='bsd/odds_all_markets_external_pairs.csv')
    ap.add_argument('--observations-csv',default='bsd/odds_all_markets_external_observations.csv')
    a=ap.parse_args()
    r=json.loads(Path(a.input).read_text(encoding='utf8'))
    Path(a.md).write_text(create_markdown(r),encoding='utf8')
    with open(a.pairs_csv,'w',encoding='utf8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=PAIR_FIELDS,extrasaction='ignore')
        writer.writeheader();writer.writerows(r['pairs'])
    with open(a.observations_csv,'w',encoding='utf8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=MARKET_FIELDS,extrasaction='ignore')
        writer.writeheader()
        for m in r['market_observations']:
            for provider,obs in m['provider_results'].items():
                writer.writerow({**m,'provider':provider,'external_status':obs['status'],
                   'external_odds':obs.get('external_odds'),
                   'difference':obs.get('difference'),'relative_pct':obs.get('relative_pct'),
                   'bookmaker':obs.get('bookmaker'),'updated_at':obs.get('updated_at')})
    print('BSD_V2_ALL_MARKETS_FILES',json.dumps({'pair_count':len(r['pairs']),
       'market_observations':len(r['market_observations']),
       'sources':list(r['by_source'])}))
if __name__=='__main__':main()
