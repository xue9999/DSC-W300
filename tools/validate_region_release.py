"""Validate a relocated portable region release without camera access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('relocated',type=Path)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():
        raise ValueError('Preserve prior validation reports')
    args.relocated.mkdir(exist_ok=False)
    with zipfile.ZipFile(args.archive) as bundle:
        for name in bundle.namelist():
            if not (args.relocated/name).resolve().is_relative_to(args.relocated.resolve()):
                raise ValueError('Archive member escapes relocation directory')
        bundle.extractall(args.relocated)
    package=(args.relocated/'W300Region').resolve()
    manifest=json.loads((package/'MANIFEST.json').read_bytes())
    for row in manifest['files']:
        path=(package/row['path']).resolve()
        if not path.is_relative_to(package):
            raise ValueError('Manifest path escapes package')
        data=path.read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    env=dict(os.environ)
    env['PATH']=str(Path(os.environ.get('SYSTEMROOT',r'C:\Windows'))/'System32')
    checks=[]
    for command,expected in [(['selftest'],0),(['--help'],0),(['change','--serial','D386002E4438','--experimental-service','--baseline','missing'],2)]:
        result=subprocess.run([str(package/'W300Region.exe'),*command],cwd=package,env=env,capture_output=True,text=True,timeout=30)
        checks.append(dict(args=command,expected=expected,exit_code=result.returncode,passed=result.returncode==expected,stdout=result.stdout,stderr=result.stderr))
    report=dict(scope='Relocated Windows executable; restricted PATH; no camera commands',archive_sha256=hashlib.sha256(args.archive.read_bytes()).hexdigest(),archive_bytes=args.archive.stat().st_size,manifest_entries_verified=len(manifest['files']),checks=checks,passed=all(row['passed'] for row in checks),w300_hardware_validated=False)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    assert report['passed']
    print('Portable validation passed:',report['archive_sha256'])

if __name__=='__main__':
    main()
