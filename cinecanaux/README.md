# Ciné Radar — annuaire Telegram simple

L'objectif de Ciné Radar est volontairement minimal : **choisir Films, Séries ou Animés → sélectionner un canal public → l'ouvrir**. Aucune inscription, aucun profil, aucun favori, aucune copie/partage du lien du canal, aucune notification personnalisée.

## Pour l'utilisateur
- Bot Telegram : trois catégories avec les liens directs, huit canaux par page si nécessaire.
- Mini App : trois catégories, recherche par nom, cartes avec les vraies images publiques des canaux lorsque Telegram en fournit, et deux actions **Aperçu** / **Ouvrir**.
- Aperçu : nom, photo du canal, photo d'une publication publique si disponible, courte description et un unique bouton d'ouverture.
- Sans photo publique, une icône neutre apparaît : aucune image n'est inventée.

## Infrastructure légère
- `radar-lean.mjs` : messages Telegram, catalogue public et vérification automatique des liens cassés.
- `app-page.mjs` : interface responsive sans authentification ni fonction personnalisée.
- `channel-preview.mjs` : récupération des seules métadonnées et images publiques via des liens Telegram ; **aucune photo ni vidéo n'est téléchargée dans D1**.
- `worker.mjs` : accès web, webhook et lecture de l'état de découverte GitHub.
- `schema.sql` : données de découverte, canaux, cache limité (une ligne par canal), état du webhook et des contrôles de liens.

Le script GitHub de découverte quotidienne conserve les trois motifs techniques : photo avec légende → vidéo, photo → texte → vidéo et fichier MKV. La synchronisation Cloudflare a lieu toutes les quatre heures. Les liens confirmés définitivement morts lors de deux contrôles indépendants sont retirés. Les erreurs HTTP 429, les indisponibilités temporaires et l'absence d'aperçu public ne suffisent pas à supprimer un canal.

Les aperçus publics sont mis en cache au maximum sept jours lorsqu'ils sont disponibles, avec une seule ligne D1 par canal. Le code ne crée aucune ligne par visiteur ni clic. Un entretien automatique supprime les cache obsolètes et les anciennes découvertes rejetées.

## Tests
- `cinecanaux/tests/radar-lean.test.mjs` et `cinecanaux/tests/channel-preview.test.mjs`.
- `cinecanaux/tests/live-smoke.mjs` teste le vrai catalogue Cloudflare.
- GitHub Actions : `.github/workflows/cine-radar-v2-ci.yml` et `.github/workflows/cine-radar-live-smoke.yml`.

La suppression des anciennes tables de favoris, de parrainage et de données personnelles a été effectuée sur la base D1 utilisée par le Worker. Le compte administrateur existant reste conservé séparément, sans interface administrative publique.

Mini App : https://cinecanaux-bot.cinecanaux-xpronos.workers.dev/app

Bot : https://t.me/CineRadarFr_Bot
