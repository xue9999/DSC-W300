"""Automatic exact-component comparison and Hreg invariants; no device access.

Matching references enables an explicitly experimental native RegionSetting trial.
It does not establish camera-wide compatibility, eligibility, or tested recovery.
Unknown binaries are reported, not treated as matching because names are similar.
"""
import hashlib
import json
from pathlib import Path
import struct

REFERENCE_SHA256 = '2f8fc395fee46328b12b7870795d7857fc52dc9df6e70f0b1ff20b538a6dab49'
OFFSETS = (0x400, 0x404, 0x408, 0x40c)
MARKER = 0x1f0
HREG = ('/boot/factory/Hreg.bin', '/boot/factory/Hreg2.bak')
XML = '/boot/dsc/RegionInfo.xml'
REQUIRED = ('/usr/dsc/fsk/regionInfo.xsb', '/usr/dsc/fsk/dsc.xsb',
            '/usr/dsc/fsk/tinyhttp', '/usr/dsc/fsk/kconfig.xml',
            '/usr/dsc/app/scripts/kconfig.xml', '/usr/dsc/fsk/PExtBackup.so',
            '/usr/dsc/fsk/PExtSenser.so', '/usr/lib/libBackupTable.so',
            '/usr/lib/libBackupCore.so', '/usr/lib/libAppBackupApi.so', '/usr/lib/libsencore.so')
COMMAND_MODULES = ('/usr/dsc/fsk/senserModule.xsb', '/usr/dsc/fsk/senserCmdTable.xsb')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_reference(base):
    path = base / 'reference-compatibility.json'
    if not path.is_file():
        path = base / 'reports/region-app/reference-compatibility.json'
    data = path.read_bytes()
    if digest(data) != REFERENCE_SHA256:
        raise ValueError('Bundled reference comparison manifest changed')
    return json.loads(data)


def hreg_values(data):
    if len(data) != 2048:
        raise ValueError('Unrecognized Hreg size; physical layout not established')
    if data[MARKER:MARKER+4] != b'\xaa'*4:
        raise ValueError('Hreg completion marker is not valid')
    return list(struct.unpack_from('<4I', data, OFFSETS[0]))


def assess(files, reference, xml_values):
    rows = []
    for path in REQUIRED + COMMAND_MODULES:
        if path not in files:
            rows.append(dict(path=path,status='missing',required=path in REQUIRED))
            continue
        data = files[path]
        matches = [r['model'] for r in reference['files'].get(path, [])
                   if r['bytes'] == len(data) and r['sha256'] == digest(data)]
        rows.append(dict(path=path,status='exact-reference-match' if matches else 'unknown-difference',
                         sha256=digest(data),reference_models=matches,required=path in REQUIRED))
    reasons = [r['path']+': '+r['status'] for r in rows
               if (r['required'] or r['status'] != 'missing') and r['status'] != 'exact-reference-match']
    if not any(r['path'] in COMMAND_MODULES and r['status']=='exact-reference-match' for r in rows):
        reasons.append('No matching complete service command module')
    coherent = None
    for row in rows:
        if row['status'] == 'exact-reference-match':
            models = set(row['reference_models'])
            coherent = models if coherent is None else coherent & models
    if not coherent:
        reasons.append('No coherent complete reference family; cross-model mixtures are not approved')
    original = signal = None
    try:
        primary, spare = (files[path] for path in HREG)
        original = hreg_values(primary)
        if hreg_values(spare) != original or primary != spare:
            raise ValueError('Original Hreg pair differs; resolve baseline selection before writing')
        values = xml_values(files[XML])
        signal = int(values['sigTyp'])
        if signal != original[3]:
            raise ValueError('Hreg and regional XML video settings disagree')
        # Restore semantics are bounded to the shared Japanese preset or valid custom Japanese/English.
        if original[0] == 0:
            if values.get('lang') != 'jpn' or values.get('langGp') != '1' or signal != 0:
                raise ValueError('Japanese preset baseline is inconsistent')
        elif original[0] == 255:
            if original[1] not in (0x8000, 0x100):
                raise ValueError('Baseline is not the reviewed Japanese or English custom configuration')
            if original[2] not in (1, 0x8000, 0x8100):
                raise ValueError('Original custom availability is outside this bounded restoration profile')
            if original[1] == 0x8000:
                if values.get('lang') != 'jpn':
                    raise ValueError('Baseline is not the reviewed Japanese custom configuration')
                group = '1' if original[2] == 1 else '99'
                if values.get('langGp') != group:
                    raise ValueError('Original custom language group disagrees with Hreg')
                if group == '99':
                    expected = {'jpn'} if original[2] == 0x8000 else {'eng','jpn'}
                    actual = {s.strip() for s in values.get('availableLang','').split(',') if s.strip()}
                    if actual != expected:
                        raise ValueError('Original custom availability disagrees with Hreg')
            elif original[1] == 0x100:
                if original[2] != 0x8100:
                    raise ValueError('Original custom availability is outside this bounded English profile')
                if values.get('lang') not in ('jpn', 'eng'):
                    raise ValueError('Baseline language is outside English/Japanese profile')
                if values.get('lang') == 'eng':
                    if values.get('langGp') != '99':
                        raise ValueError('Original custom language group disagrees with Hreg')
                    actual = {s.strip() for s in values.get('availableLang','').split(',') if s.strip()}
                    if actual != {'eng', 'jpn'}:
                        raise ValueError('Original custom availability disagrees with Hreg')
                elif values.get('lang') == 'jpn':
                    if values.get('langGp') != '1':
                        raise ValueError('Reverted baseline language group disagrees with Japanese profile')
        else:
            raise ValueError('Original region is outside this Japanese restoration profile')
    except (KeyError, ValueError) as error:
        reasons.append(str(error))
    if '/boot/dsc/UserInfo.xml' not in files:
        reasons.append('/boot/dsc/UserInfo.xml: original preferences were not acquired; unavailable does not prove absence')
    if '/boot/dsc/UserInfo.bak' not in files and (original is None or original[0] != 255 or original[1] != 0x100):
        reasons.append('/boot/dsc/UserInfo.bak: original preferences were not acquired; unavailable does not prove absence')
    return dict(schema='region-compatibility-v2',
                can_attempt_experimental_write=not reasons,
                hardware_region_change_verified=False,recovery_hardware_tested=False,
                method='Complete-file size/SHA-256 equivalence, not name or prefix matching',
                components=rows,coherent_reference_models=sorted(coherent or []),reasons=reasons,original_arguments=original,
                requested_arguments=[255,0x100,0x8100,signal] if signal is not None else None,
                hreg_file_offsets=list(OFFSETS),
                effects='RegionSetting resets user preferences; restore-region restores regional settings only')


def check_state(current, baseline, target, expected_xml, xml_values):
    allowed = {i for offset in OFFSETS for i in range(offset,offset+4)}
    for path in HREG:
        actual = hreg_values(current[path])
        if actual != target:
            raise ValueError('Regional field values have not converged')
        if any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(baseline[path],current[path]))):
            raise ValueError('Unexpected Hreg change outside region fields')
    values = xml_values(current[XML])
    for name in ('lang','langGp','sigTyp'):
        if values.get(name) != expected_xml.get(name):
            raise ValueError('Regional XML has not converged: '+name)
    if expected_xml.get('langGp') == '99':
        normalize = lambda text: {s.strip() for s in text.split(',') if s.strip()}
        if normalize(values.get('availableLang','')) != normalize(expected_xml.get('availableLang','')):
            raise ValueError('Available languages have not converged')
    return values
