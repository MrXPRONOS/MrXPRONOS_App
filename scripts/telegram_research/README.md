# Veille Telegram publique — Mr XPRONOS

Analyse en **lecture seule** des publications du canal public `@ActuFootZoneFr`.

## Configuration

Créer les secrets GitHub Actions sur ce dépôt :
- `TG_API_ID` — depuis https://my.telegram.org
- `TG_API_HASH` — depuis https://my.telegram.org
- `TG_SESSION_STRING` — chaîne d'authentification générée sur votre propre PC.

Pour générer la session : installer `telethon>=1.36,<2`, puis exécuter `python scripts/telegram_research/create_session.py` sur un ordinateur de confiance. Ne jamais transmettre la session, le code de connexion ni le mot de passe 2FA dans le chat ou dans GitHub.

## Utilisation

Dans GitHub > Actions > **Telegram - Veille canal public** > Run workflow : choisir 1, 2, 3 ou 7 jours. Le workflow est aussi programmé tous les jours à **06:20 UTC** (GitHub peut retarder la programmation).

Télécharger l'artefact du run pour obtenir les fichiers JSON et CSV. Les exports ne sont **pas commités dans le dépôt** et expirent après 7 jours. Aucun message n'est publié sur Telegram.

**Attention** : une session Telegram donne accès à votre compte ; révoquez-la si elle est compromise. Le premier déclenchement ne fonctionnera qu'une fois les trois secrets configurés.
