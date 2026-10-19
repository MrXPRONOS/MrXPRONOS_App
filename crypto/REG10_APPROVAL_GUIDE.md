# ARCHIVE — Ancienne procédure de validation humaine (désactivée)

Ce document est conservé pour historique. Le mode de production n°10 **n’utilise plus de validation humaine**. Le fonctionnement actuel est décrit dans [`REG10_AUTOMATIC_GUIDE.md`](./REG10_AUTOMATIC_GUIDE.md). Ne pas suivre la procédure ci-dessous pour de nouvelles publications.

---

# Publication n°10 : validation et diffusion d'une vraie annonce réglementaire

**État technique :** le collecteur et le rendu continuent de fonctionner automatiquement avec 11 sources RSS gratuites, mais les articles restent dans un dossier de revue. Aucun système ne peut déduire qu'une règle est en vigueur sur la seule base d'un titre RSS.

## Pourquoi cette approbation est obligatoire
Un média peut parler d'une proposition, d'une consultation, d'une sanction, d'une loi adoptée ou d'une entrée en vigueur. Ces étapes sont différentes. Une annonce réelle ne sera publiée qu'avec son **texte officiel**, sa **juridiction**, l'**étape juridique confirmée** et, lorsqu'elle est connue, sa **date d'effet**.

## Procédure complète
1. Dans GitHub Actions, exécuter **Actu Crypto - PREMIUM production scheduler #01-10**, mode **legal** (ou attendre la veille automatique de 09:43 UTC). Récupérer l'artefact \`regulation_v2_candidate.json\` et sa maquette, seulement lorsqu'un article éligible existe.
2. Lire les documents officiels, vérifier la portée et les exceptions. Ne pas inférer une date de vigueur à partir du titre.
3. Ajouter dans \`crypto/regulation_10_approvals.json\` un **objet** sous \`approved\`, utilisant les valeurs exactes \`candidate_fingerprint\` et \`source_url\` du candidat, ainsi que les contrôles ci-dessous. Faire relire le fichier dans une pull request avant fusion.
4. Depuis GitHub Actions, déclencher manuellement le même workflow avec **mode = legal_approved** et **confirm_real_production = true**. Il régénère le candidat, compare les preuves avec l'approbation, affiche une image française 1080×1350 et l'envoie à \`ACTU_CRYPTO_CHAT_ID\`, avec texte officiel et article originel en légende. Sans correspondance exacte, aucune publication.
5. Le numéro du message est inscrit dans \`crypto/production_state.json\` pour éviter une seconde diffusion.

### Structure d'une entrée (EXEMPLE DE CHAMPS, pas un événement réel)
\`\`\`json
{
  "candidate_fingerprint": "EMPREINTE_EXACTE_DU_CANDIDAT",
  "source_url": "URL_EXACTE_RSS_HTTPS",
  "human_approved": true,
  "jurisdiction_checked": true,
  "stage_checked": true,
  "effective_date_checked": true,
  "primary_text_checked": true,
  "exceptions_checked": true,
  "approved_by": "Nom de l'éditeur habilité",
  "title_fr": "Un titre français fidèle au texte officiel",
  "summary_fr": "Résumé de 60 à 340 caractères fondé sur la décision ou le projet vérifié",
  "jurisdiction": "Juridiction officiellement concernée",
  "review_note": "Pourquoi le statut et la date sont confirmés dans la source primaire",
  "verified_stage": "PROPOSITION",
  "effective_date": "non_applicable",
  "official_source": "SEC",
  "official_url": "URL_REELLE_DU_TEXTE_OFFICIEL_SUR_SEC.GOV",
  "reviewed_at": "HORODATAGE_UTC_AU_FORMAT_ISO_8601"
}
\`\`\`

\`verified_stage\` accepte \`CONSULTATION\`, \`PROPOSITION\`, \`ADOPTION ANNONCÉE\`, \`ENTRÉE EN VIGUEUR ANNONCÉE\`, \`SANCTION / DÉCISION\`. Dans le cas « ENTRÉE EN VIGUEUR », \`effective_date\` doit être une date ISO vérifiée (\`AAAA-MM-JJ\`). Pour les autres étapes, utiliser \`non_applicable\`. Sources officielles automatiquement autorisées dans cette version : SEC, ESMA et Commission européenne. Les autres juridictions exigent l'extension de la liste des domaines institutionnels avant toute annonce.

**Sécurité :** les champs vrais ne constituent pas à eux seuls une preuve. L'éditeur humain doit contrôler chaque fait. Aucune simulation QA n'est publiée. Sans entrée signée, valide et récente, la rubrique n°10 reste non publiée.
