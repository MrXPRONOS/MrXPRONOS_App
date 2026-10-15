# Telegram Cinéma — lot 1/3 (5 formats)

Scripts séparés du système de pronostics Mr XPRONOS.

## Les 5 formats

- `film` : film du jour
- `top5` : top 5 cinéma
- `sorties` : prochaines sorties
- `soir` : film de la soirée
- `quiz` : sondage Telegram natif de type quiz (4 réponses et correction)

Les quatre premières publications utilisent les Rich Messages Telegram : titre structuré, gras, italique, citation et **un seul bouton dans chaque ligne** de la publication. Telegram détermine la largeur visuelle finale; le code ne peut pas imposer 100 % de largeur. Si l'API rich échoue explicitement, le module existant `telegram_rich.py` utilise le format classique avec clavier attaché.

## Secrets GitHub à paramétrer

- `TMDB_API_KEY` : clé API TMDB. API gratuite seulement sous conditions, notamment usage non commercial.
- `CINEMA_TEST_CHAT_ID` : chat ID du **canal cinéma de test** (alternatives admises `TELEGRAM_TEST_CHAT_ID` ou `TELEGRAM_CHAT_ID_TEST`). Le bot doit être administrateur.
- `CINEMA_TELEGRAM_BOT_TOKEN` : token du bot cinéma (ou `TELEGRAM_BOT_TOKEN` existant).
- `CINEMA_PRODUCTION_CHAT_ID` : canal cinéma réel, différent des canaux de pronostics.

**Sécurité :** aucune valeur par défaut de test vers `TELEGRAM_CHAT_ID` principal. Pas d'envoi si le secret de test manque. Ne jamais mettre de token dans le dépôt.

## Actions recommandées

1. Aller dans Actions → « Cinéma Telegram - lot 1 (5 formats) » → Run workflow.
2. Définir `mode=test`, `format=all`, `dry_run=true`, `demo=true` pour tester le formatage sans frais ni envoi.
3. Pour les **5 envois réels au canal test**, utiliser `mode=test`, `format=all`, `dry_run=false`, `demo=true` (sans clé TMDB); ou `demo=false` avec TMDB configuré.
4. Vérifier les messages dans le canal test, puis seulement activer la production en définissant la variable de dépôt `CINEMA_PRODUCTION_ENABLED=true` et le secret `CINEMA_PRODUCTION_CHAT_ID`.
5. Les créneaux de production sont 09:17, 13:19, 17:23, 18:41 (quiz), 20:27 UTC (Togo).

Le workflow `push` sur la branche de développement exécute seulement les tests automatiques et le dry-run ; jamais d'envoi Telegram.

Le programme conserve la trace `cinema/sent_test.json` et `cinema/sent_production.json` par jour et format, évitant les doublons dans les exécutions normales. L'historique est commité par les actions après publication.

## Tests locaux

```bash
python -m pip install requests Pillow
python -m unittest discover -s tests -p 'test_cinema_telegram.py' -v
python scripts/cinema_telegram.py --mode test --format all --demo --dry-run
```

## Droits

Le système recommande des films sans distribuer de copies de films. Les fiches mènent à TMDB, pas à des liens de téléchargement illégaux. Le visuel est créé localement à partir de texte, sans reprise de posters. Mention de TMDB ajoutée aux fiches utilisant ses données; adapter la licence pour un usage commercial.