# Telegram BSD V2 — Ticket football inspiré du modèle fourni (2026-10-08)

## Emplacements implémentés

1. Bandeau noir en haut : **logos 1XBet et MelBet déjà stockés sur le site** (`assets/images/1xbet.webp`, `assets/images/melbet.webp`), "ou", cartouche jaune `Code Promo: XPVIP`.
2. Zone identité : **PNG football existant** `assets/images/bsd-football-generated.png`, horodatage, "Simple", identifiant BSD. Suppression du badge rouge "À venir".
3. Résumé de prix aligné sur deux colonnes : **Cotes**, **Mise** (500 000 F), **Gains potentiels** (cote × 500 000 F), **Statut** ("Pronostic", ou "Pronostic gagnant" après vérification). Ne jamais afficher "Payé" ou "Accepté", car ce ne sont pas des tickets réels.
4. Encadré rencontre : PNG football, compétition, date/heure UTC.
5. Ligne équipes : **nom domicile**, **écusson domicile**, **VS ou score final**, **écusson visiteur**, **nom visiteur**, avec espace et retours de ligne.
6. Zone sélection : marché BSD original à gauche, cote réelle BSD à droite.
7. Zone statut match : `Pronostic` ou `Gain` pour un choix vérifié gagnant.
8. Bas de carte : `Parier responsablement.` uniquement.
9. Légende Telegram : marché, match, `Parier responsablement.`
10. Boutons dans les deux cas (prédiction et gain) :
    - `Voir plus de coupons 🔥` → https://mrxpronos.github.io/MrXPRONOS_App/pronos.html
    - `S’inscrire ou réinitialiser son compte 🎯` → https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html

## Logo des équipes

Le site BSD remplit parfois `home_logo`/`away_logo` avec une chaîne vide : constaté dans `data.json`. Le moteur PNG tente d'abord un URL sécurisé fourni par BSD, puis une recherche **exacte** sur TheSportsDB si le nom est non ambigu. Il vérifie que le sport est Soccer, limite les domaines et la taille de téléchargement, et cache la recherche pendant l'exécution. Si aucune image fiable n'est trouvée, un monogramme neutre est affiché : aucun mauvais écusson n'est inventé.

L'accès aux écussons dépend des services externes : 100 % de récupération n'est pas garanti.

## Vérification

- Contrôles statiques des quinze points demandés : tous correspondent dans les fichiers GitHub.
- Tests ajoutés dans `bsd/test_bsd_v2_cards_verify.py` : assets de marques, format du nouveau ticket, découpages des noms, étiquetage BSD, échec sans réseau, résolution exacte des écussons, textes/URL des boutons.
- **Non encore vérifié** : exécution GitHub Actions, rendu réel sur Telegram, disponibilité effective des écussons chez TheSportsDB.

La forme de l'image est une **présentation des pronostics**, pas une capture certifiée 1XBet/MelBet. Le montant 500 000 F correspond à une mise de référence non encaissée.
