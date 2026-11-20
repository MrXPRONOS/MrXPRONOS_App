# Mr XPRONOS Play — recette de sécurité après l'audit du 20 novembre 2026

## Statut
- Correctifs intégrés dans la PR #513, branche `fix/mrxp-audit-lots-20261120`.
- Worker public : volontairement conservé dans la version déjà en ligne en attendant la recette finale.
- D1 `mrxpronos-play-v1` : **migration 007 appliquée** (additive), après obtention d'un bookmark de récupération ; la valeur du bookmark n'est pas committée.
- Contrôle D1 avant et après : 1 joueur, 3 syncs, 7 écritures de crédits, 0 objets, 1 236 XP et 596 taps confirmés. Les deux nouvelles tables sont vides.
- La migration n'a pas réinitialisé le moindre joueur.

## Portée du changement
1. Les événements de connexion quotidienne et les tours Lucky Wheel sont **réclamés via `POST /api/rewards/claim`** et stockés en D1 avant d'être synchronisés.
2. Le résultat de roue n'est plus publié par `/api/bootstrap` pour une journée où aucun tour serveur n'a été joué.
3. `/api/sync` ne paie **jamais** de récompense quotidienne ou de roue sur une simple date envoyée par le client : seul le registre des reçus serveur peut autoriser le gain.
4. Les messages locaux non prouvés antérieurs à cette version sont écartés lors de la reconnexion ; les taps en attente ne sont pas effacés.
5. Un plafond de requêtes par compte Telegram signé protège les actions d'écriture.
6. Taille des corps API bornée pendant la lecture du flux HTTP.
7. La politique CSP exige des hashes SHA-256 pour les deux scripts internes, sans `unsafe-inline` JavaScript. Les événements HTML `onclick` ont été raccordés en JS.
8. Les feuilles CSS sont consolidées sans changement volontaire de priorité des règles.
9. Les boutiques utilisent les opérations SQL transactionnelles existantes, avec une condition supplémentaire empêchant la création d'un reçu sync si la mise à jour joueur précédente n'a rien modifié.
10. Tests Chromium réel (avec fausse API), SQL SQLite réellement concurrent, suites Node Worker, rendu graphique et mobile dans CI.

## Limites de la sécurité
Une session Telegram authentifiée peut automatiser des interactions. Les dates falsifiées, doubles réclamations et dépassements simples de quota sont bloqués, mais aucun client web ne peut démontrer cryptographiquement la présence physique d'un humain qui tapote. Le tapotage hors connexion reste un décompte local assujetti aux limites d'énergie, de temps et de quantité lors de la synchronisation. Ne pas présenter cette fonction comme « anti-bot absolu ».

## Vérifications avant fusion ou déploiement du Worker
- Vérifier toutes les suites CI **sur le dernier commit**, notamment `node --test mrxpronos-play/tests/telegram-bot.test.mjs`, `python3 mrxpronos-play/tests/audit_sqlite_concurrency.py`, et le vrai navigateur `audit_real_browser.py`.
- Tester depuis deux **comptes Telegram réels**, avec téléphones Android et iOS, l'ouverture, la connexion, la roue et le bonus du jour, fermeture et reconnexion.
- Exécuter les scénarios de connexion après minuit UTC, duplication de requête, latence réseau et expiration de session.
- Vérifier qu'un ancien lot local de bonus sans reçu est ignoré, avec information claire. Contrôler explicitement l'absence de perte de taps locaux.
- Tester à deux joueurs les achats simultanés, l'activation concurrente et l'expiration des boosts. Les tests SQLite et mocks ne remplacent pas D1/Telegram réels.
- Vérifier avant/après les sommes et compteurs D1. Documenter et conserver un nouveau bookmark.
- Déployer en conservant les bindings `DB`, `BOT_TOKEN`, `WEBHOOK_SECRET` et `DEV_MODE` et l'identité attendue du bot.
- Faire les appels de vérification sans session (401), de santé (`reward_schema_ready` true, D1 réellement accessible) et contrôler les logs.
- Si anomalie, revenir à la version précédente du Worker ; **restaurer la base entière serait dangereux**, car cela effacerait potentiellement les nouveaux gains. La nouvelle migration est additive et peut rester en place pendant un rollback Worker.

## Publication
Ne pas confondre PR GitHub, version téléversée et **déploiement Cloudflare effectif**. Ne pas activer la nouvelle version tant que les contrôles critiques ne sont pas satisfaits.
