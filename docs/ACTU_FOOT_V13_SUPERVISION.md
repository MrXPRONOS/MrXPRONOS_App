# Actu Foot V1.3 — supervision et alertes des 10 canaux

## Objet et périmètre

V1.3 ajoute une supervision indépendante de **11 destinations** : le canal principal
`@actufoot_mrxp` (identité et sécurité) et les dix canaux spécialisés (tableaux par
rôle). Elle ne modifie ni la publication RSS V1, ni le LIVE ESPN V1.1, ni les
débriefs/classements V1.2. L'audit n'écrit jamais de faux événements et ne
relance jamais les réservations Telegram incertaines.

## Indicateurs et sécurité

- Validation en direct de l'identité du bot, du canal principal, de chaque
  destination Telegram et de son droit de publication, via la vérification V1.
- Une requête agrégée **en lecture seule** à la base D1 existante, sur les
  journées courante et précédente (heure Africa/Lome).
- Par canal : publications RSS V1, événements LIVE V1.1, débriefs/classements
  V1.2, états des réservations, derniers envois confirmés, quotas de chaque
  filière, permissions et niveau de santé.
- Alertes : droits perdus, réservations en attente de plus de 15 minutes,
  envois incertains, rejets Telegram, erreurs enregistrées, quotas à 90 %
  ou saturés. Une absence de publication n'est **pas** considérée comme une
  panne : elle peut simplement correspondre à une absence d'actualité qualifiée.
- Les quotas sont distincts : RSS 24/jour/canal ; LIVE 20/jour/canal sauf Scores
  (48/jour). Ces seuils reflètent les compteurs D1 de V1/V1.1.
- Aucun identifiant interne, contenu d'article, token, URL d'API contenant des
  secrets ou texte de message football dans le rapport.
- Les alertes privées, facultatives, passent par un chat **numérique** défini
  uniquement dans le secret GitHub `ACTUFOOT_V13_ALERT_CHAT_ID`.
  Le système ne publie jamais une alerte dans les canaux d'actualités.
- Les notifications sont dédupliquées via une réservation D1 atomique par jour
  et empreinte d'alertes. Une réponse Telegram incertaine est conservée en
  quarantaine, jamais renvoyée automatiquement.

## Fichiers livrés

- `scripts/actufoot_v13_supervision.py` : collecte, alertes, rapport Markdown,
  JSON et éventuelle notification privée.
- `tests_football_channel/test_actufoot_v13_supervision.py` : tests isolés
  des indicateurs, droits, quotas, validation, absence de fausse panne,
  déduplication et incertitude réseau.
- `.github/workflows/actufoot-v13-supervision.yml` : tests PR/push,
  surveillance réelle deux fois par heure (H:07 et H:37 UTC, identique à Lomé),
  rapport GitHub Actions et artefact JSON conservé 14 jours.

## Mise en service / contrôle

1. Fusionner seulement si les tests de PR passent.
2. Les secrets existants `FOOTBALL_NEWS_BOT_TOKEN`,
   `FOOTBALL_NEWS_CHAT_ID` et `CLOUDFLARE_API_TOKEN` sont nécessaires au
   contrôle réel. Le moteur doit déclarer un échec s'ils sont absents, pas une
   supervision fictivement « verte ».
3. Optionnel : créer `ACTUFOOT_V13_ALERT_CHAT_ID` avec un identifiant numérique
   du chat privé autorisé à recevoir les alertes ; l'envoi programmé est
   activé uniquement si ce secret existe. Sans lui, les annotations et
   rapports GitHub Actions restent fonctionnels.
4. Exécuter le workflow manuellement en mode `dry_run=true` : ce mode
   effectue la **lecture réelle** de D1/Telegram sans envoyer d'alerte.
5. Contrôler le rapport par canal, les rôles vérifiés (10/10), la situation
   des réservations et les erreurs, puis une exécution programmée réelle.
6. Pour confirmer l'envoi privé, tester seulement dans le chat privé
   configuré, avec `dry_run=false` et `send_alerts=true` ; aucun envoi
   n'est effectué s'il n'y a pas d'alerte réelle. Ne pas créer de fausse
   panne dans les canaux publics.

## Limites de preuve

Un test unitaire réussi prouve la logique de calcul ; pas la disponibilité
réelle de D1/Telegram. Un workflow sans article publié n'est pas une panne.
La lecture du ledger ne garantit pas que tous les messages sont encore
visibles dans Telegram (suppression manuelle possible).
V1.3 ne doit être déclarée **opérationnelle en production** qu'après vérification
d'une exécution du workflow avec accès réel et 10/10 permissions. Les alertes
privées ne sont opérationnelles que si le chat secret est configuré et un
envoi réel a été confirmé. Les autres limites de validation V1/V1.1/V1.2
restent indépendantes.
