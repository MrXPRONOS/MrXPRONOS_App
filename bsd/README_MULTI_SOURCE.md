# Multi-source football — Mr XPRONOS

## Objectif

Réduire les appels BSD sans diminuer la qualité du moteur. Les sources gratuites
sont consultées avant BSD quand elles peuvent fournir une donnée compatible.
BSD reste le fallback lorsque les sources gratuites ne couvrent pas la rencontre
ou ne fournissent pas le type de donnée requis.

## Ordre de qualité / fiabilité

Cet ordre sert à départager des données contradictoires, pas à déterminer
l'ordre des appels HTTP.

| Rang | Source | Qualité | Fiabilité | Rôle principal |
|---:|---|---:|---:|---|
| 1 | ESPN | 95 | 95 | scores, live, événements, compositions, stats riches |
| 2 | BSD | 92 | 92 | couverture principale, stats manquantes, H2H, cotes |
| 3 | SportScore | 88 | 86 | matchs gratuits, live, H2H, lineups, incidents, stats variables |
| 4 | TheSportsDB | 78 | 82 | confirmation et enrichissement secondaire |
| 5 | OpenLigaDB | 72 | 78 | scores/buts et confirmation sur les compétitions couvertes |

Les valeurs sont des poids internes Mr XPRONOS, pas des mesures officielles
publiées par les fournisseurs.

## Stratégie d'appel

### LIVE

1. Cache Supabase récent.
2. SportScore live.
3. ESPN.
4. TheSportsDB / OpenLigaDB pour confirmation et enrichissement.
5. BSD /events/live/ seulement si la couverture gratuite est insuffisante.
6. SportScore match detail puis TheSportsDB event stats.
7. BSD /stats/ uniquement pour les statistiques encore manquantes.

Si SportScore couvre au moins 90 % du nombre de matchs live signalé par la
couverture BSD, l'appel BSD /events/live/ est évité.

### Matchs / pronostics BSD

BSDClient.list_events() conserve les IDs BSD afin de rester compatible avec
l'historique et les modèles, puis recoupe les fixtures avec SportScore,
TheSportsDB et OpenLigaDB.

Les fournisseurs gratuits peuvent remplir des champs manquants (ligue, logo,
score) et ajoutent la provenance dans provider_matches / provider_sources.

### Forme récente

SportScore est interrogé en premier quand le nom de l'équipe est connu.
BSD reste le fallback si SportScore ne retourne pas assez de matchs terminés.

### H2H

Historique local en priorité. Pour un match futur avec historique local
insuffisant, SportScore H2H est essayé avant BSD H2H.

### Saisons et historiques BSD

Les IDs championnat/saison BSD sont conservés pour les opérations de backfill
et les traitements historiques qui dépendent de ces identifiants. Les sources
gratuites servent à enrichir les fixtures lorsqu'elles peuvent être rapprochées,
mais ne remplacent pas un identifiant BSD par un identifiant fournisseur.

## SportScore : données vérifiées le 13 octobre 2026

Test direct depuis GitHub Actions :

- 200 fixtures retournées sur la journée testée ;
- le détail match retourne lineups, incidents, stats, tracker ;
- compositions confirmées avec 11 titulaires possibles ;
- événements observés : buts, CSC, cartons, remplacements, VAR ;
- sur 12 matchs sondés : 9 avaient des statistiques et 4 une composition confirmée ;
- statistiques observées : possession, tirs cadrés, tirs non cadrés, attaques,
  attaques dangereuses ;
- Mr XPRONOS reconstruit les tirs totaux à partir de tirs cadrés + non cadrés
  lorsqu'un total explicite n'existe pas.

## SportScore et cotes

Le site SportScore affiche des cotes pré-match et des marchés live, mais
l'API REST publique documentée ne fournit actuellement aucun endpoint odds.
Un probe récursif du JSON de /api/v1/match/ n'a trouvé aucun champ contenant
odds, bookmaker, betting ou market.

Conséquence :

- aucune récupération HTML/scraping des cotes SportScore ;
- aucune dépendance à un endpoint privé/non documenté ;
- BSD reste la source de cotes du moteur tant qu'un endpoint SportScore
  officiel et stable n'est pas disponible.

## TheSportsDB

La clé publique gratuite 123 est utilisée. Les endpoints stats/lineup/timeline
peuvent répondre null selon la rencontre : ils sont donc des fallbacks et
jamais une condition nécessaire au fonctionnement du live.

## OpenLigaDB

Utilisé principalement comme source de confirmation scores/buts sur les ligues
couvertes. Ses identifiants ne remplacent jamais les IDs BSD.

## Attribution SportScore

L'offre gratuite requiert une attribution. Les pages football publiques de
Mr XPRONOS affichent donc un lien Powered by SportScore.