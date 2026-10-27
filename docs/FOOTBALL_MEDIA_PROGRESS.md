# Mr XPRONOS — état d'avancement / reprise (« continue »)

> **Branche : `feature/football-stories-v2` ; `main` et coupons inchangés.** Ne pas fusionner automatiquement. Les tests locaux ne constituent pas une preuve de CI GitHub.

## Lots

- **Lot 1 (1–6) : TERMINÉ au niveau visuel et testé en local.** Plusieurs compositions, photographie plein écran et contrôles des médias ; en mode démonstration la même image synthétique se répète (limite connue).
- **Lot 2 (7–17) : IMPLÉMENTÉ et validé en local au niveau éditorial.** Trente-deux tests au total (anciens + nouveaux), dossier FIFA du 18/12/2022 vérifié manuellement et trois scénarios comparés, sortie script/rapport, lecture robotique de contrôle (33,1 s), rendu MP4 de brouillon (25,79 s). **Publication bloquée.** L'évaluation spectateur du son et des images définitifs reste négative. Ce n'est pas une vidéo finie.
- **Lot 3 (18–32) : PROCHAIN LOT**. À « continue » vérifier d'abord l'état réellement poussé sur GitHub et les tests ; puis commencer au point 18, sauf régression détectée dans les lots 1 ou 2.
- **Lot 4 (33–36) : NON COMMENCÉ.** Aucun envoi automatique activé.

## Vérification ligne par ligne du lot 2

| N° | Réalisation | Preuve / test | Statut |
|---|---|---|---|
| 7 | Découverte API de matchs/buteurs + flux RSS thématiques en pistes non validées + dossiers factuels relus | `editorial.discover_topics`, `news_leads.discover_news_leads`, tests RSS | Implémenté avec limites de couverture |
| 8 | Score intérêt transparent (6 axes) | `score_topic`, journal des choix | Implémenté |
| 9 | Six formats, avec clips distincts via vérification des droits et dossier tactique si données fiables | `FORMAT_NAMES`, `rights.cleared`, tests formats | Implémenté ; chaque format dépend des sources disponibles |
| 10 | Rejet d'un 3–2 banal et des matchs 4–3 sans vrai récit | `merits_video`, tests 3–2/4–3 | Implémenté |
| 11 | Mémoire par événement et angle + délai entre formats | `is_duplicate`, `publish.py` append historique après publication autorisée | Implémenté, publication toujours désactivée |
| 12 | Accroche explicite dans les premières secondes : « Trois buts. Pas de titre. » | test accroches + examen du script | Implémenté |
| 13 | Histoire avec paradoxe, contexte, événements, résolution et question | `_verified_comeback`, timeline sourcée | Implémenté |
| 14 | Suspense uniquement sur faits documentés | pack vérifié manuellement + garde chronologie, aucune inférence sur score API | Implémenté |
| 15 | Identifiants de fait/source pour chaque plan | `editorial_report.json` et tests | Implémenté ; vérification sémantique finale humaine |
| 16 | Trois variantes réellement distinctes comparées | `choose_script`, points internes documentés | Implémenté |
| 17 | Contrôle répétitions/phrases vides/clichés/longueur | `review_draft`, tests de rejet | Implémenté |

## Validation et preuves

- Tests : `python -m unittest discover -s tests -p 'test_football*.py' -v` → **32/32 réussis** localement le 27/10/2026.
- Scénario d'exemple historique : Argentine 3–3 France, 18/12/2022. FIFA : https://www.fifa.com/fr/tournaments/mens/worldcup/articles/argentine-france-messi-mbappe-qatar-2022 ; https://www.fifa.com/fr/member-associations/france/articles/resume-argentine-france-finale-championne-du-monde-coupe-du-monde-qatar-2022
- Angle retenu : trois buts de Mbappé mais victoire finale de l'Argentine aux tirs au but. Accroche vocale courte, conclusion vraie et sources déclarées.
- Lecture du scénario : WAV robotique `espeak` française 33,12 secondes. **Test d'intelligibilité structurelle, pas test de qualité de voix naturelle.**
- Aperçu visuel : démonstration avec image IA fictive, 9 plans, durée 25,79 secondes, pas de piste de voix parlée, filigrane « VISUELS DEMO - NON PUBLIER ». Il n'est pas synchronisé avec la lecture de 33 s ; **lot 3 point 30**.
- Sécurité : workflow de publication et sauvegarde en mode `if: ${{ false }}` ; aucun réseau sollicité. Aucun workflow ni fichier des coupons modifié.

## Diagnostic de spectateur — lot 2

**En entendant l'histoire, m'arrêterais-je ?** Davantage qu'avec la V2 : « Trois buts. Pas de titre. » pose une tension immédiate et vérifiable. Les détails 80e, 81e, 108e, 118e et les tirs au but lui donnent une réelle substance. La fin conserve une question compréhensible.

**Regarderais-je la vidéo livrée en entier ? NON.** La même image d'un joueur fictif est répétée neuf fois et la démonstration ne contient aucune voix parlée. Le montage des plans n'est pas encore synchronisé sur le vrai débit de narration. La qualité audiovisuelle reste sous le seuil souhaité malgré la progression narrative. **Ne pas publier et ne pas présenter comme une vidéo finalisée.**

## Restrictions à résoudre dans le lot 3

- Vrais médias identifiés par joueur/action et droits compatibles ; bibliothèque d'images diversifiées et vérifiées.
- Narration neuronale expressive testée dans GitHub Actions, puis timing des plans aligné sur sa durée réelle (aujourd'hui 33,1 s de test audio séparé contre 25,79 s pour le brouillon muet).
- Vraies compilations possibles uniquement avec droits commerciaux/documentaires explicitement enregistrés.
- Le score de tri du moteur n'est pas une note de qualité créative ni un taux de rétention.
- Exécution GitHub Actions du nouveau code à vérifier après envoi sur branche ; pas de fusion `main` pendant les travaux.

## Commande « continue »

Consulter `AGENTS.md`, `docs/FOOTBALL_MEDIA_ROADMAP.md`, ce journal, puis les dernières versions GitHub/tests. Si les modifications du lot 2 sont effectivement présentes et si les tests passent, commencer **lot 3, amélioration 18**. Sinon terminer/corriger le lot 2. Avancer strictement dans l'ordre, avec un diagnostic de spectateur à la fin de chaque lot.
