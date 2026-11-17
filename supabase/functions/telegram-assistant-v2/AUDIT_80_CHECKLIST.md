# Mr XPRONOS — 80 améliorations : vérification de l'implémentation

Date : 17 novembre 2026, après la version 24 ; branche : `feature/telegram-assistant-nvidia-v2-20261107`.

## Les quatre axes fondamentaux

1. **Comprendre** les intentions, les formulations, les abréviations et le contexte.
2. **Vérifier les connaissances** : vrais coupons, pages, liens et cotes fiables.
3. **Faire dialoguer NVIDIA** naturellement, avec une aide adaptée.
4. **Contrôler avant envoi** : cohérence, sécurité, sources, boutons, présentation.

**Note de lecture :** ✅ signifie qu'une fonctionnalité est codée et couverte par des tests ou une vérification du code ; ce n'est pas une preuve de fonctionnement sur la vraie API NVIDIA. 🟡 = incomplète ou non validée en conditions réelles. ⬜ = à développer.

## A. Analyse des photos

- [ ] **01. Réparer le transfert d’images NVIDIA 410** — 🟡 Partielle. *Compression JPEG/PNG avant NVCF ; un HTTP 410 reste possible sur de très grands médias, sans essai réel de la clé NVIDIA*
- [x] **02. Envoyer les petites images en base64** — ✅ Complète au niveau du code et des tests. *Seuil 128 ko et test du choix de fichier*
- [ ] **03. Compresser ou redimensionner les images trop grandes** — 🟡 Partielle. *Réencodage et réduction progressive intégrés via codecs JPEG/PNG JavaScript pur, tests injectés ; dépendances Edge non vérifiées sur une vraie photo*
- [ ] **04. Basculer entre deux modèles visuels** — 🟡 Partielle. *Deux modèles visuels essayés séquentiellement, mais disponibilité réelle non vérifiée sur le compte NVIDIA*
- [ ] **05. Lire textes, boutons et erreurs visibles** — 🟡 Partielle. *Extraction JSON des textes, boutons et erreurs ; lecture réelle de captures non testée*
- [ ] **06. Ne pas inventer de détails visuels** — 🟡 Partielle. *Instruction de ne pas inventer, relecture JSON et rejet des réponses incertaines ; aucune vérification indépendante de chaque détail*
- [ ] **07. Reprendre une inscription via capture** — 🟡 Partielle. *Description visuelle transmise à NVIDIA avec mémoire de l’étape ; essai client réel manquant*
- [x] **08. Expliquer un échec et demander un recadrage** — ✅ Complète au niveau du code et des tests. *Erreurs spécifiques renvoyées au client*

## B. Messages vocaux

- [ ] **09. Transcrire les vocaux Telegram Ogg/Opus** — 🟡 Partielle. *ASR Ogg/Opus prévu par la passerelle Nemotron Transcribe, mais URL de service non configurée/confirmée*
- [ ] **10. Contrôler le protocole du service ASR** — 🟡 Partielle. *Endpoint HTTPS validé et disponibilité vérifiable par /health ; protocole réel non validé faute d’URL fonctionnelle*
- [x] **11. Reconnaître les noms de bookmakers après transcription** — ✅ Complète au niveau du code et des tests. *Contrôle déterministe après transcription*
- [x] **12. Faire confirmer Bedclicker avant un lien Betclic** — ✅ Complète au niveau du code et des tests. *Confirmation obligatoire*
- [ ] **13. Utiliser un score de confiance ASR** — 🟡 Partielle. *Indice heuristique de fiabilité calculé avec anomalies ASR, sans score probabiliste calibré fourni par le modèle*
- [ ] **14. Gérer accents et répétitions** — 🟡 Partielle. *Nettoyage des répétitions et correction phonétique ; gestion des accents acoustiques dépend du moteur ASR réel*
- [x] **15. Conserver la conversation après transcription confuse** — ✅ Complète au niveau du code et des tests. *Contexte vocal confirmé en mémoire de session ; réponse « oui » ou correction textuelle reliée au dialogue*
- [x] **16. Réinterpréter une transcription corrigée par le client** — ✅ Complète au niveau du code et des tests. *La commande « Non, j’ai dit … » rectifie la transcription persistante avant la réponse IA*

## C. Compréhension du langage

