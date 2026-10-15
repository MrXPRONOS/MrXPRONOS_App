# Journal des versions

## V3 — intégration Mr XPRONOS

- Installation du code dans `telegram-film-relay/` du dépôt `MrXPRONOS_App` ; workflows positionnés à la racine `.github/workflows/`.
- Découverte stricte (2 couples distincts, durées, tailles, proximité, protection noforwards).
- Liaison automatique des nouvelles chaînes découvertes à `state/auto_sources.json` sans les rejoindre ni republier sans licence.
- Préapprobation facultative d'une source découverte via secret `TG_APPROVED_SOURCES_JSON` et droit explicite.
- GitHub Actions avec contrôle de présence des secrets : en l'absence de configuration, publication et recherche sont ignorées, pas d'échec lié aux secrets manquants.
- Identifiants des canaux via variables GitHub, sans les inscrire dans un dépôt public.
- Copie via `send_file` sans le libellé « Transféré depuis… », exclusivement pour médias autorisés et non protégés.
- Limite de cinq films par exécution ; reprise des étapes privées incomplètes.

## V2

- Cadence de deux heures pour le relais ; découverte une fois par jour ; affiches + vidéos dans le canal privé.
