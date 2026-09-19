"""Build exact-component comparison profiles from provenance-pinned firmware.

No firmware bytes are copied into the portable app; only sizes and SHA-256 hashes.
Exact matches are static comparison evidence, never a hardware recovery claim.
"""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def main():
    sources = [
        ('G3', ROOT/'evidence/extracted_g3/archives_unpacked',
         ROOT/'evidence/artifact_manifest.json', 'fskrel1', 'fskapp1'),
        ('T100', BASE/'downloads/related-firmware/t100-extracted/archives_unpacked',
         BASE/'reports/t100-language-comparison/extraction.json', 'fskrel3', 'fskapp'),
    ]
    rows = {}
    for model, directory, manifest, scripts, app in sources:
        pins = {r['path']:r for r in json.loads(manifest.read_text())['artifacts']}
        mappings = {f'/usr/lib/{n}':f'lib/lib/{n}' for n in (
            'libBackupTable.so','libBackupCore.so','libAppBackupApi.so','libsencore.so')}
        mappings.update({f'/usr/dsc/fsk/{n}':f'{scripts}/dsc/fsk/{n}' for n in (
            'regionInfo.xsb','senserModule.xsb','senserCmdTable.xsb','dsc.xsb')})
        mappings.update({f'/usr/dsc/fsk/{n}':f'{scripts}/dsc/fsk/{n}' for n in (
            'PExtBackup.so','PExtSenser.so','kconfig.xml')})
        mappings['/usr/dsc/fsk/tinyhttp'] = 'fskrel1/dsc/fsk/tinyhttp'
        mappings['/usr/dsc/app/scripts/kconfig.xml'] = f'{app}/dsc/app/scripts/kconfig.xml'
        for camera_path, relative in mappings.items():
            source = directory/relative
            if not source.is_file():
                if source.name in ('senserModule.xsb','senserCmdTable.xsb') or (model == 'T100' and source.name == 'libsencore.so'):
                    continue
                raise FileNotFoundError(source)
            data = source.read_bytes()
            name = source.relative_to(ROOT).as_posix()
            pin = pins[name]
            digest = hashlib.sha256(data).hexdigest()
            if len(data) != pin['bytes'] or digest != pin['sha256']:
                raise ValueError('Reference source changed: '+name)
            rows.setdefault(camera_path,[]).append(dict(model=model,bytes=len(data),sha256=digest,source=name))
    w300_dir = ROOT/'evidence/w300/baseline_files'
    if w300_dir.is_dir():
        for camera_path in (
            '/usr/lib/libBackupTable.so', '/usr/lib/libBackupCore.so', '/usr/lib/libAppBackupApi.so', '/usr/lib/libsencore.so',
            '/usr/dsc/fsk/regionInfo.xsb', '/usr/dsc/fsk/senserModule.xsb', '/usr/dsc/fsk/senserCmdTable.xsb', '/usr/dsc/fsk/dsc.xsb',
            '/usr/dsc/fsk/PExtBackup.so', '/usr/dsc/fsk/PExtSenser.so', '/usr/dsc/fsk/kconfig.xml',
            '/usr/dsc/fsk/tinyhttp', '/usr/dsc/app/scripts/kconfig.xml'):
            source = w300_dir / camera_path.lstrip('/')
            if source.is_file():
                data = source.read_bytes()
                name = source.relative_to(ROOT).as_posix()
                digest = hashlib.sha256(data).hexdigest()
                rows.setdefault(camera_path, []).append(dict(model='W300', bytes=len(data), sha256=digest, source=name))
    report = dict(schema='region-exact-components-v1',
                  meaning='Exact matches to reviewed comparative components; W300 live behavior remains untested',
                  hreg_bytes=2048,hreg_offsets=[1024,1028,1032,1036],
                  completion_marker_offset=496,files=rows)
    path = BASE/'reports/region-app/reference-compatibility.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
