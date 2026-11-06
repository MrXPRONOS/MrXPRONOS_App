# Phase 4 — Tableau de bord Audience (Mr XPRONOS)

## Accès et architecture
- Console : \`/statistiques-audience.html\`, accessible depuis les statistiques d'installation et les pages privées de supervision.
- Le HTML et le module JS client sont publics comme l'écran de connexion, mais **aucune donnée de statistiques n'est intégrée** dans l'artefact Pages. Toutes les données réelles passent par \`admin_audience_dashboard_v1\`, fonction Supabase qui exige \`is_admin()\` et n'est autorisée qu'aux comptes \`authenticated\`.
- L'agrégateur PWA \`admin_pwa_install_funnel_v2\` conserve lui aussi son contrôle \`is_admin()\`.
- Tables \`analytics_acquisition_v1\` et \`analytics_acquisition_events_v1\` : RLS active ; aucun accès de table \`anon\` ou \`authenticated\`. Le collecteur anonyme reçoit uniquement un droit \`EXECUTE\` sur la RPC validée et plafonnée.
- Les fichiers privés \`admin.html\`, \`admin-supervision.html\` et le code serveur ne sont jamais intégrés à l'artefact public.

## Définitions utilisées
- **DAU / WAU / MAU** : identifiants pseudonymisés distincts ayant un jour de visite V2 sur les 1, 7 et 30 derniers jours UTC ; ces trois indicateurs ne dépendent pas du filtre général du tableau.
- **Sessions** : identifiants de session V2, terminés logiquement au-delà de 30 minutes sans navigation.
- **Engagement** : session avec signal de 15 secondes visibles. Pas une preuve de lecture effective.
- **J+1 / J+7 / J+30** : proportion de navigateurs dont le **premier jour observé** dans V2 appartient à la période choisie et qui sont observés **exactement** un, sept ou trente jours plus tard. Les cohortes trop récentes ne figurent pas au dénominateur. Une cohorte à zéro élément mûr affiche « — », pas 0 %.
- **Canaux** : \`direct\`, \`google\`, \`organic_search\`, \`facebook\`, \`instagram\`, \`whatsapp\`, \`telegram\`, \`youtube\`, \`tiktok\`, \`pinterest\`, \`linkedin\`, \`referral\`, \`other\`, \`unknown\`. Un visiteur V2 sans source figure sous \`unattributed\`.
- **Attribution** : catégorie du premier contact observé du navigateur ; le serveur conserve aussi le dernier contact. Une attribution UTM est déclarative et peut être incorrecte.
- **Campagne** : seulement \`utm_campaign\` normalisé, limité à un slug non personnel de 48 caractères. Le collecteur ne transmet pas d'URL référente brute, d'IP ou de terme de recherche.
- **CTA d'installation** : événement navigateur ; \`appinstalled\` et acceptation d'une installation ne constituent pas des preuves universelles. Le mode standalone est enregistré séparément.
- **Ancien journal** : n'est pas converti en sessions ; les minutes au trafic suspect et le défaut de jours sans mesures sont signalés.

## Exemples de liens de campagne
- WhatsApp : \`https://mrxpronos.github.io/MrXPRONOS_App/aujourdhui.html?utm_source=whatsapp&utm_campaign=foot_novembre\`
- Instagram : \`https://mrxpronos.github.io/MrXPRONOS_App/?utm_source=instagram&utm_campaign=story_1\`
- Telegram : \`https://mrxpronos.github.io/MrXPRONOS_App/pronos.html?utm_source=telegram&utm_campaign=canal_pronos\`

Choisissez une campagne descriptive, sans adresse, numéro de téléphone, e-mail ni information concernant une personne. Le premier contact est conservé lorsqu'un navigateur arrive ensuite par un autre canal.

## Vérifications
1. \`Phase 4 Audience Analytics\` : classification UTM/référent, intégration CSS/JS/HTML, syntaxe, tests réels Chromium pour utilisateur non connecté et administrateur simulé, desktop et mobile, navigation et export CSV.
2. \`Supabase Migration Dry Run\` : base alignée, pas de migration inattendue.
3. SQL transactionnel \`BEGIN ... ROLLBACK\` : source initiale conservée au deuxième contact ; deux événements malgré un renvoi duplicate ; cohorte synthétique J+1 = 2/3 et J+7 = 1/1, canal WhatsApp et événement d'installation reconnus ; zéro ligne de test conservée.
4. Vérifier sur un véritable compte administrateur la consultation et le rafraîchissement du tableau.
5. Ouvrir un lien de campagne en navigation privée, puis contrôler au bout de quelques minutes les statistiques d'acquisition ; ne pas déclencher d'envois artificiels de trafic.
6. Confirmer sur Android et iOS la remontée des événements d'installation et la classification du navigateur intégré après publication.

## Limites explicites
- Les navigateurs sont des identifiants pseudonymisés, pas des personnes vérifiées ; différents appareils peuvent multiplier les identifiants.
- La collecte peut être bloquée par un navigateur, une extension, une panne réseau ou une fermeture définitive de l'onglet.
- Un événement de source est pris par onglet (première entrée), pas à chaque clic interne. Les sources déclarées ne sont ni vérifiées ni certifiées par un tiers.
- Les anciennes données et pics des 12, 13 et 18 octobre 2026 ne constituent pas des cohortes V2. Aucun score de rétention historique n'a été inventé.
- Les pages restent utilisables si la télémétrie est indisponible. Le tableau présente l'absence de données plutôt qu'une valeur simulée.
