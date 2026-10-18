# Threads — reconnexion et maintenance Mr XPRONOS

## Pourquoi la publication échouait
L'ancien THREADS_ACCESS_TOKEN a expiré le 20 juin 2026. Un jeton expiré ne peut pas être renouvelé : il faut autoriser à nouveau @mr_xpronos une fois.

## Reconnexion (ne jamais communiquer de secrets dans un chat)
1. Ouvrir https://developers.facebook.com/apps/ et sélectionner **la même application Meta que celle déjà utilisée pour Threads**. Utiliser le **Threads App ID** et le **Threads App Secret** (ce sont des identifiants spécifiques au produit Threads, pas nécessairement META_APP_ID / META_APP_SECRET).
2. Dans Threads API > Settings, autoriser exactement l'URI :
   `https://mrxpronos.github.io/MrXPRONOS_App/threads-callback.html`
   Si l'app est en développement, vérifier que le profil @mr_xpronos est administrateur/développeur/testeur et a accepté l'invitation.
3. Ouvrir `https://mrxpronos.github.io/MrXPRONOS_App/threads-callback.html`, saisir uniquement le **Threads App ID**, cliquer sur « Autoriser », puis se connecter à Threads et accorder les autorisations.
4. Sur la page de retour, copier le **code d'autorisation à usage unique**. Ne pas le partager publiquement ; il expire en une heure.
5. Dans `https://github.com/MrXPRONOS/MrXPRONOS_App/settings/secrets/actions`, créer / vérifier :
   - `THREADS_APP_ID` : identifiant Threads
   - `THREADS_APP_SECRET` : secret Threads
   - `THREADS_AUTH_CODE` : code à usage unique reçu
   - `GH_PAT_SECRETS` : jeton GitHub avec droit **Actions secrets write** sur MrXPRONOS_App
   Les secrets `THREADS_ACCESS_TOKEN` et `THREADS_USER_ID` sont créés/remplacés automatiquement.
6. Dans GitHub Actions, lancer `Threads - Connexion et maintenance` avec l'option `exchange`. Ne PAS mettre le code comme input de workflow (visible dans les métadonnées). Le workflow lit uniquement les GitHub Secrets.
7. Vérifier que le log contient `Threads reconnecté : @mr_xpronos`, puis relancer avec `verify`. Aucun message n'est publié pendant ces deux actions.

En cas de problème : `HTTP 400` code 36006 = code expiré ou déjà utilisé, recommencer OAuth; code 1349168 = URL de redirection non autorisée; invitation testeur non acceptée = vérifier le rôle et l'invitation.

## Automatisation
Le workflow `.github/workflows/threads-auth.yml` s'exécute chaque dimanche à 05:17 UTC, vérifie le profil et renouvelle le jeton non expiré, puis le stocke avec `gh secret set`. Un token tout juste créé peut attendre au moins 24 heures avant son premier renouvellement.

**Important :** l'ancienne tâche générale `Refresh Social Tokens` ne persiste les tokens que lorsqu'elle est déclenchée et que GH_PAT_SECRETS est disponible. Le nouveau workflow est autonome pour Threads.

## Publication
Le script de publication `scripts/post_shorts_video.py` utilise `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` et l'URL du MP4 hébergé sur Supabase. Le workflow de reconnexion est volontairement en **lecture seule** côté Threads (aucune publication de test susceptible de créer un doublon). Une vidéo future permettra de tester le droit de publication.

## Sécurité
Jamais de token, App Secret ou code OAuth dans un commit, commentaire, issue, chat ou capture d'écran. Si le code d'autorisation a fuité, recommencer le consentement. Les traces GitHub n'affichent pas les valeurs des jetons.
