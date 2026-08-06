# Hotfix V2 — schéma SportsAPI Pro

Les logs confirment que les clés et l'API fonctionnent. Le contenu allscores se
trouve désormais dans `response["data"]`, et non directement à la racine.

Copie à la racine de ton dépôt :

- `sportdata_api.py`
- `sportdata_diagnostic.py`
- `content_generator.py`

Puis :

```bash
git add sportdata_api.py sportdata_diagnostic.py content_generator.py
git commit -m "Support new SportData data envelope"
git push
```

Le diagnostic doit ensuite afficher `schéma=root.data` et un nombre de matchs
supérieur à zéro.
