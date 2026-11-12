# Mr XPRONOS — Guide éditorial / lot 2 (améliorations 7–17)

**But :** créer une vraie raison de regarder, pas un diaporama annonçant un score. La fiabilité des faits prime sur le nombre de vidéos publiées.

## Pipeline

1. `news_leads.py` découvre des signaux football depuis des flux RSS, classe records, rivalités, retournements, performances, portraits et analyses. **Jamais de narration automatique à partir d'un titre seul.** Les pistes restent `ready_to_script=false`.
2. `editorial.py` agrège les faits structurés de l'API football-data.org (scores, top buteurs) et, si configurés explicitement, les dossiers factuels révisés de `editorial_packs/`. La source FIFA du dossier d'exemple a été consultée manuellement. Un simple lien inscrit dans un JSON n'est PAS une vérification automatique de son contenu.
3. Les six formats sont enregistrés : `highlights` (seulement les clips autorisés de `rights.cleared`), `portrait`, `story`, `tactical`, `ranking`, `comparison`.
4. Un score d'intérêt explicite classe : actualité, preuve, surprise, angle, importance, médias. Ce score **ne mesure pas l'attractivité réellement observée**.
5. Le filtre `merits_video` rejette les scores ordinaires et les événements sans angle; une rencontre 4–3 sans timeline reste insuffisante pour affirmer un retournement.
6. La mémoire empêche de re-publier le même angle; un autre angle sur le même événement est bloqué 14 jours après publication. Historique conservé séparément dans la branche d'état lors de futures publications autorisées.
7. Trois variantes de scénarios sont conçues pour les formats sourcés; la comparaison tient compte de la précision, de la longueur, de la lisibilité de l'accroche, des répétitions et des références. Les variantes ne sont pas trois copies identiques.
8. Chaque phrase factuelle de la timeline pointe vers des identifiants de faits ; contrôle de liens valides, des répétitions, des scènes vides et des accroches génériques. Cela vérifie la **traçabilité déclarée**, pas la correspondance sémantique parfaite entre les phrases et les articles : revue humaine indispensable.
9. Le résultat écrit `editorial_decisions.json`, `editorial_report.json`, `editorial_script.txt`. Publication désactivée durant les lots 2 et 3.

## Exemple documentaire vérifié (FIFA)

**Match historique, 18 décembre 2022** : Argentine 3–3 France après prolongation, Argentine victorieuse 4–2 aux tirs au but ; Messi à la 108e, Mbappé à la 80e, 81e, 118e, un triplé sans titre. Sources :

- https://www.fifa.com/fr/tournaments/mens/worldcup/articles/argentine-france-messi-mbappe-qatar-2022
- https://www.fifa.com/fr/member-associations/france/articles/resume-argentine-france-finale-championne-du-monde-coupe-du-monde-qatar-2022

**Angle sélectionné :** « Trois buts. Pas de titre. » Le récit part du paradoxe, revient au contexte, explique le retour français et révèle l'issue aux tirs au but. Une voix robotique hors production de 33,1 s a permis le contrôle de lisibilité du texte ; ce n'est PAS la voix de production. La vidéo muette d'illustration n'est PAS un rendu publiable.

## Exécution locale / GitHub Actions

```bash
python -m unittest discover -s tests -p 'test_football*.py' -v
python -m football_media_v2.engine --mode story \
  --storypack football_media_v2/editorial_packs/verified_examples.json \
  --editorial-only --out football_media_v2_editorial_review
```

Sans jeton d'API, ce test historique de scénario reste possible. `--editorial-only` ne crée aucun MP4 et n'envoie rien. Le mode `auto` doit posséder `FOOTBALL_DATA_TOKEN` pour les résultats du moment ; flux RSS `FOOTBALL_RSS_DISCOVERY=1` optionnel. Aucun fait n'est inventé si une source répond mal. La commande `--demo` ne publie jamais.

## Restrictions importantes

- Le système ne trouve pas automatiquement tous les événements : records/rivalités/exploits sont des **pistes à enrichir** tant que les API de données fiables ne fournissent pas leurs preuves. Un dossier éditorial relu peut les compléter.
- La synthèse vocale expressive, le suivi précis des scènes sur la voix, la diversité des photos et l'adéquation joueur/image relèvent du lot 3. La bande-son robotique de test n'est pas publiable.
- Le visuel de démonstration est synthétique, pas le match FIFA. Aucun clip FIFA n'est inclus ni téléchargé.
- Les deux branches de production (coupons historiques et Football Stories) restent séparées. La publication est verrouillée dans le workflow Football Stories jusqu'au lot 4.
