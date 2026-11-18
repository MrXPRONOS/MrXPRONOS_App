# Mr XPRONOS Play — Audit de fidélité visuelle (V2)

**Date :** 18 novembre 2026  
**Référence :** capture de concept de jeu « Mr XPRONOS Play » (illustrations 3D bleu nuit / or, pièce MX centrale, six raccourcis latéraux, roue et badges NFT).  
**Application :** https://mrxpronos-play.cinecanaux-xpronos.workers.dev  
**Figma :** https://www.figma.com/design/RlWwR9KutRVBRGhuELDH1N  
**État :** rapprochement visuel réalisé ; la reproduction pixel par pixel d’une image de concept (sans fichiers sources ni mesures d’origine) n’est pas certifiée.

## Vérification du dépôt

- 50 PNG et 50 WebP présents sur GitHub dans les chemins prévus du manifeste.
- Aucune image attendue manquante selon comparaison de l'arborescence avec `assets-manifest.json`.
- Les assets sont servis par les URL brutes GitHub. Une migration vers Workers Static Assets sera préférable avant un fort trafic.

## Direction visuelle

| Propriété | Valeur CSS V2 | Intention |
| --- | --- | --- |
| background main | `#030812` | Noir-bleu très profond |
| surface principale | `#071429` | Cartes sombres |
| surface surélevée | `#112B5C` | Bleu navy premium |
| accent or lumineux | `#FFD56D` | Éléments principaux |
| or profond | `#D98E18` | Reliefs et contours |
| bleu électrique | `#078AFF` | Halos, énergie, reliefs |
| bordure bleue | `#1F4A86` | Séparation de panneaux |
| texte principal | `#FFF9F0` | Blanc crème |
| texte secondaire | `#B3C4E0` | Bleu gris lisible |

**Typographie :** Montserrat, titres en 900 / Black, étiquettes en 700–800, corps en 400–600. Source front : Google Fonts, avec polices de secours.

## Résultat du contrôle du vrai site

- Rendu chargé au format mobile 390 × 844.
- Images critiques chargées : logo, avatar, XP, énergie, pièce centrale, six raccourcis et navigation.
- Tap de test : XP de 0 à 1, énergie de 500 à 499 (hors Telegram, XP provisoire).
- Vue roue accessible ; illustrations centrales et pointeur préchargées pour réduire l'apparition tardive.
- Aucune largeur dépassant le viewport à 320 / 360 / 390 / 430 px.
- Montserrat chargée dans Chromium via Cloudflare Browser Rendering.

## Comparaison aux captures d'origine

**Amélioré :** reliefs métalliques, saturation dorée, reflets cyan, panneaux bleu-nuit, gros titres denses, pièce de tap centrale, halo, menus latéraux, navigation 3D, roue de la chance et badges.

**Encore différent :** les captures d'origine sont des concepts illustrés en vue composite ; elles ne fournissent pas de grille de layout, de polices source ni de mesures de couleurs absolues. Certains éléments varient volontairement pour un affichage tactile mobile et pour garder une navigation fonctionnelle. Les maquettes Figma comportent encore des emplacements visuels éditables ; le Worker réel affiche les images WebP de GitHub. Le pixel-perfect n'est pas certifié.

## Prochaines validations avant production

1. Ouvrir la Mini App depuis un bot Telegram configuré (BOT_TOKEN / WEBHOOK_SECRET).
2. Vérifier roue, missions, profil et progression sur Android et iOS.
3. Mesurer performances, poids des images et quotas Cloudflare.
4. Conserver D1 pour les XP confirmés, valider les actions hors ligne lors de la synchronisation autorisée.
