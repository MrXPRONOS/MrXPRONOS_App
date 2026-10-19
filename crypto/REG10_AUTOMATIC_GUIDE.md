# Publication 10 — automatisation institutionnelle (sans approbation humaine)

**Objectif :** transformer la validation humaine de la rubrique réglementation en une vérification automatique et prudente d'annonces institutionnelles.

## Ce qui est réellement vérifié automatiquement

1. Collecte d'articles crypto/réglementation depuis les flux **officiels** SEC, ESMA et Commission européenne (RSS gratuits).
2. Une annonce n'est admissible que si elle concerne les cryptoactifs et un sujet réglementaire, a une date fiable et date de moins de 48 h.
3. Refus des liens non HTTPS, des domaines tiers, des connexions avec mot de passe dans les URL, des pages indisponibles, des redirections vers un autre domaine et des documents dont le titre officiel ne correspond pas au RSS.
4. Le programme relit le titre visible (H1 ou métadonnée du titre) de la page institutionnelle et le compare au titre du flux. Ce contrôle établit seulement que **l'autorité a bien publié cette annonce**.
5. L'affiche premium 1080 × 1350 est en français et indique « communiqué officiel », l'autorité et sa juridiction. Le titre original, le lien de l'autorité, la date et les limites de la vérification figurent dans la légende Telegram.
6. **Aucun programme ne peut déduire ici** qu'une loi est applicable, que sa date d'entrée en vigueur est confirmée, qu'une entreprise a enfreint une règle ou que le Togo est directement concerné. Ces affirmations ne sont ni imprimées ni envoyées.
7. Vérification du bot et de ses droits avant publication, avec envoi uniquement d'un PNG réellement généré à partir de l'annonce, **aucune simulation**, puis enregistrement de l'identifiant de l'article et du message dans `crypto/production_state.json`. Pas de deuxième publication du même article.
8. Si les contrôles ne suffisent pas, la rubrique **ne publie rien**. Elle ne demande pas d'approbation humaine.

## Horaires de production
`legal` est exécuté automatiquement chaque jour à **09 h 43, 15 h 43 et 21 h 43 UTC** (identiques à l'heure de Lomé). GitHub Actions peut retarder le déclenchement.

## Ce que cela remplace
L'ancien mode `legal_approved` (fichier d'approbations par un éditeur) n'est plus exposé par le workflow de production ni appelé par le programme. Les autres rubriques #01–#09 restent inchangées. Les autres médias RSS peuvent continuer à servir de veille mais **ne suffisent pas à déclencher seuls** une annonce réglementaire sans article officiel.

## Tests
`python -m unittest crypto.test_regulation_10_auto crypto.test_production_live_v1 -v`

`node scripts/render_crypto_regulation_auto_v2.mjs --qa` est réservé aux fichiers QA marqués. Il refuse la sortie de production lorsque les drapeaux de simulation sont présents. Un workflow CI interroge les flux réels uniquement en lecture (sans envoyer Telegram).

Ce circuit est automatique et utile pour **annoncer une publication officielle**, pas pour fournir des conclusions juridiques personnalisées. Les textes officiels demeurent les références.
