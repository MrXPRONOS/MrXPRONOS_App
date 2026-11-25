# Formations — Une seule réserve privée, cinq destinations

## Organisation

Canal de dépôt UNIQUE : la réserve privée Formation générale, déjà identifiée
et vérifiée lors de l'audit Telegram. Sa référence est configurée via
FORMATION_STAGE_CHAT. Elle peut aussi servir de staging technique.

Les bibliothèques privées Business, Finance, Digitale, Mindset restent des
DESTINATIONS, pas des canaux supplémentaires de dépôt manuel. La destination
Générale demeure le canal public de formations généralistes.

Le propriétaire dépose une photo d'affiche puis les fichiers du cours dans
le même canal. Le webhook CineRadar analyse la catégorie indiquée dans la
légende ou les mots-clés non ambigus du titre, et rattache tous les fichiers
au même identifiant Cours. Le moteur envoie chaque formation complète dans
la seule destination appropriée, avec les reçus D1 anti-doublons.

## Légendes à utiliser

Exemple de photo de couverture (une vraie photo Telegram) :

    Cours: vente-pratique-2026
    Catégorie: Business
    Auteur: Organisme de formation autorisé
    Titre: Maîtriser les techniques de vente

Exemple de premier document (PDF / vidéo / ZIP autorisé) :

    Cours: vente-pratique-2026
    Total: 2
    Partie: 1/2

Exemple de second document :

    Cours: vente-pratique-2026
    Total: 2
    Partie: 2/2

La catégorie peut être omise des fichiers, parce qu'ils héritent de la
catégorie de la couverture portant EXACTEMENT le même identifiant Cours.
Si la couverture manque ou que la classification est contradictoire, le
fichier reste en attente : il n'est jamais envoyé à l'aveugle dans Général.

Domaines reconnus : Business, Finance, Digitale, Mindset, Générale.
Sans champ de catégorie, des titres comme bitcoin, python ou leadership
peuvent être reconnus, mais une ambiguïté entre deux catégories nécessite
un examen. Les formats exécutables, médias protégés ou cours incomplets
sont bloqués par le planificateur.

## Prérequis de sécurité et de publication

- La réserve Formation générale doit rester propriétaire et accessible aux
  deux bots de réception/publication. L'identité du canal doit correspondre
  au canal technique FORMATION_STAGE_CHAT.
- Le mapping FORMATION_DESTINATIONS_JSON conserve cinq destinations distinctes :
  general, business, finance, digitale, mindset.
- Le droit de redistribution est validé par catégorie, indépendamment de la
  possession du canal ou des autres catégories. Sans cela, le média est
  enregistré en attente privée et n'est pas publié.
- Le secours ne démarre que lors d'une session personnelle absente ou
  révoquée, jamais pendant FloodWait/PeerFlood ou une panne incertaine.
- Les quatre anciennes réserves privées spécialisées ne sont pas supprimées ;
  leurs fichiers historiques sont préservés, mais le webhook n'y reçoit plus
  de nouveaux dépôts pour le secours manuel.
- Le système applique ses quotas par catégorie et les reçus D1 idempotents.
  Un essai réel sur contenu redistribuable reste obligatoire avant de
  certifier les transferts Telegram de bout en bout.

Ceci décrit un routage à source unique ; aucun numéro de canal, invitation
privée ou secret Telegram n'est publié dans le dépôt.
