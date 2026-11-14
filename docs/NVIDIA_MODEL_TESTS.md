# Test NVIDIA NIM — Mr XPRONOS (v2, multimodal)

## Configuration

Créer dans **Settings → Secrets and variables → Actions → New repository secret** :

- **Name** : \`NVIDIA_API_KEY\`
- **Secret** : clé NVIDIA Build (jamais dans les fichiers GitHub)

## Exécution

Ouvir **Actions → NVIDIA - test all AI models → Run workflow** avec :

- \`category=all\`, \`repeats=1\`, \`limit=0\`, \`models\` vide : contrôle de toutes les entrées inventoriées.
- \`category=image\`, \`video\`, \`document\`, \`vision\` ou \`audio\` pour cibler un usage.
- \`repeats=2/3\` pour comparer les temps (engendre plus de requêtes et potentiellement plus de coûts).
- \`models\` : liste d'IDs exacts séparés par des virgules, même absents de \`/v1/models\`.

**Inventaire à deux sources** :

1. \`GET https://integrate.api.nvidia.com/v1/models\` : tous les IDs renvoyés par cet endpoint pour le compte.
2. \`scripts/nvidia_extra_models.py\` : registre complémentaire d'IDs documentés et de leurs **vrais endpoints** pour images, vidéo, voix et analyse de documents.

Le registre complémentaire est une liste entretenue manuellement, **pas une preuve que tous les modèles du catalogue Build ont été découverts**. Les NIM purement téléchargeables ou demandant une autorisation distincte / un service déployé ne sont pas tous invocables avec cette seule clé.

## Couverture réelle

| Type | Méthode |
|---|---|
| Texte, code, raisonnement, sécurité, traduction textuelle | API chat/completions |
| Embedding | API embeddings et repli approprié |
| Reranking | Endpoints dédiés de classement |
| Images (FLUX.1, FLUX.2, FLUX.3, SD3, SDXL) | Endpoints NVIDIA /v1/genai spécifiques avec prompts |
| Génération vidéo (Stable Video Diffusion) | Endpoint spécifique et image synthétique d'entrée |
| Analyse de documents (Nemotron Parse) | API chat avec une page PNG créée localement |
| Raisonnement visuel (Cosmos Reason2) | API chat avec image synthétique |
| Audio (Magpie TTS Multilingual) | Endpoint HTTP de synthèse vocale avec texte de test |

Certains modèles utilisent gRPC, un autre schéma JSON ou nécessitent des entrées particulières, voire leur propre déploiement. Pour les catégories spéciales inconnues, une sonde standard est tentée et un **problème de schéma** est distingué d'un modèle réellement retiré.

Les réponses valides doivent inclure du texte, un embedding, une liste de classement ou un véritable artefact média. Les images/vidéos/audio produits ne sont **pas sauvegardés**, afin d'éviter les gros fichiers et des données potentiellement sensibles.

En cas de HTTP 202, la sonde essaie de suivre l'exécution via l'API NVIDIA NVCF si elle dispose d'un request ID. Une tâche restée pendante est indiquée comme telle, **jamais comme réussie**.

## Rapports

Sur la page de chaque exécution :

- **Summary** : tableau consolidé des modèles.
- **Artifacts → rapport-modeles-nvidia-...** : une archive ZIP contenant \`rapport.md\`, \`results.csv\` et \`results.json\`.
- \`status=ok\` : sortie exploitable avec HTTP 200.
- \`introuvable\` : HTTP 404 à l'endpoint essayé ; **pas forcément** « modèle supprimé ».
- \`limite_atteinte\` : HTTP 429 ; \`acces_refuse\` : HTTP 403.
- \`schema_specialise_inconnu\` : sonde générique incompatible, endpoint spécifique encore nécessaire.
- \`timeout\`, \`async_timeout\`, \`reponse_vide\` : résultat non confirmé.

Les secondes mesurent la durée totale de la requête ; ce n'est ni la latence du premier token ni une mesure fiable de la qualité des réponses. Les modèles aux tâches différentes **ne sont pas directement comparables** en vitesse.

## Historique

Le premier test du **14 novembre 2026** se trouve sur : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/43540499516

- 83 modèles découverts.
- 16 réponses valides, 53 réponses 404, 5 timeouts, 5 modèles non testés, 2 HTTP 500, 2 réponses 200 sans texte.

Le test complet multimodal a été déclenché une fois à l'adresse : https://github.com/MrXPRONOS/MrXPRONOS_App/actions/runs/43542251576

Le workflow est ensuite revenu en **mode manuel**, pour ne pas dépenser des crédits à chaque push.

## Exécution locale

\`\`\`bash
python -m pip install requests Pillow
export NVIDIA_API_KEY="VOTRE_CLE_PRIVEE"
python scripts/test_nvidia_models.py --category all --limit 0 --repeats 1
\`\`\`

La clé ne figure jamais dans les rapports. Le benchmark est isolé des fichiers utilisés pour les pronostics en production.
