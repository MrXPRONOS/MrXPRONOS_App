# Live Mr XPRONOS — retrait des dépendances Neon

**Date : 24 novembre 2026.** Projet Supabase existant : `nhwafcpndlufzzxexikh`.

Le workflow de validation utilise déjà Supabase (`validate_predictions.yml`, PR #677).
Le site LIVE est alimenté par `/functions/v1/live`, la base conserve l'historique LIVE, et l'envoi Telegram du moteur Supabase est doté de son contrôle anti-doublon.

Les anciens workflows portant un nom Neon sont convertis en contrôles Supabase en lecture seule, en relance Supabase manuelle, ou en opérations archivées sans effet.
Le module `neon_rest_compat` conserve ses imports pour ne pas casser les anciens collecteurs mais refuse tout appel à Neon, même si `NEON_DATABASE_URL` existe encore.
L'ancien expéditeur Telegram ne publie plus de prédictions historiques. Le secret `SUPABASE_SERVICE_ROLE_KEY` reste uniquement côté serveur.

**Limites vérifiées :** l'ancien projet Neon est bloqué avec HTTP 402. Les données non exportables depuis celui-ci ne peuvent pas être récupérées tant que ce quota persiste ; nous ne supprimons ni les archives ni l'ancienne base. Supabase conserve déjà ses données existantes. Les matchs sans signaux qualifiés ne doivent pas produire de faux coupons.

Vérifier après fusion les tests `tests_football_channel.test_no_neon_live`, les sondes Supabase et la validation périodique, sans déclencher d'envoi Telegram de rattrapage.
