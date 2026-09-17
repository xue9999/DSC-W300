"""Inspect two hash-pinned XS11 containers as bytes; do not decode or execute bytecode."""
from pathlib import Path
import hashlib
import json
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = ROOT / 'evidence/artifact_manifest.json'
pins = {item['path']: item for item in json.loads(MANIFEST.read_text())['artifacts']}
requested_names = ['xs_senser_on', 'xs_senser_ready', 'xs_senser_activeTrig',
                   'activeTrig', 'ready', 'reqStart', 'usbObject', 'Senser', 'Ready',
                   'SENSER_ON', 'SENSER_OFF', 'FORCE_USB']
results = []
for name in ['senserModule.xsb', 'senserCmdTable.xsb']:
    path = Path('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk') / name
    data = (ROOT / path).read_bytes()
    pin = pins[path.as_posix()]
    digest = hashlib.sha256(data).hexdigest()
    assert len(data) == pin['bytes'] and digest == pin['sha256']
    size, magic = struct.unpack_from('>I4s', data)
    assert size == len(data) and magic == b'XS11'
    result = dict(path=path.as_posix(), bytes=len(data), sha256=digest, manifest_pin_pass=True,
                  magic=magic.decode(), top_declared_size=size, sections=[], symbols=[], literal_occurrences={})
    offset = 8
    while offset < len(data):
        section_size, tag = struct.unpack_from('>I4s', data, offset)
        assert section_size >= 8 and offset + section_size <= len(data)
        section = dict(offset=offset, tag=tag.decode(), size=section_size,
                       payload_offset=offset+8, payload_size=section_size-8)
        result['sections'].append(section)
        if tag == b'SYMB':
            count = struct.unpack_from('>H', data, offset+8)[0]
            strings = data[offset+10:offset+section_size].split(b'\0')
            assert count == len(strings)-1 and not strings[-1]
            cursor = offset+10
            for index, raw in enumerate(strings[:-1]):
                result['symbols'].append(dict(index=index, offset=cursor, name=raw.decode('utf-8')))
                cursor += len(raw)+1
            assert cursor == offset+section_size
            section['declared_symbol_count'] = count
        offset += section_size
    assert offset == len(data)
    for query in requested_names + ['senserCmdTable.xsb']:
        raw = query.encode()
        matches = []
        cursor = 0
        while (cursor := data.find(raw, cursor)) != -1:
            matches.append(cursor)
            cursor += len(raw)
        result['literal_occurrences'][query] = matches
    result['exact_requested_symbols'] = [s for s in result['symbols'] if s['name'] in requested_names]
    results.append(result)
destination = HERE / 'xsb-inventory.json'
destination.write_text(json.dumps(dict(
    scope='Static byte-container and symbol-string inventory only; no bytecode control-flow interpretation.',
    manifest='evidence/artifact_manifest.json', artifacts=results), indent=2), encoding='utf-8')
print(destination)
for item in results:
    print(Path(item['path']).name, item['bytes'], 'PIN PASS', 'symbols', len(item['symbols']))
