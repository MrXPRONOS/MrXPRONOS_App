#!/usr/bin/env python3
"""Persist deduplication state in a dedicated GitHub branch, never main.
Requires repository GITHUB_TOKEN with contents: write permission.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import requests

BRANCH='football-media-v2-state'
FILE='state.json'


def api(method,path,**kwargs):
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    repo=os.environ.get('GITHUB_REPOSITORY')
    if not token or not repo:
        raise RuntimeError('GH_TOKEN/GITHUB_REPOSITORY manquant')
    return requests.request(method,'https://api.github.com/repos/'+repo+path,
      headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
               'X-GitHub-Api-Version':'2022-11-28'},timeout=35,**kwargs)


def load(path):
    response=api('GET',f'/contents/{FILE}',params={'ref':BRANCH})
    if response.status_code==404:
        path.write_text('{"seen":[]}',encoding='utf-8')
        print('[INFO] Aucun état distant, initialisation vide')
        return
    response.raise_for_status()
    content=base64.b64decode(response.json()['content']).decode('utf-8')
    data=json.loads(content)
    if not isinstance(data.get('seen'),list):
        raise ValueError('État distant invalide')
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"[OK] État distant: {len(data['seen'])} éléments")


def save(path):
    response=api('GET',f'/git/ref/heads/{BRANCH}')
    if response.status_code==404:
        main_branch=os.getenv('GITHUB_BASE_BRANCH','main')
        base=api('GET',f'/git/ref/heads/{main_branch}')
        base.raise_for_status()
        new=api('POST','/git/refs',json={'ref':f'refs/heads/{BRANCH}',
                   'sha':base.json()['object']['sha']})
        if new.status_code not in (201,422): new.raise_for_status()
    else:
        response.raise_for_status()
    existing=api('GET',f'/contents/{FILE}',params={'ref':BRANCH})
    if existing.status_code not in (200,404): existing.raise_for_status()
    payload={'message':'chore(media): update processed football IDs',
             'content':base64.b64encode(path.read_bytes()).decode('ascii'), 'branch':BRANCH}
    if existing.status_code==200: payload['sha']=existing.json()['sha']
    result=api('PUT',f'/contents/{FILE}',json=payload)
    result.raise_for_status()
    print('[OK] État sauvegardé sur la branche football-media-state')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('operation',choices=['load','save'])
    p.add_argument('--file',default='football_media_v2_state.json')
    args=p.parse_args()
    if args.operation=='load':load(Path(args.file))
    else:save(Path(args.file))

if __name__=='__main__':main()
