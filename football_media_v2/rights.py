"""Contrôle strict des médias audiovisuels commerciaux pour diffusion multiréseaux.

Les déclarations sont des preuves documentaires à vérifier humainement ; ne confondent
pas une URL publique avec un droit de télécharger, modifier et republier.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

ALLOWED_VIDEO_EXT={'.mp4','.mov','.mkv','.webm'}

def cleared(manifest:Path, project:Path, platforms:set[str])->list[tuple[dict,Path]]:
    if not manifest.exists(): return []
    try: items=json.loads(manifest.read_text('utf-8'))['clips']
    except (ValueError,KeyError,TypeError): return []
    if not isinstance(items,list): return []
    project=project.resolve(); result=[]; today=dt.date.today()
    for entry in items:
        if not isinstance(entry,dict): continue
        try:
            file=(project/entry['file']).resolve(strict=True)
            proof=(project/entry['proof']).resolve(strict=True)
            if not (file.is_relative_to(project) and proof.is_relative_to(project)): continue
            if file.suffix.lower() not in ALLOWED_VIDEO_EXT or not file.is_file(): continue
            if not proof.is_file() or proof.stat().st_size<32: continue
            if entry.get('commercial_use') is not True or entry.get('derivatives_allowed') is not True: continue
            if entry.get('audio_allowed') is not False: continue # ne pas importer l'audio source
            if not all(entry.get(k) for k in ('source_url','rights_holder','permission_id','license')): continue
            if not platforms.issubset(set(entry.get('platforms') or [])): continue
            if entry.get('expires') and dt.date.fromisoformat(entry['expires']) < today: continue
            if entry.get('reviewed_by_human') is not True: continue
            result.append((entry,file))
        except (OSError,ValueError,KeyError,TypeError): continue
    return result
