# Actu Crypto #10 — Réglementation crypto mondiale

## Sujet et fréquence
Veille sur les décisions ou propositions réglementaires concernant cryptos, stablecoins, plateformes, fiscalité, licences et contrôles AML. Rythme selon l'actualité, aucun horaire de publication permanent.

## Sources gratuites
8 médias crypto (catalogue partagé news_sources_v2.py): CoinDesk, Cointelegraph, The Block, Decrypt, Blockworks, BeInCrypto, Bitcoin Magazine, NewsBTC.
3 sources institutionnelles RSS, sans clé:
- SEC: https://www.sec.gov/news/pressreleases.rss
- ESMA: https://www.esma.europa.eu/rss.xml
- Commission européenne: https://ec.europa.eu/commission/presscorner/api/rss?language=en

Les sources ne garantissent pas une couverture exhaustive de la CEDEAO / du Togo. Le code refuse les pages sans date fiable, les URL non autorisées et les titres dépourvus d'éléments crypto ET réglementaires. Certains RSS peuvent être bloqués ou silencieux sans bloquer le système entier.

## Prudence juridique
- Les mentions du type PROPOSITION, CONSULTATION, ADOPTION, SANCTION ou ENTRÉE EN VIGUEUR sont des catégories provisoires inférées **exclusivement du titre**. Ce ne sont pas des affirmations sur la loi.
- Tous les articles réels ont le statut pending_human_review, le champ approval_required=true et legal_status_confirmed=false.
- Vérification humaine obligatoire avant publication: texte primaire, statut législatif exact, pays/territoire, autorité compétente, date d'application, exemptions, mise à jour.
- Aucun envoi Telegram réel n'est implémenté. Une future validation éditoriale explicite doit précéder la conception d'un module d'envoi réel.
- Les titres originaux ne sont pas traduits automatiquement afin de ne pas altérer des expressions juridiques.
- Pas de conseil juridique, pas de conseil en investissement.

## Système
- Collecteur: crypto/export_regulation_v2.py
- Contrôles offline: crypto/test_regulation_v2.py
- Visuel 1080x1350 HTML/CSS/SVG/Playwright bleu nuit / or: scripts/render_crypto_regulation_v2.mjs
- Envoi PNG TEST, DEMO uniquement: crypto/send_crypto_regulation_v2_demo_test.py
- Historique des URL revues: crypto/regulation_10_state.json
- Workflow d'intégration et stockage des images de revue: .github/workflows/actu-crypto-regulation-v2-test.yml

Une exécution ordinaire de la branche feature ne publie aucun contenu réel ou fictif dans Telegram. L'envoi d'une seule image fictive dans @predict_mrxp nécessite un déclenchement volontaire de test; l'affiche possède un bandeau rouge de simulation.

Ne pas fusionner main ni activer les automatisations durables avant inspection de l'affiche et validation de l'intégralité des rubriques.
