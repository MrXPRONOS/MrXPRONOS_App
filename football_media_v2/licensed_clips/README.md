# Vrais clips de football — droits obligatoires

Dépose une **copie du fichier vidéo autorisé** dans ce dossier (ou sous-dossier) et une preuve d'autorisation sous forme de fichier. Un opérateur doit vérifier la preuve, notamment si l'autorisation couvre **commercialisation, extraits, musique/source audio, recadrage vertical, modifications et chacune des plateformes**. Les vidéos de diffuseurs TV, résumés UEFA/FIFA/ligues, vidéos YouTube ou TikTok ne sont pas automatiquement autorisées par un lien public ni par l'ajout d'une voix.

Format d'une entrée à ajouter dans `manifest.json` :

```json
{
 "clips": [{
   "file": "football_media_v2/licensed_clips/extrait_autorise.mp4",
   "proof": "football_media_v2/licensed_clips/extrait_autorise_PERMISSION.txt",
   "source_url": "https://exemple.org/video-originale",
   "rights_holder": "Nom réel titulaire des droits",
   "license": "Licence exacte ou permission écrite",
   "permission_id": "unique-autorisation-2026-001",
   "commercial_use": true,
   "derivatives_allowed": true,
   "audio_allowed": false,
   "reviewed_by_human": true,
   "platforms": ["telegram", "youtube"],
   "expires": "2028-12-31",
   "display_title": "Arrêt incroyable"
 }]}
```

Laisse `reviewed_by_human=false` si le moindre point est douteux ; le moteur refusera le clip. Ne mets pas de grandes vidéos sous Git : stockage externe à autorisations contrôlées préférable pour un véritable catalogue. Il faut au moins deux clips valides pour une compilation.
