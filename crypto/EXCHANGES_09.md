# Publication #09 — Actualités des exchanges (Mr XPRONOS)

## Sujet
Informations pertinentes sur **Binance, Coinbase, OKX, Kraken, Bybit, Bitget, KuCoin et Gemini**. Les articles sont attribués à leurs auteurs; leurs titres originaux (anglais) ne sont pas traduits sans vérification. Les nouvelles régionales ne sont pas présumées disponibles au Togo.

## Sources gratuites exploitées (8 RSS + 2 API officielles)

**8 médias RSS, sans clé ni abonnement** (catalogue `crypto/news_sources_v2.py`) :
- CoinDesk — https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml
- Cointelegraph — https://cointelegraph.com/rss
- The Block — https://www.theblock.co/rss.xml
- Decrypt — https://decrypt.co/feed
- Blockworks — https://blockworks.co/feed
- BeInCrypto — https://beincrypto.com/feed/
- Bitcoin Magazine — https://bitcoinmagazine.com/feed
- NewsBTC — https://www.newsbtc.com/feed/

**2 API officielles gratuites, sans clé** :
- Coinbase Status, incidents : https://status.coinbase.com/api/v2/incidents.json
- Kraken Status, incidents : https://status.kraken.com/api/v2/incidents.json

Les API officielles ne fournissent **que des incidents de fonctionnement déclarés** ; elles ne remplacent pas les informations des médias sur les nouvelles fonctionnalités, frais, réglementation ou listings. Les incidents expirés ou résolus sont exclus. Une panne d'une source n'arrête pas la collecte des autres.

Les notices officielles portent la catégorie `official_notice` ; les articles de médias `attributed_report` ou `cross_reported`. Les sources primaires ne comptent **jamais** comme second média indépendant. Une source RSS gratuite n'accorde pas automatiquement de droit de republication intégrale : conserver titre, attribution et lien.

Les huit flux RSS sont des **médias**, tandis que les deux API sont des **pages de statut officielles**. Une seule source permet un aperçu marqué "information rapportée" pour les annonces courantes; **piratage, violation de sécurité, interruption majeure de service et détournement de fonds** exigent la concordance de deux médias indépendants. Le rapprochement automatisé de titres ne remplace pas la vérification manuelle du contenu.

## Contrôles
- Pas d'article de plus de 48 h, sans date fiable, ni de nouvelle future de plus de cinq minutes.
- Noms des plateformes reconnus dans le titre et catégories significatives.
- Publicités, prix prédictifs, tribunes, rumeurs et billets génériques filtrés.
- Liens HTTPS vers les domaines réels des trois médias, suppression des paramètres de suivi.
- Les annonces non corroborées de sécurité ne sont pas publiées.
- Anti-doublons sur empreintes de liens, registre `crypto/exchanges_09_state.json`.
- Si zéro news vérifiable, aucun PNG réel et aucun envoi.
- Deux modes indépendants : DEMO explicitement fictif / REAL vérifié.
- Livraison exclusivement au canal **@predict_mrxp**, après vérification du bot et des droits.
- Un échec HTTP incertain d'envoi Telegram ne déclenche pas une nouvelle tentative automatique.

## Visuels
- 1080 × 1350, même palette premium bleu nuit / or / blanc que les rubriques #01–08.
- Grande hiérarchie éditoriale, médaille 3D abstraite représentant l'échange (pas un logo officiel contrefait), catégorie, nom de la plateforme, titre original, preuve des sources.
- Rendu HTML/CSS/SVG/Playwright, titre ajusté automatiquement, vérification anti-débordement.
- Envoi Telegram via `sendPhoto`, avec PNG et légende citant les URL des sources.
- Le rendu DEMO porte un bandeau indiquant explicitement **SIMULATION — NON PUBLIABLE**.

## Code
- `crypto/export_exchanges_v2.py` : filtre RSS, horodatages, catégorie, confirmations et état.
- `crypto/test_exchanges_v2.py` : tests offline.
- `scripts/render_crypto_exchanges_v2.mjs` : affiche PNG premium.
- `crypto/send_crypto_exchanges_v2_test.py` : expédition image + légende au canal test.
- `.github/workflows/actu-crypto-exchanges-v2-test.yml` : tests, archives et collecte réel/démo.

## Lancement et prudence
Le workflow vérifie la collecte et archive les PNG sur les commits de la branche `feature/actu-crypto-lot-06-10`. Les actions de push ordinaires ne publient rien dans Telegram. Un commit portant `[exchange-demo-send]` publie **une unique simulation clairement marquée** sur le canal test, exclusivement pour approbation visuelle. Une vraie actualité ne peut être envoyée que par un déclenchement manuel avec `send_real_telegram=true`.

La programmation récurrente et la diffusion de production ne sont **pas activées**. L'affiche et l'article doivent être validés avant leur activation.
