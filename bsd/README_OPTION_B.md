# MR XPRONOS — Audit Option B (8 octobre 2026)

## Les six améliorations

| # | Amélioration demandée | Livrables GitHub | Validation restante |
|---|---|---|---|
| 1 | Seuils spécifiques aux doubles chances, BTTS et Over/Under | Profils distincts dans BSD V2, majorations prudentes fondées sur les écarts de calibration du jeu de validation fin 2025 | Rentabilité non mesurable sans véritables cotes BSD historiques ; contrôle CI à confirmer |
| 2 | Couverture des équipes et des championnats | Minimum 4 matchs au calcul, lissage de ligue renforcé, et ligue qualité à 15 | Évaluer le Brier et la couverture sur les données historiques |
| 3 | Diagnostic complet des rejets | Chaque match possède cotes BSD, sélections examinées, probabilités et raisons de rejet. Rapport `bsd/rejections_report.json` disponible en artefact de workflow | Production du premier rapport CI à vérifier |
| 4 | Combinaison de 2 matchs cotés à 1,20+ | `bsd/bsd_v2_combos.py`, carte sombre `bsd/bsd_v2_combo_card.py`, deux matchs distincts, cote multipliée, mise de référence et suivi d'envoi Supabase | Vérifier un envoi réel Telegram ; notification GAIN du combiné non couverte |
| 5 | Minimum 4 matchs au calcul / 5 au contrôle qualité | `MIN_TEAM_GAMES = 4` et `V2QualityPolicy(min_form=5)` | Contrôle CI à confirmer ; modèles spécialisés peuvent encore demander davantage de matchs |
| 6 | Deux pronostics par match | Champ historique `prediction` maintenu et champ optionnel `predictions` (jusqu'à 2), familles de marchés distinctes, site et Telegram adaptés ; suivi de chaque résultat séparément | Vérifier un vrai match avec 2 marchés coté BSD ; pas de deuxième pronostic forcé |

## Couverture des tests

- `bsd/test_bsd_v2_combos.py` : cote de combiné, éligibilité horaire, matchs distincts, rendu PNG et résultats individuels gagnant/perdant.
- `bsd/test_bsd_v2_market_capacity.py` : calcul sur 4 matchs, contrôle qualité sur 5, audit des cotes et sérialisation de deux marchés.
- `.github/workflows/bsd-v2-ci.yml` : compilation Python, régression BSD, vérification syntaxique JavaScript.
- `.github/workflows/bsd-v2-production.yml` : contrôles du flux produit, export du rapport de rejets en artefact, retrait des fichiers privés avant GitHub Pages.
- `.github/workflows/bsd-v2-telegram-hourly.yml` : passage à 05, 20, 35 et 50 minutes après chaque heure ; combiné prévu autour de 45 à 65 minutes avant le premier coup d'envoi.

## Sécurité des données

Les données historiques ne contiennent pas nécessairement de cotes bookmaker vérifiées. Aucun rendement financier historique n'est reconstruit artificiellement. Une mise affichée à 500 000 FCFA est une référence théorique, pas un pari accepté, et le gain potentiel n'est pas un paiement.

Les combinés sont enregistrés dans Supabase avec un type de message distinct pour éviter les doublons ; la notification du résultat d'un combiné n'est pas encore intégrée. Les pronostics individuels, y compris les deux marchés éventuels d'un même match, conservent leur suivi indépendant.

**État : fichiers GitHub committés, mais exécution GitHub Actions et envoi réel Telegram non encore confirmés.**


## Modification des règles des combinés — 8 octobre 2026

**Important : cette section remplace les anciennes descriptions des limites de cotes.**

- Un combiné contient exactement **deux matchs différents**.
- **Chaque sélection du combiné doit avoir une cote BSD authentifiée 1,01 <= cote < 1,50**.
- Les cotes **1,50 ou davantage** ne peuvent jamais constituer une jambe de combiné, même avec un match à faible cote.
- La restriction de 1,20 ne s'applique plus aux combinés. Les cotes **1,01 à 1,19** sont conservées uniquement si la probabilité prudente du modèle est d'au moins 90 % ; ce seuil reste un filtre prudent, non une garantie.
- Les pronostics simples demeurent soumis à leur filtre individuel **>= 1,20** et à leur marge de sélection ; les choix à moins de 1,20 ne sont **pas envoyés seuls sur Telegram**.
- Pour chaque match, le générateur peut enregistrer un marché séparé `combo_prediction` strictement sous 1,50, même si sa sélection individuelle principale est à 1,50 ou plus.
- Le moteur de combinés examine `combo_prediction`, `prediction` et `predictions`, retient au maximum une sélection pour un même match et associe uniquement deux événements distincts.
- Sur le site, **chaque sélection individuelle est présentée dans sa propre fiche** (y compris dans l'historique) ; aucune section « Pronostic 2 » n'est intégrée à la fiche du premier.
- Les matchs `combo_only` (sélection principale < 1,20) sont conservés dans `data.json` pour Telegram combiné, mais ne sont pas affichés comme pronostics individuels sur le site.
- Sur Telegram, les deux sélections individuelles sont suivies et envoyées séparément lorsque la cote de chacune est >= 1,20. Les combinés ont leur propre envoi et leur propre identifiant de dédoublonnage.
- **Under 4,5 reste entièrement interdit.**

### Tests de cette modification

`bsd/test_bsd_v2_combos.py` vérifie les limites (1,01 inclus, 1,50 exclu), la non-association d'un même match et la possibilité d'un `combo_prediction` à faible cote lorsque la sélection principale est à plus de 1,50.

`bsd/test_bsd_v2_market_capacity.py` vérifie le choix des marchés à 1,01–1,19 seulement pour l'usage combiné, à condition d'avoir une probabilité prudente élevée.

**Validation à terminer :** nouvelle génération de `data.json`, exécution des tests GitHub Actions et envoi réel du premier combiné correspondant aux règles actualisées.


## Coupons nuit — diffusion groupée à 20 h (heure du Togo)

Pour chaque date D en heure locale Togo (UTC toute l'année) :
- **20 h 00–20 h 59 le jour D** : les passages du robot regroupent les coupons de la nuit. Le workflow actuel s'exécute normalement à **20 h 05, 20 h 20, 20 h 35 et 20 h 50 UTC** ; dès le premier passage réussi, les coupons sont marqués dans Supabase. Les passages suivants constituent des essais de rattrapage uniquement pour les messages non enregistrés.
- Sont concernés les coups d'envoi entre **21 h le jour D** et **05 h 00 le jour D+1**. Les matchs à 00 h, 01 h, etc. sont attribués à la campagne du soir précédent. Après 05 h, la diffusion ordinaire reprend.
- Chaque message contient le titre **« 🌙 Coupons nuit »**, le coupon et ses deux boutons. Les pronostics restent des images individuelles, mais partent dans la même campagne.
- Les combinés de nuit ne regroupent que des matchs appartenant à cette fenêtre, selon les conditions de cotation déjà fixées : chaque cote BSD **1,01 à moins de 1,50**, deux matchs différents.
- Un match classé « Coupons nuit » **n'est plus publié** dans les envois ordinaires une à deux heures avant coup d'envoi. Les mêmes identifiants Supabase empêchent les répétitions entre passages.
- Un retard de démarrage des GitHub Actions ou un échec réseau peut décaler des messages : l'envoi à exactement 20 h 00 ne peut pas être garanti sur un système à planification GitHub.
- Vérifications automatisées : `bsd/test_bsd_v2_night.py` (bornes de nuit, passage de minuit, regroupement, exclusion du flux ordinaire et simulation d'envoi).


## Barème indicatif des mises Telegram

**Mises des pronostics simples selon la cote BSD :**

| Cote du simple | Mise affichée |
|---|---:|
| 1,20 à 1,99 | 500 000 F CFA |
| 2,00 à 2,49 | 400 000 F CFA |
| 2,50 à 2,99 | 300 000 F CFA |
| 3,00 à 3,99 | 200 000 F CFA |
| 4,00 à 100,00 | 100 000 F CFA |

**Combinés (exactement deux matchs) : 250 000 F CFA**, indépendamment de la cote combinée, dont chaque élément reste compris entre 1,01 et moins de 1,50.

Les montants affichés sur les images Telegram (y compris les images de pronostics gagnants) proviennent du module commun `bsd/bsd_v2_stakes.py`. Les gains affichés sont le **retour potentiel brut théorique** (mise × cote), pas un gain effectivement versé. Sans cote BSD admissible, aucune mise fictive n'est fabriquée.

Tests unitaires : `bsd/test_bsd_v2_stakes.py`, dont les frontières 1,99/2,00, 2,49/2,50, 2,99/3,00 et 3,99/4,00. À vérifier ensuite dans la suite GitHub Actions.


## Légendes stylées Telegram (HTML)

Toutes les légendes des images BSD V2 sont désormais construites dans `bsd/bsd_v2_captions.py` et transmises à l'API Telegram avec `parse_mode=HTML` :

- **Coupon du jour** : titre gras, introduction italique, match en gras, bloc de citation pour sélection/cote/mise indicative, heure du Togo et rappel 18+.
- **Coupons nuit** : identité « 🌙 Coupons nuit », introduction propre à la campagne 20h, puis les mêmes informations par coupon individuel.
- **Combiné (jour et nuit)** : les deux matchs et leurs marchés dans un bloc de citation, cote combinée, mise indicative de 250 000 F CFA et horaire du premier match.
- **Pronostic gagnant** : résultat et sélection validés, avec présentation sobre qui ne prétend pas qu'un bookmaker a effectivement payé un pari.

Les variables d'équipes, les noms des marchés et autres champs BSD sont échappés avec `html.escape`. Les deux boutons Telegram restent inchangés. Tests : `bsd/test_bsd_v2_captions.py`.

Ces messages sont un rendu de pronostics, pas des tickets de paris acceptés ni des garanties de gains.


## Refonte visuelle des coupons : écran clair de référence (9 octobre 2026)

- Le rendu graphique pour **Simple / Journée, Coupons nuit, Gagnant, Combiné** partage les fonctions du nouveau module `bsd/bsd_v2_ticket_ui.py`.
- Palette blanche et gris pâle, bleus de la référence, barre supérieure, informations du coupon, cinq lignes de synthèse, sous-carte par match, noms/logos/VS/noms et séparateurs fins.
- Les logos des deux équipes sont récupérés de sources BSD autorisées ; si le vrai logo n'est pas disponible, un rond neutre avec les initiales remplace le logo (il est interdit d'inventer un écusson).
- Les identifiants visuels enlèvent les préfixes techniques `bsd:` / `combo:` ; la référence complète reste identique pour les traitements internes.
- En raison du caractère **prévisionnel** des coupons MR XPRONOS, la disposition visuelle est celle de la référence mais le statut indique **Simulation** ou **Pronostic gagnant**, pas « Accepté/Payé » : ces derniers prétendraient à tort qu'un bookmaker a réellement validé ou réglé un pari. La ligne « Versé » reste à « — » car aucun dépôt ni règlement n'est vérifié.
- Les mises et gains sont donnés à titre théorique selon `bsd_v2_stakes.py`. Le rappel 18+ reste dans la légende Telegram.
- Nom de ligue : ne jamais répéter `Football. Football`. Les ligues sont reprises directement des événements BSD, de l'ancien feed ou recherchées dans le catalogue officiel `/leagues/` avec pagination limitée. En dernier recours, « Football · Compétition n° … » est affiché si seul un identifiant est connu.
- **Aucune modification** de la sélection du marché, des cotes réelles BSD, des règles de combiné, des seuils de confiance ni des horaires Telegram.
- Tests ajoutés : `bsd/test_bsd_v2_ticket_ui.py`, en complément des tests des images simples et combinées adaptés aux dimensions (1080×1080 et 1080×1580).

**Vérification finale du design :** les fichiers et tests ont été enregistrés sur GitHub, mais les jobs GitHub Actions et un envoi image réel doivent être observés avant de confirmer une reproduction visuelle intégrale.


## Audit des endpoints images BSD (9 octobre 2026)

Endpoint public officiel des clubs : `https://sports.bzzoiro.com/img/team/{id}/?bg=transparent`.
Endpoint public officiel des compétitions : `https://sports.bzzoiro.com/img/league/{id}/?bg=transparent`.
Catalogue : `GET /api/v2/leagues/` ; détail : `GET /api/v2/leagues/{id}/`.

- `bsd/bsd_v2_assets.py` génère les URL uniquement à partir d'IDs BSD numériques positifs et n'accepte ni chemin arbitraire ni ID nul.
- `bsd/bsd_v2_publish.py` renseigne désormais `home_logo`, `away_logo`, `league_logo` dans le JSON, y compris pour les matchs archivés. Les noms de ligues manquants sont recherchés dans le catalogue puis dans les détails officiels.
- `bsd/bsd_v2_card.py` donne priorité au logo BSD officiel, contrôle l'hôte HTTPS, refuse les redirections et les images excessives, et conserve un repli si la ressource échoue.
- `bsd/bsd_v2_ticket_ui.py` affiche le logo de compétition officiel à la place du pictogramme générique, avec pictogramme neutre en cas d'indisponibilité.
- Le `data.json` existant a reçu les **84 liens** des images d'équipes/ligues (28 rencontres) et perdu ses faux intitulés `Football`. Ses vrais noms de championnats sont encore absents et seront résolus lors d'une prochaine génération BSD authentifiée.
- Tests hors ligne : `bsd/test_bsd_v2_assets.py`. Les appels HTTP en direct depuis l'environnement actuel n'ont pas pu établir de connexion ; **la disponibilité HTTP 200 et la compatibilité du contenu doivent encore être confirmées sur GitHub Actions avec le réseau**, avant d'affirmer une vérification intégrale.

Ne jamais interpréter une URL théorique comme la preuve qu'un logo distant existe.
