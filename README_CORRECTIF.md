# Correctif SportData — Mr XPRONOS

## Diagnostic

Les logs ne montrent pas une erreur Python. Ils montrent un faux succès :

- HTTP 200 est accepté immédiatement ;
- le code lit seulement `response.json().get("games", [])` ;
- une réponse d'erreur métier ou un JSON au schéma inattendu devient donc `0 match` ;
- `continue-on-error: true` permet ensuite au workflow de publier malgré l'échec ;
- `generate_data.py` peut finir par maintenir ou produire un `data.json` vide.

Le format de date `DD/MM/YYYY` était déjà correct.

## Fichiers à remplacer/ajouter

Ajoute :

- `sportdata_api.py`
- `sportdata_diagnostic.py`

Remplace :

- `generate_data.py`
- `update_historical.py`
- `update_scores.py`
- `allmatches.py`
- `content_generator.py`
- `.github/workflows/daily-update.yml`

Le fichier `api_utils.py` peut rester en place pour les autres scripts.

## Ce que fait le correctif

1. Utilise d'abord l'URL canonique :
   `https://api.sportsapipro.com/v1/football/games/allscores`
2. Garde l'ancien sous-domaine en secours.
3. Vérifie chaque clé sans l'afficher.
4. Continue la rotation si HTTP 200 contient une erreur métier.
5. Vérifie que le JSON possède réellement le schéma `allscores`.
6. Refuse de réécrire `data.json` lorsque les trois journées renvoient zéro match.
7. Arrête le workflow si la source critique est invalide.
8. Télécharge l'historique par plages de trois jours au lieu de mois entiers.

## Installation

Copie les fichiers à la racine du dépôt, en conservant le chemin du workflow, puis :

```bash
git add .
git commit -m "Fix SportData empty responses"
git push
```

Lance ensuite manuellement **Daily Update** dans GitHub Actions.

## Résultat attendu dans les logs

```text
[SportData status] clé #1 | ok=True | HTTP=200 | ...
[SportData] réponse valide: 123 match(s), clé #1, hôte=https://api...
OK: ... matchs reçus sur les trois journées.
```

Si le diagnostic affiche `remaining_today=0`, la clé a atteint son quota.
Si toutes les clés affichent `ok=False`, il faut renouveler/corriger les secrets.
