# Mr XPRONOS — 80 améliorations : vérification de l'implémentation

Date : 17 novembre 2026 ; branche : `feature/telegram-assistant-nvidia-v2-20261107`.

## Les quatre axes fondamentaux

1. **Comprendre** les intentions, les formulations, les abréviations et le contexte.
2. **Vérifier les connaissances** : vrais coupons, pages, liens et cotes fiables.
3. **Faire dialoguer NVIDIA** naturellement, avec une aide adaptée.
4. **Contrôler avant envoi** : cohérence, sécurité, sources, boutons, présentation.

**Note de lecture :** ✅ signifie qu'une fonctionnalité est codée et couverte par des tests ou une vérification du code ; ce n'est pas une preuve de fonctionnement sur la vraie API NVIDIA. 🟡 = incomplète ou non validée en conditions réelles. ⬜ = à développer.

## A. Analyse des photos

- [ ] **01. Réparer le transfert d’images NVIDIA 410** — 🟡 Partielle. *Petites versions Telegram prioritaires ; grands fichiers dépendent toujours de NVCF*
- [x] **02. Envoyer les petites images en base64** — ✅ Complète au niveau du code et des tests. *Seuil 128 ko et test du choix de fichier*
- [ ] **03. Compresser ou redimensionner les images trop grandes** — ⬜ Non implémentée. *Aucun processeur de redimensionnement installé*
- [ ] **04. Basculer entre deux modèles visuels** — 🟡 Partielle. *Code disponible, clés et appels réels non validés*
- [ ] **05. Lire textes, boutons et erreurs visibles** — 🟡 Partielle. *Prompt prévu ; performances réelles inconnues*
- [ ] **06. Ne pas inventer de détails visuels** — 🟡 Partielle. *Consignes conservatrices, pas de validation indépendante*
- [ ] **07. Reprendre une inscription via capture** — 🟡 Partielle. *Vision raccordée au dialogue, intégration réelle non certifiée*
- [x] **08. Expliquer un échec et demander un recadrage** — ✅ Complète au niveau du code et des tests. *Erreurs spécifiques renvoyées au client*

## B. Messages vocaux

- [ ] **09. Transcrire les vocaux Telegram Ogg/Opus** — 🟡 Partielle. *Requiert un service Nemotron Transcribe configuré*
- [ ] **10. Contrôler le protocole du service ASR** — 🟡 Partielle. *Formats contrôlés, endpoint réel non vérifié*
- [x] **11. Reconnaître les noms de bookmakers après transcription** — ✅ Complète au niveau du code et des tests. *Contrôle déterministe après transcription*
- [x] **12. Faire confirmer Bedclicker avant un lien Betclic** — ✅ Complète au niveau du code et des tests. *Confirmation obligatoire*
- [ ] **13. Utiliser un score de confiance ASR** — ⬜ Non implémentée. *La passerelle actuelle ne fournit pas ce score*
- [ ] **14. Gérer accents et répétitions** — 🟡 Partielle. *Normalisation de variantes, pas évaluation acoustique*
- [ ] **15. Conserver la conversation après transcription confuse** — 🟡 Partielle. *Historique augmenté à 20 messages*
- [ ] **16. Réinterpréter une transcription corrigée par le client** — 🟡 Partielle. *L’IA exploite l’historique, pas de procédure dédiée*

## C. Compréhension du langage

- [x] **17. Comprendre les fautes et abréviations** — ✅ Complète au niveau du code et des tests. *Règles SMS et 1000 exemples synthétiques*
- [x] **18. Comprendre cote dix et cote totale 10** — ✅ Complète au niveau du code et des tests. *Détection spécifique*
- [x] **19. Distinguer cote, coupon et score exact** — ✅ Complète au niveau du code et des tests. *Intentions séparées*
- [ ] **20. Éviter les réponses hors sujet** — 🟡 Partielle. *Garde-fous présents, pas de mesure sémantique exhaustive*
- [x] **21. Utiliser les relances et messages courts** — ✅ Complète au niveau du code et des tests. *Historique porté à 20 messages*
- [ ] **22. Poser une seule clarification utile** — 🟡 Partielle. *Règle IA ; pas de validateur systématique*
- [ ] **23. Reformuler une explication incomprise** — 🟡 Partielle. *Comportement demandé à NVIDIA*
- [ ] **24. Distinguer erreur de formulation et absence de données** — 🟡 Partielle. *Sources vérifiées dans certains domaines*

## D. Guidage pas à pas

- [x] **25. Reconnaître les demandes de guide** — ✅ Complète au niveau du code et des tests. *Expressions courantes et confirmation « fait »*
- [ ] **26. Conserver la progression durablement** — 🟡 Partielle. *Historique en base, sans table d’étapes dédiée*
- [x] **27. Envoyer une seule étape à la fois** — ✅ Complète au niveau du code et des tests. *Découpage du guide et tests*
- [x] **28. Ne pas déclarer une action réussie sans confirmation** — ✅ Complète au niveau du code et des tests. *Le bot attend « fait »*
- [x] **29. Reconnaître fait, fini, suivant, terminé** — ✅ Complète au niveau du code et des tests. *Expressions courantes gérées*
- [ ] **30. Rester sur une étape en cas de blocage** — 🟡 Partielle. *Heuristique, cas complexes incomplets*
- [ ] **31. Utiliser la photo pour guider l’étape** — 🟡 Partielle. *Dépend de la vision NVIDIA*
- [x] **32. Reprendre ou abandonner un guide par commande** — ✅ Complète au niveau du code et des tests. *`/restart`, « Recommence depuis le début » et `/stop` sont pris en charge ; la conservation de progression reste partielle (point 26).*

