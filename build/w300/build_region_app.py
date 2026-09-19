"""Build a separate portable region engineering app; never access the camera."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parent
UPSTREAM = BASE / 'upstream/Sony-PMCA-RE'
PIN = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'


def git_bin() -> str:
    found = shutil.which('git')
    if found:
        return found
    for c in [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Git/cmd/git.exe',
        Path('C:/Program Files/Git/cmd/git.exe'),
        Path('C:/Program Files (x86)/Git/cmd/git.exe'),
    ]:
        if c.is_file():
            return str(c)
    return 'git'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(BASE) or output.exists():
        raise ValueError('Use a new output directory within build/w300')
    from region_app import PINS
    auth_source = BASE / 'auth'
    for name, expected in PINS.items():
        source = UPSTREAM / 'pmca/usb' / name
        original = subprocess.check_output([git_bin(),'-C',str(UPSTREAM),'show',PIN+':pmca/usb/'+name])
        source_content = source.read_bytes().replace(b'\r\n', b'\n')
        if source_content != original or hashlib.sha256(original).hexdigest() != expected:
            raise ValueError('Pinned authentication input changed')
    output.mkdir(parents=True)
    command = [sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--console',
               '--name','W300Region','--distpath',str(output/'dist'),
               '--workpath',str(output/'work'),'--specpath',str(output),
               '--collect-all','libusb_package','--hidden-import','usb.backend.libusb1',
               str(BASE/'region_app.py')]
    with (output/'build.log').open('w',encoding='utf-8') as log:
        subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
    package = output/'dist/W300Region'
    (package/'auth').mkdir()
    for name in PINS:
        auth_file = auth_source / name
        if auth_file.is_file() and hashlib.sha256(auth_file.read_bytes()).hexdigest() == PINS[name]:
            shutil.copy2(auth_file, package/'auth'/name)
        else:
            (package/'auth'/name).write_bytes(subprocess.check_output([git_bin(),'-C',str(UPSTREAM),'show',PIN+':pmca/usb/'+name]))
    (package/'source').mkdir()
    for name in ('region_app.py','region_protocol.py','region_compat.py','build_region_app.py','build_region_references.py'):
        shutil.copy2(BASE/name,package/'source'/name)
    for name in ('README.md','reference-compatibility.json','recovery-layout.md'):
        shutil.copy2(BASE/'reports/region-app'/name,package/name)
    licenses = package/'licenses'
    licenses.mkdir()
    shutil.copy2(UPSTREAM/'LICENSE.txt',licenses/'Sony-PMCA-RE-LICENSE.txt')
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python-LICENSE.txt')
    for dist in importlib.metadata.distributions():
        if dist.metadata['Name'].lower() not in ('pyusb','libusb-package','pyinstaller'):
            continue
        for relative in dist.files or []:
            if any(word in relative.name.lower() for word in ('license','copying','notice')):
                source = Path(dist.locate_file(relative))
                target = licenses/dist.metadata['Name']/str(relative)
                if source.is_file() and target.resolve().is_relative_to(licenses.resolve()):
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
    (package/'START.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\nW300Region.exe selftest\r\nW300Region.exe --help\r\necho Read README.md before connecting or changing drivers.\r\npause\r\n',encoding='ascii')
    check = subprocess.run([str(package/'W300Region.exe'),'selftest'],capture_output=True,text=True)
    (output/'frozen-selftest.txt').write_text(check.stdout+check.stderr,encoding='utf-8')
    if check.returncode:
        raise RuntimeError('Frozen selftest failed')
    # Omit local selftest sessions from the transferable artifact.
    records = []
    for path in sorted(package.rglob('*')):
        relative = path.relative_to(package)
        if path.is_file() and 'sessions' not in relative.parts:
            records.append(dict(path=relative.as_posix(),bytes=path.stat().st_size,
                                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (package/'MANIFEST.json').write_text(json.dumps(dict(
        scope='Automatic exact-component comparison and experimental native region change/restoration',
        w300_hardware_validated=False,reference_equivalence_required=True,recovery_hardware_tested=False,
        pmca_commit=PIN,files=records),indent=2)+'\n',encoding='utf-8')
    archive = output/'W300Region-Windows-x64.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for row in records+[{'path':'MANIFEST.json'}]:
            bundle.write(package/row['path'],'W300Region/'+row['path'])
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(json.dumps(dict(archive=str(archive),sha256=digest,bytes=archive.stat().st_size)))


if __name__ == '__main__':
    main()
