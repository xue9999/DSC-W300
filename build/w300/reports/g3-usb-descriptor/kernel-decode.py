"""Static selected ET_REL ARM decoding with annotations from retained relocations."""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1] / 're-tools/site'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_OP_MEM
from capstone.arm import ARM_REG_PC

record = json.loads((HERE / 'kernel-unified_drv.ko.json').read_text())
data = (ROOT / record['path']).read_bytes()
assert hashlib.sha256(data).hexdigest() == record['sha256']
sections = {s['name']: s for s in record['sections']}
text_offset = sections['.text']['offset']
relocations = {r['offset']: r for r in record['relocations'] if r['target_section'] == '.text'}

def describe(relocation, value):
    symbol = relocation['symbol']
    name = symbol['name'] or symbol.get('section', 'UND')
    if relocation['type'] in [28, 29]:
        immediate = (value & 0xffffff) << 2
        if immediate & 0x2000000:
            immediate -= 0x4000000
        return (f"R_ARM_BRANCH {name}+{immediate + 8:#x} => "
                f"{symbol.get('section', 'UND')}:{symbol['value'] + immediate + 8:#x}")
    if relocation['type'] == 2:
        target = symbol['value'] + value
        description = (f"R_ARM_ABS32 {name}+{value:#x} => "
                       f"{symbol.get('section', 'UND')}:{target:#x}")
        if symbol.get('section') in sections and symbol['section'] != '.bss':
            offset = sections[symbol['section']]['offset'] + target
            description += f' file={offset:#x}'
            literal = data[offset:offset+80].split(b'\0', 1)[0]
            if literal and all(32 <= c < 127 for c in literal):
                description += ' string=' + repr(literal.decode())
        return description
    return str(relocation)

lines = [
    'Capstone 5.0.6 static data analysis only. ELF ET_REL, ARM little endian.',
    'Instruction addresses are .text section offsets, not runtime camera addresses.',
    'Raw displayed branch targets are UNRELOCATED; use R_ARM_BRANCH annotations.',
    'UND targets identify imported symbols, not resolved implementation addresses.',
    'Retained unified_drv.ko has a truncated relocation tail. No absent entries are synthesized.',
    f"Source SHA256: {record['sha256']}",
]
decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
decoder.detail = True
for start, end in [(0xb480, 0xb5e4), (0x19cc4, 0x1a650)]:
    lines.append(f'\nRange .text:{start:#x}..{end:#x} file:{start+text_offset:#x}..{end+text_offset:#x}')
    for instruction in decoder.disasm(data[start+text_offset:end+text_offset], start):
        annotations = []
        if instruction.address in relocations:
            annotations.append(describe(relocations[instruction.address], int.from_bytes(instruction.bytes, 'little')))
        for operand in instruction.operands:
            if operand.type == CS_OP_MEM and operand.mem.base == ARM_REG_PC:
                offset = instruction.address + 8 + operand.mem.disp
                value = struct.unpack_from('<I', data, offset + text_offset)[0]
                annotations.append(f'literal .text:{offset:#x} value={value:#x} ' +
                    (describe(relocations[offset], value) if offset in relocations else 'no retained relocation'))
        lines.append(f'{instruction.address:08x} {instruction.bytes.hex()} {instruction.mnemonic:6s} {instruction.op_str}' +
                     (' ; ' + ' | '.join(annotations) if annotations else ''))
destination = HERE / 'kernel-sen-driver.asm.txt'
destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(destination)
