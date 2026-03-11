import os
import json
from supabase import create_client
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

matches = data.get('matches', [])
today = datetime.now().date().isoformat()

#  Filtrer les matchs du jour (vous pouvez ajuster)
today_matches = [m for m in matches if m.get('date') == today]

# Insérer ou mettre à jour dans la table pronostics
for m in today_matches:
    supabase.table('pronostics').upsert({
        'match': f"{m['home_team']} vs {m['away_team']}",
        'prediction': m['prediction']['double_chance'],
        'cote': m['prediction']['odds'],
        'competition': m['league'],
        'date': today
    }, on_conflict='match').execute()