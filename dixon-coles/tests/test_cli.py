from dcscore import cli


def test_cli_demo_predict_backtest(tmp_path,capsys,monkeypatch):
    path=str(tmp_path/'console.db')
    monkeypatch.delenv('FOOTBALL_DATA_TOKEN',raising=False)
    assert cli.main(['--db',path,'demo'])==0
    assert 'demo:tomorrow' in capsys.readouterr().out
    assert cli.main(['--db',path,'leagues'])==0
    assert 'demo:SIM' in capsys.readouterr().out
    assert cli.main(['--db',path,'fixtures','--competition','demo:SIM'])==0
    assert cli.main(['--db',path,'predict','demo:tomorrow'])==0
    output=capsys.readouterr().out
    assert 'top_scores' in output
    assert cli.main(['--db',path,'backtest','--competition','demo:SIM','--samples','2'])==0
    assert 'top1_hit_rate' in capsys.readouterr().out


def test_cli_missing_csv_is_explicit_error(tmp_path,capsys):
    assert cli.main(['--db',str(tmp_path/'err.db'),'import-csv',str(tmp_path/'missing.csv')])==1
    assert 'ERREUR' in capsys.readouterr().err


def test_cli_server_configuration(tmp_path,monkeypatch):
    calls={}
    monkeypatch.setattr(cli.uvicorn,'run',lambda *args,**kwargs:calls.update({'args':args,'kwargs':kwargs}))
    assert cli.main(['--db',str(tmp_path/'srv.db'),'serve','--port','8089'])==0
    assert calls['kwargs']['host']=='127.0.0.1'
    assert calls['kwargs']['port']==8089
    assert calls['kwargs']['factory'] is True
