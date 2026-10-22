# Free Pronos V3 — réception des améliorations

**Date de contrôle : 22 octobre 2026 (UTC).** Nom public : **Free Pronos**. Bot : `@FreePronos_mrxp_bot`. Worker : `xpronos-coupons-bot`.

## Faits vérifiés

- GitHub : tests Node, Python/SQLite et compilation Wrangler validés sur les changements V3 (PR #204, #206).
- Cloudflare : Worker et Mini App répondent HTTP 200, API privée non authentifiée répond HTTP 401.
- Administration : `/api/admin/overview` a répondu HTTP 200 avec une session Telegram signée, sans désactiver le contrôle HMAC ni la liste des administrateurs. Correction du test et de l'en-tête : PR #205 à #207.
- Source sportive : `/api/admin/provider-check` a répondu HTTP 200, état `reachable`, pour le flux ESPN football. Attention : API de scores ESPN publique **non officielle**, susceptible de changer.
- Telegram : `setMyProfilePhoto` a accepté le nouveau profil Free Pronos ; un vrai `sendMessage` de notification à l’administrateur a réussi (ID de message 65).
- Cloudflare D1 : migrations **4**, tables de métadonnées et de suivi de livraison présentes ; **1 utilisateur** conservé, **0 coupon** et **0 envoi historisé en D1** au dernier contrôle.
- Cron des alertes actif : `*/10 * * * *` (UTC), avec préférences opt-in.

## Design : les 8 améliorations demandées

| Amélioration | État V3 | Vérification et limite |
|---|---|---|
| Identité visuelle, avatar, bannière | **Appliqué** | Emblème SVG bleu nuit/orange servi par le Worker et photo officielle Telegram installée, logo sur l'accueil Mini App |
| Menu interactif | **Appliqué** | Clavier Telegram, navigation inline et Mini App |
| Cartes des coupons enrichies | **Appliqué pour les nouveaux coupons ESPN** | Compétition, équipes et écussons vérifiés lors de leur création ; les anciens coupons sans ID n'ont pas de rapprochement automatique fiable |
| Portefeuille XP visuel | **Appliqué** | Solde, XP cumulés et progression de niveau |
| Textes hiérarchisés | **Appliqué** | HTML Telegram : gras, italique et citations |
| Couleurs cohérentes | **Appliqué** | Boutons Telegram primary/success/danger et thème bleu/orange Mini App |
| Notifications visuelles | **Appliqué techniquement et test d'envoi réel réussi** | L'envoi à l'administrateur a été confirmé ; aucun coupon réel n'a encore déclenché un envoi à un abonné opt-in |
| Profil Telegram professionnel | **Appliqué** | Nom, descriptions, commandes, menu Mini App et photo de profil |

## Fonctionnalités : les 10 améliorations demandées

| Amélioration | État V3 | Vérification et limite |
|---|---|---|
| Tableau de bord personnel | **Appliqué** | API authentifiée, tests et Mini App |
| Historique XP | **Appliqué** | Journal D1 et consultation personnelle |
| Notifications de coupons | **Appliqué** | Préférences consenties, cron, envoi Telegram réel de test, suivi par ID ; pas de coupon en production à notifier à ce jour |
| Résultats sportifs | **Partiellement automatisé selon les marchés** | ESPN contactable ; 1X2, plus/moins de buts 1,5/2,5 et BTTS sur score final validé. Corners, cartons et autres marchés non couverts exigent une source spécialisée ou une validation humaine. Aucun résultat réel d'un coupon V3 n'a encore été liquidé en production |
| Missions quotidiennes/hebdomadaires | **Appliqué** | D1, contraintes d'unicité et tests |
| Niveaux fidélité | **Appliqué** | Débutant, Amateur, Expert, Légende selon XP cumulés |
| Parrainage enrichi | **Appliqué** | Liens, messages autonomes et états des filleuls |
| Filtres coupons | **Appliqué** | SIMPLE/PRO/VIP, coût XP, expiration, Mini App |
| Centre d'aide | **Appliqué** | Tickets, suivi, réponses admin, formulaire Mini App ; échange réel utilisateur-admin encore à exercer |
| Administration graphique | **Appliqué** | Publication ESPN vérifiée, contrôle des résultats avec source, tickets, indicateurs, alertes ; accès avec session signée validé HTTP 200 |

## Conditions de sûreté

1. Pas de carte ou résultat inventé : seules les références de matchs ESPN trouvées permettent la publication enrichie.
2. Pas de liquidation automatique de corners, cartons, prolongations ambiguës ou tout marché non pris en charge par le modèle score final. Une équipe doit contrôler manuellement.
3. Réseau ESPN non officiel : s'il ne répond pas, conserver les données connues, ne pas décréter gagnant/perdant et maintenir les notifications indépendamment.
4. Pas de notification promotionnelle aux utilisateurs sans consentement.
5. Les XP sont non monétaires ; service 18+ et avertissements de risque conservés.

## Derniers tests à faire avec de vraies données (aucune donnée inventée)

- Ouvrir la Mini App en tant qu'admin dans Telegram et publier un nouveau coupon avec un vrai ID ESPN, après contrôle du titre, des dates et des cotes.
- Sur ce coupon, vérifier les logos, la source, la cote et l'historique sur un iPhone et un Android.
- Activer volontairement l'alerte depuis un compte de test, observer la prochaine notification cron et son historique D1.
- Tester un ticket support réel suivi d'une réponse administrateur.
- Comparer les décisions de score aux scores officiels pour plusieurs matchs terminés, avant d'étendre l'automatisation.

## Références

- Pull requests : #204, #205, #206, #207.
- Exécution de déploiement finale validée : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39728364956
- Mini App : https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev/app
- Logo : https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev/brand.svg

**Règle de réception :** « code implémenté », « déployé », « testé avec des données simulées » et « validé sur un vrai utilisateur/match » sont des statuts différents. Ne pas déclarer un résultat sportif entièrement automatisé sans couvrir tous les marchés du coupon.
