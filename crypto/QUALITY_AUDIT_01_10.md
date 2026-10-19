# AUDIT DES DIX AFFICHES ACTU CRYPTO — MR XPRONOS

Audit visuel fondé sur les captures de production fournies (#01/#02/#03/#05/#06/#07) et la capture antérieure de #09 ; examen des générateurs GitHub des dix rubriques. Pour #04, #08 et #10, seules des maquettes ou des captures de tests existent : elles **ne valent pas validation d'une publication réelle**.

## Défauts et corrections, rubrique par rubrique

| N° | Défauts relevés | Corrections intégrées | État / limites |
|---|---|---|---|
| 01 | Capitalisation et volume CoinLore multipliés par 1 000 000 000 ; mélange $/T/B/UTC ; courbe 48h colorée selon pourcentage 24h | Unités natives USD, contrôle d'ordre de grandeur avant photo, Md USD francophone, prix adaptés, couleur selon courbe 48h, collision CSS surveillée | Corrigé dans le code et les QA ; message historique Telegram n°2 non modifié |
| 02 | Arrondi des microprix (PEPE à 6 décimales) ; logos carrés/cercles non homogènes ; barres de variation relative peu expliquées | Précision variable de 6 à 12 décimales, prix Telegram sans faux « 0.00 », conteneurs circulaires premium, étiquette de meilleure hausse | Corrigé en QA ; harmonisation des logos sources externes imparfaite |
| 03 | Même erreur ×1e9 que #01 ; badges de logos de styles différents ; couleurs 48h dépendant de variation 24h | Valeurs mondiales corrigées et contrôlées, unités Md USD, couleurs de courbes propres à 48h, cadres homogènes et vérification anticollision | Corrigé dans le code et en QA ; ancien message Telegram n°8 non modifié |
| 04 | Pas de preuve de franchissement instantané à partir d'un snapshot 24h ; courbe 48h possible avec seulement 12 valeurs ; notation USD non francophone | Terminologie « palier observé », 36 observations minimum pour une vraie courbe, format USD francophone, couleur de courbe selon 48h | Vérifié seulement avec maquette (aucune alerte réelle confirmée lors du lancement initial) |
| 05 | Dégradé horizontal incohérent avec aiguille angulaire ; zones d'indice non proportionnelles ; ancien test figé expiré | Cinq arcs correspondant aux limites 0–24/25–44/45–54/55–74/75–100 ; échelle proportionnelle ; dates de test dynamiques | Correction automatisée vérifiée en QA ; contrôle esthétique visuel final encore à réaliser |
| 06 | « 2,72 billions $ » ambigu ; garde d'unités trop permissive | Affichage clair en milliards USD, vérification partagée des ordres de grandeur à la source | Corrigé en QA ; ancien PNG historique non modifié |
| 07 | Dates US MM/JJ sous les 8 observations ; « billions $ » ; BTC/ETH en médailles génériques plutôt qu'assets approuvés | Dates JJ/MM, montants Md USD, images premium BTC/ETH communes, contrôle financier source | Corrigé en QA ; ancien PNG historique non modifié |
| 08 | La concordance lexicale automatique de deux flux RSS était présentée comme une confirmation factuelle | Formules « rapporté par deux médias » et « titres recroisés » ; maintien des deux sources et interdiction des simulations en production | Partiel : le rapprochement de titres ne suffit pas à une vérification éditoriale humaine ; pas de breaking réel garanti |
| 09 | Un article SEC/tokenisation/OKX faussement classé FRAIS & TRADING ; OKX mentionné mais pas sujet principal ; icône à flèches ressemblant à un faux logo | Filtre « régulation => rubrique 10 », plateforme doit être sujet initial, regression sur le titre litigieux, illustration réseau neutre | Partiel : titres journalistiques anglais conservés pour éviter une traduction infidèle ; ancien message Telegram n°6 non modifié |
| 10 | Statut juridique déduit provisoirement d'un titre ; pas de garantie sur la date d'entrée en vigueur ou la juridiction | Maquette indique validation humaine et statut provisoire ; aucune diffusion réglementaire réelle avant approbation | Partiel et volontairement bloqué : pas d'approbation juridique ni publication réelle |

## Procédure technique contrôlée
`API/RSS publics → Python validation des unités/fraîcheur → JSON → Playwright/HTML/SVG → PNG 1080×1350 → contrôle anti-doublon → Telegram seulement si réel admissible`.

Le protocole QA crée dix PNG **fictifs et marqués non publiables** : #01–03 par `crypto/quality_layout_fixtures.py`, #04–10 par leurs modes `--demo`. Ils valident la mécanique et la mise en page, **pas la fraîcheur de dix nouvelles réelles**.

Contrôles : source USD native CoinLore, borne de capitalisation/volume, prix minuscules, suffixes français, dates, classifications éditoriales, human review #10, limites de visuel 1080×1350, prévention collision pour #01/#03. Exécution : `.github/workflows/actu-crypto-quality-audit.yml`. Artefacts visibles sous l'exécution GitHub Actions de la branche `fix/actu-crypto-10-quality-audit`.

## Production et historique
Les sept messages historiques Telegram du 18 octobre restent archivés sous leurs identifiants 2 à 8. La modification du code ne change pas rétroactivement les photos déjà envoyées. Le déploiement n'implique **aucune nouvelle publication immédiate** ni insertion de données fictives dans `@actucrypto_mrxp`.

Après validation automatique, fusionner les correctifs pour les **prochaines** publications. Les n°08/09 nécessitent toujours des améliorations sémantiques avant de pouvoir être qualifiés entièrement ; le n°10 exige une revue humaine. Une correction des messages historiques inexacts doit être décidée séparément (édition/suppression/remplacement avec données réelles de même date si disponibles).

Référence API USD : https://dev.coinlore.com/cryptocurrency-data-api
