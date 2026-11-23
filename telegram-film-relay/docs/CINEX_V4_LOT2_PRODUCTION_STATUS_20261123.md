# CinéX V4 — Lot 2 : implémentation, preuves et blocages au 23/11/2026

**Ne pas confondre code déployé, audit vert et publication réelle vérifiée.**

## Preuves de production déjà obtenues

| Volet | Résultat constaté | Source |
| --- | --- | --- |
| Comptes Telegram des bots | 10 identités distinctes et vérifiées, parmi les secrets réellement configurés | [Action #45108372741](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/45108372741) |
| Administrateurs | 140/140 affectations vérifiées pour les 10 bots, sur 7 Secours + 7 principaux ; 58 nouvelles promotions/corrections et zéro erreur Telegram | Même Action |
| Secret réaction `TELEGRAM_REACTION_BOT_16_TOKEN` | Non valide (getMe HTTP 404) : jamais ajouté ; ce secret explique l'échec final de l'Action **malgré 140/140 accès réussis** | Même Action |
| Prévol Lot 2 (six catégories) | 6/6 : stock CineRadar D1 autorisé, publication et liens Secours/dossier | [Action #45106210205](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/45106210205) |
| Audit de vrais nouveaux posts V4 | 0/6 : aucune vidéo portant le tag V4 dans l'historique contrôlé ; pas d'erreur ; **aucun bouton réel encore démontré** | [Action #45108681606](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/45108681606) |
| Bot Anime V2 autonome | Bloqué : token dédié absent, sources et destinations incomplètes, état persistant/bascule non attestés ; ancien lot avec un épisode en attente | [Action #45106533609](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/45106533609) |

## Corrigé et testé dans le code du Lot 2

- **Public :** photo et vidéo V4 avec 4 boutons et URLs vérifiées, sans publier de lien de téléchargement inventé.
- **Vidéothèques :** photo privée à 3 boutons, sans ajouter de bouton Secours dans le stock.
- **CineRadar :** émission conditionnée à un fichier central enregistré ; audit D1 renforcé par vérification de l'identité du stock **et** du message source.
- **Séries et animés :** le bouton Télécharger les vidéos peut pointer vers un index privé de saison, distinct du reçu D1 d'un film individuel. La validation retrouve le vrai message index, le code SxxExx exact et le reçu D1 associé à cet épisode.
- **Couplage réel :** l'affiche privée validée doit correspondre à la même vidéo (ou affiche de saison) et au même téléchargement que la publication publique ; une ancienne fiche quelconque ne compte pas.
- **Surveillance :** tests hors ligne sur PR et audit Telegram en lecture seule sur main, recontrôle quotidien. En l'absence d'échantillons : état `pending`, avertissement GitHub, jamais `validated`.
- **Sécurité :** aucune nouvelle publication, suppression, édition, création de canal ou de token pendant les vérifications.

## Restant réellement à accomplir / hors du seul développement

1. **Preuve end-to-end :** attendre ou publier par le pipeline propriétaire un contenu **dont les droits de redistribution sont établis**, puis observer, dans chacune des six catégories, 4 boutons sur la photo et la vidéo, 3 boutons sur la photo de vidéothèque et la remise du média par CineRadar. L'audit ne crée pas de nouveaux contenus pour forcer un résultat.
2. **Secret n°16 :** remplacer ou désactiver le jeton invalide directement dans GitHub Settings → Secrets and variables → Actions. Les autres 10 bots ont été vérifiés comme administrateurs ; ne pas leur accorder de droits inutiles.
3. **Bot Anime V2 :** fournir le token **d'un bot dédié identifié**, les ID Telegram des sources dont l'utilisation est autorisée, ses permissions effectives, une persistance durable et les validations de migration. Résoudre l'unique épisode de l'ancien lot en cours **avec sa preuve réelle**, sans réinitialiser les reçus ni déclencher deux relais.
4. **Acceptation finale :** vérifier au moins une publication V4 de chaque catégorie et le fonctionnement d'au moins un téléchargement réel, puis documenter les reçus, erreurs et reprises sans doublon.

Un succès de workflow avec 0 échantillon reste **PARTIEL EN PRODUCTION**, même lorsque toutes les suites de tests sont vertes. Ce document sert de checklist factuelle, pas de certificat de déploiement complet.
