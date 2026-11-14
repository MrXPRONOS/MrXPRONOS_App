# Test des modèles NVIDIA — Mr XPRONOS

## 1. Configurer la clé

Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New repository secret**

- **Name** : `NVIDIA_API_KEY`
- **Secret** : votre clé API obtenue sur [build.nvidia.com](https://build.nvidia.com/)

Ne jamais placer la clé dans un fichier du dépôt, une URL ou un message.

## 2. Lancer les tests

Dans **Actions → NVIDIA - test all AI models → Run workflow** :

- `category=all` : tous les modèles recensés par l'API.
- `repeats=1` : premier contrôle peu coûteux ; augmenter à 3 pour mesurer une tendance.
- `limit=0` : pas de limite de modèles.
- `models` vide : discovery automatique via `GET https://integrate.api.nvidia.com/v1/models`.
- `models` peut contenir une liste d'identifiants exacts séparés par une virgule ; cette liste est testée même si certains IDs n'apparaissent plus au catalogue.

Un inventaire peut être incomplet pour les API spécialisées non exposées par ce point d'accès. Les modèles de type image, audio et vision spécialisée sont signalés **api_specialisee_non_testee**, et non déclarés en panne. Les classificateurs de capacité sont des heuristiques.

## 3. Lire les résultats

Ouvrir l'exécution du workflow ; les résultats apparaissent dans **Summary**. En bas de l'exécution, télécharger l'archive **rapport-modeles-nvidia-...** contenant :

- `rapport.md` : tableau ordonné des modèles qui répondent le plus vite.
- `results.csv` : statut, code HTTP, moyenne/min/max/médiane en secondes, tokens.
- `results.json` : mêmes données pour une exploitation par des scripts.

**Interprétation des erreurs :** `ok` = HTTP 200 et sortie non vide ; `reponse_vide` = HTTP 200 sans sortie exploitable ; `cle_invalide` = HTTP 401 ; `acces_refuse` = HTTP 403 ; `limite_atteinte` = HTTP 429 ; `introuvable` = HTTP 404 ; `timeout` = aucune réponse dans le délai alloué. Un HTTP 403 ne prouve pas que le modèle est arrêté : le compte peut simplement ne pas avoir l'autorisation.

Le temps rapporté est la **durée totale de la requête non-streaming**, pas le temps de premier token. Des tests consécutifs avec `repeats=3` permettent de comparer médianes et dispersion ; les réponses peuvent varier selon la charge et le quota. Les modèles ne sont pas classés par qualité de raisonnement : le test vérifie la capacité à répondre.

Le workflow est **manuel** et n'altère ni les pronostics, ni les données du site, ni les autres automatisations. Chaque lancement consomme éventuellement des crédits NVIDIA et, selon le nombre de modèles, peut prendre du temps. Les artefacts sont conservés 30 jours.

## 4. Test en local

```bash
python -m pip install requests
export NVIDIA_API_KEY="VOTRE_CLE" # Linux/macOS, seulement dans votre terminal privé
python scripts/test_nvidia_models.py --category chat --limit 5 --repeats 1
```

Pour évaluer tous les modèles du catalogue : `python scripts/test_nvidia_models.py --category all --limit 0`.

Le fichier est **un outil de diagnostic**, pas un système de remplacement automatique des modèles en production.
