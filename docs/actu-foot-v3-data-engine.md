# Actu Foot V3 — Moteur de données

## Portée livrée
- Index inversés éphémères sur les collections chiffrées V2 (aucun index en clair publié)
- Recherche déterministe, filtres autorisés, tri, pagination opaque, curseurs invalidés par génération
- Lots d'insertion, upsert et suppression validés comme une unité dans **une seule collection**
- Persistance par V2 CollectionVault avec compare-and-swap SHA et tentatives contrôlées
- Cache mémoire avec TTL, capacité maximale, invalidation par génération
- Préparation d'archivage par seuil temporel, sans supprimer la source tant que l'archive n'est pas persistée
- Export/import chiffrés authentifiés via AES-256-GCM de V2
- Compression Zlib existante conservée pour tous les exports V2/V3

## Limites réelles
- GitHub n'est pas une base temps réel. Une transaction atomique *entre plusieurs collections* n'est pas fournie.
- Les index sont reconstruits en mémoire après déchiffrement ; les performances réelles doivent être mesurées.
- Les curseurs sont opaques, non secrets et ne sont pas des jetons d'autorisation.
- La pagination est stable uniquement avec une génération inchangée ; modifier la base sans augmenter sa génération est interdit.
- L'archivage renvoie (conservé, à archiver) et **n'efface pas** la source.
- Le système ne programme pas lui-même des compactions ni des tâches de rétention sans vérification du stockage durable.
- Aucun basculement Telegram. Synchronisation des matchs et de l'outbox prévue en V4.

## Conditions avant activation
1. V2 : initialiser les collections et secrets sans publier de données en clair.
2. Tester sauvegardes et restauration réelles, puis installer une destination indépendante.
3. Profilage sur volumes comparables à la production.
4. Intégration V4 avec réservations Telegram transactionnelles et reprise contrôlée.
