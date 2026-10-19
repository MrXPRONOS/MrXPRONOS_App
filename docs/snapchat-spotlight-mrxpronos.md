# Snapchat Spotlight — Mr XPRONOS (19 octobre 2026)

## État réel

La préparation Spotlight est intégrée à GitHub Actions **sans publication automatique**. L’accès en écriture de l’API Snapchat Public Profile est limité : il ne faut pas inventer un token, un endpoint ou supposer que la Marketing API donne le droit de publier des Spotlight organiques.

L'interface Snapchat permet l'envoi et la programmation depuis un navigateur :
- https://profile.snapchat.com/
- https://businesshelp.snapchat.com/s/article/public-profiles-content-web?language=en_US
- https://help.snapchat.com/hc/en-us/articles/7012293789972-How-do-I-submit-a-Snap-to-Spotlight-from-the-web

## Procédure de mise en place

1. Ouvrir https://forbusiness.snapchat.com/public-profiles et se connecter / créer un **Public Profile** Mr XPRONOS. Vérifier que le compte a le rôle Admin ou Collaborator pour pouvoir publier.
2. Préparer une courte vidéo de **football général**, actualités, statistiques ou culture sportive **sans bookmakers, codes promo, cotes, coupons ni redirections vers les paris**. Ne pas utiliser les clips premium des coupons, car leur bannière bookmaker est intégrée.
3. Charger ce MP4 dans Supabase Storage, bucket `videos`, dossier `snapchat/`. Exemple de chemin : `snapchat/mon-analyse-football.mp4`. Le fichier doit être public et accessible à :
   `https://nhwafcpndlufzzxexikh.supabase.co/storage/v1/object/public/videos/snapchat/mon-analyse-football.mp4`
   **N’utiliser que tes vidéos dont tu possèdes les droits.**
4. Lancer manuellement [Snapchat - Prepare Spotlight](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/snapchat-spotlight-prepare.yml) :
   - `source_url` : URL publique du MP4 dans `videos/snapchat/` ;
   - `title` : titre factuel, sans publicité de paris ;
   - `review_confirmation` : `football-only-reviewed-no-betting` uniquement si le contenu a été intégralement visionné et vérifié.
5. Télécharger dans **Artifacts** l'archive `snapchat-spotlight-review-and-upload`. Elle contient :
   - `mrxpronos_snapchat_spotlight.mp4` (H.264, 1080×1920, 5–60 s);
   - `snapchat_manifest.json` (titre, description, durée, empreinte SHA-256 et statut `READY_FOR_HUMAN_UPLOAD_ONLY`);
   - `LIRE_AVANT_PUBLICATION.txt` (procédure).
6. Ouvrir https://profile.snapchat.com/ , choisir le **Public Profile**, importer la vidéo, cocher **Spotlight Snaps**, choisir les #Topics, accepter les Creator Terms et cliquer sur **Post to Snapchat**. Si ton interface offre la programmation, choisir la date et l’heure; vérifier ensuite les Insights et le statut de modération.

### Restrictions produit et sécurité

- Pas de publication par ce workflow. Aucun accès Snapchat, mot de passe ou cookie n'est utilisé. L’API Snapchat pour profils publics nécessite des droits spécifiques et, selon les intégrateurs, une approbation / allowlisting.
- Ne pas tenter de contourner l'authentification avec un navigateur connecté, extraction de cookies ou robot non officiel.
- Les règles Snap interdisent de faciliter le jeu en ligne; le contenu recommandable Spotlight ne doit pas promouvoir paris/jeux d'argent.
  https://values.snap.com/policy/policy-community-guidelines/illegal-regulated-activities
  https://values.snap.com/policy/content-guidelines-recommendation-eligibility/recommendation-eligibility/illegal-regulated-activities
- Les contenus organiques sont modérés et peuvent être limités dans Spotlight; une publication n'assure pas la recommandation.
- Le fichier MP4 doit durer de 5 à 60 secondes, orientation portrait, taille initiale au minimum 540×960.
- Le dossier d'entrée `videos/snapchat/` est volontairement **distinct** de `videos/shorts/` des coupons premium.

## Intégration automatique future

Une véritable publication automatique nécessite de vérifier avec Snap :
1. si le Public Profile Mr XPRONOS est éligible à son API de gestion de contenu organique;
2. si notre OAuth client peut être autorisé (allowlist) pour les opérations de création Spotlight;
3. les scopes, quotas, formats, endpoints et règles de consentement actuellement accordés;
4. les exigences de validation des contenus de football et les restrictions relatives aux paris.

**Ne pas ajouter Snapchat à `POST_PLATFORMS` des deux workflows de coupons** tant que ces quatre conditions ne sont pas remplies.

Sources : aide officielle Snap, liens ci-dessus.
