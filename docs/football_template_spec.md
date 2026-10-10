# Spécification des templates Telegram Mr XPRONOS

Référence de rendu : **1080 x 1080 px**.
Origine des coordonnées : `(0,0)` en haut à gauche.

Les PNG sources peuvent être plus grands (ex. 1254 x 1254), mais le renderer les normalise à 1080 x 1080 avant toute injection.

## Règles globales

- Les cadres, cercles, capsules, titres, séparateurs et CTA appartiennent au PNG : **ne pas les redessiner**.
- Les textes dynamiques sont mesurés en pixels avec Pillow `textbbox()`.
- La limite en caractères est seulement un garde-fou.
- Noms d'équipes : une seule ligne, réduction de police puis ellipsis.
- Flash / question sondage : retour à la ligne uniquement entre les mots.
- Logos : `contain` / `thumbnail`, jamais étirer ni recadrer.
- Emojis interdits dans les images générées si la police ne les supporte pas.
- Lato Bold pour les données fortes, Lato Regular pour date/résumé.
- Seul `template_stat_du_jour.png` contient encore des placeholders à effacer localement.

## 1. Matchs du jour

### Date
- box : `(465,251)-(680,300)`
- 10 caractères (`DD/MM/YYYY`)
- 24 px Bold, min 20 px

### 5 lignes
Centres Y : `371, 487, 602, 717, 833`

- logo gauche centre X : `140`
- logo droite centre X : `941`
- logo max : **60 px**
- heure centre X : `540`
- heure max 5 caractères (`19h00`), 21 px Bold

Nom gauche / droite :
- ligne 1 : `(189,346)-(431,394)` / `(650,346)-(891,394)`
- ligne 2 : `(189,462)-(431,510)` / `(650,462)-(891,510)`
- ligne 3 : `(189,577)-(431,625)` / `(650,577)-(891,625)`
- ligne 4 : `(189,692)-(431,741)` / `(650,692)-(891,741)`
- ligne 5 : `(189,808)-(431,856)` / `(650,808)-(891,856)`

Police nom :
- <=19 caractères : 24 px
- <=21 : 22 px
- <=24 : 20 px
- <=28 : 18 px
- au-delà : 17 px + ellipsis

`VS` est statique dans le template.

## 2. Avant-match

### Logos
- gauche : `(237,431)`
- droite : `(842,431)`
- max : **105 px**

### Noms
- gauche : `(112,521)-(362,564)`
- droite : `(719,521)-(969,564)`
- <=17 caractères : 28 px
- <=20 : 25 px
- <=23 : 22 px
- <=28 : 19 px
- au-delà : 17 px + ellipsis

### Heure
- box : `(455,405)-(625,462)`
- 5 caractères
- 36 px Bold, min 30 px

### Forme récente
Centres gauche : `(227,699) (282,699) (336,699) (391,699) (445,699)`
Centres droite : `(624,699) (679,699) (734,699) (789,699) (843,699)`
- une lettre `V`, `N` ou `D` par cercle
- 16 px Bold
- points : `9/15 pts`, 16 px Bold
- ne pas réécrire les noms d'équipes dans cette zone

### Date
- `(482,840)-(689,883)`
- 18 px Regular

## 3. Résultat final

### Logos
- gauche : `(216,487)`
- droite : `(862,487)`
- max : **125 px**

### Noms
- gauche : `(99,594)-(336,642)`
- droite : `(745,594)-(982,642)`
- <=16 caractères : 29 px
- <=19 : 26 px
- <=22 : 22 px
- <=25 : 18 px
- au-delà : 18 px + ellipsis

### Score
- `(394,437)-(687,576)`
- 68 px Bold
- max 7 caractères (`12 - 10`)

### Verdict
- `(310,663)-(771,711)`
- `VICTOIRE • équipe` ou `MATCH NUL`
- <=32 caractères : 28 px
- <=38 : 24 px
- <=45 : 20 px
- au-delà : 18 px + ellipsis

### Date
- `(508,831)-(663,874)`
- 18 px Regular

## 4. La stat du jour

### Valeur
- `(356,405)-(723,574)`
- 1-2 caractères : 92 px
- 3 : 82 px
- 4 : 72 px

### Type de stat
- `(370,577)-(711,613)`
- <=18 caractères : 22 px
- <=24 : 19 px
- au-delà : 17 px + ellipsis

### Logos
- gauche : `(164,691)`
- droite : `(915,691)`
- max : **64 px**

### Noms
- gauche : `(215,667)-(431,715)`
- droite : `(655,667)-(870,715)`
- <=15 caractères : 27 px
- <=18 : 23 px
- <=21 : 20 px
- <=24 : 17 px
- au-delà : ellipsis

### Score
- `(463,658)-(617,724)`
- 34 px Bold
- max 7 caractères

### Date
- `(508,896)-(655,939)`
- 18 px Regular

`FOOTBALL` et les textes explicatifs restent statiques dans le PNG.

## 5. Flash Foot

### Photo
- `(79,234)-(1001,606)`
- **922 x 372 px**
- `ImageOps.fit`
- radius **27 px**
- aucun contour supplémentaire

### Titre
- `(125,644)-(792,699)`
- max 2 lignes
- <=43 caractères : 30 px
- 44-100 : 26 px avec wrap
- max total 100 caractères, puis ellipsis

### Source
- `(125,704)-(603,736)`
- 17 px Bold
- max 50 caractères

### Date
- `(736,699)-(818,734)`
- 15 px Regular
- 10 caractères

### Résumé
- `(267,797)-(956,868)`
- max 3 lignes
- 17 px Regular
- max **180 caractères**
- couper au dernier mot puis ellipsis

### CTA
- `(336,932)-(810,980)`
- 20 px Bold
- texte fixe : `LIRE L’ARTICLE COMPLET`

## 6. Sondage / Débat

### Question
- `(129,349)-(952,435)`
- max 2 lignes
- <=52 caractères : 30 px
- 53-100 : 26 px
- au-delà : 100 caractères + ellipsis
- ne jamais réécrire `MR XPRONOS / LE DÉBAT DU JOUR`

### Options
- option 1 : `(293,508)-(861,560)`
- option 2 : `(293,634)-(861,686)`
- option 3 : `(293,760)-(861,812)`
- <=32 caractères : 24 px
- <=45 : 20 px
- au-delà : 17 px + ellipsis
- une seule ligne

### Icônes / logos
Centres : `(155,534) (155,660) (155,786)`
- logo équipe domicile : max **52 px**
- option `Match nul` : signe `=` 26 px Bold
- logo équipe extérieure : max **52 px**
- pas d'emoji dans l'image

### Date
- `(491,868)-(680,909)`
- 18 px Regular

## Contrôle obligatoire

Chaque modification du renderer doit conserver :
1. output exactement `1080x1080`;
2. données dynamiques dans les boxes ci-dessus;
3. aucun gros rectangle ajouté au-dessus du template;
4. aucun logo déformé;
5. aucune chaîne dynamique hors zone;
6. aucun placeholder visible derrière les vraies données.