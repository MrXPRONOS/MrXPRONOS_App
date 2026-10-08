# Nouveau moteur BSD — phase 1

**État : diagnostic uniquement.** SportData, `data.json`, Supabase, le site et Telegram restent inchangés.

## Configuration

Créer le secret GitHub Actions `BSD_API_KEY` via
**Settings → Secrets and variables → Actions → New repository secret**.

Ne jamais stocker la clé dans le dépôt, les logs ou une issue.

## Exécution sans effet sur la production

Actions → **BSD - Diagnostic (manuel)** → **Run workflow**.

La tâche lance d'abord les tests unitaires hors ligne, puis récupère
uniquement les fixtures d'une journée BSD (5 appels HTTP maximum par lancement).
Elle ne publie aucun coupon. Si la pagination n'est pas complète, le
diagnostic se termine avec un code non nul.

## Fichiers

- `bsd_api.py` : client BSD football v2 (clé, erreurs, pagination, cache, budget).
- `bsd_diagnostic.py` : contrôle des rencontres et du quota, sans écriture de pronostics.
- `test_bsd_api.py` : tests hors ligne.
- `cache/` : cache HTTP éphémère non versionné.

## Prochaines phases

1. Valider les schémas des fixtures avec une vraie clé BSD.
2. Construire un historique BSD séparé et des H2H en cache.
3. Tester le moteur BSD dans `bsd/data_bsd.json`, sans toucher à `data.json`.
4. Comparer la couverture, les pronostics et les taux d'échec.
5. Basculer manuellement site et Telegram lorsque la nouvelle chaîne est fiable.

Documentation : https://sports.bzzoiro.com/docs/football/events/