- [x] **17. Comprendre les fautes et abréviations** — ✅ Complète au niveau du code et des tests. *Règles SMS et 1000 exemples synthétiques*
- [x] **18. Comprendre cote dix et cote totale 10** — ✅ Complète au niveau du code et des tests. *Détection spécifique*
- [x] **19. Distinguer cote, coupon et score exact** — ✅ Complète au niveau du code et des tests. *Intentions séparées*
- [ ] **20. Éviter les réponses hors sujet** — 🟡 Partielle. *Filtre de pertinence pour installation/cote et contrôles des réponses ; aucune couverture sémantique exhaustive*
- [x] **21. Utiliser les relances et messages courts** — ✅ Complète au niveau du code et des tests. *Historique porté à 20 messages*
- [x] **22. Poser une seule clarification utile** — ✅ Complète au niveau du code et des tests. *Une seule question de clarification autorisée dans la sortie de contrôle, avec tests*
- [x] **23. Reformuler une explication incomprise** — ✅ Complète au niveau du code et des tests. *Consigne de reformulation au modèle et réponse de secours tenant compte de la dernière explication, avec tests*
- [x] **24. Distinguer erreur de formulation et absence de données** — ✅ Complète au niveau du code et des tests. *Distingue les demandes ambiguës, les sources manquantes et les données vérifiées dans les domaines publiés, avec tests*

## D. Guidage pas à pas

- [x] **25. Reconnaître les demandes de guide** — ✅ Complète au niveau du code et des tests. *Expressions courantes et confirmation « fait »*
- [x] **26. Conserver la progression durablement** — ✅ Complète au niveau du code et des tests. *État des étapes, but et plateforme persistés dans la table RLS mx_telegram_assistant_sessions*
- [x] **27. Envoyer une seule étape à la fois** — ✅ Complète au niveau du code et des tests. *Découpage du guide et tests*
- [x] **28. Ne pas déclarer une action réussie sans confirmation** — ✅ Complète au niveau du code et des tests. *Le bot attend « fait »*
- [x] **29. Reconnaître fait, fini, suivant, terminé** — ✅ Complète au niveau du code et des tests. *Expressions courantes gérées*
- [x] **30. Rester sur une étape en cas de blocage** — ✅ Complète au niveau du code et des tests. *Questions de blocage et captures conservent l’étape, les nouveaux sujets ferment le guide*
- [ ] **31. Utiliser la photo pour guider l’étape** — 🟡 Partielle. *La description d’une photo s’intègre à l’étape guidée persistante ; reconnaissance visuelle réelle non confirmée*
- [x] **32. Reprendre ou abandonner un guide par commande** — ✅ Complète au niveau du code et des tests. *`/restart`, « Recommence depuis le début » et `/stop` sont pris en charge ; la conservation de progression reste partielle (point 26).*

## E. Pronostics et données sportives

- [x] **33. Lire les coupons publiés à la date demandée** — ✅ Complète au niveau du code et des tests. *Source data.json*
- [x] **34. Exclure matchs terminés ou déjà commencés** — ✅ Complète au niveau du code et des tests. *Filtre des heures et statuts*
- [x] **35. Supprimer les doublons de sélections** — ✅ Complète au niveau du code et des tests. *Filtre équipe, date, sélection*
- [x] **36. Distinguer confiance estimée et taux de réussite** — ✅ Complète au niveau du code et des tests. *Consignes et formatage*
- [ ] **37. Réconcilier les horaires contradictoires entre toutes les pages** — 🟡 Partielle. *Rapprochement des horaires data.json et scores-exacts-daily, seuil de 5 minutes ; pas toutes les pages du site*
- [ ] **38. Construire une cote combinée 10 vérifiée** — 🟡 Partielle. *Moteur de combinaisons testé sur cotes réelles issues d’un flux horodaté valide, mais aucun flux odds.json alimenté*
- [x] **39. Ne jamais inventer une cote quand la source manque** — ✅ Complète au niveau du code et des tests. *Garde-fou de sortie*
- [x] **40. Après un coupon, proposer site et canal** — ✅ Complète au niveau du code et des tests. *Deux boutons contextuels*

## F. Bookmakers et promotion

- [x] **41. Limiter les liens à un catalogue officiel** — ✅ Complète au niveau du code et des tests. *Liste blanche de partenaires*
- [ ] **42. Appliquer une liste de bookmakers exclus** — 🟡 Partielle. *Exclusions configurables via MX_ASSISTANT_EXCLUDED_BOOKMAKERS ; aucune liste métier explicite fournie pour activation*
- [ ] **43. Proposer des alternatives explicitement autorisées** — 🟡 Partielle. *Alternatives explicitement approuvées configurables via MX_ASSISTANT_APPROVED_ALTERNATIVES ; valeurs non fournies*
- [ ] **44. Reconnaître toutes les variantes phonétiques** — 🟡 Partielle. *Rapprochement phonétique et confirmation des noms proches, sans garantie sur toute prononciation possible*
- [x] **45. Vérifier la destination de chaque lien partenaire** — ✅ Complète au niveau du code et des tests. *Validation de liste blanche*
- [x] **46. Affirmer XPVIP dans l’inscription appropriée** — ✅ Complète au niveau du code et des tests. *Code séparé et formaté*
- [ ] **47. Adapter les inscriptions selon pays et conditions** — 🟡 Partielle. *Pays détecté et vérification légale demandée ; aucune source juridique par pays intégrée*
- [x] **48. Ne pas recommander un bookmaker hors contexte** — ✅ Complète au niveau du code et des tests. *Filtre de contexte promotionnel*

