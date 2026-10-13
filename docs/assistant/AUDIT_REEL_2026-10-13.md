# Audit réel de l'assistant Mr XPRONOS — 13 octobre 2026

## Périmètre, méthode et preuves
- Site public : https://mrxpronos.github.io/MrXPRONOS_App/
- Backend : Supabase Edge Function `assistant` (V65, vérifiée pendant l'audit).
- 20 questions réelles envoyées à la fonction : 8 initiales + 12 supplémentaires.
- 12 parcours Playwright : 6 pages x ordinateur/mobile, avec ouverture/saisie/envoi/fermeture sur les pages qui chargent l'assistant.
- 7 vérifications d'entrées HTTP : JSON invalide, longueur, type, avis, méthode, suggestions.
- 1 essai du bouton de feedback : enregistrement Supabase vérifié puis entrée de test supprimée.
- Vérification en ligne des fichiers `data.json`, `bonus.json`, `articles.json`, `conseils.json`.

Exécutions reproductibles :
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38380654507
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38381334525
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38380930949
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38381269113
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38381791437
- https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/38381746148

## Corrections prioritaires — P0
1. **Informations VIP/LIVE devenues fausses.** Le site public précise que Simple, Pro, VIP et LIVE sont consultables gratuitement. La fonction annonce encore « code VIP actif, 5 000 F CFA/mois ». En cause : `BUSINESS_CONFIG.vip`, `renderVipResponse()`, `renderLiveResponse()`, messages d'accueil. Utiliser une configuration officielle unique, ne jamais inventer ou annoncer un tarif obsolète.
2. **Source des pronostics différente du site.** `data.json`, généré le 13/10 à 02:35 UTC, contient 244 entrées, dont 4 datées du 13/10, 10 du 12/10 et 3 du 14/10. L'assistant répond « aucun pronostic aujourd'hui » et « aucun résultat hier », car il interroge uniquement `public.pronostics` (dernier enregistrement daté du 09/10) et `pronostics_cache`. Lire les mêmes données publiées et appliquer exactement les mêmes règles que les pages publiques ; distinguer entrées, pronostics disponibles, résultats terminés et résultats validés.
3. **FAQ sémantiquement incorrecte.** Test réel « Que signifie xG ? » → réponse sur 1X2. Le tokeniseur supprime les termes de 2 caractères et maximise les mots communs « que signifie ». Implémenter priorité au match exact/termes spécialisés, stopwords, score robuste (PostgreSQL FTS/pg_trgm) et seuil de refus ; ajouter des tests sur xG, xA, 1X2, BTTS et corners.
4. **Le chatbot manque sur la page LIVE.** `live.html` ne charge pas `assets/js/assistant.js` : constat confirmé sur mobile et PC. L'ajouter sans casser React/JSX, avec tests UI.
5. **Question mineur mal orientée.** « J'ai 16 ans, est-ce que je peux parier ? » → « aucun pronostic aujourd'hui ». Ajouter intent sécurité/adulte prioritaire et réponse appropriée au lieu de rediriger vers les paris.

## Corrections importantes — P1
6. **Questions LIVE sans réponse à la demande :** « Quels signaux corners LIVE maintenant ? » ou « Explique la pression et le momentum... » renvoient l'ancien message d'abonnement VIP. Privilégier aide explicative, données LIVE vérifiées et lien direct ; indiquer la fraîcheur des données.
7. **Intents trop larges :** « Quels matchs sont à venir ? », « Les pronostics PRO sont gratuits ? » → absence de pronos. Séparer questions d'accès, de calendrier, d'éducation, de résultats et de sélections.
8. **Historique hebdomadaire mal compris :** « résultats de cette semaine » → « aucun résultat hier ». Supporter la fenêtre demandée, au minimum lien filtré, et ne pas confondre statut du coupon et score du match.
9. **Offres et bonus non synchronisés :** le chatbot liste six bookmakers avec les champs `bookmakers.bonus` (ex. 1xBet 130% jusqu'à 130€), alors que `bonus.json` publie 30 offres avec d'autres montants et critères (ex. première offre 1xBet 100 % jusqu'à 100 USD). Adopter les données de la page Bonus, mentionner dates/conditions/région ; éviter une « offre actuelle » sans validation.
10. **Contenu non retrouvé :** `getArticlesSlugs()` et `getConseilsSlugs()` lisent les tables `articles` et `conseils` qui ne figurent pas dans le schéma public inspecté. Le site a 86 entrées dans `articles.json` et 49 dans `conseils.json`. Adapter la recherche à la source publiée.
11. **Support incomplet :** la réponse donne WhatsApp/Telegram et le lien Contact ; le site propose aussi téléphone, Instagram, Facebook, YouTube, Threads. Autoriser les liens strictement extraits du site officiel.
12. **Réponses déterministes ignorent le contexte de page,** et ne renvoient aucun identifiant de conversation ; cela complique suivi et mesure des réponses.
13. **Contrôle qualité des FAQ** : QA automatique sur entités/mots-clés courts (xG, 1X2, DNB, BTTS) et réponses incohérentes ; conserver une validation humaine avant publication.

## Améliorations structurelles — P2
14. Une source de vérité versionnée pour accès gratuit, catégories, services, contacts, promos et liens, sans chiffres commerciaux en dur.
15. Afficher `source`, date de mise à jour et lien des informations variables ; éviter de figer des réponses LIVE ou bonus dans le cache.
16. Un statut assistant réellement fondé sur la disponibilité de l'API et des fournisseurs gratuits ; repli utile si l'IA n'est pas disponible.
17. Vérifier la gestion multi-utilisateur et de la limite de fréquence, notamment lorsque les en-têtes IP sont absents (identifiant « unknown » commun).
18. Limiter et authentifier les demandes d'avis. La branche `feedback` de la fonction est traitée avant la limitation de requêtes du chatbot.
19. Ajouter tests de non-régression réguliers GitHub Actions : accès VIP/LIVE, disponibilité des pronostics, xG/1X2, formulaires, mobile, liens.
20. Conserver un tableau d'erreurs de réponse et une file de relecture, sans transformer automatiquement les réponses IA en FAQ officielles.

## Ce qui fonctionne lors des tests
- HTTP 200 pour les sept pages/ressources testées.
- Échange dans le navigateur réussi sur Accueil, Pronostics, Historique, Bonus et Contact (ordinateur et mobile), sans overflow horizontal dans la fenêtre 390px.
- Entrées invalides HTTP 400, GET non prévu HTTP 405, suggestions HTTP 200.
- Bonnes réponses sur « plus de 2,5 buts », « BTTS » et le code XPVIP.
- Boutons d'avis visibles ; clic 👍 validé et bien enregistré en base, enregistrement synthétique retiré après test.

## Limites
Les 20 questions et 12 parcours sont des échantillons ciblés, pas la preuve exhaustive de toutes les combinaisons de réponses. Le LIVE a été chargé mais son flux sportif et chaque interaction de filtrage ne sont pas exhaustivement qualifiés ici. Aucun correctif fonctionnel n'a été déployé en production dans cette campagne d'audit ; seuls les scripts de test ont été ajoutés à la branche `assistant-real-audit-oct2026`.
