# Cinéma Telegram — lot 2/3 (5 nouveaux formats)

Cette livraison ajoute `scripts/cinema_batch2.py` sans modifier le générateur des pronostics ni le premier lot.

- `series` — les séries du moment, sélectionnées parmi les tendances TMDB TV.
- `notes` — films bien notés (au moins 500 votes), top 5 du moment.
- `pepites` — pépites avec une bonne note et un nombre de votes modéré.
- `acteur` — acteur/actrice du jour, plus une sélection vérifiable de films joués.
- `sondage` — sondage natif Telegram permettant de choisir entre 4 films.

Quatre publications photo utilisent l'API `sendRichMessage` déjà présente dans Mr XPRONOS : vrai titre, gras, italique, citations et bouton `tg-button` dans un `tg-button-row` avec un seul bouton par ligne. La largeur physique du bouton dépend du client Telegram et ne peut pas être forcée. Si Telegram rejette explicitement le message enrichi, le module existant tente le rendu classique avec clavier sous la publication.

Le sondage exploite `sendPoll` natif : les choix sont dans le message lui-même (pas un faux clavier).

## Sécurité

- Tests uniquement dans `@predict_mrxp` (canal fixé en dur par le premier lot).
- Vérification des droits du bot (`getMe` et `getChatMember`) avant publication.
- Aucune publication vers le canal principal des pronostics.
- Production bloquée sauf si `CINEMA_PRODUCTION_ENABLED=true` et `CINEMA_PRODUCTION_CHAT_ID` renseigné.
- Pas d'appel IA, pas de serveur : Pillow/requests + données TMDB gratuites sous réserve des conditions de licence non commerciale et d'attribution.
- Les démonstrations fictives sont interdites en production.
- Anti-doublon via `cinema/sent_test_batch2.json` et `cinema/sent_production_batch2.json`.

## Test sur GitHub

Dans **Actions** → **Cinéma Telegram - lot 2 (5 formats)** → **Run workflow** :
- `mode=test` ; `format=all` ; `demo=true` ; `dry_run=true` pour aperçu sans envoi.
- `mode=test` ; `format=all` ; `demo=true` ; `dry_run=false` pour envoyer 5 publications fictives au canal de test.
- `demo=false` nécessite `TMDB_API_KEY` en plus d'un token Telegram.

Les 5 nouveaux formats passent automatiquement en production à raison d'un par jour ouvré à 15 h 07 (heure du Togo) **uniquement après activation explicite**. Cette fréquence sera harmonisée avec les 15 formats au lot 3 pour éviter trop de messages quotidiens.

## Vérifications locales

```
python -m pip install requests Pillow
python -m unittest discover -s tests -p 'test_cinema_batch2.py' -v
python scripts/cinema_batch2.py --mode test --format all --demo --dry-run
```