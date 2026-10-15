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
- **Canal de test fixé** : [@predict_mrxp](https://t.me/predict_mrxp), directement dans le script. Aucun secret d'identifiant de canal n'est nécessaire. Le bot doit en être administrateur avec droit de publier.
- `CINEMA_TELEGRAM_BOT_TOKEN` : token du bot cinéma (ou `TELEGRAM_BOT_TOKEN` existant).
- `CINEMA_PRODUCTION_CHAT_ID` : canal cinéma réel, différent des canaux de pronostics.

**Sécurité :** test toujours vers `@predict_mrxp` (jamais vers `TELEGRAM_CHAT_ID` principal). Le script vérifie le rôle du bot avant tout envoi. Ne jamais mettre de token dans le dépôt.

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

## Campagne de test unique sur la branche

Un push contenant le marqueur exact `[cinema-live-test]` vers la branche de développement lance les 5 démonstrations sur **@predict_mrxp uniquement**, avec le token `TELEGRAM_BOT_TOKEN` du dépôt. Sans accès administrateur du bot, le contrôle préalable interrompt le test avant l'envoi. Cette étape ne déclenche jamais une publication sur les canaux des pronostics.

## Règle stricte des visuels (mise à jour)

Aucune image n’est fabriquée ni modifiée. Pour les films, séries, top 5, sorties et pépites, la photo publiée est le **poster original fourni par TMDB** du premier titre sélectionné possédant une image; pour l’acteur du jour, le **portrait officiel TMDB**. Les octets JPEG/PNG sont transmis tels quels à Telegram : zéro composition Pillow, zéro logo, zéro texte superposé, zéro image générée. Si TMDB ne fournit pas d’image valide, la publication devient un message texte enrichi. Les démos fictives sont elles aussi uniquement textuelles; les quiz utilisent les sondages natifs de Telegram.

Pour afficher de véritables images sur le canal de test, lancer avec `--mode test --format all` **sans** `--demo` et configurer `TMDB_API_KEY`. Les images de TMDB et leur diffusion doivent respecter les conditions/licences de la source.