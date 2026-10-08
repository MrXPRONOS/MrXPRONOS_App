# MR XPRONOS — Migration BSD V2 vers production

## Flux de production
- Workflow `.github/workflows/bsd-v2-production.yml` : toutes les heures à minute :05 UTC, ou manuel.
- Source de données : historique BSD chiffré (`BSD_HISTORY_KEY`) + données de matchs BSD (`BSD_API_KEY`).
- `bsd/bsd_v2_publish.py` : construit `data.json` pour GitHub Pages ; sélection immuable pour chaque rencontre ; résultats historiques mis à jour sur 14 jours.
- Telegram : `bsd/bsd_v2_telegram.py` sélectionne **tous** les matchs dont le début se situe entre 60 et 120 minutes après le contrôle; un message par match, aucun plafond; aucun match déjà commencé.
- Anti-doublon : insertion avec unique `kind,ref_id,ref_date` dans Supabase `telegram_sent` ; par canal et match. En cas de rejet explicite Telegram, libération de la réservation pour réessai au prochain cron.
- Déploiement GitHub Pages explicitement intégré au workflow (un push effectué avec `GITHUB_TOKEN` seul ne déclenche pas forcément d'autres workflows).
- Sources visibles sur le site : `source=bsd`, `model_version=bsd-v2-isolated`.
- Le site affiche le marché choisi : résultat, double chance, BTTS, over/under. L'ancien libellé « Double chance » n'est plus imposé.

## Workflows précédents
- `daily-update.yml` : déclencheur horaire/journalier SportData retiré, job désactivé.
- `daily-pronos.yml` : ancienne génération via fonction Supabase désactivée.
- `telegram-simple-coupons.yml` : les deux jobs legacy désactivés, y compris la limite 5.
- `create-video.yml` : anciennes vidéos SportData désactivées, à migrer séparément si désiré.
- Les workflows live indépendants et autres campagnes promotionnelles ne sont pas modifiés.

## Secrets requis (dans GitHub Actions)
`BSD_API_KEY`, `BSD_HISTORY_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` ou `SUPABASE_KEY`. `SUPABASE_ANON_KEY` sert à configurer le navigateur via le template.

## Sécurité et garde-fous
- Échec strict si API de rencontres incomplète ; aucune insertion de résultats fictifs.
- `bsd/all_matches_bsd.json` déchiffré est supprimé du runner avant publication GitHub Pages.
- Le moteur ne fabrique aucune cote bookmaker, ni garantie de rentabilité.
- Le code n'est pas une confirmation de fonctionnement live : vérifier un lancement complet (tests, export, déploiement et envoi).
- Les schedules GitHub Actions peuvent être retardés : la fenêtre est déterminée à l'heure réelle d'exécution. Un runner retardé peut manquer certains matchs.
- Le protocole de réservation Supabase privilégie la suppression des doublons ; une erreur après la réservation mais avant l'envoi pourrait exiger un contrôle de livraison manuel.
- Les horaires des matchs sont calculés en UTC et envoyés explicitement avec l'étiquette UTC ; Togo = UTC.

## Tests de réception
1. Déclencher `BSD V2 - Production hourly` manuellement, vérifier `BSD_V2_SITE` et l'étape `BSD_V2_FEED_OK`.
2. Vérifier `data.json` et `pronos.html` sur GitHub Pages après `Deploy updated BSD V2 website`.
3. Vérifier `BSD_V2_TELEGRAM` : les champs `due, sent, already_claimed, errors`.
4. Attendre un second cron ; un pronostic précédemment partagé ne doit pas être renvoyé.
5. Vérifier la validation d'une rencontre terminée et le libellé de marché sur la page historique.
6. Si Supabase `telegram_sent` refuse un nouveau `kind`, adapter le schéma/permission de service. Ne pas prétendre que Telegram a publié sans confirmation.
