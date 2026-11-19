# Ciné X — Rotation des vidéos publiques

Ce module conserve les **10 dernières vidéos** de `@CineXFilms_vf` et traite les vidéos plus anciennes uniquement si une affiche correspondante et un lien de vidéothèque ont été vérifiés.

## Fonctionnement

- Utilise la session propriétaire Telethon déjà présente dans GitHub Secrets pour lire l'historique du canal.
- Compte les vidéos natives et documents vidéos (.mkv, .mp4…), sans compter les affiches.
- Protège les 10 publications vidéo les plus récentes, par identifiant de message décroissant.
- Cherche une **affiche située avant la vidéo**, proche dans le canal, dont le titre est clairement concordant. Un doute = aucune suppression.
- Vérifie si le même document est déjà dans `TG_PRIVATE_CHANNEL` ; le réutilise au lieu de le publier une deuxième fois.
- Si absent, copie le média dans la vidéothèque puis vérifie son existence.
- Modifie les boutons de l'affiche originale (seulement si le bot est autorisé à modifier ce post) :
  - 🎬 VOIR LE FILM → lien du message privé exact ;
  - 👥 REJOINDRE LA TEAM → lien de dossier Telegram.
- **Ne supprime l'ancienne vidéo publique qu'après vérification des deux boutons et de la vidéo privée**.
- Logs et bilan GitHub Actions ; les éléments incertains restent intacts.

## Activation

Workflow : `.github/workflows/cinex-public-video-rotation.yml`.

Planification à `0 0 * * *` UTC (= 00:00 à Lomé).

Par défaut, **le workflow programmé est une simulation**. Pour activer réellement la rotation après examen des logs : déclarer la variable GitHub Actions `CINEX_ARCHIVE_ENABLED=true` dans le dépôt.

Pour une exécution manuelle : GitHub → Actions → **CineX - Rotation quotidienne des 10 videos** → Run workflow → `apply=false` (simulation), puis `apply=true` seulement après validation.

Variables / secrets repris du workflow existant : `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` (alias pris en charge), `FOOTBALL_NEWS_BOT_TOKEN` (ou `TELEGRAM_BOT_TOKEN`), `TG_PRIVATE_CHANNEL`, `CINEX_FILM_FOLDER_URL`. **Le bot doit être administrateur du canal public et auteur des affiches à modifier.** Le compte utilisateur doit disposer du droit de suppression et d'accès au canal privé.

## Limites délibérées

- Ne publie **pas** automatiquement les futurs films en vidéo dans le canal principal : cette fonctionnalité est distincte du nettoyage et nécessite une adaptation du relais, avec checkpoint et anti-doublons.
- Un poster publié manuellement par un autre compte ou bot peut être impossible à modifier avec le bot configuré : la vidéo reste en place.
- Vidéo sans titre concordant, vidéo protégée, album ambigu ou affiche introuvable : la vidéo reste en place.
- Fenêtre historique par défaut de 4 000 messages, ajustable avec `--limit` (20 à 20 000). Les vidéos plus anciennes hors fenêtre ne sont pas touchées.
- En cas d'échec de suppression, le film privé et les boutons ne sont pas annulés.
- `t.me/c/...` donne accès au message exact **uniquement aux abonnés autorisés du canal privé**.
- Les limites de Telegram sur les droits de modification/suppression et sur les médias restent applicables.
- Ne distribuer que des vidéos pour lesquelles vous disposez des droits nécessaires.

## Commandes

```bash
cd telegram-film-relay
python -m unittest discover -s tests -p test_public_video_archive.py -v
python -m film_relay.public_video_archive
python -m film_relay.public_video_archive --apply
```
