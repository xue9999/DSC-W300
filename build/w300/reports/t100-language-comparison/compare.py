"""Reproduce bounded T100/G3 native-table and XS language comparisons offline."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'g3-usb-descriptor'))
sys.path.insert(0, str(HERE.parent / 'g3-xs-entry'))
from inspect_usb import Elf, cstr
import frame_xs

TBASE = 'build/w300/downloads/related-firmware/t100-extracted/archives_unpacked/'
GBASE = 'evidence/extracted_g3/archives_unpacked/'


def atoms(data):
    assert data[4:8] == b'XS11' and int.from_bytes(data[:4], 'big') == len(data)
    at = 8
    result = {}
    while at < len(data):
        size, tag = struct.unpack_from('>I4s', data, at)
        assert size >= 8 and at + size <= len(data)
        result[tag] = (at + 8, data[at + 8:at + size])
        at += size
    base, symbols = result[b'SYMB']
    count = int.from_bytes(symbols[:2], 'big')
    names = symbols[2:].split(b'\0')[:-1]
    assert len(names) == count
    base, code = result[b'CODE']
    return base, code, names


def branch(elf, va):
    word = elf.word(va)
    assert word >> 24 == 0xea
    displacement = word & 0xffffff
    if displacement & 0x800000:
        displacement -= 1 << 24
    return va + 8 + 4 * displacement


def main():
    extracted = json.loads((HERE / 'extraction.json').read_text())
    tpins = {r['path']: r for r in extracted['artifacts']}
    gpins = {r['path']: r for r in json.loads((ROOT / 'evidence/artifact_manifest.json').read_text())['artifacts']}

    def read(path):
        pin = (tpins if path.startswith(TBASE) else gpins)[path]
        data = (ROOT / path).read_bytes()
        assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
        return data

    def elf(path):
        return Elf(path, pin=(tpins if path.startswith(TBASE) else gpins)[path])

    runtime = elf(TBASE + 'fskrel1/dsc/fsk/tinyhttp')
    dispatch = {op: branch(runtime, 0x9cab0 + 4 * (op - 0x20)) for op in range(0x20, 0x8c)}
    assert {op: target - 0x8a60 for op, target in dispatch.items()} == frame_xs.DISPATCH
    # Preserve actual ARM decoding used to review the remapper, not an assumed XS version.
    (HERE / 't100-remapper.asm.txt').write_text(runtime.decode('fxRemapIDs') + '\n', encoding='utf-8')
    summaries = []
    codes = {}
    selected_rows = {}
    specifications = [
        ('T100', 'regionInfo.xsb', [(0, 0x698), (0x700, 0xe40)]),
        ('T100', 'dsc.xsb', [(0xc480, 0xc680)]),
        ('T100', 'senserModule.xsb', [(0x12150, 0x12245)]),
        ('G3', 'regionInfo.xsb', [(0, 0x698), (0x700, 0xe40)]),
        ('G3', 'dsc.xsb', [(0x165fa, 0x16830), (0x1ce00, 0x1cee0)]),
        ('G3', 'senserCmdTable.xsb', [(0x82a, 0x8f0)]),
    ]
    for model, name, ranges in specifications:
        path = (TBASE + 'fskrel3/dsc/fsk/' if model == 'T100' else GBASE + 'fskrel1/dsc/fsk/') + name
        base, code, names = atoms(read(path))
        rows = frame_xs.frame(code, names, base,
                              dispatch=dispatch if model == 'T100' else None,
                              target_bias=0x8a60 if model == 'T100' else 0)
        bounds = {r['offset'] for r in rows} | {len(code)}
        branches = 0
        for row in rows:
            if row['opcode'] in (0x28, 0x29, 0x2a):
                target = row['offset'] + 3 + int.from_bytes(bytes.fromhex(row['raw'])[1:], 'big', signed=True)
                assert target in bounds
                branches += 1
        selected = [r for r in rows if any(lo <= r['offset'] <= hi for lo, hi in ranges)]
        key = model + '-' + name
        codes[key] = code
        selected_rows[key] = selected
        summary = dict(model=model, path=path, sha256=hashlib.sha256(read(path)).hexdigest(),
                       code_base=base, instructions=len(rows), checked_branches=branches, ranges=ranges)
        summaries.append(summary)
        (HERE / (key + '.json')).write_text(json.dumps(summary | {'selected': selected}, indent=2) + '\n', encoding='utf-8')
        (HERE / (key + '.txt')).write_text('\n'.join(
            f"{r['offset']:06x} {r['raw']:24s} {' '.join(r['symbols'])} {r['note']}" for r in selected) + '\n', encoding='utf-8')
    assert codes['T100-regionInfo.xsb'][:0x423] == codes['G3-regionInfo.xsb'][:0x423]
    masks = []
    initial = selected_rows['T100-regionInfo.xsb']
    for index, row in enumerate(initial):
        if 0x1bb <= row['offset'] < 0x3fa and row['opcode'] == 0x6a:
            previous = initial[index - 1]
            assert previous['opcode'] in (0x89, 0x8a, 0x48)
            value = int.from_bytes(bytes.fromhex(previous['raw'])[1:], 'big', signed=True)
            language = bytes.fromhex(row['raw'])[1:-1].decode()
            assert initial[index + 3]['symbols'] == ['18:LanguageData']
            masks.append(dict(language=language, mask=value, mask_hex=hex(value), code_offset=previous['offset']))
    assert len(masks) == 25 and {m['language']: m['mask'] for m in masks}['eng'] == 0x100
    groups = []
    for model, low, high, default in [('T100', 0xc4cf, 0xc4f8, 0xc646), ('G3', 0x16634, 0x16664, 0x167ff)]:
        rows = selected_rows[model + '-dsc.xsb']
        by_offset = {r['offset']: r for r in rows}
        cases = []
        for index, row in enumerate(rows):
            if low <= row['offset'] < high and row['opcode'] == 0x89:
                assert [r['opcode'] for r in rows[index:index + 3]] == [0x89, 0x69, 0x29]
                jump = rows[index + 2]
                target = jump['offset'] + 3 + int.from_bytes(bytes.fromhex(jump['raw'])[1:], 'big', signed=True)
                literal = by_offset[target]
                assert literal['opcode'] == 0x6a
                cases.append(dict(group=int.from_bytes(bytes.fromhex(row['raw'])[1:], 'big', signed=True),
                                  target=target, literal=bytes.fromhex(literal['raw'])[1:-1].decode()))
        groups.append(dict(model=model, cases=cases, default=bytes.fromhex(by_offset[default]['raw'])[1:-1].decode()))
    assert [r['group'] for r in groups[0]['cases']] == [0, 1, 2, 3, 4, 99]
    assert [r['group'] for r in groups[1]['cases']] == [0, 1, 2, 3, 4, 5, 99]
    handlers = []
    for opcode, size in [(0x89, 0x40), (0x8a, 0x50), (0x48, 0x58), (0x69, 0x14), (0x24, 0x40), (0x29, 0x38)]:
        start = branch(runtime, 0x99230 + 4 * (opcode - 0x21))
        handlers.append(f'Opcode {opcode:#x}\n' + runtime.decode(f'range@{start:#x}:{start + size:#x}'))
    handlers.append(runtime.decode('range@0x9c760:0x9c940'))
    (HERE / 't100-selected-handlers.asm.txt').write_text('\n\n'.join(handlers) + '\n', encoding='utf-8')

    fields = []
    native_decode = []
    xmls = []
    for model, prefix, pins, app in [('T100', TBASE, tpins, 'fskapp'), ('G3', GBASE, gpins, 'fskapp1')]:
        table = elf(prefix + 'lib/lib/libBackupTable.so')
        rows = []
        for array in ['HOST_PROD_REG', 'HOST_COM_REG']:
            symbol = table.sym(array)
            count = table.word(table.sym(array + '_NUM')['value'])
            assert symbol['size'] == count * 20
            for index in range(count):
                va = symbol['value'] + index * 20
                row = struct.unpack_from('<5I', table.data, table.off(va))
                if row[0] in (0x10400, 0x40000, 0x40400, 0x40800, 0x40c00):
                    rows.append(dict(array=array, va=va, file_offset=table.off(va), values=row))
        assert len(rows) == 5
        core = elf(prefix + 'lib/lib/libBackupCore.so')
        files = []
        for name in ['_ZN12FileAccesser9FILE_NAMEE', '_ZN28FileAccesserMeasures2BattOff15SPARE_FILE_NAMEE']:
            va = core.sym(name)['value']
            assert next(r for r in core.reloc if r['offset'] == va)['type'] == 23
            files.append(cstr(core.data, core.off(core.word(va))))
        assert files == ['/boot/factory/Hreg.bin', '/boot/factory/Hreg2.bak']
        fields.append(dict(model=model, table_sha256=table.sha, rows=rows, category0_files=files))
        native_decode.append(model + '\n' + '\n'.join(table.decode(name) for name in
                              ['_ZN9DataTable13getCategoryIdEj', '_ZN9DataTable9getOffsetEj']) + '\n' +
                              core.decode('_ZN12CommonMethod5flushEj'))
        if model == 'T100':
            native_decode.append(table.decode('range@0x1dcc:0x1de8'))
        extension = elf(prefix + ('fskrel3' if model == 'T100' else 'fskrel1') + '/dsc/fsk/PExtBackup.so')
        grammar = struct.unpack_from('<6I', extension.data, extension.off(extension.sym('PExtBackupGrammar')['value']))
        symbols = extension.data[extension.off(grammar[1]):extension.off(grammar[1]) + grammar[2]]
        names = symbols[2:].split(b'\0')[:-1]
        code = extension.data[extension.off(grammar[3]):extension.off(grammar[3]) + grammar[4]]
        framed = frame_xs.frame(code, names, dispatch=dispatch if model == 'T100' else None,
                                target_bias=0x8a60 if model == 'T100' else 0)
        associations = []
        for index, row in enumerate(framed):
            if row['opcode'] == 0x7c and any(term in str(row['symbols']) for term in
                     ['DestinationID', 'regionData', 'initLangData', 'availLangData', 'signalTypeData']):
                sequence = framed[index - 6:index + 1]
                assert [r['opcode'] for r in sequence] == [0x6a, 0x89, 0x6d, 0x42, 0x2e, 0x6c, 0x7c]
                associations.append(dict(property=row['symbols'], literal=sequence[0]['note'], sequence=sequence))
        assert len(associations) == 5
        fields[-1]['grammar_associations'] = associations
        for path in sorted((ROOT / prefix / app / 'dsc/app/systemData/RegionInfo').glob('*.xml')):
            rel = path.relative_to(ROOT).as_posix()
            data = read(rel)
            doc = ET.fromstring(data)
            xmls.append(dict(model=model, path=rel, sha256=hashlib.sha256(data).hexdigest(),
                             values={e.tag.split('}')[-1]:e.text for e in doc.iter() if e.text and e.text.strip()}))
    assert sorted(r['values'] for r in fields[0]['rows']) == sorted(r['values'] for r in fields[1]['rows'])
    (HERE / 'native-fields.asm.txt').write_text('\n\n'.join(native_decode) + '\n', encoding='utf-8')
    result = dict(ok=True, scope='Static comparison of Sony T100 updater and retained G3 firmware',
                  fields=fields, region_xml=xmls, scripts=summaries, language_masks=masks, language_groups=groups,
                  region_initialization_equal_bytes=0x423, remapper_target_bias=0x8a60,
                  camera_accessed=False, firmware_executed=False, w300_qualified=False)
    (HERE / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(ok=True, matching_fields=5, scripts=len(summaries), region_xml=len(xmls), w300_qualified=False)))


if __name__ == '__main__':
    main()
