# Phase 5 — optimisation UX contrôlée de Mr XPRONOS

## Portée et objectifs
Cette phase permet **de mesurer des hypothèses**, pas d'affirmer des résultats d'optimisation avant réception de visiteurs réels.

Les deux expériences 50/50 portent uniquement sur la présentation de fonctionnalités :
1. \`install_value_v1\` — accueil \`index.html\`, panneau d'installation facultative. A = formulation existante ; B = bénéfice explicite de l'accès par icône. Objectif : **clic réel sur le CTA du panneau** après qu'il a été visible. Ce n'est ni une installation confirmée ni un achat.
2. \`favorites_guidance_v1\` — \`aujourdhui.html\`, encart de favoris. A = formulation existante ; B = consigne plus directe. Objectif : **ajout effectivement validé d'une équipe ou compétition** dans le formulaire, après exposition à l'encart. Le nom du favori n'est pas envoyé aux statistiques de l'expérience.

Aucune variante n'ajoute de pression pour parier, ne masque les résultats négatifs ni ne promet de gain. La page est utilisable avec les deux versions, même si les outils de mesure sont hors ligne.

## Déroulement d'un test
- **Attribution** : fonction \`experiment_variant_v1\`, uniquement pour deux noms autorisés. Le serveur attribue A ou B par le premier octet d'un MD5 d'un secret interne, du nom de l'expérience et de l'identifiant aléatoire du navigateur. Le secret n'est jamais transmis au client ; l'identifiant de navigateur est pseudonymisé avant stockage serveur.
- **Exposition** : signal uniquement lorsque l'encart concerné est effectivement visible, au moyen d'\`IntersectionObserver\` et d'une vérification de la surface visible. L'absence du service de mesure laisse la version A et n'enregistre rien.
- **Conversion** : clic sur le vrai bouton ou ajout confirmé dans le vrai formulaire, uniquement après exposition. L'action est comptée au maximum une fois par navigateur/test, dans les **sept jours** qui suivent l'exposition.
- **Fiabilité** : file locale \`sessionStorage\`, UUID d'événement et tentative de reprise après reconnexion. Les duplications ne créent ni exposition ni conversion supplémentaire.
- **Activation et pause** : deux expériences créées **désactivées** dans Supabase. Le bouton « Activer » ou « Suspendre » de l'administration appelle \`admin_set_experiment_v1\` après confirmation. Tous les changements sont journalisés. Suspendre interdit de nouvelles expositions et laisse les conversions déjà légitimes se terminer pendant sept jours.

## Mesures et décision
Dans \`statistiques-audience.html\` → « Expériences A/B » :
- Exposés A/B et conversions constatées depuis leur exposition (ces données récentes sont provisoires).
- Expositions **arrivées à maturité**, ayant au moins sept jours d'observation ; conversions de cette cohorte.
- Taux des conversions mûres et intervalles descriptifs de Wilson à 95 %.
- Série quotidienne par groupe, journal d'état, bouton de suspension et export CSV des agrégats.

**Ne désignez pas de gagnant** sur quelques visiteurs ou à chaque rafraîchissement de la page : les intervalles affichés ne corrigent pas le risque de faux positifs lié aux vérifications répétées. Le seuil indicatif de revue humaine est **200 expositions mûres par groupe**, au moins sept jours de suivi et vérification des différences de sources/appareils. Définissez à l'avance votre période de décision et, idéalement, appliquez un plan statistique à taille d'échantillon fixée. Aucun changement automatique de variante ne se produit.

Les sessions et la fidélisation DAU/WAU/MAU / J+1 J+7 J+30 restent distinctes des conversions des tests ; l'analyse de retour quotidien doit être rapprochée des métriques générales de phase 4 et des sources d'acquisition. Les visites manquantes ne sont pas inférées.

## Confidentialité et limites
- Tables privées, RLS, pas de lecture directe par \`anon\` ou \`authenticated\`.
- RPC publiques strictement limitées aux deux expériences, aux variantes A/B, aux événements \`exposure\`/\`conversion\` ; throttling existant partagé avec la télémétrie V2.
- Contrôles d'accès administrateur \`is_admin()\` pour les résultats et le bouton de suspension.
- Aucun nom d'équipe, contenu de favori, e-mail, IP ou URL référente brute n'est enregistré dans les nouvelles tables A/B.
- Un navigateur n'est pas une personne ; changer d'appareil ou nettoyer le stockage peut créer un nouvel identifiant.
- Bots, blocages de scripts, pertes de réseau et très petites cohortes peuvent fausser une comparaison ; ne pas convertir des données anciennes en résultats de tests.

## Vérification
1. \`Phase 5 A/B Experience Optimization\` : tests JavaScript/Python, Chromium réel avec backend simulé sur accueil et page Aujourd'hui, action réelle sur bouton et formulaire.
2. \`Phase 4 Audience Analytics\` : onglets admin, calculs des cohortes, bouton activer/suspendre simulé et CSV.
3. \`Supabase Migration Dry Run\` : migration de la base alignée avec l'historique.
4. Tests SQL en transaction \`BEGIN ... ROLLBACK\` : exposition préalable, stabilité de la variante, anti-doublon, conversion, accès admin et contrôle des agrégats ; **aucune donnée fictive conservée**.
5. Après déploiement GitHub Pages, vérifier fichiers publiés, RPC et états d'activation en base ; pour arrêter une expérience problématique, utiliser le bouton de suspension dans la console.

Le résultat attendu de la phase 5 est un **dispositif prêt à mesurer et à piloter des expériences**, pas une amélioration de conversion déjà démontrée.
