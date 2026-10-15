# Cinéma Telegram — troisième série (formats 11 à 15)

Le script `scripts/cinema_batch3.py` complète les deux premières séries. Aucun script de pronostics n'est modifié. **Aucun fichier image synthétique n'est créé** : les visuels sont les octets JPEG ou PNG originaux servis par TMDB, transmis via la fonction `download_source_image` du premier lot, sans composition, recadrage, nouveau fond ou texte incrusté.

## Contenus

| Commande | Publication | Sources et limites |
|---|---|---|
| `duel` | Affiche TMDB du film A + message enrichi (2 liens sur 2 lignes), puis vote natif Telegram A/B | Titres, affiches, identifiants TMDB ; les 2 envois sont suivis séparément pour éviter les doublons |
| `anecdote` | Le savais-tu ? Réalisateur du film, extrait directement des crédits | `/movie/{id}/credits` ; pas de fiction ou d'anecdote sans preuve |
| `boxoffice` | Top 5 de recettes mondiales cumulées renseignées sur TMDB pour un échantillon de films à l'affiche en France | `/movie/now_playing?region=FR`, puis `/movie/{id}` ; **pas** un classement du week-end, montants incomplets possibles |
| `bandeannonce` | Affiche source + bouton ouvrant une bande-annonce officielle YouTube et un bouton fiche TMDB | `/movie/{id}/videos` ; `site=YouTube`, `type=Trailer`, `official=true` et clé validée |
| `weekend` | Suggestions de films dans quatre genres différents ; liens vers les fiches TMDB | `trending/movie/week`, `genre_ids` |

Les messages comportent des sections HTML structurées (`h3`, `b`, `i`, `blockquote`) et des boutons enrichis organisés **un bouton par ligne**. La largeur finale dépend du client Telegram, et le module commun se replie sur les boutons standards si le rendu enrichi n'est pas accepté.

## Commandes et sécurité

```bash
python -m pip install requests
python -m unittest discover -s tests -p 'test_cinema_batch3.py' -v
python scripts/cinema_batch3.py --mode test --format all --demo --dry-run
```

La démonstration fictive (`--demo`) ne publie jamais d'image inventée : le message devient textuel et clairement identifié comme fictif. Pour une **publication réelle contenant les véritables images de la source**, définir les secrets `TMDB_API_KEY` et `CINEMA_TELEGRAM_BOT_TOKEN` (ou réutiliser `TELEGRAM_BOT_TOKEN`) puis exécuter :

```bash
python scripts/cinema_batch3.py --mode test --format all
```

Le mode test ne publie **que** dans `@predict_mrxp`. Il vérifie avec `getMe` et `getChatMember` que le bot est administrateur de ce canal avant tout envoi. Les canaux de pronostics sont explicitement exclus. Les images manquantes ou les faits insuffisamment documentés entraînent une erreur plutôt qu'un visuel fabriqué ou une information inventée.

La production n'est pas activée par défaut. Elle exige la variable GitHub `CINEMA_PRODUCTION_ENABLED=true` et le secret `CINEMA_PRODUCTION_CHAT_ID`, distinct du canal de pronostics.

## Automatisation gratuite

Workflow `.github/workflows/cinema-telegram-batch3.yml`. S'il est activé en production : lundi 16 h 17 = duel ; mardi anecdote ; mercredi box-office ; jeudi bande-annonce ; vendredi sélection week-end. Fuseau **UTC (Togo)**. Les déclenchements planifiés peuvent être retardés par GitHub Actions. Pas de serveur ni LLM payant. Les conditions de licence TMDB, notamment l'attribution et les restrictions d'utilisation commerciale, sont à respecter.

L'historique (`cinema/sent_test_batch3.json`, `cinema/sent_production_batch3.json`) est mis à jour par format et par jour. En cas d'échec entre l'affiche et le sondage du duel, le workflow sauvegarde le message déjà envoyé pour permettre de reprendre sans le publier de nouveau.

## Vérification réelle

Une exécution locale `--dry-run` et les tests automatisés prouvent seulement le code. Une validation réelle nécessite de confirmer les identifiants `message_id`, les envois dans `@predict_mrxp` et les journaux GitHub Actions. Ne pas annoncer d'envoi réussi sans ces éléments.