# Actu Foot V1 — Routeur RSS multicanal

## Objectif

Un seul collecteur de nouvelles `fetch_foot_news.py` et un seul diffuseur
principal `scripts/actu_foot_d1_news.py`. Dix canaux secondaires reçoivent
**uniquement les articles dont la publication dans le canal principal est
confirmée dans Cloudflare D1**. Les actualités restent tirées des résumés RSS
réels, sans recopier des articles complets provenant de sites externes.

## Destinations — 11 canaux

| Rôle | Ligne éditoriale |
|---|---|
| Principal, `@actufoot_mrxp` | Toutes les actualités RSS sélectionnées, format existant inchangé |
| `flash` | Annonces urgentes et annonces officielles importantes |
| `mercato` | Transferts, prêts, contrats, signatures, négociations |
| `champions` | UEFA Champions League |
| `premier` | Premier League et clubs anglais |
| `liga` | La Liga et clubs espagnols |
| `ligue1` | Ligue 1 et clubs français |
| `africa` | CAN, CAF, clubs et sélections africains |
| `national` | Sélections nationales et compétitions internationales |
| `scores` | Nouvelles RSS sur scores, résultats, programmes et classements (PAS encore le live ESPN V1.1) |
| `debrief` | Analyses et comptes rendus sourcés après-match |

Le routeur attribue plusieurs rôles à une même information. Les identifiants
publics viennent du dossier Telegram personnel « Actu Foot » et sont vérifiés
par `scripts/actufoot_v1_discover.py`. Le bot de publication
`FOOTBALL_NEWS_BOT_TOKEN` doit être administrateur et pouvoir publier dans
les dix nouveaux canaux.

## Fréquence, quotas et sécurité

- Workflow RSS `.github/workflows/update-footnews.yml` à **07 et 37 minutes
  de chaque heure** (configuration GitHub, exécution réelle à surveiller).
- Principal **inchangé** : deux nouvelles par cycle, maximum 24/jour, D1
  `actu_foot_flash_v2`.
- Nouveaux canaux : jusqu'à deux articles pertinents par cycle **par canal**,
  maximum 24/jour par canal. Aucun post si aucun sujet admissible.
- Aucun article vieux de plus de 24 heures dans les canaux spécialisés.
- D1 atomique : `actu_foot_multichannel_v1_article`,
  `actu_foot_multichannel_v1_halfhour`,
  `actu_foot_multichannel_v1_daily`. Les destinataires ne partagent jamais
  leurs clés de déduplication.
- Une preuve du canal principal `delivery_status='sent'` est obligatoire
  pour chaque article secondaire. Aucune diffusion si le canal principal
  est absent, non conforme ou si l'article est seulement « reserved ».
- Identité des canaux et droit `can_post_messages` vérifiés par
  `getChat` et `getChatMember`; toute destination inconnue est exclue.
- Erreur de publication après réservation : réserve conservée,
  **aucune répétition aveugle** (même en cas de délai d'attente réseau).
  Les autres canaux peuvent continuer.
- La diffusion reste désactivée (`enabled:false`) jusqu'à confirmation
  des dix vrais @usernames par l'audit Telegram et validation du mode test.

## Format des messages

Identique au canal principal : **titre en gras**, texte français intégralement
issu du RSS (rédigé/vérifié par le système), paragraphes espacés, **catégorie
et source en italique**. Aucun hyperlien, aucun bouton, aucune URL visible,
aucun message publicitaire ajouté. La source est indiquée uniquement par son
nom : `Source : Foot Mercato`, `Source : RFI`, etc. Les images sources sont
réutilisées lorsqu'elles ont passé les contrôles du collecteur ; les visuels
génériques autorisés restent soumis au seuil éditorial.

## Tester

```sh
python -m unittest discover -s tests_football_channel -p test_actufoot_v1_router.py -v
python -m unittest discover -s tests_football_channel -p test_actufoot_v1_discover.py -v
python scripts/actufoot_v1_router.py --news telegram_out/actu_foot_source_news.json --dry-run
```

Le test complet est effectué par le workflow RSS et la CI football.
Une exécution réussie confirme le **logiciel**, pas à elle seule le débit
de publications du canal. Vérifier le résumé `ACTUFOOT_V1_ROUTER` et les
compteurs par rôle sur plusieurs cycles, puis le contenu des canaux.

## Prochaines versions (hors V1)

V1.1 : brancher les signaux ESPN et les statistiques live ; V1.2 : débriefs
enrichis et classements avancés ; V1.3 : tableau de supervision et alertes
par canal.
