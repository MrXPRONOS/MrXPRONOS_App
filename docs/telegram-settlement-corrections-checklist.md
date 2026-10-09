# Checklist — corrections validation Telegram BSD V2

**Ne pas fusionner la PR avant application de la migration Supabase**
`supabase/migrations/20261009020000_telegram_coupon_settlement.sql`.
Les nouveaux scripts écrivent et lisent ces colonnes : une fusion avant migration
bloquerait la diffusion ou le règlement.

| N° | Correctif | Code | En production |
|---|---|---|---|
| 1 | Valider les combinés uniquement si les **deux** marchés publiés gagnent | Implémenté pour les **nouveaux** combinés avec snapshot | À activer après migration; anciens combinés déjà marqués validés non récupérables automatiquement |
| 2 | Éviter la double annonce de gain après une erreur réseau | Réservation atomique + statut `sending`; cas ambigu `manual_review` | À activer après migration; les erreurs ambiguës exigent contrôle humain |
| 3 | Ne pas expirer les lignes ouvertes à J+10 | Sélection de tous les `validation_sent=false` | À activer après migration, historique Git encore borné à 14 jours |
| 4 | Ne pas bloquer un match reprogrammé | Correspondance par ID BSD, décalage toléré jusqu'à 30 jours | Partiel : si BSD range l'événement seulement sous sa nouvelle date, récupération multi-jours requise |
| 5 | Détailler les `pending` | Compteurs distincts : `verification_wait`, `official_not_finished`, `official_result_unavailable`, `invalid_kickoff`, `unsupported_market_or_score`, `kickoff_mismatch_review` | À activer après migration |
| 6 | Préserver la sélection exacte envoyée | Snapshot JSON immuable à la réservation des nouveaux coupons (simples et combinés), cotes et marché conservés | À activer après migration; anciennes publications sans snapshot restent en repli historique |

## Vérifications avant fusion

- [ ] La migration SQL est appliquée à la base Supabase de production.
- [ ] Confirmer l'existence de `selection_snapshot`, `delivery_status`, `settlement_status`, `telegram_message_id` et `validation_message_id`.
- [ ] Les tests de la PR passent intégralement.
- [ ] Tester un nouvel envoi avec un coupon simple et un combiné ; vérifier les enregistrements SQL.
- [ ] Tester un simple perdant : `settlement_status=lost`, sans photo supplémentaire.
- [ ] Tester un combiné partiellement gagnant : `lost`, sans photo de gain.
- [ ] Tester un combiné entièrement gagnant : une seule photo, deux scores officiels.
- [ ] Tester une erreur réseau Telegram incertaine : `manual_review`, aucune republication aveugle.
- [ ] Contrôler les anciens coupons sans snapshot : ne pas les annoncer gagnants sur des marchés modifiés.
- [ ] Contrôler le compte rendu des prochains déclenchements cron-job.org.

**Ne pas prétendre avoir terminé les vérifications en production avant les tests en base réelle.**
