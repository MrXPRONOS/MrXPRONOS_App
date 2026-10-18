# Actu Crypto — automatisation du lot 1 à 5

## Rubriques incluses

1. Cours BTC, ETH, SOL, BNB, XRP (prix USD, variation 24h).
2. Top 5 hausses parmi les 100 premières capitalisations, avec volume 24h >= 1 million USD.
3. Top 5 baisses dans le même univers.
4. Alertes par paliers de variation **24h** +/-5 %, +/-10 %, etc. avec état.
5. Indice Crypto Fear & Greed quotidien.

Le module n'utilise ni flux RSS ni IA payante : ces cinq rubriques nécessitent des API **numériques** et non des articles. Les RSS serviront aux lots de nouvelles et analyses.

## Sources publiques utilisées

- Primaire : [CoinPaprika REST API](https://api.coinpaprika.com/), `/v1/tickers?quotes=USD`. Plan gratuit soumis aux limites publiées par le fournisseur.
- Repli 1 : [CoinLore](https://www.coinlore.com/cryptocurrency-data-api), `/api/tickers/?start=0&limit=100`, sans clé.
- Repli 2 optionnel : [CoinGecko Demo API](https://docs.coingecko.com/), nécessite sa clé gratuite `COINGECKO_DEMO_API_KEY`.
- Sentiment : [Alternative.me](https://alternative.me/crypto/fear-and-greed-index/), `/fng/?limit=1&format=json`, sans clé.

Aucune ressource n'est garantie sans interruption : si les données sont indisponibles ou non valides, publication annulée plutôt qu'inventée. Les fournisseurs peuvent faire évoluer leurs plans.

## Secrets GitHub à configurer

GitHub > dépôt > Settings > Secrets and variables > Actions > New repository secret :

| Nom | Usage |
|---|---|
| `ACTU_CRYPTO_CHAT_ID` | **Obligatoire** : identifiant du canal crypto, par exemple `@NomDuCanalCrypto`, différent d'Actu Foot. Ajouter le bot en administrateur avec droit de publier. |
| `TELEGRAM_ACTU_FOOT_BOT_TOKEN` | **Optionnel si déjà connu** : token du bot Actu Foot existant. Ne créer AUCUN nouveau bot. Le script accepte aussi `ACTU_FOOT_BOT_TOKEN` puis `TELEGRAM_BOT_TOKEN` de ton dépôt. |
| `COINGECKO_DEMO_API_KEY` | Optionnel : clé Demo gratuite CoinGecko pour le 3e fournisseur de secours. |

Les secrets restent dans GitHub Actions. **Ne jamais écrire un token dans un fichier versionné.**

## Validation

Depuis Actions > **Actu Crypto - publications 1 a 5** > Run workflow :
1. Choisir `mode=all` et `dry_run=true` (par défaut). Vérifier les logs et les sources.
2. Faire le test réel avec `mode=prices` et `dry_run=false` après avoir configuré le bot et le canal.
3. Fusionner la branche dans `main` lorsque le test est satisfaisant : les tâches planifiées ne se déclenchent que sur la branche par défaut.

Horaires UTC / Lomé prévus : 07h07 (toutes rubriques), 12h17 (tops), 18h23 (prix), 08h41, 10h41, ... 22h41 (alertes). GitHub Actions peut être en retard ou manquer un lancement lors de forte charge. Cron-job.org peut être ajouté plus tard en **remplacement**, pas en parallèle, pour éviter les doubles exécutions.

Le workflow committe `crypto/telegram_state.json` à chaque modification de l'état pour limiter les doublons entre exécutions. Supabase permettrait plus tard un état transactionnel, plus robuste sur plusieurs runners. La confirmation d'envoi Telegram et le commit GitHub ne sont pas une transaction atomique : en cas d'échec GitHub après publication, un doublon reste possible. Aucune garantie d'instantanéité.

## Commande locale

```bash
pip install requests
python crypto/publish_crypto_1_5.py --mode all --dry-run
```

## Consignes permanentes pour les prochains lots

- Réaliser **exactement cinq rubriques à la fois**, avec recherche indépendante des meilleures sources API/RSS gratuites et de leurs limites.
- Favoriser plusieurs sources complémentaires et repli, ne jamais inventer de données.
- Réutiliser le **bot Actu Foot**, mais publier vers un **canal Actu Crypto distinct**.
- Garder tout **gratuit**, isoler les secrets dans GitHub et indiquer ceux à créer.
- Intégrer le code directement dans le dépôt, vérifier syntaxe/logique, contrôler doublons et horaires.
- Ne pas modifier les pipelines critiques Mr XPRONOS lors des lots crypto.
