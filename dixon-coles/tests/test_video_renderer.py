"""Video renderer tests: no invented scores, stale data, or accidental production MP4."""
import copy
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import wave

import pytest
from dcscore.video_render import validate_payload, cover, slide, ending, soundtrack, render, W, H


def sample(n=2):
    clips=[]
    for i in range(n):
        clips.append({'order':i+1,'headline':f'Club Démo {i+1} - Club Démo {i+2}',
                      'competition':'COMPÉTITION FICTIVE', 'display_score':'2-1',
                      'display_probability_percent':14.2,
                      'top_3':[{'score':'2-1','probability':.142},
                               {'score':'1-1','probability':.12},
                               {'score':'1-0','probability':.11}]})
    return {'schema_version':1,'ready_for_video':False,'status':'PREVIEW_ONLY',
            'selected_count':n,'clips':clips}


def test_production_requires_real_ready_list():
    with pytest.raises(ValueError,match='NOT READY'):
        validate_payload(sample())


def test_partial_preview_must_be_explicit():
    with pytest.raises(ValueError,match='partielle'):
        validate_payload(sample(),preview=True)
    assert len(validate_payload(sample(),preview=True,allow_partial_preview=True))==2


def test_production_requires_ten_clips():
    p=sample()
    p.update(ready_for_video=True,status='READY')
    with pytest.raises(ValueError,match='10 matchs'):
        validate_payload(p)


def test_score_and_probability_validation():
    p=sample();p['clips'][0]['display_score']='score mystère'
    with pytest.raises(ValueError,match='Score exact'):
        validate_payload(p,preview=True,allow_partial_preview=True)
    p=sample();p['clips'][0]['display_probability_percent']=180
    with pytest.raises(ValueError,match='Probabilité'):
        validate_payload(p,preview=True,allow_partial_preview=True)


def test_production_blocks_stale_generation_and_started_games():
    now=datetime.now(timezone.utc)
    p=sample(10)
    p.update(ready_for_video=True,status='READY',date_local_africa_lome=now.date().isoformat(),
             generated_at_utc=(now-timedelta(hours=7)).isoformat())
    for c in p['clips']:c['kickoff_utc']=(now+timedelta(hours=3)).isoformat()
    with pytest.raises(ValueError,match='trop anciens'):
        validate_payload(p)
    p['generated_at_utc']=now.isoformat()
    p['clips'][0]['kickoff_utc']=(now-timedelta(minutes=2)).isoformat()
    with pytest.raises(ValueError,match='Match commencé'):
        validate_payload(p)
    p['clips'][0]['kickoff_utc']=(now+timedelta(hours=3)).isoformat()
    assert len(validate_payload(p))==10


def test_visuals_correct_dimensions_and_legible():
    c=sample()['clips'][0]
    for image in [cover(2,True),slide(c,1,2,True),ending(2,True)]:
        assert image.size==(W,H)
        assert image.getpixel((100,700))!=(0,0,0,0)


def test_soundtrack_is_original_pcm(tmp_path):
    path=tmp_path/'original.wav'
    soundtrack(path,1.0,[0,.5])
    with wave.open(str(path),'rb') as wf:
        assert wf.getframerate()==32000
        assert wf.getnframes()==32000


@pytest.mark.skipif(shutil.which('ffmpeg') is None,reason='ffmpeg not installed')
def test_real_mp4_render_has_h264_and_audio(tmp_path):
    path=tmp_path/'demo.mp4'
    result=render(sample(1),path,preview=True,allow_partial_preview=True,fps=12)
    assert result['clips']==1
    assert path.stat().st_size>50_000
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height',
                          '-of','json',str(path)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams']
    assert any(s.get('codec_name')=='h264' and s.get('width')==W and s.get('height')==H for s in streams)
    assert any(s.get('codec_name')=='aac' for s in streams)
