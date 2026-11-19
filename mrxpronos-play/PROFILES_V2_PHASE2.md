# Mr XPRONOS Play — V2 / Phase 2 : profils évolutifs

**Objectif :** des profils de joueurs prestigieux, avec les onze avatars africains déjà existants, des badges et étoiles provisoires, la collection des rangs débloqués et les conditions détaillées du prochain rang.

## État fonctionnel

- Les avatars de rang 1 à 11 sont les fichiers présents dans `assets/07-rank-avatars/`. Aucune régénération d’icônes n’a été nécessaire.
- L’**avatar automatique** correspond au rang officiel du joueur, calculé sur le serveur à partir des XP confirmés et des défis (phase 1).
- Le joueur peut choisir **un ancien avatar déjà débloqué**. Le choix est conservé entre les appareils par Cloudflare D1 et associé à son identité Telegram signée.
- **Le badge, le nom du rang, les étoiles et les conditions de progression correspondent toujours au véritable niveau**, même lorsque le portrait affiché est un rang inférieur.
- Les avatars non obtenus sont grisés et verrouillés : le bouton est désactivé et indique le niveau à atteindre. La vérification existe également côté serveur.
- « Utiliser automatiquement mon meilleur avatar » efface le choix manuel en enregistrant `selected_rank=0`.
- L’effet de montée en rang est une animation CSS légère, désactivée quand l’appareil demande une réduction des animations. Les badges et étoiles sont **temporaires** jusqu’au lot de visuels définitifs.
- Les portraits Telegram ne sont pas utilisés pour définir l’apparence du joueur.

## Règles de collection

| Avatar | Nom | Niveau requis |
|---:|---|---|
| 1 | Recrue | 1 |
| 2 | Éclaireur | 2 |
| 3 | Combattant | 3 |
| 4 | Sentinelle | 5 |
| 5 | Chevalier | 6 |
| 6 | Élite | 10 |
| 7 | Maître | 15 |
| 8 | Champion | 20 |
| 9 | Légende | 30 |
| 10 | Mythique | 40 |
| 11 | Souverain MX | 50 |

Les rangs sont permanents : une fois obtenus, leurs avatars restent utilisables. Le niveau officiel ne diminue jamais et le mode portrait « ancien rang » n’a **aucun effet sur les XP, crédits, missions, classements ou éventuels boosts**.

## Détails du prochain rang

La page Profil affiche :

- Le rang suivant, son niveau minimum et son seuil cumulé de XP confirmés.
- Les XP supplémentaires nécessaires.
- Le nombre de défis de maîtrise requis et déjà réalisés.
- Jusqu’à trois défis inachevés les plus proches d’être réalisés.
- La jauge de progression XP de la phase 1.
- Les cinq étoiles de prestige **provisoires** au fil de l’avancement dans le rang officiel.

Pour le niveau 50, « Souverain MX » remplace la condition du prochain rang.

## Architecture technique

La migration additive `migrations/003_avatar_profiles.sql` crée uniquement :

```sql
CREATE TABLE IF NOT EXISTS player_avatar_prefs (
  user_id TEXT PRIMARY KEY REFERENCES players(user_id),
  selected_rank INTEGER NOT NULL DEFAULT 0 CHECK (selected_rank BETWEEN 0 AND 11),
  updated_ms INTEGER NOT NULL
);
```

`selected_rank=0` signifie « utiliser automatiquement le rang officiel ». L'absence d’une ligne a le même sens et garantit la compatibilité avec les comptes préexistants.

### API privée

Ces routes exigent toujours `x-telegram-init-data` signé et contrôlé côté Worker :

- `GET /api/profile` : renvoie la progression officielle et la collection avec états `unlocked`, `current` et `selected`.
- `POST /api/profile/avatar` : corps `{"rank":0..11}`; 0 revient au mode automatique, les autres valeurs sélectionnent un avatar précédemment débloqué.
- `GET /api/bootstrap` : retourne maintenant aussi `profile` pour éviter une requête supplémentaire au lancement.

Une requête invalide est rejetée (400), un choix verrouillé retourne une erreur 403, et un client non authentifié reçoit 401. Aucun client ne peut déclarer son propre niveau ou débloquer un avatar via le corps de requête.

## Compatibilité et sécurité

- `players`, `player_progress_v2`, `mission_claims`, `daily_claims`, `wheel_claims`, `sync_receipts` restent inchangés.
- Le choix du portrait est **cosmétique**, isolé par utilisateur et stocké séparément.
- Si l’utilisateur progresse et qu’il est en mode automatique, le portrait affiché suit son nouveau rang.
- Si l’utilisateur a choisi un ancien avatar, ce choix reste actif après progression jusqu’à l’utilisation du bouton automatique.
- Les avatars sont chargés en WebP depuis GitHub, avec chargement différé dans la collection, et aucune photo personnelle Telegram n’est nécessaire.
- Les contrôles de confidentialité, signature Telegram, modération des actions et délai de synchronisation de 12 h restent ceux de la phase 1.

## Test et critères de fin

- [ ] 11 avatars affichés dans la collection (rangs verrouillés et débloqués).
- [ ] Seuls les rangs réellement atteints peuvent être sélectionnés.
- [ ] Choix mémorisé après fermeture/réouverture, sur le même compte Telegram.
- [ ] Un second compte Telegram ne récupère pas le choix d’un premier compte.
- [ ] Le choix d’un ancien portrait ne modifie pas le rang officiel et ses badges.
- [ ] Retour au mode automatique fonctionnel.
- [ ] Les étoiles et la progression reflètent le niveau officiel.
- [ ] Les conditions du prochain rang s’affichent correctement.
- [ ] Le rang Souverain MX affiche l’état final au niveau 50.
- [ ] Les anciens comptes n’ont aucune donnée perdue après la migration.
- [ ] Les tests CI passent et le Worker est déployé, avec les secrets/bindings existants.

## Étapes suivantes

La **phase 3** portera sur les cartes de profil partageables (formats carré et vertical), puis les **phases 4 et 5** sur les crédits MRXP gratuits et la boutique de boosts. Les icônes définitives seront créées après le développement des fonctions, selon la consigne du projet.
