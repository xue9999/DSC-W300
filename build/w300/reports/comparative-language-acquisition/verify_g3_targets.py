"""Extract hash-pinned G3 comparison targets without executing firmware."""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'g3-xs-entry'))
from frame_xs import parse

EXPECTED = {
    'regionInfo.xsb': {
        0x4a5: (0x2e, '34:deleteUserInfoFiles'),
        0x4dd: (0x2e, '39:checkLanguageName'),
        0x4e8: (0x2e, '40:getLanguageGroup'),
        0x4fb: (0x2e, '41:getAvailableLanguageList'),
        0x547: (0x2e, '34:deleteUserInfoFiles'),
        0x55d: (0x2e, '43:createManualRegionInfoFile'),
        0x570: (0x7c, '44:makeRegionInfoFile'),
        0x631: (0x2e, '50:write'),
        0x63f: (0x2e, '50:write'),
        0x64d: (0x2e, '50:write'),
        0x65b: (0x2e, '50:write'),
        0x66c: (0x2e, '52:flush'),
        0x672: (0x7c, '53:saveRegionInfoData'),
    },
    'senserCmdTable.xsb': {
        0x864: (0x2e, '120:makeRegionInfoFile'),
        0x87d: (0x2e, '121:saveRegionInfoData'),
        0x887: (0x2e, '123:reset'),
        0x891: (0x2e, '14:initialize'),
    },
}
results = []
for name, expected in EXPECTED.items():
    parsed = parse('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/' + name)
    rows = parsed['instructions']
    by_offset = {row['offset']: row for row in rows}
    bounds = set(by_offset) | {parsed['code_bytes']}
    for row in rows:
        if row['opcode'] in (0x28, 0x29, 0x2a):
            target = row['offset'] + 3 + int.from_bytes(bytes.fromhex(row['raw'])[1:], 'big', signed=True)
            assert target in bounds
    for offset, (opcode, symbol) in expected.items():
        row = by_offset[offset]
        assert row['opcode'] == opcode and row['symbols'] == [symbol]
    if name == 'regionInfo.xsb':
        for offset, symbol in [(0x62a, '6:bdIDRegion'), (0x638, '7:bdIDLanguage'),
                               (0x646, '8:bdIDAvailLang'), (0x654, '9:bdIDSignalType'),
                               (0x665, '10:bcIDHostRegulation')]:
            assert by_offset[offset]['opcode'] == 0x42
            assert by_offset[offset]['symbols'] == [symbol]
        selected = [row for row in rows if 0x423 <= row['offset'] <= 0x688]
    else:
        selected = [row for row in rows if 0x82a <= row['offset'] <= 0x891]
    results.append({key: value for key, value in parsed.items() if key != 'instructions'} |
                   {'selected_instructions': selected, 'checked_targets': len(expected)})
output = {'ok': True, 'scope': 'Static G3 call sites and framing only; no complete data-flow or persistence proof',
          'camera_io': False, 'firmware_executed': False, 'w300_qualified': False, 'scripts': results}
(HERE / 'g3-targets.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: value for key, value in output.items() if key != 'scripts'}))
