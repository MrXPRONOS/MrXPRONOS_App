# Ciné X — Phase 1 : sécurité et fiabilité (2026-11-19)

## Mesures appliquées
1. **Invitations Telegram privées** : les fichiers JSON suivis dans le dépôt public ne doivent plus jamais contenir de lien d'invitation. Ils retiennent uniquement `invite_sha256` et les IDs. Les liens Secours sont récupérés auprès du compte propriétaire via Telegram au lancement, vérifiés par empreinte, puis conservés dans un fichier temporaire hors dépôt, en mode 0600, uniquement pendant le workflow. Si Telegram ne retourne pas le lien attendu, aucun bouton Secours de remplacement n'est généré.
2. **Sérialisation** : les workflows utilisant la session personnelle partagent `concurrency.group=mrx-telegram-personal-account`, avec `cancel-in-progress=false` et `queue=max`. GitHub accepte une file maximale de 100 tâches en attente, et non une infinité de déclenchements.
3. **Archivage destructif** : suppression par message de commit interdite. Seuls un lancement manuel explicitement demandé ou la planification normale peuvent supprimer, à condition d'avoir les trois variables GitHub **CINEX_ARCHIVE_ENABLED=true**, **CINEX_ARCHIVE_DELETE_APPROVED=true**, **CINEX_RIGHTS_VERIFIED=true**. L'opération manuelle s'arrête après deux suppressions confirmées et la planification après dix. Si les conditions ne sont pas satisfaites, exécution en lecture seule. Le bot et le compte propriétaire doivent chacun avoir réellement le droit de supprimer.
4. **Protection des dix dernières vidéos** : avant chaque suppression, le script parcourt les messages nécessaires pour identifier dix vidéos effectivement récentes, même si de nombreuses affiches les séparent.
5. **Visibilité des erreurs** : un module Secours partiellement en échec retourne désormais un statut GitHub rouge ; le relais signale aussi les erreurs de vidéos directes et d'invitations. Les rapports GitHub conservent l'issue réelle par catégorie.
6. **Prévention de régression** : les tests CI vérifient les secrets dans les états suivis, les restrictions de déclenchement, la file d'attente, les permissions et l'intégrité YAML. Les fichiers JSON sont recontrôlés à chaque PR.

## Attention : anciens liens exposés dans l'historique Git
La migration protège les **nouveaux commits**, mais **ne purge pas l'historique de Git**. Les URL qui y ont figuré restent récupérables par les commits précédents. Si elles sont considérées sensibles, il faudra les révoquer dans Telegram, mais cette rotation rendrait inopérants les boutons déjà publiés. La marche à suivre sans rupture : inventorier toutes les fiches concernées, générer une nouvelle invitation, modifier leurs boutons en utilisant le nouvel identifiant, vérifier les liens, puis révoquer l'ancienne invitation. Ce processus de rotation des liens et de réécriture de tout l'historique des fiches **n'est pas lancé automatiquement dans cette phase**.

## Dépendances et fonctionnement dégradé
- L'étape de récupération des invitations nécessite le compte propriétaire et l'accès API Telegram. Si elle échoue, les publications ne doivent jamais substituer un lien non vérifié, et le cycle GitHub remonte une erreur.
- Un lien exporté depuis Telegram ne doit jamais être imprimé dans les logs ou commité.
- Ne pas stocker de fichier `cinex-rescue-links.json` dans `state/` ou tout autre dossier suivi par GitHub ; le workflow utilise `RUNNER_TEMP`.
- Les canaux Tendances conservent leurs invitations **en mémoire** et uniquement les empreintes dans les checkpoints.
- La nouvelle file GitHub accepte 100 tâches au maximum ; il est toujours utile de surveiller la saturation.

## Contrôles
```bash
cd telegram-film-relay
python -m unittest discover -s tests -v
python -m pip install PyYAML==6.0.3
python scripts/cinex_phase1_audit.py
```

**Validation de déploiement recommandée :** tester la récupération de liens en lecture seule avant d'activer les workflows destructifs, puis ne publier que dans les canaux où les droits de distribution sont établis.
