"""Verify retained G3 file-reader evidence statically; no USB or firmware execution."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'g3-usb-descriptor'))
from inspect_usb import Elf

core = Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so')
pro = Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libpro00.so')
adj = Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libadj30.so')
assert adj.sym('StoreSenserMode')['value'] == 0x24b4
assert adj.sym('LoadSenserMode')['value'] == 0x2440
assert adj.word(0x2400) == 0x1241
assert adj.data[adj.off(0x3b64):].split(b'\0', 1)[0] == b'/boot/sen/smode'
assert core.sym('_Z11FileControlPK12SenserPacket')['value'] == 0xed1c
for address, value in {0xed88: 0xe3a02004, 0xedac: 0xe3530002,
                       0xedb0: 0x0a000069, 0xd0c4: 0xe3a02a01,
                       0xd0c8: 0xe3a03902}.items():
    assert core.word(address) == value, hex(address)
pic = (0xed34 + 8 + core.word(0xefe8)) & 0xffffffff
assert pic == 0x1b2d4
assert (pic + core.word(0xf00c)) & 0xffffffff == 0xcfb4
assert core.plt[0x5da4] == '_ZN14ReadDeviceDataC1EPKcij'
assert core.plt[0x61e8] == '_ZN8DeviceIo4openEPKci'
assert core.plt[0x5d44] == '_ZNK8DeviceIo4readEPvj'
assert core.plt[0x6260] == '_ZNK8DeviceIo4sizeEv'
assert pro.plt[0x8df4] == 'open'
assert pro.plt[0x8fb0] == 'read'
assert pro.plt[0x91cc] == '_ZNK8DeviceIo5fstatER4stat'
assert any(r['offset'] == 0x1b8cc and r['symbol'] == '_ZNK14ReadDeviceData7GetSizeEv'
           and r['symbol_value'] == 0x9d80 for r in core.reloc)

pin = 'a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'
checkout = ROOT / 'build/w300/upstream/Sony-PMCA-RE'
source = (checkout / 'pmca/usb/sony.py').read_bytes()
assert source == subprocess.check_output(['git', '-C', str(checkout), 'show', pin + ':pmca/usb/sony.py'])
tree = ast.parse(source)
camera = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SonySenserCamera')
constants = {n.targets[0].id: ast.literal_eval(n.value) for n in camera.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and isinstance(n.value, ast.Constant)}
assert constants['SONY_PFUNC_FileControl'] == 0xff01
assert constants['SONY_FILE_CONTROL_READ'] == 2
assert constants['SONY_FILE_CONTROL_WRITE'] == 1
assert constants['SONY_FILE_CONTROL_DELETE'] == 3
selected = {}
for name in ('_sendFileControlPacket', 'readFile'):
    node = next(n for n in camera.body if isinstance(n, ast.FunctionDef) and n.name == name)
    selected[name] = ast.get_source_segment(source.decode(), node)

ranges = [(core, [(0xed1c, 0xefe8), (0xcfb4, 0xd184), (0xb3c0, 0xb5a8),
                  (0x9d80, 0x9d98), (0x9df4, 0x9e10), (0xaf10, 0xafa0),
                  (0x6994, 0x6bfc), (0x6814, 0x697c)]),
          (pro, [(0xc2f4, 0xc3a8), (0xc854, 0xc8d4), (0xc150, 0xc198)]),
          (adj, [(0x1e9c, 0x1f30), (0x20f4, 0x23e4), (0x2440, 0x24ec)])]
decoded = ['Static ARM disassembly. Ranges can include literal data; decoded data words are not claimed executed.']
for elf, spans in ranges:
    decoded.append(elf.relative + '\nSHA256 ' + elf.sha)
    decoded.extend(elf.decode(f'range@{lo:#x}:{hi:#x}') for lo, hi in spans)
(HERE / 'file-read.asm.txt').write_text('\n\n'.join(decoded) + '\n', encoding='utf-8')
result = dict(ok=True, camera_io=False, firmware_executed=False, w300_qualified=False,
              scope='Pinned static G3 file reader and PMCA constants; not an end-to-end transport test',
              firmware=[dict(path=e.relative, sha256=e.sha) for e in (core, pro, adj)],
              read_callback=hex(0xcfb4), open_flags=hex(0x1000), buffer_bytes=0x8000,
              pmca=dict(commit=pin, sha256=hashlib.sha256(source).hexdigest(), functions=selected))
(HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('ok', 'camera_io', 'firmware_executed', 'w300_qualified', 'scope')}))
