"""Decode bounded hash-pinned G3 backup routines as data; never execute firmware code."""
from pathlib import Path
import hashlib
import json
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / 'build' / 'w300' / 're-tools' / 'site'))
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN, CS_OP_IMM, CS_OP_REG, CS_OP_MEM
from capstone.arm import ARM_REG_IP, ARM_REG_PC

SELECTED = {
    'libBackupCore.so': ['_Z15backupFileWritePKcljPKv','_ZN11ShadowTableC1Ev','_ZN11ShadowTable13getShadowAddrEj','_ZN14ShadowAccesser16createShadowAreaEv','_ZN14ShadowAccesser16createSharedAreaEPPvjj','_ZN30ShadowAccesserMeasures2BattOff14selectDataAreaEv','_ZN28FileAccesserMeasures2BattOff13checkFlushFlgEjPj','_ZN12CommonMethod5flushEj','_ZN12CommonMethod7refreshEj','_ZN12CommonMethod5eraseEj','_ZN11BasicMethod5flushEjjj','_ZN11BasicMethod5eraseEjjj','_ZN12FileAccesser11getFileNameEj','_ZN28FileAccesserMeasures2BattOff5writeEjjjPKv','_ZN28FileAccesserMeasures2BattOff9writeUserEjjjPKv','_ZN28FileAccesserMeasures2BattOff5eraseEjjjPKv','_ZN28FileAccesserMeasures2BattOff11writeSafelyEjPKcjjPKv'],
    'libAppBackupApi.so': ['_ZN13BackupWatcher5startEv', '_ZN13BackupWatcher13postAVCommandEP9AVCommand', '_ZN13BackupWatcher24handleAllCommandCallbackEiP9AVCommand', '_ZN13BackupWatcher14publishCommandEiP11BackupEvent', '_ZN13BackupWatcher8callbackEiP11BackupEvent', '_ZN13BackupWatcher12executeEventEP11BackupEvent', '_ZN13BackupWatcher12publishEventEP9AVCommand', '_ZN13BackupWatcher3runEv'],
}

# Exclusive code ends confirmed at the final unconditional return in these
# selected routines. The remaining symbol bytes are literal-pool data.
CODE_ENDS = {
    'libBackupCore.so': {
        0x6ab8: 0x6b74, 0x6c20: 0x6c44, 0x7b58: 0x7bc8,
        0x8414: 0x845c, 0x895c: 0x8aa4, 0x8aa8: 0x8c54,
    },
    'libAppBackupApi.so': {
        0x48b4: 0x4958, 0x49ec: 0x4a74, 0x4c54: 0x4d84,
        0x4d8c: 0x4f54,
    },
}

inventory = json.loads((ROOT / 'build/w300/reports/retained-service-inventory.json').read_text())
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
        if requested == 'local-category-helper':
            # Exact direct branch target in AdjustControlFunc, ending before it.
            symbol = {'value':'0xd7c0', 'file_offset':'0xd7c0', 'size':56}
        else:
            symbol = next(s for s in item['symbols'] if s['name'] == requested and 'file_offset' in s)
        value = int(symbol['value'], 16)
        start = value & ~1
        offset = int(symbol['file_offset'], 16)
        payload = data[offset:offset + symbol['size']]
        decoder = Cs(CS_ARCH_ARM, (CS_MODE_THUMB if value & 1 else CS_MODE_ARM) | CS_MODE_LITTLE_ENDIAN)
        decoder.detail = True
        lines.append('\n%s %s file=%s value=%s size=%d sha256=%s' % (name, requested, symbol['file_offset'], symbol['value'], symbol['size'], item['sha256']))
        code_end = CODE_ENDS.get(name, {}).get(start, start + len(payload))
        code = list(decoder.disasm(payload[:code_end-start], start))
        assert sum(len(i.bytes) for i in code) == code_end-start
        if code_end < start + len(payload):
            assert code[-1].mnemonic in ('ldm', 'ldmib') and code[-1].op_str.endswith('pc}')
        for instruction in code:
            annotation = ''
            if instruction.mnemonic.startswith('ldr') and len(instruction.operands)>1 and instruction.operands[1].type == CS_OP_MEM and instruction.operands[1].mem.base == ARM_REG_PC and instruction.operands[1].mem.index == 0:
                lit = instruction.address+8+instruction.operands[1].mem.disp
                loc = next((z[4]+lit-z[3] for z in sections if z[1]!=8 and z[3]<=lit<z[3]+z[5]), None)
                if loc is not None:
                    annotation = ' ; literal@0x%x=0x%08x' % (lit, struct.unpack_from('<I', data,loc)[0])

            if instruction.mnemonic in ['b', 'bl', 'blx'] and instruction.op_str.startswith('#0x'):
                target = int(instruction.op_str[1:], 16)
                names = sorted(set(s['name'] for s in item['symbols'] if int(s['value'],16) == target))
                if target in imported:
                    names.append('PLT:' + imported[target])
                annotation = ' ; symbol=' + ','.join(names) if names else ''
            lines.append('0x%08x  %-12s %-8s %s%s' % (instruction.address, instruction.bytes.hex(), instruction.mnemonic, instruction.op_str, annotation))
        if code_end < start + len(payload):
            lines.append('; trailing literal pool: data, not instructions')
            assert (len(payload) - (code_end-start)) % 4 == 0
            for at in range(code_end-start, len(payload), 4):
                raw = payload[at:at+4]
                lines.append('0x%08x  %-12s .word    0x%08x ; data' % (start+at, raw.hex(), int.from_bytes(raw, 'little')))
destination = HERE / 'linux-backup.asm.txt'
destination.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(destination)
