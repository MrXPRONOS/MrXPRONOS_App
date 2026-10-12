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
