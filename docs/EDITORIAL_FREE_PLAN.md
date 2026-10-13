# Améliorations gratuites Mr XPRONOS — suivi

Toutes les images éditoriales sont créées localement avec Pillow, sans aucun appel de génération d'image payant.

## Commandes
\`\`\`sh
pip install Pillow
python scripts/content_studio.py --limit 12 --news-limit 20
python scripts/editorial_pages.py
python scripts/editorial_queue.py
python scripts/editorial_metrics.py
python scripts/editorial_quality.py --strict
\`\`\`

## Fonctionnement
- Couvertures: 1200x630 (Open Graph), 1080x1080 (réseaux), 1080x1920 (stories), WebP.
- Variantes déterministes, basées sur le slug pour des rendus stables.
- \`articles/<slug>/index.html\` et \`conseils/<slug>/index.html\` incluent OG/Twitter et redirigent vers les pages JS du site; les anciennes URLs continuent à fonctionner.
- \`assets/data/editorial_share_queue.json\` est une file **préparatoire seulement** : elle ne poste aucun contenu et conserve les états par plateforme. Les clés d'API ne sont jamais nécessaires pour générer cette file.
- \`assets/data/editorial_metrics.json\` compte les variantes sans suivre les visiteurs.
- Le workflow \`editorial-free.yml\` actualise les visuels quotidiennement à 05:41 UTC, séparé des workflows BSD V2 et Telegram.
- Les contenus anciens restent disponibles. Aucun script ne supprime automatiquement les images existantes.
- Vérification: attention, les droits d'auteur des photographies de presse ne sont pas octroyés automatiquement par un flux RSS. Les images éditoriales locales sont un fallback sûr; ne pas republier des photographies tierces sans droit.

## Limitations assumées
- La file sociale n'est pas connectée aux API de publication; un examen humain est requis.
- Pas de métriques de clics externes ni de test A/B de conversion sans statistiques réelles.
- Les matchs non présents dans les données existantes ne sont jamais inventés.
- Les pages OG statiques sont dédiées au partage; l'article complet reste rendu par \`article.html\` / \`conseil.html\`.


## Phase 2 (sans abonnement supplémentaire)
- \`scripts/editorial_bsd_bridge.py\` : génère un maximum de 5 nouvelles fiches factuelles par jour, uniquement à partir de \`data.json\` signé dans le format BSD V2 (\`source=bsd\`, \`model_version=bsd-v2-isolated\`). Pas de score inventé ni de scraping incontrôlé.
- \`fetch_foot_news.py\` : interroge MadeInFoot, France 24 Football et Foot Mercato avec délai réseau et fenêtre de fraîcheur de 96 h; conserve les nouveaux visuels WebP si une actualité réapparaît à la collecte suivante. Une source inaccessible n'arrête pas les autres.
- Le workflow \`update-footnews.yml\` rend désormais les nouveaux visuels immédiatement après une collecte, sans attendre le prochain studio quotidien.
- Le visuel Flash Foot du canal utilise une illustration originale de terrain et ballon en l'absence de photographie. Les photographies de presse ne sont utilisées que si \`EDITORIAL_ALLOW_NEWS_PHOTOS=1\` a été activé **et que les droits ont été vérifiés**.
- \`scripts/editorial_telegram.py\` : canal éditorial séparé, bouton de lecture vers l'article et paramètres UTM. Aucun envoi sans les Secrets \`EDITORIAL_TELEGRAM_BOT_TOKEN\` et \`EDITORIAL_TELEGRAM_CHAT_ID\`, ou sans déclenchement explicite \`--publish\`. Le workflow planifié envoie au plus une publication de moins de 48 h par jour. Si les secrets n'existent pas, la publication est ignorée.
- \`editorial_metrics.py\` : nombre de couvertures, distribution des variantes, volume WebP et état par réseau. \`real_clicks\` est nul jusqu'à connexion de vraies données de fréquentation. Les UTM permettent une analyse externe sans achat.
- \`editorial_cleanup_audit.py\` : audit de poids et nettoyage optionnel, strictement dans \`assets/images/editorial\` et uniquement sur des images générées, non référencées et âgées d'au moins 30 jours. Aucun nettoyage automatique des médias historiques.
- Les tests ne nécessitent pas de secrets ni de dépenses. Les API sociales externes sont limitées par les autorisations des comptes et par les politiques de chaque plateforme.

### Publication Telegram éditoriale
1. Ajouter, dans les GitHub Actions Secrets du dépôt, \`EDITORIAL_TELEGRAM_BOT_TOKEN\` et \`EDITORIAL_TELEGRAM_CHAT_ID\` du canal éditorial autorisé. **Ne pas utiliser le canal des pronostics pour ce flux sans le vouloir.**
2. Dans Actions, ouvrir \`Editorial - Telegram diffusion contrôlée\` et exécuter avec l'option \`publish=false\` pour vérifier la sélection, ou \`true\` pour un envoi réel.
3. Une tâche planifiée à 08h12 UTC (heure de Lomé) traite au maximum un article/conseil récent ; elle garde une trace \`platform_status.telegram=sent\` et \`message_id\` en cas de confirmation de Telegram.
4. Le comportement est anti-doublon au niveau du registre GitHub, sous réserve qu'un envoi réussi puisse effectivement être enregistré (comme toute intégration distante, pas de garantie exactement-une-fois après panne réseau ou conflit Git).


### Publication Facebook (facultative, gratuite)
- \`scripts/editorial_facebook.py\` diffuse une **publication avec lien** (aperçu Open Graph généré côté Meta), pas un téléchargement de photographie protégée.
- Les Secrets existants \`META_PAGE_ID\` et \`META_PAGE_ACCESS_TOKEN\` doivent être valides et permettre \`pages_manage_posts\`.
- Le workflow \`Editorial - Facebook Page liens du site\` permet un test manuel \`publish=false\` ou une publication autorisée \`publish=true\`.
- L'automatisation quotidienne de 09h12 (heure de Lomé) est inactive **tant que la variable GitHub Actions \`EDITORIAL_FACEBOOK_ENABLED=true\` n'a pas été activée**.
- Chaque publication reçoit un \`post_id\` et des UTM \`utm_source=facebook\`. Les autres plateformes ne sont pas annoncées comme actives sans leurs autorisations de publication.


## Phase 3 : sûreté des envois et première mesure d'attribution

- Les pages \`articles/<slug>/\` et \`conseils/<slug>/\` restent compatibles avec les lecteurs sociaux Open Graph, mais transmettent maintenant les paramètres UTM autorisés lors de la redirection navigateur.
- Les seuls paramètres UTM conservés sont \`utm_source\`, \`utm_medium\`, \`utm_campaign\` et \`utm_content\`, avec une validation stricte.
- Après arrivée depuis Telegram, Facebook, Instagram, Threads, WhatsApp, YouTube ou TikTok, le navigateur enregistre anonymement un événement \`editorial_view\` dans la table \`analytics\` **déjà existante**. \`user_id\` est NULL pour ces événements. Une copie effective du code promo sur la page enregistre séparément \`editorial_promo_copy\`.
- \`scripts/editorial_attribution.py\` lit ces événements via les secrets GitHub \`SUPABASE_URL\` et \`SUPABASE_SERVICE_ROLE_KEY\` **uniquement côté GitHub Actions**, puis publie uniquement des agrégats dans \`assets/data/editorial_performance.json\`.
- Le workflow \`Editorial - Mesures de performance anonymes\` s'exécute à 06h17 UTC et calcule les 30 derniers jours, sans hébergement externe payant. En l'absence de credentials, il ne publie aucun chiffre fictif.
- Les agrégats donnent les visites attribuées et les copies du code promo. Ils ne représentent pas des personnes uniques, des inscriptions, des dépôts, des bénéfices, ni une expérience A/B randomisée. Aucun classement des variantes n'est présenté comme causal sans assignation expérimentale.
- Les workflows sociaux Telegram et Facebook utilisent un même groupe de concurrence pour ne pas modifier le registre de diffusion simultanément. Le script \`editorial_merge_receipts.py\` garde les confirmations \`sent\` après une actualisation concurrente de la file.
- **Sécurité :** la publication automatique Telegram exige maintenant aussi \`EDITORIAL_TELEGRAM_ENABLED=true\` dans les Variables GitHub Actions du dépôt. Facebook continue d'exiger \`EDITORIAL_FACEBOOK_ENABLED=true\`. Une exécution manuelle \`publish=true\` reste possible. Les secrets ne sont jamais mis dans le dépôt.
- Limite : comme tout envoi externe suivi d'un commit Git, une panne entre l'acceptation par Telegram/Meta et la sauvegarde du \`message_id\`/\`post_id\` peut laisser un résultat ambigu. Un opérateur doit vérifier l'historique avant toute relance forcée.

### Confidentialité Supabase (audit indépendant)
Le projet Supabase existant présente des tables publiques sans RLS et une politique de lecture anonyme ouverte sur \`analytics\`. Ces paramètres existaient avant la phase 3. Ils nécessitent une **revue de sécurité distincte** avant toute modification: activer RLS sans préparer les politiques pourrait casser le site. Cette phase n'a changé ni le schéma ni les politiques de la base.


### Publication Threads en option
- \`scripts/editorial_threads.py\` utilise les deux opérations officielles Meta \`/threads\` (création du conteneur texte avec \`link_attachment\`) puis \`/threads_publish\` (confirmation de publication).
- Utilise exclusivement les Secrets \`THREADS_ACCESS_TOKEN\` et \`THREADS_USER_ID\`, sans les exposer au navigateur.
- La publication quotidienne à 10h22 UTC n'est effective que si la variable GitHub \`EDITORIAL_THREADS_ENABLED=true\` est définie; l'envoi manuel exige \`publish=true\`.
- Au plus un lien récent par exécution. Le statut \`threads=sent\` n'est conservé qu'après réception d'un identifiant de publication officiel.
- Aucun coût d'API ou abonnement supplémentaire n'est prévu, sous réserve des droits d'accès et des quotas de Meta.


## Phase 4 — Publications Instagram et comparaison visuelle A/B (gratuit)

**Instagram** : les images Open Graph et réseaux sont au format WebP. L'API de publication Instagram demande au contraire une image JPEG publiquement accessible. Pour les contenus article/conseil nouveaux ou récents, \`scripts/editorial_instagram_assets.py\` fabrique des JPG 1080×1080, sans service d'hébergement supplémentaire, sous \`assets/images/editorial/\`. Le studio éditorial les versionne avec les visuels WebP existants. Le site GitHub Pages les sert publiquement.

- \`scripts/editorial_instagram.py\` attend une URL qui sert réellement \`image/jpeg\`, avant toute requête d'envoi.
- La publication utilise les appels officiels Instagram Graph API \`/{IG_USER_ID}/media\` puis \`/{IG_USER_ID}/media_publish\`.
- Il faut un compte Instagram professionnel, des accès Meta valides et les secrets \`IG_USER_ID\` + \`META_ACCESS_TOKEN\` (ou \`META_PAGE_ACCESS_TOKEN\` valide selon le type d'authentification).
- L'automatisation reste **désactivée** tant que \`EDITORIAL_INSTAGRAM_ENABLED=true\` n'est pas ajouté aux Variables Actions; lancement manuel avec \`publish=true\` possible après test.
- Les publications se limitent à un contenu récent, avec mention 18+ / jeu responsable. Un identifiant \`media_id\` est enregistré uniquement lorsque Meta confirme la publication.
- Un lien dans une légende Instagram n'est pas cliquable automatiquement; le lien dans le texte est donc informatif, contrairement au bouton Telegram.
- \`editorial-instagram.yml\` utilise la même file anti-doublon et le même groupe de concurrence que Facebook et Threads.

**Test A/B de présentation sur le site** : chaque article et conseil éditorial reçoit en plus une seconde couverture \`ab_image_url\`, graphiquement différente mais au contenu textuel identique. Sur les listes Blog et Conseils, le navigateur attribue A ou B par tirage 50/50, stable dans \`sessionStorage\` pour cette session.

- L'affichage visible d'une carte enregistre \`editorial_ab_exposure\` et l'ouverture du contenu \`editorial_ab_click\` dans la table \`analytics\` existante, avec \`user_id=null\`.
- Le rapport \`editorial_performance.json\` présente désormais les impressions et ouvertures par article/conseil et variante. Le taux est fourni à titre descriptif, sans prétention statistique (au moins 30 impressions par variante pour le simple statut descriptif).
- Les sessions répétées et les interactions interrompues ne permettent pas un décompte garanti de visiteurs uniques. Les événements sont anonymes; les tests A/B des **créations de réseaux sociaux** ne sont pas encore randomisés, seulement ceux des couvertures **affichées sur le site**.
- Les images A/B utilisent Pillow local (gratuit), n'inventent aucune statistique de match. Aucune photographie soumise à des droits n'est automatiquement republiée.
