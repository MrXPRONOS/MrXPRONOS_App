"""Display saved public channel URLs. Does not contact Telegram."""
import json
from pathlib import Path

path = Path('state/discovered_channels.json')
if not path.exists():
    raise SystemExit('Aucun rapport trouvé. Lancez le workflow Telegram Public Channel Discovery.')
report = json.loads(path.read_text(encoding='utf-8'))
print('Dernière vérification :', report.get('last_scan') or 'aucune')
print('Droits de redistribution non vérifiés ; ne pas republier sans autorisation.')
for i, info in enumerate(report.get('channels', []), start=1):
    print(f"{i:02d}. {info.get('title', '')} | {info['url']} | {info.get('matching_pairs', 0)} paire(s) exemples")
