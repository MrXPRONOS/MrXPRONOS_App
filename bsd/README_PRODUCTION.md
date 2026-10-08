# MR XPRONOS — Migration BSD V2 vers production

## Flux de production
- Workflow `.github/workflows/bsd-v2-production.yml` : une seule fois par jour à 00:05 UTC, ou manuel.
- Source de données : historique BSD chiffré (`BSD_HISTORY_KEY`) + données de matchs BSD (`BSD_API_KEY`).
- `bsd/bsd_v2_publish.py` : construit `data.json` pour GitHub Pages ; sélection immuable pour chaque rencontre ; résultats historiques mis à jour sur 14 jours.
- Telegram : workflow `.github/workflows/bsd-v2-telegram-hourly.yml` toutes les heures à HH:05, lecture de `data.json` sans appel BSD; `bsd/bsd_v2_telegram.py` sélectionne **tous** les matchs dont le début se situe entre 60 et 120 minutes après le contrôle; un message par match, aucun plafond; aucun match déjà commencé.
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
1. Déclencher `BSD V2 - Generation quotidienne` manuellement, vérifier `BSD_V2_SITE` et l'étape `BSD_V2_FEED_OK`.
2. Vérifier `data.json` et `pronos.html` sur GitHub Pages après `Deploy updated BSD V2 website`.
3. Vérifier `BSD_V2_TELEGRAM` : les champs `due, sent, already_claimed, errors`.
4. Attendre un second cron ; un pronostic précédemment partagé ne doit pas être renvoyé.
5. Vérifier la validation d'une rencontre terminée et le libellé de marché sur la page historique.
6. Si Supabase `telegram_sent` refuse un nouveau `kind`, adapter le schéma/permission de service. Ne pas prétendre que Telegram a publié sans confirmation.

## Architecture finale et maîtrise des quotas
- **00:05 UTC** : production du fichier unique `data.json` avec les matchs futurs d'aujourd'hui et de demain (fenêtre jusqu'à 48h), et déploiement du site. Les pronostics déjà présents sont conservés.
- **Chaque heure à HH:05 UTC** : Telegram lit exclusivement `data.json` présent dans le dépôt, sans restaurer l'historique, sans entraîner le modèle, et **sans utiliser BSD_API_KEY**.
- Telegram n'envoie qu'un match dont le coup d'envoi est prévu dans **60 à moins de 120 minutes**, jamais après le début, et utilise `telegram_sent` pour éviter les doublons.
- Un retard GitHub Actions peut provoquer un créneau manqué : une garantie d'envoi de tous les matchs 1 à 2 heures avant le coup d'envoi nécessite un déclencheur plus ponctuel qu'un cron non garanti.
- Aucune garantie de livraison Telegram sans première vérification des secrets et de la table de dédoublonnage.


## Coupons Telegram PNG et validation des gains (nouveau)
- Génération avec Pillow : bsd/bsd_v2_card.py (1080 × 1260), même style visuel pour avant-match et gain.
- Image football réellement générée et version transparente PNG intégrée au dépôt : assets/images/bsd-football-generated.png.
- En-tête : 1XBET, MELBET, CODE PROMO XPVIP. Montant illustratif : 500 000 F.
- L'affichage est explicitement une SIMULATION et ne prouve aucun pari accepté ou paiement.
- Cotes : bsd/bsd_v2_publish.py interroge le flux consensus de BSD une fois lors de la génération du site. Une cote absente reste « Non disponible », jamais transformée en cote théorique. Le bookmaker affiché en entête ne garantit PAS que la cote consensus soit disponible chez 1XBet ou MELBET.
- Seuls les marchés et les sélections effectivement retournés par le flux de cotes BSD sont affichés avec un prix; notamment le marché Under 4.5 exige une intégration spécifique depuis l'endpoint par match pour être couvert.
- Messages d'annonce : bsd/bsd_v2_telegram.py envoie une image par match avec Telegram sendPhoto, sans supprimer la diffusion progressive 60–120 min avant le début.
- Identifiant stable : chaque coupon utilise son BSD event ID, enregistré dans Supabase telegram_sent avec kind=bsd_v2_hourly et validation_sent=false. Le suivi se fait par canal.
- Toutes les heures à HH:40 UTC : .github/workflows/bsd-v2-telegram-wins.yml lance bsd/bsd_v2_verify_telegram.py. Il vérifie les scores finaux BSD après une marge de 4 heures et évalue le marché original du coupon enregistré.
- Gain : même rendu PNG avec badge GAIN, score réel, et publication Telegram; ensuite validation_sent=true. Perte : validation_sent=true, **aucune publication**. En attente : aucune action.
- Le contrôle des gains consomme un faible nombre de requêtes BSD sur les journées à vérifier, contrairement au distributeur d'annonces qui ne consomme aucune requête BSD.
- La publication exacte et sans doublon dépend de la réponse Telegram et du registre Supabase; les délais et l'incertitude des erreurs réseau ne permettent pas de promettre un « exactement une fois » sans protocole de sortie transactionnelle.
- Installation: pip install pillow requests cryptography.
- Vérifier le workflow GitHub Actions complet et un envoi réel avant de déclarer l'automatisation opérationnelle.
