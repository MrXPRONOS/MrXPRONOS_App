"""One-screen layout: no intro/outro, proper visual and publication safety."""
from __future__ import annotations
import copy
import json
import subprocess
import shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path

import pytest
from PIL import Image
from dcscore.video_grid import (
    CARD_ROWS,CARD_COLS,CARD_H,CARD_W,CARD_Y0,CARD_X,
    FIRST_REVEAL,REVEAL_INTERVAL,REVEAL_EFFECT,FINAL_HOLD,
    _title_date, layout_positions, _static_frame, compose_frame, render,W,H
)
from dcscore.video_render import Crest,validate_payload


def example():
    return {
        'status':'PREVIEW_ONLY','ready_for_video':False,'selected_count':10,
        'date_local_africa_lome':'2026-11-10',
        'clips':[{'order':i+1,'headline':f'Club Alpha{i} - Club Beta{i}',
                  'display_score':f'{i%4}-{(i+1)%3}'} for i in range(10)]
    }


def fake_crests():
    mark=Image.new('RGBA',(65,65),(54,229,207,255))
    return [(Crest(mark,False),Crest(mark,False)) for _ in range(10)]


def test_grid_is_two_columns_five_rows_no_extra_panels():
    pos=layout_positions()
    assert (CARD_COLS,CARD_ROWS,len(pos))==(2,5,10)
    assert len(set(pos))==10
    assert pos[0][1]==pos[1][1] and pos[2][1]>pos[0][1]
    assert pos[0][0]+CARD_W < pos[1][0]
    assert pos[-1][1]+CARD_H<H-35


def test_first_frame_has_all_ten_cards_and_no_intro_outro():
    p=example();clips=validate_payload(p,preview=True)
    base=_static_frame(p,clips,fake_crests(),True)
    first=compose_frame(base,clips,0,reveal_starts=[FIRST_REVEAL+i*REVEAL_INTERVAL for i in range(10)])
    assert first.size==(W,H)
    for x,y in layout_positions():
        assert first.convert('RGB').getpixel((x+7,y+10))!=(7,17,34)
    assert '10 NOVEMBRE 2026' in _title_date(p)


def test_reveal_changes_score_but_not_logos_or_club_names():
    p=example();clips=validate_payload(p,preview=True)
    base=_static_frame(p,clips,fake_crests(),True)
    starts=[FIRST_REVEAL+i*REVEAL_INTERVAL for i in range(10)]
    before=compose_frame(base,clips,0,reveal_starts=starts)
    first=compose_frame(base,clips,FIRST_REVEAL+.8,reveal_starts=starts)
    last=compose_frame(base,clips,starts[-1]+1,reveal_starts=starts)
    # Score center changes; all logos remain identical across full timeline.
    x,y=layout_positions()[0]
    assert before.crop((x+118,y+51,x+209,y+102)).tobytes()!=first.crop((x+118,y+51,x+209,y+102)).tobytes()
    for x,y in layout_positions():
        assert before.crop((x+40,y+24,x+107,y+85)).tobytes()==last.crop((x+40,y+24,x+107,y+85)).tobytes()


def test_title_is_current_local_date_and_no_fake_future_date():
    assert _title_date(example())=='DU 10 NOVEMBRE 2026'
    p=example();p['date_local_africa_lome']='invalid'
    assert _title_date(p)=='DATE DE DÉMONSTRATION'


def test_strict_production_safety_still_enforced():
    with pytest.raises(ValueError,match='NOT READY'):
        render(example(),Path('/tmp/should-not-exist.mp4'))


@pytest.mark.skipif(shutil.which('ffmpeg') is None,reason='ffmpeg not present')
def test_real_video_has_10_cards_and_no_intro_outro(tmp_path):
    p=example();out=tmp_path/'grid.mp4'
    res=render(p,out,preview=True,fps=10)
    assert res['format']=='single_screen_grid_2x5'
    assert res['intro'] is False and res['outro'] is False
    assert res['matches_visible_from_first_frame']==10
    assert res['duration_seconds']<20
    assert out.stat().st_size>60_000
    raw=subprocess.run(['ffprobe','-v','error','-show_entries',
                        'stream=codec_name,width,height:format=duration',
                        '-of','json',str(out)],capture_output=True,text=True,check=True)
    j=json.loads(raw.stdout)
    assert any(z.get('codec_name')=='h264' and z.get('width')==W for z in j['streams'])
    assert any(z.get('codec_name')=='aac' for z in j['streams'])
    assert abs(float(j['format']['duration'])-res['duration_seconds'])<.25
