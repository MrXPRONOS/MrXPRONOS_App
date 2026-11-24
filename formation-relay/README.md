# Formation Telegram V1

Public : Formation 360. Privés : Business, Finance, Digitale, Mindset.
Exécution 08:00 et 20:00 UTC. Une formation par destination et par cycle.
Les sources doivent être autorisées par les titulaires de droits ; aucune
copie de messages protégés. Les crédits sont conservés. Le compte personnel
lit et transfère vers un canal technique privé ; le bot copie vers la destination.
Les archives ne sont jamais extraites ni exécutées. Leur contenu n'est pas
analysé : elles peuvent contenir des fichiers dangereux.

## Configuration (GitHub Actions)

Variables :
- FORMATION_ENABLED=true seulement après la configuration et les tests.
- FORMATION_RIGHTS_ATTESTED=true seulement après vérification des droits.
- TG_PERSONAL_COOLDOWN_UNTIL_UTC (partagé avec CineX).

Secrets existants : TG_API_ID, TG_API_HASH, TG_SESSION_STRING (ou alternatives
déjà configurées), FOOTBALL_NEWS_BOT_TOKEN (ou TELEGRAM_BOT_TOKEN).

Nouveaux secrets (ne jamais commiter les IDs privés ou les clés) :
- FORMATION_SOURCES_JSON : [{"chat":-1001111111111,"authorized":true,"credit":"Auteur autorisé","category":"auto"}]
- FORMATION_DESTINATIONS_JSON : {"general":-1002222222222,"business":-1003333333333,"finance":-1004444444444,"digitale":-1005555555555,"mindset":-1006666666666}
- FORMATION_STAGE_CHAT : ID numérique du canal technique privé.
- FORMATION_STATE_KEY : clé aléatoire stable de 32 caractères minimum, ne jamais la changer sans migration des empreintes.

Exemples fictifs à remplacer. Compte personnel membre de chaque canal ;
bot administrateur des cinq destinations et du canal technique.

## Exploitation
Les tests hors ligne tournent sur la PR. Après fusion, configurer les secrets
et variables, puis lancer manuellement sans publication pour le diagnostic.
L'activation du planning doit suivre la validation des droits et du diagnostic.

Le regroupement est conservateur : affiche (y compris image document), texte
optionnel, fichiers, puis affiche suivante ou total explicite. Un groupe
ambigu ou protégé est ignoré. Aucun plafond de dix pièces ; fenêtre de lecture
de 600 messages par source et par cycle. Classification par mots-clés ou
catégorie source configurée. Le canal général reçoit une formation distincte.

Les reçus HMAC sont sauvegardés dans Git sans titre, nom de fichier ni ID
de canal privé. Une réponse incertaine n'est jamais automatiquement rejouée ;
le marqueur de publication est recherché dans la destination. Une vérification
manuelle est nécessaire si elle est introuvable. Ne pas supprimer l'état pour
contourner ce contrôle.

Limites : pas de comparaison perceptuelle, OCR, IA ou empreinte du contenu
binaire. Pas de garantie de détecter un fichier réencodé ou un ensemble
sans frontières explicites. Les volumes legacy .r00/.z01 nécessitent une
revue. Les archives numérotées sans preuve de fin exigent une revue.
