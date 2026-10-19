# TikTok — connexion Mr XPRONOS (octobre 2026)

## Situation vérifiée
L'audit des secrets GitHub (run 39197892620) a trouvé :
- Manquants : `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_ACCESS_TOKEN`, `TIKTOK_REFRESH_TOKEN`, `TIKTOK_OPEN_ID`.
- Configuré : `GH_PAT_SECRETS` pour mettre à jour les GitHub Secrets.
Le moteur vidéo fonctionne pour Telegram/Facebook/Instagram/YouTube/Threads, mais TikTok ne peut pas être déclaré connecté. On ne tente PAS de publier à l'aveugle.

## Mise en place officielle (aucun secret dans un chat ou un commit)

1. Connecte-toi à https://developers.tiktok.com/ > Manage apps et crée/sélectionne l'application TikTok. Il faut une app développeur pour obtenir **Client Key** et **Client Secret**.
2. Ajoute **Login Kit** à l'app. Enregistre exactement cette redirect URI HTTPS, dans les paramètres Login Kit :
   `https://mrxpronos.github.io/MrXPRONOS_App/tiktok-callback.html`
   L'URI ne doit contenir aucun paramètre ni fragment.
3. Vérifie les scopes approuvés. `user.info.basic` est nécessaire pour identifier le compte. `video.list` est facultatif pour les statistiques et doit être approuvé; `video.publish` nécessite une autorisation de TikTok pour l'application et de l'utilisateur. Les scopes absents de la liste approuvée ne doivent pas être demandés.
4. Dans [GitHub Actions Secrets](https://github.com/MrXPRONOS/MrXPRONOS_App/settings/secrets/actions), ajoute :
   - `TIKTOK_CLIENT_KEY`
   - `TIKTOK_CLIENT_SECRET`
   - `GH_PAT_SECRETS` doit rester présent avec Actions secrets write (déjà confirmé).
5. Sur le même navigateur où tu es connecté à TikTok, ouvre la [page de connexion Mr XPRONOS](https://mrxpronos.github.io/MrXPRONOS_App/tiktok-callback.html). Entre uniquement le Client Key public.
   - **Étape initiale recommandée** : laisse `video.publish` et `video.list` désactivés si TikTok ne les a pas approuvés. `user.info.basic` est toujours demandé.
   - Si TikTok les a approuvés, tu peux les sélectionner avant de lancer le consentement.
6. Après autorisation, la page renvoie un **code à usage unique**. Copie-le immédiatement dans le secret `TIKTOK_AUTH_CODE`. N'envoie jamais ce code à ChatGPT ou dans un commit.
7. Dans [GitHub Actions](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/workflows/tiktok-auth.yml), lance `TikTok - Connexion et maintenance` avec `exchange`. Les logs doivent confirmer les tokens sauvegardés, sans afficher leurs valeurs.
8. Relance le même workflow avec `verify` (lecture seule) et, *si `video.publish` a été approuvé*, coche `check_publish_scope` pour tenter `creator_info/query` sans publier.
9. Le workflow renouvelle ensuite les tokens à 04h23 et 16h23 UTC (Lomé), en enregistrant **à la fois** l'access token et le refresh token. L'access token TikTok expire normalement en 24 h; le refresh token est prévu pour un maximum de 365 jours selon l'API.

## Restrictions importantes : TikTok ne se comporte pas comme YouTube ou Threads

- Un upload avec `publish_id` n'est **pas** une publication confirmée. Seul `status/fetch` avec statut `PUBLISH_COMPLETE` le confirme.
- Le produit Content Posting API requiert l'approbation `video.publish`, le contrôle de `creator_info`, une UI où le créateur contrôle les réglages (visibilité, interactions, informations commerciales) et consent *à chaque publication*. Une app non auditée ne peut publier que dans des conditions privées; TikTok refuse des utilitaires internes limités au compte d'une équipe et demande un produit destiné à des créateurs. Ne pas présenter l'intégration actuelle comme une app approuvée pour public posting.
- Les règles TikTok restreignent le marketing et les redirections vers les services de paris sportifs, ainsi que les codes promotionnels. Les coupons avec bannières de bookmakers ne doivent pas être automatiquement répliqués vers TikTok. Un contenu sur le football sans publicité de paris peut être une piste, sous réserve des règles TikTok.
- `TIKTOK_DIRECT_POST_ENABLED` est **false** par défaut et la publication TikTok a été retirée des deux workflows de pronostics en production; cela n'affecte pas Telegram/Facebook/Instagram/YouTube/Threads. Le futur circuit d'édition TikTok devra prévoir une interface conforme, la prévisualisation et le consentement avant activation.

## Travaux réalisés
- `tiktok-callback.html` : autorisation officielle TikTok OAuth avec `state` aléatoire anti-CSRF.
- `scripts/tiktok_auth.py` : échange OAuth sécurisé, vérification du compte, renouvellement des deux tokens et écriture des GitHub Secrets via stdin.
- `.github/workflows/tiktok-auth.yml` : vérification, échange, refresh biquotidien, tests et diagnostic sûr de présence des secrets.
- `scripts/post_shorts_video.py` : protection contre les publications involontaires, consultation de creator_info, vérification des options de visibilité et de la durée, suivi du statut (pas de faux succès après upload).
- `scripts/refresh_social_tokens.py` : le renouvellement TikTok non persistant a été supprimé du parcours général pour éviter d'invalider le refresh token enregistré.
- `tests/test_tiktok_auth.py` et `tests/test_tiktok_post.py` : tests hors ligne de sécurité.

Documentation officielle : https://developers.tiktok.com/docs/en/login-kit-web ;
https://developers.tiktok.com/docs/en/oauth-user-access-token-management ;
https://developers.tiktok.com/docs/en/content-posting-api-get-started ;
https://developers.tiktok.com/docs/en/content-sharing-guidelines .
