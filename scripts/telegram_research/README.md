# Extracteur Telegram réutilisable

Utilitaire **manuel uniquement**. Aucun workflow GitHub n'est fourni.

## Préparer
```bash
python -m pip install -r scripts/telegram_research/requirements.txt
```

Secrets/env requis :
- `TG_API_ID`
- `TG_API_HASH`
- `TG_SESSION_STRING`

## Exemple
```bash
python scripts/telegram_research/extract_history.py --channel ActuFootZoneFr --hours 72
```

Le script produit JSON, CSV et TXT dans `telegram_exports/`.

Pour un autre canal :
```bash
python scripts/telegram_research/extract_history.py --channel NomDuCanal --hours 48
```

Ne jamais partager ou commit la StringSession.
