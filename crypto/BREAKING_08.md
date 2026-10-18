# Publication #08 — Breaking News Bitcoin et Ethereum

## Statut
Prototype de test sur feature/actu-crypto-lot-06-10. Aucun horaire permanent et aucune diffusion en production.

## Sources gratuites (8 RSS médias indépendants)
Catalogue partagé : `crypto/news_sources_v2.py`. Sources sans abonnement ni clé :
- CoinDesk : https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml
- Cointelegraph : https://cointelegraph.com/rss
- The Block : https://www.theblock.co/rss.xml
- Decrypt : https://decrypt.co/feed
- Blockworks : https://blockworks.co/feed
- BeInCrypto : https://beincrypto.com/feed/
- Bitcoin Magazine : https://bitcoinmagazine.com/feed
- NewsBTC : https://www.newsbtc.com/feed/

La publication #08 exige **deux médias de domaines distincts** sur une actualité BTC/ETH de moins de 12 h. Si un RSS est indisponible, les autres restent utilisables. Aucune API payante. RSS public ne signifie pas droit de republier des articles complets ; l'affiche affiche le titre avec attribution et la légende lie la source.

## Design premium — aligné avec les publications #01 à #07
- Même format 1080 × 1350, palette bleu nuit/or/blanc, panneaux en relief et typographie lisible.
- Même moteur reproductible que les publications premium : données Python validées → JSON → JavaScript/HTML/CSS/Playwright → PNG → Telegram sendPhoto.
- Réutilisation directe des visuels BTC/ETH approuvés `crypto/assets/premium_market/btc.png` et `eth.png`, utilisés pour les premiers visuels ; aucun faux logo généré en CSS.
- Composition de breaking news propre à la rubrique : titre original, une source principale, une deuxième source, les heures UTC et une légende avec liens.
- Contrôle Playwright des débordements, de la taille du titre et du chargement de l'image premium.
- Pour un aperçu Telegram authentique, le workflow `actu-crypto-breaking-delivery-test.yml` produit `breaking_v2_demo.json` puis `breaking_v2_demo.png` avec le vrai moteur du #08. L'image est explicitement marquée SIMULATION et envoyée uniquement sur action intentionnelle à `@predict_mrxp`.
- La réussite de ce test atteste que l'image et la légende sont livrées ; elle ne signifie pas qu'une actualité réelle a été trouvée ou publiée.

## Contrôles avant publication
1. Titre concernant clairement BTC ou ETH et un événement d'importance.
2. Date source valide, article de moins de 12 heures.
3. Deux sources distinctes mentionnant vraisemblablement le même événement : croisement de mots-clés significatifs.
4. Exclusion des prédictions de prix, tribunes, sponsorisations et articles génériques.
5. Si aucun cas admissible, aucune publication réelle n'est produite.
6. Les titres originaux restent en anglais pour éviter des traductions non vérifiées ; les liens des deux articles sont envoyés dans la légende.

Attention : le rapprochement de deux titres constitue un filtrage automatisé, pas une confirmation journalistique complète. Il peut produire des faux positifs ou faux négatifs.

## Fichiers
- crypto/export_breaking_v2.py : collecte RSS, dates, source, qualification et anti-doublon.
- crypto/test_breaking_v2.py : tests unitaires hors ligne.
- scripts/render_crypto_breaking_v2.mjs : affiche dynamique 1080 × 1350.
- crypto/send_crypto_breaking_v2_test.py : canal de test Telegram uniquement.
- crypto/breaking_08_state.json : registre de liens déjà envoyés.
- .github/workflows/actu-crypto-breaking-v2-test.yml : automatisation des tests DEMO/REAL.

## Validation sur GitHub Actions
Les pushes sur les fichiers #08 déclenchent les tests, un rendu DEMO non publiable et une tentative de collecte réelle.
En l'absence de nouvelles corroborées, la génération réelle est ignorée normalement et le workflow peut réussir.
L'envoi vers @predict_mrxp demande une action explicite : workflow_dispatch avec send_telegram=true (disponibilité selon présence du workflow sur la branche par défaut), ou un push portant le marqueur [breaking-test-send] sur la branche feature.
Ne jamais activer ce marqueur sans intention d'envoyer. Le script revérifie l'identité et les permissions du canal ainsi que la provenance des données.
Après envoi réussi, le workflow committe le registre anti-doublon sur la branche feature.

## Limites
- Le registre de liens limite la duplication, mais le commit GitHub et l'envoi Telegram ne sont pas atomiques : un échec de commit après envoi comporte un risque de doublon.
- Les flux RSS tiers ne garantissent ni disponibilité permanente ni exhaustivité.
- L'affiche n°08 et son contenu doivent être validés visuellement avant tout usage durable.
- Aucune publication automatique de production avant validation et coordination de l'ensemble des workflows.
