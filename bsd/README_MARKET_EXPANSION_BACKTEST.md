# Recherche BSD V2 : sept nouvelles familles de paris

Branche de recherche sans modification des pronostics publies ou du bot Telegram.

**Nouvelles familles** : buts domicile >0,5 ; buts exterieur >0,5 ; buts domicile <1,5 ; buts exterieur <1,5 ; handicap +1,5 (domicile/exterieur) ; Draw No Bet (domicile/exterieur, match nul = remboursement) ; total de buts en premiere periode <1,5. Elles representent 9 selections concretes. Le systeme couvre aussi les 16 anciens codes.

**Evaluation** : exercice sur chaque rencontre terminee disponible dans l'archive 2024-2026. Historique 2024 utilise dans l'ajustement des modeles, 2025 pour la calibration, 2026 pour le test temporel. Toutes les rencontres sont etudiees pour chaque marche, pas seulement les selections que l'ancien moteur publiait. Les probabilites des anciens marches reappliquent les sous-modeles V2 : buts totaux, BTTS, resultats/double chance.

**Audit** : recoupement des scores et des gains/pertes du marche original avec le registre immutable `bsd/publication_ledger.json`, sur les matchs communs 2026. Attention, les marches originaux publies ne doivent pas etre confondus avec les probabilites de tous les candidats : historique des choix, marche et controles de publication sont differents.

**Limitations** : aucune cote bookmaker historique universelle n'est fournie : ROI, filtre de cotes 1,40-1,55 et probabilite de reussite d'une montante ne sont pas verifiables sur cette archive. Pour le DNB, un match nul est rembourse et n'est pas une perte. Pour la mi-temps, aucun resultat n'est infere : si le schema de l'archive ne contient pas d'observation mi-temps, le backtest renverra des donnees absentes au lieu d'une statistique trompeuse. La probabilite mi-temps est un indicateur de recherche si au moins 100 matchs 2024 possedent un vrai score HT.

**Lancer** : GitHub Actions, workflow `BSD V2 - Backtest tous les marches (recherche)`, `Run workflow`, branche `analyse/bsd-v2-sept-marches-backtest-20261102`, `max_matches=0`. Le secret BSD_HISTORY_KEY doit etre configure. Le rapport sera telechargeable comme artifact `bsd-v2-all-markets-backtest`. **Aucun envoi automatique en production.**
