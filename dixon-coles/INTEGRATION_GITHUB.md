# Intégration GitHub du nouveau système Dixon-Coles

- Répertoire indépendant : `dixon-coles/`
- Workflow CI indépendant : `.github/workflows/dixon-coles-independent-tests.yml`
- Rien n’est branché au site existant ni aux anciens moteurs de pronostics.
- L’API `football-data.org` exige une clé pour les vrais matchs ; ne jamais la commiter.
- Démarrage depuis la racine du dépôt : `cd dixon-coles`, `python -m pip install -e ".[test]"`, `python -m dcscore.cli serve`.
- Interface privée locale : http://127.0.0.1:8088. Pas de déploiement public sans authentification.
- Les données de démonstration sont fictives.
