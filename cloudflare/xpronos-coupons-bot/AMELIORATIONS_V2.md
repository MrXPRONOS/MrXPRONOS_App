# Free Pronos — suivi des améliorations (22 octobre 2026)

> **Nom public : Free Pronos.** Dépôt historique : `MrXPRONOS/MrXPRONOS_App`. Worker conservé : `xpronos-coupons-bot`.
> Statuts ci-dessous = état du code et de la production. Un test GitHub réussi ne remplace pas les essais sur plusieurs téléphones.

## Design — 8 recommandations initiales

| # | Recommandation | Implémentation | Statut |
|---|---|---|---|
| D1 | Identité visuelle et bannière | Mini App CSS bleu nuit/orange, en-tête Free Pronos, présentation du bot mise à jour | **Partiel** : pas encore de photo de profil officielle ni de bannière image publiée dans le chat |
| D2 | Menu intelligent interactif | Menu clavier et commandes, navigation inline avec modification de message, Mini App | **Appliqué** |
| D3 | Cartes de coupons premium | Messages HTML, cartes Mini App, cote, catégorie, prix XP et expiration ; détails après déblocage | **Partiel** : compétition structurée/logos des équipes non inclus dans le modèle de données des coupons |
| D4 | Portefeuille XP visuel | Tableau de bord, progression, niveau, solde, XP du jour | **Appliqué** |
| D5 | Textes hiérarchisés | Titres, gras, italiques, citations Telegram et messages segmentés | **Appliqué** |
| D6 | Boutons aux couleurs cohérentes | primary/success/danger officiels ; thème Mini App bleu/orange | **Appliqué**, rendu adapté par le client Telegram |
| D7 | Notifications soignées | Alertes coupons et résultats HTML, boutons et avertissements, préférences opt-in | **Appliqué au code** ; aucun test de réception volontaire avec un abonné réel n'est documenté |
| D8 | Fiche Telegram professionnelle | Nom Free Pronos, description, description courte, commandes, menu Mini App | **Partiel** : avatar/photo de profil pas encore remplacé par un asset validé |

## Fonctionnalités — 10 recommandations initiales

| # | Recommandation | Implémentation | Statut |
|---|---|---|---|
| F1 | Tableau de bord personnel | /dashboard et Mini App, XP, niveau, coupons, missions, filleuls | **Appliqué** |
| F2 | Historique des XP | /history, transactions D1, Mini App | **Appliqué** |
| F3 | Notifications nouveaux coupons | Consentement explicite, cron Cloudflare 10 min, déduplication d'envoi et quotas | **Appliqué au code** ; livraison réelle non testée pour compte opt-in |
| F4 | Statut des coupons | available/live/won/lost/void, /result admin avec source HTTPS, historique, notifications finales | **Partiel** : vérification des rencontres et des résultats manuelle, pas de fournisseur API indépendant |
| F5 | Missions quotidiennes et hebdomadaires | /daily, /weekly, Mini App, unicité période UTC, XP via trigger D1 | **Appliqué** |
| F6 | Niveaux fidélité | Débutant (0), Amateur (100), Expert (300), Légende (800), sur XP cumulés positifs | **Appliqué** |
| F7 | Parrainages améliorés | Carte partageable, liens individuels, liste des filleuls et états de vérification | **Appliqué** |
| F8 | Filtres coupons | Catégories ALL/SIMPLE/PRO/VIP ; Mini App prix XP et tri par expiration | **Appliqué en Mini App**, filtres Telegram en chat limités à la catégorie |
| F9 | Centre d'aide | /support, /mytickets, /tickets, /replyticket, /closeticket ; formulaire Mini App et D1 | **Appliqué au code** ; essais échange utilisateur-administrateur restant à réaliser |
| F10 | Administration avancée | /adminstats, /result, /tickets, commandes missions/coupons, chiffres agrégés | **Partiel** : pas encore d'espace administrateur graphique de publication/modération dans la Mini App |

## Mini App et aspects techniques

| Domaine | Fonctionnalité | Statut |
|---|---|---|
| Mini App | Interface responsive, couleurs Free Pronos, navigation, XP, coupons, missions, historique et préférences | **Appliqué** |
| Mini App | Déblocage coupons et missions directement dans l'interface | **Appliqué au code**, vérifier avec un utilisateur réel |
| Sécurité | Signature Telegram initData vérifiée HMAC côté Worker, protection données par ID | **Appliqué** et testé localement |
| XP/stock | Triggers SQLite, anti-doublon des tâches et des coupons, anti-rejeu webhook | **Appliqué** et tests de non-régression |
| Résultats | Source d'un match affichée lorsqu'un administrateur l'a enregistrée | **Appliqué** ; authenticité de la source reste sous contrôle humain |
| Alertes | Consentement, désactivation possible, exécution par lots et CRON toutes les 10 minutes | **Appliqué** |
| Protection | Confirmation 18+, avertissement de risque, XP sans valeur monétaire | **Appliqué** |
| Logo | Photo de profil et bannière-image alignées sur la marque Free Pronos | **À finaliser** avec un élément graphique confirmé |

## Déploiements et vérifications

- D1 migrations : `0001_initial.sql`, `0002_free_pronos_experience.sql`, `0003_support_tickets.sql`.
- Code GitHub : pull requests #197 et #198 fusionnées dans `main`, tests GitHub de Node + SQLite + Wrangler réussis.
- Worker : `https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev`.
- Mini App : `https://xpronos-coupons-bot.cinecanaux-xpronos.workers.dev/app`.
- Telegram : `https://t.me/FreePronos_mrxp_bot`.
- Données / secrets Cloudflare existants préservés.
- Le workflow contient désormais un **smoke test de production** : /health 200, /app 200, /api/me non autorisée 401.
- La conformité 18+ est déclarative ; pas de KYC ni de vérification d'identité.

## Tests manuels à faire pour clore les parties encore non validées

1. Depuis Telegram, vérifier le menu Free Pronos et ouvrir la Mini App sur iPhone et Android.
2. Faire une mission /daily, vérifier +3 XP et le blocage d'un deuxième crédit dans la journée.
3. Activer une alerte de nouveau coupon sur un compte de test consentant, publier un coupon fictif dédié, vérifier une notification unique, puis supprimer l'exemple.
4. Envoyer `/support` depuis un membre, répondre avec `/replyticket` depuis un administrateur, vérifier le retour dans le bot et la Mini App.
5. Enregistrer un résultat depuis `/result ID won|lost|void SOURCE_HTTPS` sur un coupon de test, vérifier son état, la source et l'impossibilité de l'acheter une fois terminé.
6. Finaliser l'avatar et les visuels du bot avec des assets Free Pronos validés.

**Ne pas confondre « code déployé » et « fonctionnement validé par un utilisateur sur Telegram ».** Aucun résultat sportif n'est garanti.
