"""Verify or create the current editorial revision; preserve prior checkpoints."""
from pathlib import Path
import argparse,hashlib,json
BASE=Path(__file__).resolve().parent

def record(p):
 data=p.read_bytes()
 return dict(path=p.relative_to(BASE).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['create','verify']);a=parser.parse_args()
 path=BASE/'package_manifest.json'
 if a.command=='create':
  old=json.loads((BASE/'manifests/package_manifest.pre-editorial-r3.json').read_text())
  changes=[]
  for row in old['artifacts']:
   p=BASE/row['path'];new=record(p)
   if new!=row:
    allowed=p.suffix in ['.md','.py','.ps1'] or row['path']=='reports/g3-module-recovery/recovery-evidence.json'
    assert allowed, 'Unexpected preserved-data change: '+row['path']
    changes.append(dict(path=row['path'],previous_sha256=row['sha256'],current_sha256=new['sha256']))
  roots=['reports','downloads','wheels','re-tools/wheels','manifests']
  files=set(p for folder in roots for p in (BASE/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
  files.update(BASE.glob('*.py'));files.update(BASE.glob('*.ps1'));files.add(BASE/'requirements.lock.txt')
  files.discard(BASE/'reports/offline-xs-checks-r3.json')
  files.discard(BASE/'reports/release-r3-verification.json')
  data=dict(schema_version=1,editorial_revision=3,scope='Current scripts, reports and offline research inputs',pmca_commit=old['pmca_commit'],camera_communication_verified=False,w300_language_write_verified=False,historical_manifest='manifests/package_manifest.pre-editorial-r3.json',editorial_changes=changes,artifacts=[record(p) for p in sorted(files)])
  path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
 data=json.loads(path.read_text())
 for row in data['artifacts']: assert record(BASE/row['path'])==row,row['path']
 print(json.dumps(dict(ok=True,editorial_revision=data.get('editorial_revision'),artifacts=len(data['artifacts']))))
if __name__=='__main__':main()
