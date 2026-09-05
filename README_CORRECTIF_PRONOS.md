# Correctif d’affichage des pronostics — Mr XPRONOS

## Diagnostic

`generate_data.py` fonctionne : il écrit bien les matchs dans `data.json`.
Le problème se produit ensuite dans le navigateur.

Trois défauts ont été corrigés :

1. `main.js` attendait la fin de Supabase, des compteurs et des notifications avant de charger `data.json`.
   Une erreur secondaire pouvait donc empêcher complètement `loadData()`.
2. `Notification.permission` était utilisé sans vérifier si l’API `Notification` existe.
   Sur certains navigateurs, WebViews et installations PWA, cela peut interrompre le script.
3. Le Service Worker mettait en cache `data.json?t=<timestamp>` avec une URL différente à chaque appel.
   En cas d’échec réseau, il renvoyait ensuite un faux JSON HTTP 200 contenant `matches: []`, que `main.js`
   sauvegardait à la place du bon cache.

## Fichiers corrigés

- `assets/js/main.js`
- `service-worker.js`
- `pronos.html`

## Installation

Copier le contenu de ce dossier à la racine du dépôt et accepter les remplacements.

```powershell
git add assets/js/main.js service-worker.js pronos.html
git commit -m "Fix affichage des pronostics et cache data.json"
git push
```

## Après le déploiement GitHub Pages

1. Ouvrir `pronos.html?v=20260806-pronos-fix`.
2. Faire `Ctrl + F5` sur ordinateur.
3. Dans l’application installée, la fermer complètement puis la rouvrir deux fois afin que le nouveau Service Worker prenne le contrôle.

En dernier recours dans Chrome :

- `F12` → **Application** → **Service Workers** → **Unregister**
- **Storage** → **Clear site data**
- recharger la page.

## Nouveau comportement

- Les pronostics sont chargés avant Supabase et l’analytics.
- Simple, Pro et VIP sont affichés ensemble pour la journée choisie.
- Le champ `date` de chaque match est utilisé en priorité, ce qui évite un décalage lié à l’heure ISO.
- Un ancien cache non vide n’est jamais remplacé par un faux résultat vide plus ancien.
- Si aucun match ne correspond à la journée, l’écran affiche le nombre total chargé et la répartition par date.
- Le Service Worker utilise une clé stable pour `data.json`, même lorsque l’URL contient `?t=...`.
- Le Service Worker renvoie HTTP 503 en cas de vraie absence de données, au lieu de fabriquer 0 match.

## Test local

```powershell
python test_correctif_pronos.py
node --check assets/js/main.js
node --check service-worker.js
```
