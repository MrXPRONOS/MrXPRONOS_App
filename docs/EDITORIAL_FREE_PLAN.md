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
