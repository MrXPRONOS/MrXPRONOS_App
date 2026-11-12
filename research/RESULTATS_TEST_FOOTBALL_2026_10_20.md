# Mr XPRONOS — test rétrospectif du mardi 20 octobre 2026

**Exécution GitHub Actions validée :** https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39522118027

**Source des scores finaux :** SportsAPI Pro, `/v1/football/games/allscores`; 440 rencontres renvoyées TOUTES DISCIPLINES CONFONDUES, dont 210 identifiées explicitement `sportId=1` (football), 187 avec score final valide et `statusGroup=4`. Exclusion explicite des sports différents.

**Historique d'entraînement :** 11 332 rencontres antérieures au 20 octobre, parmi 97 libellés de compétitions reconnus comme football par les métadonnées du fournisseur le 20 octobre. L'ancien `cache/all_matches.json` ne conserve pas `sportId` ; ces données historiques filtrées sont un **sous-ensemble conservateur**, pas une archive sportive complètement certifiée. Aucun résultat du 20 octobre n'a été injecté dans l'entraînement.

**Nature du test :** les scores ont été recalculés APRÈS les rencontres, en respectant la coupure temporelle du 19 octobre. Pas de prétention à une publication réelle avant match ; pas de ROI prouvé.

## Méthodes individuelles, 187 matchs

| Modèle | Scores exacts corrects | Taux |
|---|---:|---:|
| Machine Learning | 21 | 11,230 % |
| Dixon-Coles | 19 | 10,160 % |
| Poisson | 18 | 9,626 % |
| Poisson bivariée | 18 | 9,626 % |
| Monte-Carlo | 15 | 8,021 % |
| Bayésien Gamma | 14 | 7,487 % |

## Six votes, score unique retenu seulement si accord requis

| Consensus minimum | Matchs retenus | Bons scores | Taux | Non retenus |
|---|---:|---:|---:|---:|
| ≥3/6 | 182 | 18 | 9,890 % | 5 |
| ≥4/6 | 164 | 16 | 9,756 % | 23 |
| ≥5/6 | 125 | 12 | 9,600 % | 62 |
| 6/6 | 64 | 3 | 4,688 % | 123 |

### Ligue des champions, neuf rencontres du 20 octobre

| Match | Pronostic majoritaire (score) | Votes | Décision au seuil 5/6 | Résultat réel |
|---|---|---:|---|---|
| Roma – Slovan Bratislava | 2-1 | 5/6 | retenu, faux | 4-0 |
| Porto – PSV Eindhoven | 1-1 | 6/6 | retenu, faux | 0-1 |
| Fenerbahçe – Slavia Praha | 1-1 | 4/6 | refusé | 2-2 |
| Liverpool – Villarreal | 1-1 | 4/6 | refusé | 4-3 |
| Manchester City – AEK Athens | égalité de votes, **abstention** | 3-3 | refusé | 5-1 |
| Napoli – Bodø/Glimt | 1-1 | 4/6 | refusé | 4-3 |
| PSG – FC Barcelona | 2-1 | 5/6 | retenu, faux | 4-2 |
| Sabah – Borussia Dortmund | 1-1 | 4/6 | refusé | 1-2 |
| Stuttgart – Atlético de Madrid | 1-1 | 4/6 | refusé (4 modèles ont raison) | 1-1 |

**Au seuil 5/6 : 3 matchs UCL retenus, 0 score exact sur ces 3.**
**Au seuil 4/6 : 8 matchs retenus, 1 score exact sur 8.**

### Trois exemples de réussites à l'unanimité (6/6)
- Gillingham – Port Vale : 1-1 pronostiqué, 1-1 réalisé.
- Yate Town – Sholing : 1-1 pronostiqué, 1-1 réalisé.
- Manchester City U19 – AEK U19 : 1-1 pronostiqué, 1-1 réalisé.

## Avertissement sur les backtests 2026 précédemment rapportés

L'endpoint dit «football» mélange tennis, volley et football. Les anciennes archives ne gardent pas `sportId`; **les 81 154 rencontres des analyses précédentes ne sont donc pas une population football garantie**. Le test présent a corrigé les rencontres cibles en filtrant explicitement `sportId=1`. Un backtest annuel de football certifié doit être recalculé sur des archives incluant `sportId` à chaque match, avant de retenir un seuil définitif. Même ici, certaines ambiguïtés de ligue historiques subsistent.

Le moteur combiné et ces tests sont sur une branche de recherche, non fusionnée dans la production.
