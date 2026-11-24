# Actu Foot V3 — Moteur de données

## Portée livrée
- Index inversés éphémères sur les collections chiffrées V2 (aucun index en clair publié)
- Recherche déterministe, filtres autorisés, tri, pagination opaque, curseurs invalidés par génération
- Lots validés dans une collection et transactions atomiques multicollections au moyen d'un seul commit Git non forcé
- Persistance par V2 CollectionVault avec compare-and-swap SHA et tentatives contrôlées
- Cache mémoire avec TTL, capacité maximale, invalidation par génération
- Préparation d'archivage par seuil temporel, sans supprimer la source tant que l'archive n'est pas persistée
- Export/import chiffrés authentifiés via AES-256-GCM de V2
- Compression Zlib existante conservée pour tous les exports V2/V3

## Limites réelles
- GitHub n'est pas une base temps réel. L'atomicité V3 entre collections dépend de l'utilisation du même mécanisme de ref Git non forcée ; les writers externes ne coopérant pas peuvent encore concurrencer ces écritures.
- Les index sont reconstruits en mémoire après déchiffrement ; les performances réelles doivent être mesurées.
- Les curseurs sont opaques, non secrets et ne sont pas des jetons d'autorisation.
- La pagination est stable uniquement avec une génération inchangée ; modifier la base sans augmenter sa génération est interdit.
- La préparation renvoie (conservé, à archiver). La compaction opérationnelle ne retire les sources qu'après copie indépendante chiffrée et relue dans Cloudflare, avec audit, dans un commit Git atomique.
- La maintenance autonome est programmée le lundi à 02:21 UTC et refuse la compaction sans preuve de copie Cloudflare indépendante.
- Aucun basculement Telegram. Synchronisation des matchs et de l'outbox prévue en V4.

## Conditions avant activation
1. V2 : initialiser les collections et secrets sans publier de données en clair.
2. Tester sauvegardes et restauration réelles, puis installer une destination indépendante.
3. Profilage sur volumes comparables à la production.
4. Intégration V4 avec réservations Telegram transactionnelles et reprise contrôlée.

## Finalisation V3 — moteur intégré

Le lecteur SnapshotReader fixe un commit Git, prépare les index une fois, réutilise le cache TTL et invalide index/résultats/curseurs après changement de snapshot. Les recherches d'archives utilisent le chemin de shard authentifié et explicite. La capacité reste 5 000 enregistrements et 2 Mo par enveloppe; le test de capacité couvre 50 pages. Aucun index ou résultat métier n'est écrit en clair. Migration de schéma appliquée par les transactions V3; l'audit hashé demeure inchangé. La V4 reste responsable du raccordement du bot et de l'import historique.

## Clôture réelle V3

PRs #665/#667/#669 fusionnées. Workflow automatique et E2E Cloudflare 45408241722 ; sauvegarde 45408510666 ; restauration 45408645985, tous réussis. La migration et la connexion des données football au bot Telegram relèvent toujours de la V4.
