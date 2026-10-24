# Changement de forme — filtre H2H contextuel (recherche)

**Objectif :** empêcher qu'un vieux face-à-face 1-1 soit traité comme un indice
suffisant de match fermé lorsque les deux attaques ou défenses ont changé
de régime. Le moteur de buts attendus BSD V2 prenait déjà en compte la forme
récente (demi-vie 120 jours) ; ce nouveau filtre vise plus spécialement le
**décalage entre l'époque des H2H et le football joué actuellement**.

## Améliorations implémentées

1. **Fenêtres temporelles 5 contre 10** : buts marqués et encaissés sur les
   cinq derniers matchs réglés par rapport aux dix précédents. Seuils
   exploratoires sur les différences de moyennes.
2. **Contexte lors des anciens H2H** : pour les rencontres déjà disputées,
   mesure du potentiel offensif et défensif des deux clubs avec les données
   qui étaient publiées **avant chacun de ces H2H**. La mesure n'est
   retenue qu'avec au moins deux rencontres convenablement documentées.
3. **Changements défensifs** : détecte aussi les défenses qui encaissent
   soudain plus ou moins de buts. Un « nouveau bon attaquant » ne peut être
   affirmé : seules des différences observées de scores sont disponibles.
4. **Domicile / extérieur** : compare les quatre derniers matchs du club
   dans le lieu pertinent aux quatre précédents matchs dans le même lieu,
   seulement si ces séries existent.
5. **Contradiction entre modèles** : confronte les buts attendus au signal
   Under 2,5 et la direction 1X/X2 au rapport de forme des deux équipes.
   Un 1X ne signifie pas une victoire certaine à domicile.

**Confidentialité temporelle :** `V2History.team(..., at)` ne rend
un match disponible qu'après sa date de coup d'envoi + 4 heures. Les résultats
et transferts connus après la date du pronostic sont exclus du calcul.

## Utilisation

- `bsd/bsd_form_shift.py` expose les indicateurs de forme, les drapeaux
  d'incertitude, les règles d'ablation et le petit ensemble de marchés de
  score faible qu'il serait raisonnable d'éviter.
- `bsd/grouped_correct_score_engine.py` accepte
  `evaluate_form_shift=True` ; ce drapeau est **désactivé par défaut**.
  Il calcule le contexte coûteux uniquement pour H2H stable + Under 2,5
  favorable et compare « ancienne règle », attaque, défense, époque H2H,
  lieu, cohérence, fusion conservatrice et filtre strict.
- `bsd/grouped_correct_score_backtest.py` calcule la réussite, la couverture,
  les pertes dans les matchs exclus, le Brier, les résultats par groupe
  et par semestre sur les mêmes rencontres.
- `bsd/bsd_form_shift_singles_backtest.py` garde le moteur
  `predict_v2` **inchangé** et compare sur 2025 et 2026 la sortie
  standard aux choix après exclusion de `UNDER_15`, `UNDER_25`,
  `UNDER_35`, `UNDER_45`, `BTTS_NO` ou `X` lorsqu'un risque haussier
  suffisamment étayé est détecté. Les Over, BTTS Oui et autres marchés
  ne sont pas systématiquement supprimés.

## Critères avant activation dans BSD V2 (simples)

Les alertes ne sont pas une preuve d'amélioration. Il faudra vérifier que :

- le nombre de matchs concernés est suffisamment élevé pour une conclusion
  utile, avec les années 2025 et 2026 présentées séparément ;
- les matches écartés sont effectivement plus souvent perdants,
  en conservant une couverture exploitable ;
- les pronostics simples de remplacement sont au moins aussi précis que
  ceux qu'ils remplacent, et non simplement plus nombreux ;
- l'amélioration tient sur de **nouvelles prévisions horodatées** après
  la date d'élaboration du filtre ;
- le site ne reçoit jamais de nouvelle publication expérimentale avant
  cette validation.

Les données exactes de blessure, recrutement, composition d'équipe ou xG
ne sont **pas** fournies par ces modules. Un changement de rythme de buts
peut avoir plusieurs causes ; aucune n'est automatiquement attribuée à un
transfert. Aucun calcul de rendement financier n'est possible sans les
cotes et marchés réellement proposés.

**Aucun changement de sélection n'est activé en production.**

## Verdict des backtests complets — 20 octobre 2026

### Scores groupés 1xBet

Backtest complet réussi : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39372238140

| Règle (référence) | Matchs | Gagnants | Taux |
|---|---:|---:|---:|
| H2H + Under 2,5 original | 122 | 65 | 53,28 % |
| Changement de forme de l'attaque | 103 | 55 | 53,40 % |
| Comparaison de l'époque des H2H | 111 | 59 | 53,15 % |
| Défense | 114 | 59 | 51,75 % |
| Domicile/extérieur | 89 | 46 | 51,69 % |
| Forme combinée | 109 | 56 | 51,38 % |
| Forme stricte | 70 | 37 | 52,86 % |

Le filtre combiné écarte 13 matchs, dont 9 gagnants. **Ne pas activer.**
L'analyse des transferts/attaquants réels reste impossible sans autre fournisseur.

### Pronostics simples BSD V2

Backtest complet réussi : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/39373474923

| Année | Moteur original | Veto + Under 4,5 | Base matchs | Filtre conservés |
|---|---|---|---:|---:|
| 2025 | 14 447 / 16 600 = 87,03 % | 13 534 / 15 874 = 85,26 % | 16 600 | 95,63 % |
| 2026 | 13 875 / 16 257 = 85,35 % | 13 100 / 15 640 = 83,76 % | 16 257 | 96,20 % |

En 2026, 2 875 sélections Under 4,5 ont déclenché l'alerte ;
**2 495/2 875 (86,78 %) étaient gagnantes**, alors que les 2 258 marchés
de remplacement n'ont réussi que 1 720 fois (76,17 %).
Le moteur s'est abstenu sur 617 matchs, et **557 de leurs sélections
Under 4,5 originales étaient gagnantes**.

**Ne pas adopter le veto dans BSD V2**. Under 4,5 tolère jusqu'à quatre
buts : une hausse du rythme offensif n'implique pas suffisamment de
défaites de ce marché.

### Monitoring sans risque de changement de comportement

`bsd/bsd_v2_shadow.py` possède maintenant l'option explicite
`--form-diagnostics`. Après la décision de pronostic normal du moteur,
il attache les drapeaux de forme à `model_audit.form_shift_shadow`.
Il ne modifie ni le marché sélectionné, ni la cote, ni les candidats.
L'option est **désactivée par défaut** et ne publie rien sur le site.

Les prochains signaux doivent être évalués sur des prédictions
horodatées réellement futures. Il ne faut pas réoptimiser les seuils
sur le même historique 2026 sans validation indépendante.
