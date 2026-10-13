# Routage des fournisseurs football

Mis à jour : 13 octobre 2026.

Les scores ci-dessous sont des **poids internes Mr XPRONOS** utilisés pour arbitrer et router les données. Ils ne constituent pas une notation officielle des fournisseurs.

| Source | Poids | Usage principal |
|---|---:|---|
| ESPN | 98 | Faits de match, compositions, timeline, stats, validation pré-publication |
| BSD | 96 | Couverture étendue, IDs historiques, marchés et odds documentées |
| football-data.org | 94 | Classements sur compétitions couvertes, clé optionnelle |
| SportScore | 91 | Live, fixtures, H2H, forme, détail match, standings, joueurs |
| API-Football | 90 | Buteurs/statistiques optionnels à clé |
| SportsAPI Pro | 88 | Source existante à clés rotatives |
| OpenLigaDB | 84 | Résultats, buts, classements, ligues couvertes |
| TheSportsDB | 80 | Détails, timeline, lineups et stats en fallback |

## Ordre d'appel pour réduire BSD

Pour les données de match : **ESPN → SportScore → OpenLigaDB/TheSportsDB → BSD**.

Le moteur ne choisit pas aveuglément la première réponse : il rapproche les fixtures par équipes/date et conserve les identifiants BSD lorsque BSD est nécessaire.

### LIVE
- ESPN + SportScore + TheSportsDB sont récupérés avant `/events/live/` BSD.
- `coverage.live_now` BSD sert de référence de couverture.
- Si les sources gratuites atteignent le ratio configuré (85% par défaut), la découverte BSD est sautée.
- Les stats détaillées SportScore/TheSportsDB sont essayées avant `/events/{id}/stats/`.
- BSD complète seulement les matchs encore incomplets.

### Actu Foot
- Calendrier gratuit avant BSD.
- Forme récente : SportScore avant BSD.
- H2H : archive locale → SportScore → BSD.
- OpenLigaDB intervient de façon league-aware et pour les classements/buteurs disponibles.
- TheSportsDB sert de détail/fallback; sa clé publique gratuite impose une couverture plus limitée.

### Archive
Les journées anciennes déjà présentes localement peuvent être reconfirmées gratuitement avant de rappeler BSD. Les backfills saisonniers initiaux restent BSD afin de conserver les IDs BSD et l'intégrité de l'archive.

## Cotes / odds

**SportScore affiche des cotes sur son site, mais son API REST publique documentée ne publie actuellement aucun endpoint odds.**
Les conditions du site ne permettent pas d'en faire un flux de scraping automatisé.

Politique actuelle :
- odds pré-match : BSD ;
- odds live : aucune nouvelle source gratuite validée ;
- SportScore odds : désactivé tant qu'un endpoint officiel n'est pas documenté.

Ne jamais fabriquer, scraper ou dériver une cote en la présentant comme une cote bookmaker.

## SportScore attribution

L'offre gratuite SportScore exige une attribution visible. Les surfaces publiques qui rendent ses données doivent inclure un lien dofollow vers `https://sportscore.com/` avec une mention SportScore.