## G. Site et communauté

- [x] **49. Connaître installer.html** — ✅ Complète au niveau du code et des tests. *Lien officiel ajouté au bot*
- [x] **50. Inclure la page installation dans le sitemap public** — ✅ Complète au niveau du code et des tests. *Page installer.html ajoutée au sitemap sur la branche main (commit 60787aaf) ; propagation du site externe à vérifier*
- [x] **51. Offrir un bouton vers l’installation** — ✅ Complète au niveau du code et des tests. *Lien testé*
- [x] **52. Adapter installation Android, iOS et Windows** — ✅ Complète au niveau du code et des tests. *Guides iPhone/Safari, Android/Chrome et Windows/Edge dérivés de la page officielle ; tests de contenu*
- [x] **53. Diriger vers les pronostics et non l’accueil générique** — ✅ Complète au niveau du code et des tests. *Destination dédiée*
- [x] **54. Envoyer le canal pour les alertes de coupons** — ✅ Complète au niveau du code et des tests. *Lien officiel*
- [x] **55. Proposer le site et le canal ensemble** — ✅ Complète au niveau du code et des tests. *CTA double vérifié*
- [x] **56. Éviter les boutons dans les politesses** — ✅ Complète au niveau du code et des tests. *Filtrage contextuel*

## H. Formatage Telegram

- [x] **57. Mettre en gras les informations principales** — ✅ Complète au niveau du code et des tests. *HTML Telegram*
- [x] **58. Séparer un titre du texte** — ✅ Complète au niveau du code et des tests. *Ligne vide automatique*
- [x] **59. Espacer la première étape et les paragraphes** — ✅ Complète au niveau du code et des tests. *Tests d’espacement*
- [x] **60. Mettre les réserves en italique** — ✅ Complète au niveau du code et des tests. *HTML Telegram*
- [x] **61. Utiliser des citations pour la prudence** — ✅ Complète au niveau du code et des tests. *HTML Telegram*
- [ ] **62. Supprimer tous les doublons de code et de lien** — 🟡 Partielle. *Déduplication des lignes et XPVIP identiques, liens invalides filtrés ; toutes répétitions libres ne sont pas détectables*
- [ ] **63. Corriger toutes les phrases maladroites** — 🟡 Partielle. *Nettoyage et contrôle de cohérence des phrases fréquentes, sans relecture linguistique exhaustive indépendante*
- [x] **64. Adapter la longueur et les liens multiples** — ✅ Complète au niveau du code et des tests. *1 à 5 messages, 3 boutons + liens ancrés*

## I. Fiabilité des modèles

- [x] **65. Suivre les temps de réponse** — ✅ Complète au niveau du code et des tests. *Latences, résultats et modèles enregistrés en table RLS ; commande administrateur /health*
- [x] **66. Éviter les modèles NVIDIA qui échouent en boucle** — ✅ Complète au niveau du code et des tests. *Historique d’erreurs partagé entre instances via Supabase et temporisation après deux pannes ; tests*
- [x] **67. Limiter délais par modèle et délai global** — ✅ Complète au niveau du code et des tests. *Timeout et budget définis*
- [x] **68. Arrêter au premier modèle ayant réussi** — ✅ Complète au niveau du code et des tests. *Failover testé*
- [x] **69. Contrôler JSON mal formé** — ✅ Complète au niveau du code et des tests. *Parse et repli*
- [x] **70. Éviter doublon après échec au milieu d’un message multiple** — ✅ Complète au niveau du code et des tests. *Réservation unique de chaque fragment en base AVANT l’envoi : absence de double envoi lors d’un rejeu testé ; possible fragment non transmis lors d’une coupure*
- [x] **71. Conserver plus de huit messages** — ✅ Complète au niveau du code et des tests. *Résumé contextualisé persistant dans Supabase et réinjecté dans NVIDIA après la fenêtre des messages récents*
- [x] **72. Garantir un secours totalement contextuel** — ✅ Complète au niveau du code et des tests. *Repli contextualisé sans second appel NVIDIA, sur les intentions et liens officiels, avec tests*

## J. Sécurité et confidentialité

