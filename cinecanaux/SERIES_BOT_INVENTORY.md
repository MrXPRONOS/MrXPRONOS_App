# CinéX Séries — affiches épinglées et livraison multi-saisons

**Aucune session Telegram personnelle.** Les nouveaux workflows utilisent uniquement les jetons des bots de publication et @CineRadarFr_Bot, le Worker Cloudflare et D1. Aucun secret TG_SESSION_STRING, TG_API_ID ou TG_API_HASH n'est chargé. Aucune suppression de contenu source.

## 1. Variables GitHub

Ouvrir **Settings → Secrets and variables → Actions → Variables** du dépôt MrXPRONOS/MrXPRONOS_App.

| Nom | Valeur indicative | Utilisation |
| --- | --- | --- |
| CINEX_SERIES_CHANNEL_IDS | -1001234567890 -1009876543210 | IDs privés séparés par des espaces (obligatoire) |
| CINEX_SERIES_SEASON_COUNTS | -1001234567890:3 -1009876543210:1 | Optionnel : nombre total de saisons, pour repérer les saisons manquantes |
| CINEX_SERIES_FOLDER_URL | https://t.me/addlist/XXXXXXXXXXX | Lien du dossier Séries (nécessaire pour publier) |
| CINEX_SERIES_RIGHTS_ATTESTED | false | Mettre true seulement après confirmation des droits de diffusion |
| CINEX_SERIES_PUBLISH_ENABLED | false | Mettre true quand la publication est autorisée |

Un secret facultatif CINEX_SERIES_RESCUE_INVITE_URL peut être enregistré dans **Actions → Secrets** si le bot ne peut pas retrouver l'invitation du secours. Cette URL est acceptée uniquement si elle correspond à l'empreinte vérifiée du registre.

Canal principal Séries : @seriesvf_cinex (ID -1004406527554).
Canal secours Séries **déjà existant** : ID -1003822435811, enregistré dans telegram-film-relay/state/rescue_channels.json.

## 2. Inventorier sans publier

**Actions → CineX Séries — synchroniser affiches et publier avec les bots → Run workflow → publish=false.**

Le workflow lit la liste des IDs, vérifie les droits des deux bots et les titres des canaux, synchronise D1 et récupère la **dernière affiche épinglée accessible** renvoyée par getChat. Il extrait le numéro de saison (ex. « Saison 1 », « S02 ») et éventuellement le nombre d'épisodes (ex. « 12 épisodes »). Il enregistre un rapport téléchargeable en artifact.

**Limite Telegram :** la Bot API ne peut pas parcourir tout l'historique ou retrouver les autres anciens messages épinglés depuis le seul ID du canal. Pour importer des affiches anciennes, transférer **les messages originaux** depuis chaque canal à @CineRadarFr_Bot en conversation privée, depuis le compte reconnu comme propriétaire. Le bot enregistre l'identifiant source. La description doit contenir « Saison 1 », « Saison 2 », etc. Ne pas envoyer une nouvelle image sans origine de transfert.

Les nouveaux épinglages et les nouveaux épisodes postés dans un canal enregistré seront détectés par le webhook du bot Radar. Les vidéos déjà anciennes peuvent également être transférées au bot pour indexer leurs IDs originaux, avec une légende explicite telle que « S01E01 », « S02E12 » ou « Saison 2 épisode 12 ». **Sans ces IDs, les saisons historiques ne peuvent pas être livrées automatiquement avec l'API des bots.**

## 3. Vérifier les saisons complètes

Avant toute publication, chaque série doit disposer d'une affiche S1 et de toutes les affiches S2…SN, du nombre d'épisodes attendu pour chacune et des IDs exacts de chaque épisode dans l'ordre 1…N. Le nombre de saisons est au minimum le plus grand numéro détecté dans les affiches, ou celui déclaré dans CINEX_SERIES_SEASON_COUNTS. Si une saison manque, si le nombre d'épisodes est inconnu ou si un numéro est absent, aucune diffusion de cette série n'est activée.

La présence des épisodes 1 à 8 ne suffit pas à prouver que la saison comporte exactement huit épisodes : l'affiche doit préciser « 8 épisodes » ou le total doit être vérifié.

## 4. Publier dans les deux canaux

Mettre CINEX_SERIES_RIGHTS_ATTESTED et CINEX_SERIES_PUBLISH_ENABLED à true uniquement après vérification, puis relancer **Run workflow** avec publish=true. Le verrou général D1 cine_delivery_enabled doit aussi être actif. Le bot contrôlera son accès administrateur aux deux canaux publics/secours et vérifiera le lien d'invitation du secours, sans création de canal.

Pour chaque série complète, l'affiche originale de la saison 1 est copiée **une fois** dans le canal principal et le secours. Les trois boutons sont :

- 📥 Télécharger toutes les saisons — vert (success), vers @CineRadarFr_Bot, avec un lien de démarrage dédié à la série.
- 🛟 Rejoindre le canal de secours — rouge (danger), vers le secours Séries vérifié.
- 📂 Rejoindre le dossier — bleu (primary), vers le dossier Telegram configuré.

Les couleurs réelles dépendent de la version Telegram. Les publications déjà réalisées ne sont pas envoyées à nouveau : les boutons sont mis à jour sur place. Les appels ayant un résultat incertain sont bloqués pour contrôle.

## 5. Téléchargement et expiration 24h

Quand l'abonné clique sur le premier bouton, Ciné Radar valide la complétude de S1…SN, puis copie les épisodes en conversation privée dans l'ordre : S1E1 → S1E2 → ... → S2E1... L'envoi fonctionne par lots (maximum 300 épisodes par demande) pour respecter les limites Telegram. Chaque copie privée reçoit sa propre échéance de suppression **24 heures après l'envoi**. En cas d'échec, les opérations incertaines ne sont pas relancées aveuglément.

Les copies privées sont supprimées, jamais les vidéos sources, ni les affiches des canaux publics ou de secours. Le transfert effectué par un utilisateur vers ses Messages enregistrés n'est pas concerné.

## 6. Fichiers techniques

- Migration : cinecanaux/migrations/019_cinex_individual_series.sql
- Worker : cinecanaux/individual-series.mjs, intégré dans cinecanaux/worker.mjs
- Script de synchronisation et de publication : cinecanaux/scripts/publish_individual_series_bot.py
- Audit lecture seule : cinecanaux/scripts/audit_series_bots.py
- Workflows : cinex-series-bot-inventory.yml, cinex-series-bot-sync.yml, cinex-series-bot-ci.yml
- Tests : cinecanaux/tests/individual-series.test.mjs et test_individual_series_publish.py

Tous ces nouveaux scripts fonctionnent **sans** Telethon et **sans** session personnelle Telegram.