## E. Pronostics et données sportives

- [x] **33. Lire les coupons publiés à la date demandée** — ✅ Complète au niveau du code et des tests. *Source data.json*
- [x] **34. Exclure matchs terminés ou déjà commencés** — ✅ Complète au niveau du code et des tests. *Filtre des heures et statuts*
- [x] **35. Supprimer les doublons de sélections** — ✅ Complète au niveau du code et des tests. *Filtre équipe, date, sélection*
- [x] **36. Distinguer confiance estimée et taux de réussite** — ✅ Complète au niveau du code et des tests. *Consignes et formatage*
- [ ] **37. Réconcilier les horaires contradictoires entre toutes les pages** — ⬜ Non implémentée. *Aucun comparateur multi-source*
- [ ] **38. Construire une cote combinée 10 vérifiée** — 🟡 Partielle. *Intention reconnue, pas de cotes bookmaker réelles*
- [x] **39. Ne jamais inventer une cote quand la source manque** — ✅ Complète au niveau du code et des tests. *Garde-fou de sortie*
- [x] **40. Après un coupon, proposer site et canal** — ✅ Complète au niveau du code et des tests. *Deux boutons contextuels*

## F. Bookmakers et promotion

- [x] **41. Limiter les liens à un catalogue officiel** — ✅ Complète au niveau du code et des tests. *Liste blanche de partenaires*
- [ ] **42. Appliquer une liste de bookmakers exclus** — ⬜ Non implémentée. *Règle métier contradictoire à clarifier*
- [ ] **43. Proposer des alternatives explicitement autorisées** — ⬜ Non implémentée. *Catalogue complémentaire à définir*
- [ ] **44. Reconnaître toutes les variantes phonétiques** — 🟡 Partielle. *Principaux cas reconnus et confirmés*
- [x] **45. Vérifier la destination de chaque lien partenaire** — ✅ Complète au niveau du code et des tests. *Validation de liste blanche*
- [x] **46. Affirmer XPVIP dans l’inscription appropriée** — ✅ Complète au niveau du code et des tests. *Code séparé et formaté*
- [ ] **47. Adapter les inscriptions selon pays et conditions** — 🟡 Partielle. *Réserve générale, pas de vérification par pays*
- [x] **48. Ne pas recommander un bookmaker hors contexte** — ✅ Complète au niveau du code et des tests. *Filtre de contexte promotionnel*

## G. Site et communauté

- [x] **49. Connaître installer.html** — ✅ Complète au niveau du code et des tests. *Lien officiel ajouté au bot*
- [ ] **50. Inclure la page installation dans le sitemap public** — 🟡 Partielle. *Modification commise sur branche non publiée*
- [x] **51. Offrir un bouton vers l’installation** — ✅ Complète au niveau du code et des tests. *Lien testé*
- [ ] **52. Adapter installation Android, iOS et Windows** — 🟡 Partielle. *IA informée, test appareil manquant*
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
- [ ] **62. Supprimer tous les doublons de code et de lien** — 🟡 Partielle. *Nettoyage de cas connus*
- [ ] **63. Corriger toutes les phrases maladroites** — 🟡 Partielle. *Contrôle partiel*
- [x] **64. Adapter la longueur et les liens multiples** — ✅ Complète au niveau du code et des tests. *1 à 5 messages, 3 boutons + liens ancrés*

## I. Fiabilité des modèles

- [ ] **65. Suivre les temps de réponse** — 🟡 Partielle. *Logs de modèles, pas de tableau de bord dédié*
- [ ] **66. Éviter les modèles NVIDIA qui échouent en boucle** — 🟡 Partielle. *Circuit breaker temporaire par instance*
- [x] **67. Limiter délais par modèle et délai global** — ✅ Complète au niveau du code et des tests. *Timeout et budget définis*
- [x] **68. Arrêter au premier modèle ayant réussi** — ✅ Complète au niveau du code et des tests. *Failover testé*
- [x] **69. Contrôler JSON mal formé** — ✅ Complète au niveau du code et des tests. *Parse et repli*
- [ ] **70. Éviter doublon après échec au milieu d’un message multiple** — ⬜ Non implémentée. *Pas de suivi d’envoi par fragment*
- [ ] **71. Conserver plus de huit messages** — 🟡 Partielle. *20 relus, 12 réinjectés, pas de résumé durable*
- [ ] **72. Garantir un secours totalement contextuel** — 🟡 Partielle. *Templates partiels*

## J. Sécurité et confidentialité

- [x] **73. Protéger les mineurs** — ✅ Complète au niveau du code et des tests. *Réponse déterministe sans promotion*
- [x] **74. Détecter les situations de perte de contrôle** — ✅ Complète au niveau du code et des tests. *Réponse prudente*
- [x] **75. Ne jamais garantir de gain** — ✅ Complète au niveau du code et des tests. *Prompt et vérification de sortie*
- [ ] **76. Distinguer analyse sportive et conseil à risque** — 🟡 Partielle. *Filtre partiel*
- [x] **77. Ne jamais demander des OTP ou mots de passe** — ✅ Complète au niveau du code et des tests. *Filtre et archivage masqué*
- [ ] **78. Masquer les données sensibles à l’intérieur des images** — ⬜ Non implémentée. *Pas de masquage visuel*
- [x] **79. Ne pas prétendre lire des médias indisponibles** — ✅ Complète au niveau du code et des tests. *Retour d’erreur transparent*
- [x] **80. Escalader vers un responsable** — ✅ Complète au niveau du code et des tests. *Notification et pause de conversation*

## Bilan chiffré

✅ Code/tests : **44** ; 🟡 partiellement : **29** ; ⬜ à faire : **7**.

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
