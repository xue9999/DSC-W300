"""Scoped integration replay of new static analyses; preserve earlier pins."""
from pathlib import Path
import hashlib,json,subprocess,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUILD=ROOT/'build/w300'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for folder,command in [('g3-entry-events','reproduce_events.py'),('g3-config-read','reproduce.py')]:
 directory=HERE/folder
 before={p.relative_to(directory).as_posix():digest(p) for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 r=subprocess.run([sys.executable,'-B',str(directory/command)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
 assert r.returncode==0,r.stdout+r.stderr
 after={p.relative_to(directory).as_posix():digest(p) for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 assert before==after,folder
 checks.append(dict(folder=folder,returncode=r.returncode,identical_files=len(before),stdout=r.stdout.strip()))
manifest=json.loads((BUILD/'package_manifest.json').read_text())['artifacts']
assert manifest # Verify the complete active revision; prior checkpoints remain historical.
for row in manifest:
 p=BUILD/row['path'];assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],row['path']
for name in ['EXECUTION_PLAN.md','VERIFICATION.md']:
 text=(ROOT/'docs/w300'/name).read_text(encoding='utf-8')
 assert 'W300' in text and ('qualification' in text.lower())
result=dict(ok=True,checks=checks,existing_package_pins_verified=len(manifest),camera_io=False,w300_language_qualified=False)
(HERE/'offline-xs-checks-r3.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
