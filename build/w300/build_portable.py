"""Build the existing read-only W300 workbench for transfer to Windows x64.

This packages the identification workflow with private runtimes. Continue
model-specific language qualification using the included research instructions.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
UPSTREAM = BASE / 'upstream' / 'Sony-PMCA-RE'
PIN = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'


def finalize_package(package):
    package = Path(package).resolve()
    if not package.is_relative_to(BASE) or not (package / 'W300Workbench.exe').is_file():
        raise ValueError('Expected a built package inside build/w300')
    # Retain the complete available pinned upstream source and dependency licenses.
    tracked = subprocess.check_output(['git', '-C', str(UPSTREAM), 'ls-files'], text=True).splitlines()
    for path in tracked:
        source = UPSTREAM / path
        if source.is_file():
            target = package / 'upstream' / 'Sony-PMCA-RE' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    licenses = package / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', licenses / 'Python-LICENSE.txt')
    for dist in importlib.metadata.distributions():
        for relative in dist.files or []:
            if any(term in relative.name.lower() for term in ['license', 'copying', 'notice']):
                source = Path(dist.locate_file(relative))
                target = licenses / dist.metadata['Name'] / str(relative)
                if source.is_file() and target.resolve().is_relative_to(licenses.resolve()):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    for filename in ['w300_workbench.py', 'legacy_codec.py', 'inventory.ps1', 'build_portable.py']:
        shutil.copy2(BASE / filename, package / 'source' / filename)
    shutil.copy2(REPO / 'docs' / 'w300' / 'EXECUTION_PLAN.md', package / 'RESEARCH_PLAN.md')
    shutil.copy2(REPO / 'docs' / 'w300' / 'VERIFICATION.md', package / 'VERIFICATION.md')
    handoff = REPO / 'docs' / 'w300' / 'PORTABLE_HANDOFF.md'
    if handoff.is_file():
        shutil.copy2(handoff, package / 'PORTABLE_HANDOFF.md')
    shutil.copy2(REPO / 'docs/w300/RELEASE_RESTORE.md', package / 'RELEASE_RESTORE.md')
    # Adapt repository navigation to the portable directory's own file layout.
    plan = package / 'RESEARCH_PLAN.md'
    plan.write_text(plan.read_text(encoding='utf-8').replace(
        '](../../build/w300/reports/w300-readiness-audit/README.md)',
        '](https://github.com/xue9999/DSC-W300/blob/w300-research-r3/build/w300/reports/w300-readiness-audit/README.md)'),
        encoding='utf-8', newline='\n')
    verification = package / 'VERIFICATION.md'
    verification.write_text(verification.read_text(encoding='utf-8').replace(
        '](EXECUTION_PLAN.md)', '](RESEARCH_PLAN.md)'), encoding='utf-8', newline='\n')
    records = []
    for path in sorted(package.rglob('*')):
        relative = path.relative_to(package)
        if path.is_file() and not {'reports', '__pycache__'}.intersection(relative.parts) and relative.as_posix() != 'MANIFEST.json':
            records.append({'path': relative.as_posix(), 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (package / 'MANIFEST.json').write_text(json.dumps({'scope': 'Portable identification environment; language-operation qualification follows the research plan',
             'pmca_commit': PIN, 'language_write_implemented': False, 'files': records}, indent=2), encoding='utf-8')
    archive = package.parent.parent / 'W300-Workbench-Windows-x64.zip'
    if archive.exists():
        raise ValueError('Existing handoff ZIP will not be overwritten')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for record in records + [{'path': 'MANIFEST.json'}]:
            path = package / record['path']
            bundle.write(path, 'W300Workbench/' + record['path'])
    (archive.with_suffix('.zip.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n', encoding='ascii')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE / 'portable' / 'release3')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(BASE.resolve()) or output.exists():
        raise SystemExit('Use a new output directory inside build/w300; existing outputs are preserved')
    manifest = json.loads((REPO / 'sources' / 'manifest.json').read_text(encoding='utf-8'))
    pins = next(a for a in manifest['artifacts'] if a['path'] == 'sources/Sony-PMCA-RE')['reviewed_files']
    assert subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    for record in pins:
        assert hashlib.sha256((UPSTREAM / record['path']).read_bytes()).hexdigest() == record['sha256']
    archive = BASE / 'downloads' / 'portable-runtime' / 'PowerShell-7.4.18-win-x64.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'd018ed5f92ff15a28442dce6a804b1e2aa6153d9fe1e9a06de8fd8142b171f4a'
    output.mkdir(parents=True)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--console',
               '--name', 'W300Workbench', '--distpath', str(output / 'dist'),
               '--workpath', str(output / 'work'), '--specpath', str(output),
               '--paths', str(UPSTREAM), '--collect-all', 'libusb_package']
    for name in ['pmca.usb.driver.windows.msc', 'pmca.usb.driver.windows.wpd',
                 'pmca.usb.driver.windows.driverless']:
        command.extend(['--hidden-import', name])
    for name in ['pyusb', 'pywin32', 'comtypes', 'libusb-package']:
        command.extend(['--copy-metadata', name])
    command.append(str(BASE / 'w300_workbench.py'))
    (output / 'build-command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    package = output / 'dist' / 'W300Workbench'
    shutil.copy2(BASE / 'inventory.ps1', package)
    (package / 'source-pins.json').write_text(json.dumps({'pmca_commit': PIN, 'reviewed_files': pins}, indent=2), encoding='utf-8')
    for path in [record['path'] for record in pins] + ['LICENSE.txt']:
        target = package / 'upstream' / 'Sony-PMCA-RE' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(UPSTREAM / path, target)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            destination = (package / 'runtime' / 'powershell' / member.filename).resolve()
            if not destination.is_relative_to(package.resolve()):
                raise RuntimeError('Archive path escapes package')
        bundle.extractall(package / 'runtime' / 'powershell')
    # Include our actual source for inspection; the runnable entry point is the EXE.
    sources = package / 'source'
    sources.mkdir()
    for filename in ['w300_workbench.py', 'legacy_codec.py', 'inventory.ps1', 'build_portable.py']:
        shutil.copy2(BASE / filename, sources / filename)
    shutil.copy2(REPO / 'docs' / 'w300' / 'EXECUTION_PLAN.md', package / 'RESEARCH_PLAN.md')
    (package / 'README.txt').write_text(
        'W300 portable identification workbench, Windows x64\n'
        'Available commands: selftest, inventory, inquiry. Continue language-operation qualification in RESEARCH_PLAN.md.\n'
        'Keep this whole directory together. No Python, Git, Codex or separate PowerShell installation is needed.\n'
        'From PowerShell in this directory: .\\W300Workbench.exe selftest\n'
        'With the camera available: .\\W300Workbench.exe inventory\n'
        'Only after current identity review: .\\W300Workbench.exe inquiry --serial <CURRENT_USB_SERIAL>\n'
        'Reports are written under reports/. Keep Microsoft USBSTOR for identification.\n'
        'No driver is installed and no service command or settings write is performed.\n'
        'Retain receiving-PC reports to qualify the actual W300 connection and subsequent language operation.\n', encoding='utf-8')
    print(package)
    print(finalize_package(package))


if __name__ == '__main__':
    main()
