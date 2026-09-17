"""Read retained G3 modules as ELF data; do not load or execute firmware."""
from pathlib import Path
import hashlib
import json
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pins = {r['path']: r for r in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts']}
for filename in ['unified_drv.ko', 'unified_drv2.ko']:
    path = ROOT / 'evidence/extracted_g3/rootfs/initrd/bin' / filename
    data = path.read_bytes()
    relative = path.relative_to(ROOT).as_posix()
    digest = hashlib.sha256(data).hexdigest()
    assert relative in pins and digest == pins[relative]['sha256'] and len(data) == pins[relative]['bytes'], relative
    header = struct.unpack_from('<HHIIIIIHHHHHH', data, 16)
    assert data[:6] == b'\x7fELF\x01\x01' and header[0] == 1 and header[1] == 40
    sections = [struct.unpack_from('<IIIIIIIIII', data, header[5] + i * header[10]) for i in range(header[11])]
    string_section = sections[header[12]]
    strings = data[string_section[4]:string_section[4] + string_section[5]]
    names = [strings[s[0]:].split(b'\0', 1)[0].decode() for s in sections]
    symbols = []
    tables = {}
    for index, section in enumerate(sections):
        if section[1] != 2:
            continue
        assert section[4] + section[5] <= len(data)
        string_section = sections[section[6]]
        assert string_section[4] + string_section[5] <= len(data)
        strings = data[string_section[4]:string_section[4] + string_section[5]]
        table = []
        for offset in range(section[4], section[4] + section[5], section[9]):
            n, value, size, info, other, target = struct.unpack_from('<IIIBBH', data, offset)
            rec = dict(name=strings[n:].split(b'\0', 1)[0].decode(), value=value, size=size,
                       type=info & 15, bind=info >> 4, section_index=target)
            if 0 < target < len(sections):
                rec['section'] = names[target]
                if sections[target][1] != 8:
                    rec['file_offset'] = sections[target][4] + value
            table.append(rec)
        tables[index] = table
        symbols += table
    relocations = []
    for index, section in enumerate(sections):
        if section[1] != 9:
            continue
        for offset in range(section[4], min(section[4] + section[5], len(data)) - 7, section[9]):
            rel_offset, info = struct.unpack_from('<II', data, offset)
            relocations.append(dict(rel_section=names[index], target_section=names[section[7]],
                offset=rel_offset, type=info & 255, symbol=tables[section[6]][info >> 8]))
    section_records = [dict(name=names[i], offset=s[4], size=s[5], index=i, type=s[1],
        stored_completely=s[1] == 8 or s[4] + s[5] <= len(data)) for i, s in enumerate(sections)]
    result = dict(path=relative, bytes=len(data), sha256=digest, artifact_manifest_pin_verified=True,
        sections=section_records, symbols=symbols, relocations=relocations,
        incomplete_sections=[s['name'] for s in section_records if not s['stored_completely']])
    (HERE / ('kernel-' + filename + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
    matches = [s for s in symbols if re.search('usb|senser|descriptor|gcore', s['name'], re.I)]
    print(filename, 'symbols', len(symbols), 'available relocations', len(relocations),
          'matches', len(matches), 'incomplete', result['incomplete_sections'])
    for symbol in matches:
        print(symbol['name'], hex(symbol['value']), hex(symbol['size']), symbol.get('section'),
              hex(symbol['file_offset']) if 'file_offset' in symbol else '-')
