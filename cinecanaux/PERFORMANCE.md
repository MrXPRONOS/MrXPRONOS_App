# Ciné Radar — mesure et optimisation des temps de réponse

Date : 22 octobre 2026. Route de production : https://cinecanaux-bot.cinecanaux-xpronos.workers.dev

## Méthode

`node cinecanaux/tests/latency-benchmark.mjs` sur GitHub Actions (Node 22) : 10 requêtes GET **séquentielles** par route, réponse entièrement reçue, 50 ms de repos entre les requêtes. Statistiques P50 et P90 sur les 10 observations. Mesure externe depuis un runner GitHub, **pas** depuis le réseau mobile togolais. Les jobs indépendants peuvent utiliser des routes réseau ou emplacements différents : ce n'est pas un benchmark A/B réseau contrôlé.

- [Avant, exécution 39785231557](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39785231557)
- [Après première optimisation, exécution 39786413149](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39786413149)
- [Après toutes les optimisations, exécution 39787046853](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39787046853)

| Route | Avant P50 / P90 (ms) | Final P50 / P90 (ms) |
|---|---:|---:|
| `/health` | 129,2 / 140,2 | 108,3 / 123,3 |
| `/app` | 16,7 / 44,2 | 19,6 / 36,3 |
| `/api/catalog` | 13,5 / 39,1 | 18,1 / 35,4 |
| `/api/catalog?type=films` | 13,9 / 19,7 | 17,8 / 19,0 |
| `/api/catalog?type=series` | 14,3 / 21,6 | 15,9 / 16,5 |
| `/api/catalog?type=animes` | 15,7 / 24,4 | 18,0 / 18,4 |
| `/api/channel-preview?id=1` | 100,8 / 110,7 | **18,7 / 20,6** |

**Important :** les chiffres ne mesurent pas le temps de rendu intégral ni l'ouverture d'un canal dans l'application Telegram. Les petites différences (< 10 ms) peuvent provenir du réseau différent des runners.

## Optimisations déployées

1. Mini App : HTML accompagné du catalogue public, échappement des titres pour éviter toute injection HTML/JS. Les canaux sont affichés sans attente d'une deuxième requête réseau ; API de repli disponible en cas d'erreur D1.
2. SDK Telegram externe en `defer` pour ne plus bloquer l'analyse initiale du HTML. API Telegram détectée à la demande.
3. Filtres et recherche locale, cache mémoire du catalogue des 12 canaux : aucune requête à chaque sélection.
4. Page d'aperçu ouverte immédiatement, sans attendre Telegram ; photos chargées progressivement.
5. Un seul `LEFT JOIN` D1 par cache d'aperçu au lieu de deux lectures séquentielles.
6. Cache mémoire en Worker pour les aperçus : 30 secondes, maximum 100 références publiques, déduplication des requêtes simultanées. Le cache ne stocke ni utilisateurs, ni historique de navigation.
7. Lecture groupée du statut du webhook et du nombre de canaux pour `/health`.
8. Les secrets du bot et les tâches programmées de découverte et de santé des liens sont préservés.

## Reproduire

```bash
BENCH_SAMPLES=10 BENCH_VERSION=repeat node cinecanaux/tests/latency-benchmark.mjs
```

Suivre le test de production `.github/workflows/cine-radar-live-smoke.yml` et les tests Node `.github/workflows/cine-radar-v2-ci.yml`.

**Suivi recommandé :** mesurer sur un vrai téléphone et réseau 4G à Lomé le délai de première ouverture, le clic sur une catégorie et l'affichage des photos. Les médianes depuis GitHub ne suffisent pas pour garantir la fluidité perçue.
