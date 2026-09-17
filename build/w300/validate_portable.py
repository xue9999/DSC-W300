"""Validate a newly extracted handoff without development executables on PATH.

Runs selftest and OS inventory only. Never calls inquiry or service functions.
The current host has no connected W300; the result is a portability check.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
ARCHIVE = BASE / 'portable' / 'release3' / 'W300-Workbench-Windows-x64.zip'
DESTINATION = BASE / 'portable' / 'relocation release3 ąę'


def main():
    global ARCHIVE, DESTINATION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ARCHIVE)
    parser.add_argument('--destination', type=Path, default=DESTINATION)
    parser.add_argument('--report', type=Path, default=BASE / 'reports' / 'portable-validation-r3.json')
    args = parser.parse_args()
    ARCHIVE, DESTINATION = args.archive.resolve(), args.destination.resolve()
    if args.report.exists():
        raise ValueError('Use a new report path to preserve earlier verification records')
    extract = not DESTINATION.exists()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as archive:
        for item in archive.infolist():
            if not (DESTINATION / item.filename).resolve().is_relative_to(DESTINATION.resolve()):
                raise RuntimeError('ZIP path escapes relocation directory')
        if extract:
            archive.extractall(DESTINATION)
        expected_manifest = archive.read('W300Workbench/MANIFEST.json')
    package = DESTINATION / 'W300Workbench'
    assert (package / 'MANIFEST.json').read_bytes() == expected_manifest
    manifest = json.loads((package / 'MANIFEST.json').read_text(encoding='utf-8'))
    for record in manifest['files']:
        path = package / record['path']
        if not path.resolve().is_relative_to(package.resolve()):
            raise RuntimeError('Manifest path escapes package')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise RuntimeError('Package integrity mismatch: ' + record['path'])
    # A plain dict does not preserve os.environ's case-insensitive Windows lookup.
    environment = {key.upper(): value for key, value in os.environ.items()}
    environment['PATH'] = os.pathsep.join([str(Path(environment['SYSTEMROOT']) / 'System32'), environment['SYSTEMROOT']])
    environment['PSMODULEPATH'] = os.pathsep.join([
        str(Path(environment['SYSTEMROOT']) / 'System32' / 'WindowsPowerShell' / 'v1.0' / 'Modules'),
        str(package / 'runtime' / 'powershell' / 'Modules')])
    for variable in ['PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONDA_PREFIX']:
        environment.pop(variable, None)
    result = {'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Relocated runtime, not camera or language verification',
              'archive': str(ARCHIVE), 'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              'extraction': str(package), 'files_verified': len(manifest['files']),
              'path': environment['PATH'], 'ps_module_path': environment['PSMODULEPATH'],
              'external_tools_visible': {name: shutil.which(name, path=environment['PATH']) for name in ['python', 'git', 'pwsh']},
              'runs': []}
    try:
        for operation in ['selftest', 'inventory']:
            process = subprocess.run([str(package / 'W300Workbench.exe'), operation],
                                     cwd=DESTINATION, env=environment, capture_output=True, timeout=90)
            stdout = process.stdout.decode('utf-8-sig', errors='replace')
            stderr = process.stderr.decode('utf-8-sig', errors='replace')
            entry = {'operation': operation, 'exit_code': process.returncode, 'stdout': stdout, 'stderr': stderr}
            result['runs'].append(entry)
            if process.returncode:
                raise RuntimeError(operation + ' failed')
            parsed = json.JSONDecoder().raw_decode(stdout)[0]
            entry['report'] = parsed
            if operation == 'selftest':
                assert parsed['result']['frozen_portable_executable'] is True
                assert str(package) in parsed['result']['libusb_dll_loaded']
            else:
                assert str(package) in parsed['result']['powershell_executable']
        result['ok'] = True
    except Exception as error:
        result.update(ok=False, error=str(error))
    output = args.report
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding='utf-8')
    print(json.dumps({'ok': result['ok'], 'files_verified': result['files_verified'],
                      'external_tools_visible': result['external_tools_visible'],
                      'runs': [{'operation': r['operation'], 'exit_code': r['exit_code']} for r in result['runs']],
                      'report': str(output)}, indent=2))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
