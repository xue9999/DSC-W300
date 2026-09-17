"""Decode three bounded G3 routines as data; never execute firmware code."""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1] / 're-tools' / 'site'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN, CS_OP_IMM, CS_OP_REG, CS_OP_MEM
from capstone.arm import ARM_REG_IP, ARM_REG_PC

SELECTED = {'libsencore.so': ['fallback11', 'direct-handler', 'ipc-helper']}

inventory = json.loads((HERE.parent / 'retained-service-inventory.json').read_text())
lines = ['Capstone 5.0.6; static decoding only. Addresses below are G3 ELF addresses, not W300 camera addresses.']
for item in inventory:
    name = Path(item['path']).name
    if name not in SELECTED:
        continue
    data = (ROOT / item['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['sha256']
    header = struct.unpack_from('<HHIIIIIHHHHHH', data, 16)
    sections = [struct.unpack_from('<IIIIIIIIII', data, header[5] + i * header[10]) for i in range(header[11])]
    names = sections[header[12]]
    names = data[names[4]:names[4]+names[5]]
    named = {names[s[0]:].split(b'\0',1)[0].decode():s for s in sections}
    def file_offset(va):
        section = next(s for s in sections if s[1] != 8 and s[3] <= va < s[3]+s[5])
        return section[4] + va - section[3]
    def word(va):
        return struct.unpack_from('<I', data, file_offset(va))[0]
    def text_at(va):
        return data[file_offset(va):].split(b'\0', 1)[0].decode('ascii')
    base = 0xd818 + word(0xd89c)
    slot = base + word(0xd8a8)
    rel = named['.rel.dyn']
    rels = {struct.unpack_from('<II', data, at)[0]:struct.unpack_from('<II', data, at)[1]
            for at in range(rel[4], rel[4]+rel[5], rel[9])}
    symbol_table = sections[rel[6]]
    string_table = sections[symbol_table[6]]
    dynstrings = data[string_table[4]:string_table[4]+string_table[5]]
    info = rels[slot]
    assert info & 255 == 21  # R_ARM_GLOB_DAT
    name_at, table_va, table_size = struct.unpack_from('<III', data, symbol_table[4]+(info>>8)*symbol_table[9])
    assert dynstrings[name_at:].split(b'\0',1)[0] == b'AdjustCommunication' and table_size == 64
    assert rels[table_va+4] == 23  # R_ARM_RELATIVE, zero symbol index
    assert word(table_va+4) == 0xe894
    strings = {}
    for label, literal in [('device', 0xe7b0), ('connect_error', 0xe7c0),
                           ('transaction', 0xe7c4), ('av_result', 0xe7cc), ('mapping', 0xe7d8)]:
        va = (base + word(literal)) & 0xffffffff
        strings[label] = {'va':hex(va), 'file_offset':hex(file_offset(va)), 'text':text_at(va)}
    evidence = {'source':item['path'], 'sha256':item['sha256'], 'pic_base':hex(base),
                'got_slot':hex(slot), 'got_relocation':'R_ARM_GLOB_DAT: AdjustCommunication',
                'table_va':hex(table_va), 'table_file_offset':hex(file_offset(table_va)),
                'index_for_header_0x11':1, 'entry_relocation':'R_ARM_RELATIVE', 'target':'0xe894',
                'strings':strings, 'connect_ioctl':hex(word(0xe7bc)),
                'seus_ascii_hits':{term.decode():data.count(term) for term in [b'SEUS', b'Seus', b'seus']}}
    (HERE / 'fallback11-evidence.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
    plt, reloc = named['.plt'], named['.rel.plt']
    assert reloc[9] == 8 and plt[5] == 20 + (reloc[5] // 8) * 12
    table = sections[reloc[6]]
    strings = sections[table[6]]
    strings = data[strings[4]:strings[4]+strings[5]]
    imported = {}
    plt_decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    plt_decoder.detail = True
    for index, at in enumerate(range(reloc[4], reloc[4]+reloc[5], 8)):
        got_slot, info = struct.unpack_from('<II', data, at)
        assert info & 255 == 22  # R_ARM_JUMP_SLOT, checked against actual entries.
        entry_address = plt[3]+20+index*12
        entry_offset = plt[4]+20+index*12
        stub = list(plt_decoder.disasm(data[entry_offset:entry_offset+12], entry_address))
        assert len(stub) == 3 and [i.mnemonic for i in stub] == ['add', 'add', 'ldr']
        first, second, third = [i.operands for i in stub]
        assert [o.type for o in first[:3]] == [CS_OP_REG, CS_OP_REG, CS_OP_IMM]
        assert [o.type for o in second[:3]] == [CS_OP_REG, CS_OP_REG, CS_OP_IMM]
        assert first[0].reg == second[0].reg == second[1].reg == ARM_REG_IP and first[1].reg == ARM_REG_PC
        assert [o.type for o in third] == [CS_OP_REG, CS_OP_MEM]
        assert third[0].reg == ARM_REG_PC and third[1].mem.base == ARM_REG_IP and third[1].mem.index == 0
        # Capstone can show the encoded rotation as a fourth operand (e.g. #0,#12).
        # Decode ARM ADD's modified immediate directly, avoiding display conventions.
        additions = []
        for instruction, expected_base in zip(stub[:2], [15, 12]):
            word = int.from_bytes(instruction.bytes, 'little')
            assert word & (1 << 25) and (word >> 21) & 15 == 4
            assert (word >> 16) & 15 == expected_base and (word >> 12) & 15 == 12
            immediate, rotation = word & 255, ((word >> 8) & 15) * 2
            additions.append(((immediate >> rotation) | (immediate << (32-rotation))) & 0xffffffff if rotation else immediate)
        calculated_slot = (entry_address + 8 + sum(additions) + third[1].mem.disp) & 0xffffffff
        assert calculated_slot == got_slot, (name, hex(entry_address), hex(calculated_slot), hex(got_slot))
        string_offset = struct.unpack_from('<I', data, table[4] + (info >> 8) * table[9])[0]
        imported[entry_address] = strings[string_offset:].split(b'\0',1)[0].decode()
    lines.append('%s: verified %d PLT stub GOT slots against relocation r_offset.' % (name, len(imported)))
    for requested in SELECTED[name]:
        if requested == 'fallback11':
            # AdjustCommunication[1], derived via GOT and R_ARM_GLOB_DAT, then R_ARM_RELATIVE; bound ends at next table target.
            symbol = {'value':'0xe894', 'file_offset':'0xe894', 'size':124}
        elif requested == 'direct-handler':
            # Direct BL target at 0xe904; stops at final return before literal pool.
            symbol = {'value':'0xe104', 'file_offset':'0xe104', 'size':1676}
        elif requested == 'ipc-helper':
            # Direct BL from 0xe3d4; stops at final return before literal pool.
            symbol = {'value':'0xdd84', 'file_offset':'0xdd84', 'size':360}
        else:
            symbol = next(s for s in item['symbols'] if s['name'] == requested and 'file_offset' in s)
        value = int(symbol['value'], 16)
        start = value & ~1
        offset = int(symbol['file_offset'], 16)
        payload = data[offset:offset + symbol['size']]
        decoder = Cs(CS_ARCH_ARM, (CS_MODE_THUMB if value & 1 else CS_MODE_ARM) | CS_MODE_LITTLE_ENDIAN)
        lines.append('\n%s %s file=%s value=%s size=%d sha256=%s' % (name, requested, symbol['file_offset'], symbol['value'], symbol['size'], item['sha256']))
        for instruction in decoder.disasm(payload, start):
            annotation = ''
            if instruction.mnemonic in ['b', 'bl', 'blx'] and instruction.op_str.startswith('#0x'):
                target = int(instruction.op_str[1:], 16)
                names = sorted(set(s['name'] for s in item['symbols'] if int(s['value'],16) == target))
                if target in imported:
                    names.append('PLT:' + imported[target])
                annotation = ' ; symbol=' + ','.join(names) if names else ''
            lines.append('0x%08x  %-12s %-8s %s%s' % (instruction.address, instruction.bytes.hex(), instruction.mnemonic, instruction.op_str, annotation))
destination = HERE / 'fallback11.asm.txt'
destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(destination)