- [x] **73. Protéger les mineurs** — ✅ Complète au niveau du code et des tests. *Réponse déterministe sans promotion*
- [x] **74. Détecter les situations de perte de contrôle** — ✅ Complète au niveau du code et des tests. *Réponse prudente*
- [x] **75. Ne jamais garantir de gain** — ✅ Complète au niveau du code et des tests. *Prompt et vérification de sortie*
- [x] **76. Distinguer analyse sportive et conseil à risque** — ✅ Complète au niveau du code et des tests. *Détection étendue des pertes, dettes, doubles mises et demandes à risque avec réponse non promotionnelle*
- [x] **77. Ne jamais demander des OTP ou mots de passe** — ✅ Complète au niveau du code et des tests. *Filtre et archivage masqué*
- [ ] **78. Masquer les données sensibles à l’intérieur des images** — 🟡 Partielle. *Avertissement et blocage des captures explicitement décrites comme sensibles ; aucun masquage automatique garanti des pixels ou secrets invisibles*
- [x] **79. Ne pas prétendre lire des médias indisponibles** — ✅ Complète au niveau du code et des tests. *Retour d’erreur transparent*
- [x] **80. Escalader vers un responsable** — ✅ Complète au niveau du code et des tests. *Notification et pause de conversation*

## Bilan chiffré

✅ Code/tests : **59** ; 🟡 partiellement : **21** ; ⬜ à faire : **0**.

## Conditions avant une validation réelle

- Test d'une capture avec la clé NVIDIA : le transfert NVCF a auparavant répondu HTTP 410 ; le repli vers une photo moins volumineuse ne garantit pas à lui seul la compatibilité réelle.
- Test d'un vocal Ogg/Opus après configuration d'un endpoint Nemotron Transcribe compatible.
- Clarification officielle des bookmakers autorisés, exclus et alternatives.
- Publication du sitemap modifié sur la branche qui alimente le site public.
- Mémoire d'étapes et de fragments de messages plus durable en cas d'échec réseau.
- Mesure des réponses sur un échantillon réel de clients sans exposer leurs données sensibles.

## Ressources de test

- `tests/assistant.test.mjs` : sécurité, coupons, contexte, NVIDIA, multimédia et formatage.
- `tests/corpus.test.mjs` : contrôle des 1000 exemples.
- `tests/fixtures/1000_messages_clients.csv` : 1000 formulations synthétiques.

## Revue complémentaire des anciennes améliorations partielles

Les 29 éléments partiels initiaux ont été réévalués. 8 sont désormais considérés complets au niveau du code et des tests. Les deux éléments précédemment absents (#13 et #70) sont devenus partiels grâce aux heuristiques ASR et aux reçus de livraison.

**Éléments bloquants toujours ouverts :** validation réelle de NVIDIA Vision sur les documents volumineux (410), serveur ASR Ogg/Opus effectif, légalité et disponibilité des bookmakers selon pays, accès à des cotes bookmaker en temps réel, qualité sémantique des réponses libres, impossibilité d'obtenir une garantie de livraison exactement une fois avec l'API Telegram.

**Nouvelles tables privées :** `mx_telegram_assistant_sessions`, `mx_telegram_assistant_model_events` et `mx_telegram_assistant_delivery_receipts`. Leur RLS est activée, avec droits réservés au rôle serveur.

**Tests :** 114 fonctions historiques + 15 scénarios avancés + 5 contrôles du corpus, soit 134/134 dans le harnais simulé ; simulation du webhook de guide, coupon et accueil vérifiée.

## Revue des 28 derniers points — version 23

Dans les 28 éléments encore ouverts, 7 passent à « complet au niveau du code et des tests » (#22, #23, #24, #70, #71, #72, #76), les 5 éléments auparavant absents deviennent partiels (#03, #37, #42, #43, #78). Les autres progressent, mais un succès de test simulé ne prouve pas leur fonctionnement sur des images, transcriptions ou flux réels.

**Dépendances à finaliser :** vérification du chargement npm des codecs d'image et d’une capture réelle ; disponibilité d’un endpoint Nemotron Transcribe HTTPS et d'un vrai vocal Ogg/Opus ; flux officiel `odds.json` alimenté ; définition des bookmakers exclus et alternatives approuvées ; sources légales par pays ; analyse automatique avec masquage des secrets dans les pixels (non disponible). L’API Telegram ne garantit pas une livraison exactement une fois lors d’une panne réseau, même avec la réservation en base.

**Version production :** `telegram-assistant-v2` 24 ACTIVE, bot de coupons `telegram_webhook` 38 ACTIVE. **150/150** tests JavaScript simulés réussis, aucune preuve de conversation réelle supplémentaire depuis le déploiement. Les nouvelles tables RLS sont réservées au rôle serveur.

## Correctif vocal de la version 24

Le bot recalcule maintenant l'intention sur le contenu réellement confirmé. Une correction de nom de marque conserve l'objectif d'inscription uniquement si la première transcription l'exprimait explicitement. Un test de régression supplémentaire porte le total à **150/150 tests réussis**.
