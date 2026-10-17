# Shorts Mr XPRONOS — planning production

Timezone de référence : UTC, identique à Lomé.

## Publication des pronostics

### 18:15 — vague « evening »
- Cible : matchs du lendemain.
- Fenêtre : coups d'envoi avant 15:00 UTC.
- Maximum : 5 matchs.
- Minimum : 1 match.
- Priorité : cote la plus élevée, puis heure de coup d'envoi.
- Catégories : SIMPLE, PRO et VIP sans distinction.
- Les matchs déjà utilisés dans une vidéo ne peuvent pas être repris.

### 08:15 — vague « morning »
- Cible : matchs du jour encore disponibles.
- Fenêtre : coups d'envoi à partir de 15:00 UTC.
- Maximum : 5 matchs.
- Minimum : 1 match.
- Priorité : cote la plus élevée, puis heure de coup d'envoi.
- Si aucun match ne reste, aucune vidéo n'est publiée.

## Validation des lots

Contrôles automatiques : 12:30, 15:30, 18:30, 23:30 et 02:30 UTC.

Chaque contrôle relit exactement les matchs enregistrés dans le lot de production.
Aucun bilan n'est publié tant que tous les matchs du lot ne sont pas officiellement terminés.

- 0 perte : vidéo de validation publiée.
- 1 perte : vidéo de validation publiée.
- 2 pertes ou plus : lot clôturé silencieusement, sans vidéo bilan.
- Les validations sont marquées dans Supabase pour empêcher tout doublon.

Le contrôle de 12:30 permet une validation précoce si le lot est déjà terminé.
Les contrôles suivants servent de rattrapage, notamment pour les matchs d'après-midi,
de soirée ou de nuit.

## Canaux

La vidéo de pronostics est envoyée au canal Telegram de production puis publiée
sur les plateformes sociales configurées. Le lot n'est inscrit dans le ledger
Supabase qu'après acceptation de la vidéo par Telegram.

Workflow publication :
.github/workflows/shorts-coupons-production.yml

Workflow validation :
.github/workflows/shorts-coupons-production-validation.yml
