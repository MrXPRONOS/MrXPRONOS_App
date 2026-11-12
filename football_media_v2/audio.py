"""Voix expressive quand l'accès TTS fonctionne, musique originale sans copyright.

Le mode réel bloque la publication si la voix naturelle échoue.
"""
from __future__ import annotations
import asyncio
import math
from pathlib import Path
import os
import random
import wave
import numpy as np
from .visuals import run,duration


def summary_narration(kind:str, data:dict)->str:
    if kind=='match':
        a,b=data['a'],data['b']; total=a+b
        if a==b:
            conclusion='Personne ne gagne : match nul.'
        else:
            winner=data['home'] if a>b else data['away']
            conclusion=f'Le vainqueur : {winner}, avec {abs(a-b)} but' + ('s' if abs(a-b)>1 else '') + " d'écart."
        return (f'{total} buts dans ce match ! {data["home"]} face à {data["away"]}. '
                f'Score final : {a} à {b}. {conclusion} '
                f'Tu donnes combien sur dix à ce résultat ? Réponds en commentaire !')
    s=data['scorers']; top=s[0]
    middle=', '.join(f'{x["name"]}, {x["goals"]} buts' for x in s[1:3])
    return (f'Qui domine le classement des buteurs en {data["competition"]} ? '
            f'Voici les chiffres : {middle}. '
            f'Et en tête : {top["name"]}, {top["goals"]} buts. '
            'Ton favori pour la fin de saison ? Dis-le en commentaire !')


def voice_edge(text:str,where:Path)->tuple[Path|None,str]:
    if os.environ.get('FOOTBALL_DISABLE_TTS')=='1':
        return None,'no_voice_demo'
    try:
        import edge_tts
        async def _save():
            talk=edge_tts.Communicate(text=text,voice=os.environ.get('FOOTBALL_VOICE','fr-FR-RemyMultilingualNeural'),
                                      rate=os.environ.get('FOOTBALL_VOICE_RATE','+4%'))
            await talk.save(str(where))
        asyncio.run(_save())
        if where.is_file() and where.stat().st_size>1500 and duration(where)>1.5:
            return where,'edge_neural'
    except (ImportError,RuntimeError,OSError,ValueError,Exception) as e:
        print('[WARN] Service vocal indisponible :',str(e)[:170])
    return None,'unavailable'


def beat(original:Path,length:float,scene_points:list[float]):
    """Rythme original généré par oscillateurs ; aucun extrait musical tiers."""
    rate=22050; n=round(length*rate)
    audio=np.zeros(n,dtype=np.float32)
    t=np.arange(n,dtype=np.float32)/rate
    # Soft atmospheric synth pulse
    audio+=0.025*np.sin(2*math.pi*55*t)*(0.5+0.5*np.sin(2*math.pi*.33*t))
    rng=np.random.default_rng(81001)
    beat_sec=60/124
    def add(at,signal):
        start=int(at*rate)
        if start<0 or start>=n:return
        end=min(n,start+len(signal))
        audio[start:end]+=signal[:end-start]
    # Drum kit originally synthesized (bass kick, hats, claps)
    for i in range(round(length/beat_sec)+1):
        at=i*beat_sec
        klen=int(.23*rate); kk=np.arange(klen,dtype=np.float32)/rate
        pitch=54+82*np.exp(-kk*35)
        phase=2*math.pi*np.cumsum(pitch)/rate
        kick=np.sin(phase)*np.exp(-kk*24)*.28
        add(at,kick)
        for off in (0,.5):
            hlen=int(.055*rate)
            hh=rng.standard_normal(hlen).astype(np.float32)*np.exp(-np.arange(hlen)/rate*86)*.026
            add(at+off*beat_sec,hh)
        if i%4==2:
            slen=int(.15*rate)
            sn=rng.standard_normal(slen).astype(np.float32)*np.exp(-np.arange(slen)/rate*22)*.085
            add(at,sn)
    for at in scene_points:
        sz=int(.25*rate); tt=np.arange(sz,dtype=np.float32)/rate
        rise=(rng.standard_normal(sz).astype(np.float32)*np.sin(math.pi*tt/.25)**2*.055)
        add(at,rise)
    peak=np.max(np.abs(audio)) or 1
    audio=np.asarray(np.clip(audio/max(1,peak/.6),-.95,.95)*32767,dtype='<i2')
    original.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(original),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(audio.tobytes())


def soundtrack(video:Path,output:Path,speech:Path|None,bed:Path):
    secs=duration(video)
    if speech:
        filters='[1:a]aresample=44100,volume=1.25,adelay=350|350,apad[voice];[2:a]aresample=44100,volume=0.45[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=0,alimiter=limit=0.90[a]'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-i',str(speech),'-i',str(bed),
             '-filter_complex',filters,'-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k',
             '-t',f'{secs:.3f}','-movflags','+faststart',str(output)]
    else:
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-i',str(bed),'-filter_complex',
             '[1:a]volume=0.8,alimiter=limit=0.85[a]','-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac',
             '-b:a','160k','-t',f'{secs:.3f}','-movflags','+faststart',str(output)]
    run(cmd)
