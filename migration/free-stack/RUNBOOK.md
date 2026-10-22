# Exécution contrôlée du transfert PostgreSQL

## État
Le workflow `.github/workflows/neon-full-db-stage.yml` a été ajouté **sur la branche de migration uniquement**. GitHub exige généralement qu'un workflow `workflow_dispatch` soit présent sur la branche par défaut pour le déclencher depuis l'interface Actions ; le commit sur une branche ne l'exécute pas. Aucun dump complet n'a donc été lancé.

Ne pas fusionner ce workflow pour le seul motif de le rendre exécutable sans avoir sécurisé les secrets et validé le plan d'exécution. Le processus de restauration devra gérer certaines fonctions SQL incompatibles avec Neon (notamment les références `auth.*` Supabase), sinon `pg_restore --exit-on-error` stoppera avec un échec attendu.

## Secrets nécessaires, jamais affichés dans les logs
- `SUPABASE_DB_URL`: chaîne de connexion PostgreSQL **en lecture** si possible, pointant sur la source Supabase
- `NEON_STAGING_DB_URL`: connexion privilégiée seulement sur la base Neon vide `mrxpronos_full_stage` (et jamais la base test `mrxpronos`)

Configurer les valeurs dans les secrets du dépôt ou dans une exécution de migration isolée et éphémère. Les secrets GitHub ne peuvent pas être supposés présents. Éviter d'utiliser le rôle super-admin en dehors du staging.

## Limitations et validation préalable
- La copie du schéma `public` n'inclut **pas** les comptes Supabase Auth, les objets Storage, les webhooks, les fonctions Edge ni les secrets.
- La restauration directe peut échouer sur les dépendances `auth.uid()` et autres fonctions dépendant de Supabase ; préparer l'adaptation avant l'exécution.
- La comparaison des nombres de lignes est un premier contrôle, **pas** une preuve d'intégrité complète ; vérifier identifiants et empreintes, séquences, contraintes, fonctions, politiques RLS et triggers.
- Supabase continue à recevoir des écritures. Une copie ponctuelle ne suffit pas : effectuer une synchronisation différentielle ou un cutover avec interruption d'écriture maîtrisée avant production.
- Aucune publication sur le site public, aucune modification des URLs, aucun déploiement de fonctions à ce stade.

## Critères de bascule
1. Schéma portable intégralement restauré et routines testées.
2. Données rapprochées table par table, séquences synchronisées.
3. Média : 113 objets et environ 215 Mo migrés avec validation de taille et empreinte.
4. Fonctions HTTP, authentification, RLS, permissions VIP et admin revues.
5. Chronjobs, Telegram, LIVE, CMS, push, publications et assistant testés en bout en bout.
6. Tests de charge/quotas et plan de retour arrière validés.
