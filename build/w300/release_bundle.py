"""Build or restore the revision-3 offline research asset with exact byte checks.

All archive paths are repository-relative. Restore is additive and refuses to
replace a differing existing file. No camera or network operations are used.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PIN = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'
OUTPUT = BASE / 'publication'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selected_files():
    for relative in ['downloads', 'wheels', 're-tools/wheels']:
        for p in sorted((BASE / relative).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                yield p, p.relative_to(ROOT).as_posix()
    for name in ['Sony-PMCA-RE.bundle', 'editorial-baseline-r2.zip']:
        yield OUTPUT / name, 'build/w300/offline-inputs/' + name
    # The matching Python 3.12 x64 base runtime makes offline wheel restoration
    # independent of a developer-machine Python installation.
    runtime = Path(sys.base_prefix)
    assert sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32
    for p in sorted(runtime.rglob('*')):
        relative = p.relative_to(runtime)
        if p.is_file() and not {'site-packages', '__pycache__', 'Scripts'}.intersection(relative.parts) and p.suffix != '.pyc':
            yield p, 'build/w300/runtime/python312/' + relative.as_posix()
    yield ROOT / 'docs/w300/RELEASE_RESTORE.md', 'RESTORE_RESEARCH.md'


def build():
    OUTPUT.mkdir(exist_ok=True)
    bundle = OUTPUT / 'Sony-PMCA-RE.bundle'
    if not bundle.exists():
        subprocess.run(['git', '-C', str(BASE / 'upstream/Sony-PMCA-RE'),
                        'bundle', 'create', str(bundle), 'HEAD'], check=True)
    subprocess.run(['git', 'bundle', 'verify', str(bundle)], cwd=ROOT, check=True)
    archive = OUTPUT / 'W300-Research-Offline-r3.zip'
    rows = []
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p, name in selected_files():
            data = p.read_bytes()
            z.writestr(name, data)
            rows.append(dict(path=name, bytes=len(data), sha256=sha(data)))
        manifest = dict(revision=3, pmca_commit=PIN, files=rows,
                        scope='Offline research inputs and Python 3.12 x64 runtime')
        data = (json.dumps(manifest, indent=2) + '\n').encode()
        z.writestr('RESEARCH_MANIFEST.json', data)
    (BASE / 'manifests/research-asset-r3.json').write_bytes(data)
    archive.with_suffix('.zip.sha256').write_text(sha(archive.read_bytes()) + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps(dict(archive=str(archive), files=len(rows), bytes=archive.stat().st_size)))


def restore(archive, destination):
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('RESEARCH_MANIFEST.json'))
        expected = {row['path'] for row in manifest['files']} | {'RESEARCH_MANIFEST.json'}
        assert len(z.namelist()) == len(expected) and set(z.namelist()) == expected
        # Validate the entire archive and all destinations before writing files.
        for row in manifest['files']:
            name = row['path']
            posix = PurePosixPath(name)
            assert not posix.is_absolute() and '..' not in posix.parts and '\\' not in name and ':' not in name
            assert name.startswith('build/w300/') or name == 'RESTORE_RESEARCH.md'
            target = (destination / name).resolve()
            assert target.is_relative_to(destination)
            data = z.read(name)
            assert len(data) == row['bytes'] and sha(data) == row['sha256'], name
            if target.exists():
                assert target.is_file() and sha(target.read_bytes()) == row['sha256'], 'Existing bytes differ: ' + name
        for row in manifest['files']:
            target = destination / row['path']
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(row['path']))
    upstream = destination / 'build/w300/upstream/Sony-PMCA-RE'
    if not upstream.exists():
        subprocess.run(['git', '-c', 'core.autocrlf=false', 'clone', '--no-checkout',
                        str(destination / 'build/w300/offline-inputs/Sony-PMCA-RE.bundle'), str(upstream)], check=True)
        subprocess.run(['git', '-C', str(upstream), 'config', 'core.autocrlf', 'false'], check=True)
        subprocess.run(['git', '-C', str(upstream), 'checkout', '--detach', PIN], check=True)
    assert subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    for row in manifest['files']:
        assert sha((destination / row['path']).read_bytes()) == row['sha256']
    print(json.dumps(dict(ok=True, files_verified=len(manifest['files']), destination=str(destination), pmca_commit=PIN)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('build')
    p = sub.add_parser('restore')
    p.add_argument('archive', type=Path)
    p.add_argument('--destination', type=Path, default=ROOT)
    args = parser.parse_args()
    build() if args.command == 'build' else restore(args.archive, args.destination)
