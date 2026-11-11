# Mr XPRONOS — Publication flexible V4 : vérification et procédures

## Objectif et portée

Finaliser le point encore « partiel » de la V3 : les vidéos peuvent présenter **1 à 9 matchs**, lorsque 10 matchs réels admissibles ne sont pas disponibles, tout en conservant les protections du parcours strict à 10. Cela ne garantit ni un pronostic tous les jours ni une publication acceptée par un réseau social.

## Liste de contrôle d'implémentation

- [x] **Sélection réellement publiable** : `--require-renderable` exclut les affiches à écussons manquants, à source non vérifiée ou à terrain inconnu pour une finale *avant* le classement et le calcul, afin d'essayer les rencontres suivantes. Activé **seulement** dans `create_social_exact_score_video.py`, pas dans les backtests classiques.
- [x] **Mise en page 1–9** : dernière carte seule centrée ; pas d'étiquette superposée au nom des clubs sur la neuvième carte ; mise en page 9:16 inchangée.
- [x] **Écussons** : deux vrais logos requis par match, aucun remplacement par initiales dans le rendu de production ; compteur de logos corrige désormais les réutilisations du même écusson.
- [x] **Sélection synchronisée** : identité, ordre, équipes, score calculé, date/heure de coup d'envoi, et URLs des deux logos cohérents entre les prédictions et le storyboard.
- [x] **Fichier MP4 dynamique** : `social_exact_scores_N.mp4`, N réel entre 1 et 10. Preuve de rendu Full HD, 2N logos, aucun placeholder.
- [x] **Manifeste V3 flexible** : SHA-256 du MP4, des prédictions et du storyboard ; liste ordonnée des IDs ; preuves d'écussons. Le publish refuse un décalage ou une altération.
- [x] **Contrôle média indépendant avant publication** : `ffprobe` vérifie H.264, format vertical 1080 × 1920, une piste audio et une durée de 2 à 60 secondes.
- [x] **Publications par plateforme et idempotence** : Facebook, YouTube, Instagram, Threads et Bluesky ; même cible/date, preuves D1 anti-doublon et retour ID du fournisseur. Le rapport contient le nombre d'affiches, le mode, la date et SHA-256, recoupés en fin de job.
- [x] **TikTok** : autorisé seulement en `workflow_dispatch` avec consentement du créateur *par vidéo*, confidentialité explicitement choisie et les secrets TikTok appropriés ; désactivé pour la tâche automatique.
- [x] **Prévisualisation sans diffusion** : exécution de validation technique et création de vidéo sans upload social ; la tâche de 20 h reste **strict**.
- [x] **Tests GitHub** : `tests/test_social_flexible_e2e.py` exerce les comptes 1, 3 et 9, la vérification des hashes, les clips altérés, l'encodeur FFmpeg réel hors réseau, et la simulation des 5 fournisseurs avec stockage D1 idempotent.
- [x] **Prévisualisation de la source ESPN réelle** : job `live_preview` (sans secret social ni publication), qui produit soit le MP4 réel, soit un refus explicite accompagné des motifs.

## Validation qui doit rester distinguée

- [ ] **Réussite bout-en-bout réelle auprès de chaque réseau** : un test avec un véritable compte autorisé est nécessaire pour obtenir les reçus d'API individuels de Facebook, YouTube, Instagram, Threads et Bluesky ; TikTok nécessite le consentement vidéo. Les tests hors réseau, même réussis, ne sauraient être présentés comme des confirmations réelles.
- [ ] **Prédiction garantie tous les jours** : aucune garantie n'est possible. Le backtest d'octobre V3 n'avait que 28/31 journées avec au moins un pronostic, 14/31 avec dix.

## Comment publier une vidéo flexible réelle après déploiement

1. Ouvrir GitHub Actions → « Dixon-Coles - Social Top10 20h » → « Run workflow ».
2. Lancer d'abord `mode=preview`, `publication_mode=flexible`, `source=espn` et inspecter l'artefact de la vidéo, du manifeste et des prédictions.
3. Après vérification humaine du nombre, du logo, du score et de la légende, relancer avec `mode=publish` et choisir les plateformes. Pour TikTok, cocher `tiktok_consent` pour cette vidéo uniquement.
4. Examiner `social_post_results.json` : un réseau n'est confirmé que si sa ligne `ok=true` contient l'identifiant de publication du fournisseur, et que l'audit final correspond au manifeste. Ne pas réessayer un envoi ambigu avant vérification manuelle, afin d'éviter les doublons.

Ces procédures ne contournent aucune restriction de plateforme ni condition d'utilisation d'ESPN. La publication de la même vidéo dans la même journée est protégée par les réservations D1 existantes.
