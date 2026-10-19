# Audit des heures de publication — Mr XPRONOS

**Date du diagnostic :** 19 octobre 2026 · **Fuseau :** Lomé UTC+0  
**Dépôt :** `MrXPRONOS/MrXPRONOS_App`  
**Exécutions :** [90 jours](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39196608217) · [180 jours](https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39196807683)

## Évidence recueillie (données réelles)
- **Telegram — canal Coupon Gratuit (@mrxpronosfr)** : 30 posts uniques de 12–17 octobre en base Supabase. À 17h, 4 publications ont une moyenne relevée de 52,3 vues; à 19h, 3 publications font 39,3 vues; à 20h, 2 publications font 43 vues; à 05h, 5 publications font 37,8 vues. Mesures cumulées prises à différents âges, comparaison **descriptive seulement**. Les autres canaux Telegram ne sont pas inclus dans le classement.
- **Instagram** : 100 derniers Reels recensés, 61 ont au moins 72 heures; 60/61 ont été publiés 00h–05h59, 1/61 14h–17h59. Médiane = **1 like+comment** sur ces 60 Reels de nuit. Impossible d'obtenir les vues : Insights refuse avec HTTP 400 / code 10. **Aucun meilleur horaire statistiquement identifiable**, faute de variation des heures.
- **Facebook** : 61 vidéos âgées de plus de 72h dans 90 jours; API `video_insights` refuse HTTP 403 / code 200. Vues non accessibles, aucune comparaison valide.
- **YouTube** : l'API de la chaîne fonctionne. Sur 180 jours, 9 vidéos éligibles assez anciennes; 7 entre 00h–05h59, médiane **19 vues**, 1 entre 14h–17h59 (**13 vues**) et 1 entre 22h–23h59 (**19 vues**). Ces faibles échantillons ne montrent aucune supériorité causale.
- **Threads** : API de lecture accessible, mais aucun post d'âge supérieur à 72h dans la fenêtre des 180 jours parmi les 100 posts récupérés. Le nouveau token permet de publier; pour obtenir Insights, demander `threads_manage_insights` lors d'une autorisation ultérieure.
- **TikTok** : `TIKTOK_ACCESS_TOKEN` non présent; aucune statistique exploitable.

**Réserve méthodologique :** les vues sont des compteurs à durée de vie variable (sauf comparaison approchée Telegram à 24h+), pas des vues comparables 24h après publication. Aucun test A/B randomisé n'a eu lieu. La valeur du pronostic, la compétition, la date, l'algorithme, la couverture géographique et la qualité du contenu influencent le résultat.

## Créneaux candidats à TESTER, pas «meilleures heures prouvées»

| Réseau | Test A (Lomé) | Test B (Lomé) | Priorité |
|---|---|---|---|
| Telegram — Coupon Gratuit | 17h15 | 19h15 | Élevée : premiers signaux locaux favorables le soir |
| Facebook vidéos | 12h15 | 19h00 | Moyenne : Insights à autoriser |
| Instagram Reels | 12h30 | 19h30 | Très élevée : corriger concentration nocturne |
| YouTube Shorts | 12h00 | 19h00 | Élevée : échantillon historique très limité |
| Threads | 08h30 | 19h30 | Moyenne : historique récent insuffisant |
| TikTok | 12h30 | 20h00 | Après connexion du compte et approbation des scopes |

Le calendrier **ne remplace pas** les deux vagues métier (`morning` 08:15 UTC / `evening` 18:15 UTC) : les matchs doivent être publiés **avant leur coup d'envoi**, et les sélections ne doivent pas être réutilisées dans le ledger. Pour un match à 15:00, ne pas attendre 19:00. On peut générer à l'heure actuelle puis programmer *la diffusion par plateforme* seulement si l'événement reste futur.

## Méthode d'optimisation

1. Pendant au moins 3 à 4 semaines, répartir les contenus comparables (Reels pré-match, vidéos résultats, éditions news) entre A et B, en variant les jours équitablement. Éviter de republier les mêmes matchs.
2. Relever pour chaque vidéo à **24h** et **72h** : vues, portée (si disponible), likes, commentaires, partages, suivi du compte, nouveaux abonnés, clics vers Telegram, heure de diffusion et heure de coup d'envoi. Ne pas assimiler vues et engagements.
3. Comparer **la médiane** des vues à âge égal, par réseau et type de contenu. Ne sélectionner un gagnant qu'avec au moins 10 publications comparables par créneau et des jours suffisamment répartis; sinon poursuivre les essais.
4. Maintenir la mention 18+ et le rappel au jeu responsable. Respecter la réglementation et les règles de chaque plateforme.

## Permissions statistiques nécessaires
- Meta Facebook : examiner `read_insights`, `pages_read_engagement` et les tâches de Page adaptées, puis confirmer que la métrique demandée est encore disponible dans la version de Graph API.
- Instagram professionnel : `instagram_manage_insights` (ou permissions équivalentes de l'application), puis tester `/{media_id}/insights`.
- YouTube : pour les rapports de la chaîne et l'activité des spectateurs, ajouter à une future autorisation les scopes `youtube.readonly` et `yt-analytics.readonly`. Ne pas remplacer le refresh token de publication sans les scopes de publication existants.
- Threads : `threads_manage_insights` en plus de `threads_basic` et `threads_content_publish`, avec nouvelle autorisation Meta.
- TikTok : compléter la connexion et demander `video.list` pour les statistiques des vidéos.

**Scripts livrés :** `scripts/social_timing_audit.py` et `.github/workflows/social-timing-audit.yml`. Consultation en lecture seule, secrets non affichés, artefact JSON agrégé téléchargeable depuis le run. Les heures des workflows de publication n'ont pas été modifiées dans cet audit.
