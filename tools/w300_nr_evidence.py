"""Read-only, standard-library verification of pinned W300 NR dispatch evidence.

Decodes only the small Thumb-1 instruction patterns used by the reviewed anchors.
It does not execute firmware, generate patches, access USB or qualify a write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
AV = ROOT / 'evidence/w300/av.bin'
AV_SHA256 = 'bfa4df20f5d25daf82419c12ab7efb16ea39420c544a72a3d5037c71ac49bd30'
AV_SIZE = 2233094
SA = ROOT / 'evidence/w300/sa.bin'
SA_SHA256 = '5126c376de296624280ccdc1c8692d98ec674cfaf69bfa8ef6dfa2e367010d44'
BACKUP_CORE = ROOT / 'evidence/w300/baseline_files/usr/lib/libBackupCore.so'
BACKUP_CORE_SHA256 = '56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b'
BASE = 0x20100000
PROGRAM_TABLE = 0x16eaf4
# ID, wrapper, dispatch call, normal gate, alternate gate, name.
STAGES = (
    (3, 0xab34a, 0x2c2bc, 0x2c2a8, 0x2c29e, 'NR16_RAWNR'),
    (4, 0xab370, 0x2c364, 0x2c352, 0x2c348, 'NR32_RAWNR'),
    (5, 0xab396, 0x2c3ce, 0x2c3c0, 0x2c3b6, 'NR32_CNR_2GCC'),
    (6, 0xab3bc, 0x2c43a, 0x2c42c, 0x2c422, 'NR32_CNR_NR'),
    (7, 0xab3e2, 0x2c4d8, 0x2c4ca, 0x2c48c, 'NR32_CNR_2RGB'),
)
SA_HEADERS = ('NR16_RAW0.07', 'NR32_RAW0.07', 'NR32_GCC0.11',
              'NR32_CNR0.07', 'NR32_RGB0.11')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def half(data, at):
    return struct.unpack_from('<H', data, at)[0]


def word(data, at):
    return struct.unpack_from('<I', data, at)[0]


def thumb_bl(data, at):
    hi, lo = struct.unpack_from('<HH', data, at)
    require(hi & 0xf800 == 0xf000 and lo & 0xf800 == 0xf800,
            f'Expected Thumb BL at {at:#x}')
    delta = ((hi & 0x7ff) << 12) | ((lo & 0x7ff) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return at + 4 + delta


def gate_offset(data, at):
    """Decode bank+constant LDRB, without guessing addresses from nearby bytes."""
    start = at
    op = half(data, at)
    if op & 0xff00 == 0x2100:  # movs r1, #imm8
        value = op & 0xff
        shift = half(data, at + 2)
        require(shift & 0xf83f == 0x0009, 'Expected lsls r1,r1,#imm')
        value <<= (shift >> 6) & 31
        at += 4
    else:
        require(op & 0xff00 == 0x4900, 'Expected ldr r1,[pc,#imm]')
        literal = ((at + 4) & ~3) + (op & 0xff) * 4
        value = word(data, literal)
        at += 2
    require(half(data, at) == 0x1840, 'Expected adds r0,r0,r1')
    load = half(data, at + 2)
    require(load & 0xf83f == 0x7800, 'Expected ldrb r0,[r0,#imm]')
    value += (load >> 6) & 31
    return {'file_offset': start, 'bytes': data[start:at+4].hex(), 'bank_offset': value}


def program_names(data):
    """Follow the actual consumer: row[0] is a name pointer, row[4] is its ID."""
    require(half(data,0x1bb7c) == 0x4860, 'Program-table literal load differs')
    pointer_at = ((0x1bb7c+4)&~3) + (half(data,0x1bb7c)&0xff)*4
    table = word(data,pointer_at)-BASE
    require(table == PROGRAM_TABLE, 'Program-table start differs')
    for at, opcode in ((0x1a37e,0x6820),(0x1a396,0x6820),
                       (0x1a3a2,0x6860),(0x1a3a6,0x3408)):
        require(half(data,at) == opcode, 'Program-name consumer layout differs')
    require(thumb_bl(data,0x1bb80) == 0x1a378 and half(data,0x1bb86) == 0x0001
            and thumb_bl(data,0x1bb8a) == 0x44340, 'Name-to-program getter chain differs')
    result = {}
    for index in range(33):
        pointer, pid = struct.unpack_from('<II',data,table+8*index)
        at = pointer-BASE
        require(0 <= at < len(data), 'Program name pointer escapes image')
        name = data[at:data.index(0,at)].decode('ascii')
        if name == 'NULL':
            return result
        require(pid not in result and pid < 32, 'Invalid or duplicate program ID')
        result[pid] = dict(name=name,name_file_offset=at,row_offset=table+8*index)
    raise ValueError('Program-name table sentinel missing')


def compare_program_container(data, av):
    require(len(data) == 336664 and hashlib.sha256(data).hexdigest() == SA_SHA256,
            'Unreviewed SA program container')
    require(data[:8] == b'SA2U_APP', 'Unexpected SA header')
    names = program_names(av)
    entries = []
    for (pid, *_, av_name), expected_header in zip(STAGES, SA_HEADERS):
        at = word(data, 0x10+4*pid)
        end = word(data, 0x10+4*(pid+1))
        require(at+12 < end <= len(data), 'SA member boundary differs')
        header = data[at:at+12].rstrip(b'\0').decode('ascii')
        require(header == expected_header, 'SA program header differs')
        require(names[pid]['name'] == av_name, 'SA comparison disagrees with AV consumer')
        entries.append(dict(program_id=pid, av_name=av_name, sa_file_offset=at,
                            sa_header=header, sa_payload_offset=at+12,
                            member_end=end, payload_bytes=end-at-12))
    return dict(source='evidence/w300/sa.bin', sha256=SA_SHA256,
                getter_index_expression='(base + uint32(base + 0x10 + 4*program_id) + 0xC) & 0x0FFFFFFF',
                static_name_index_alignment_verified=True,
                runtime_container_observed=False, entries=entries,
                finding='Correct (name pointer, ID) AV rows agree with raw SA indices; no index shift is needed.')


def engine_submission_contract(data):
    calls = ((0xab476,0x19e44),(0x19e46,0x19f92),(0x1a030,0x44298),
             (0x1a03a,0x442d8),(0x1a044,0x442d8),(0x1a04e,0x442d8),
             (0x1a056,0x442d8),(0x1a078,0x44286))
    for call, target in calls:
        require(thumb_bl(data,call) == target, 'Engine submission call differs')
    require(word(data,0xacb70) == 0x79500000 and word(data,0xacb74) == 0x79500040,
            'Engine MMIO register bases differ')
    for at, expected in (
            (0x1a024,'e06801210001000949074018'),
            (0x1a034,'206901680020'), (0x1a03e,'206941680120'),
            (0x1a048,'206981680220'), (0x1a052,'00210320'),
            (0xaca6e,'404a9168890f890780008008084390607047'),
            (0xacb16,'174a8000801801607047'),
            (0xab3be,'0001000984b00c000090')):
        require(data[at:at+len(expected)//2].hex() == expected,
                f'Engine parameter or register instruction differs at {at:#x}')
    return dict(dispatcher=0x19f92, calls=[dict(call=a,target=b) for a,b in calls],
                program_register=0x79500008,
                parameter_registers=[0x79500040,0x79500044,0x79500048],
                fourth_parameter_register=0x7950004c, fourth_parameter_value=0,
                start_register=0x79500004, start_bit=0,
                program_address_expression='(descriptor.program & 0x0FFFFFFF) + 0x20000000',
                cnr_wrapper_explicit_input_word=0,
                cnr_input_word_0='low-28-bit address of the dispatcher parameter block',
                remaining_input_word_meaning_verified=False,
                sa_isa_verified=False, dsp_pixel_format_verified=False,
                finding='ARM submits a program address to a hardware engine; this path does not parse SA member contents.')


def processing_contract(data):
    """Verify the narrow host-side CNR skip; do not infer DSP pixel semantics."""
    require(word(data,0xab48c) == 0x203b2b60 and word(data,0xab490) == 0x203b2bc0,
            'CNR/RGB parameter descriptors differ')
    for at in (0x2c3f2,0x2c402,0x2c45e,0x2c46c):
        require(half(data,at-2) == 0x2003 and thumb_bl(data,at) == 0x6c9b6,
                'CNR/RGB buffer selection differs')
    for at in (0x2c3fa,0x2c40c,0x2c466,0x2c476):
        require(half(data,at-2) == 0x4030 and half(data,at) == 0x6028,
                'CNR/RGB descriptor address store differs')
    require(word(data,0x2c4b0) == 0x0ffffff8, 'Buffer address mask differs')
    require(data[0x6c94a:0x6c950].hex() == '052902a308d2'
            and half(data,0x6c962) == 0xbdf8, 'Buffer-state no-change branch differs')
    require(data[0x2c4de:0x2c4f8].hex() ==
            '0120c0430422009006206946d6f7c3fc1949174809688847f8bd',
            'Zero-gate completion path differs')
    for at in (0x1d04d8,0x1d04fc,0x1d0520):
        require(half(data,at+4) == 5, 'Conversion/CNR buffer-state argument differs')
    return dict(cnr_descriptor_va=0xa03b2b60, rgb_descriptor_va=0xa03b2bc0,
                address_expression='(selected_base + buffer_offset(3)) & 0x0FFFFFF8',
                buffer_offset_getter=0x6c9b6, buffer_state_setter=0x6c93c,
                sequence_buffer_argument=5, argument_5_changes_buffer_state=False,
                cnr_zero_gate_target=0x2c4de, completion_event=6,
                completion_payload=0xfffffffe,
                finding='CNR skip posts completion without an explicit image copy or buffer swap in this handler.',
                dsp_pixel_contract_verified=False,
                limitation='Shared descriptor address and host completion do not prove that RGB accepts unfiltered input.')


def raw_skip_contract(data):
    require(data[0x2c2c2:0x2c2c8].hex() == '012078610ae1', 'RAW bypass flag set differs')
    for at in (0x2c2b4,0x2c35c):
        require(data[at:at+4].hex() == '00207861', 'Enabled RAW flag clear differs')
    require(word(data,0x2c4ac) == 0x2032ccd8, 'RAW bypass flag base differs')
    events = []
    for row, event, handler, flag_at, call in (
            (0x20cd08,0x12b,0x2bf3c,0x2bf52,0x2bf5a),
            (0x20cd18,0x12a,0x2bf9a,0x2bfdc,0x2bfe4)):
        require(word(data,row) == event and word(data,row+4) == BASE+handler+1,
                'RAW completion event registration differs')
        require(half(data,flag_at) in (0x6948,0x6960)
                and data[flag_at+2:flag_at+6].hex() == '002802d1'
                and thumb_bl(data,call) == 0x6c93c,
                'RAW completion bypass condition differs')
        events.append(dict(event=event, handler=handler, flag_read=flag_at,
                           buffer_promotion_call=call))
    require(data[0x6c95e:0x6c964].hex() == '60682060f8bd', 'Pending-buffer promotion differs')
    sequences = []
    for at, stage, final_event in ((0x1d0358,5,0x12a),(0x1d04b4,6,0x12b)):
        records = [struct.unpack_from('<6H',data,at+12*i) for i in range(3)]
        require(records[0][:3] == (0x130,stage,3) and records[1][:3] == (0x131,stage,3)
                and records[2][0] == final_event and records[2][2] == 0,
                'RAW completion sequence differs')
        sequences.append(dict(file_offset=at,records=[list(r) for r in records]))
    return dict(bypass_flag_va=0x2032ccec, flag_set=0x2c2c2,
                input_buffer_argument=3, output_buffer_argument=4,
                current_state_va=0x203315b4, pending_state_va=0x203315b8,
                completion_events=events, sequences=sequences,
                native_skip_preserves_input_buffer_selection=True,
                all_nr_removed_verified=False,
                limitation='Host buffer handling is verified; DSP internals and every photographic mode are not.')


def backup_dirty_contract(data):
    """Reuse the retained ELF section/relocation method on pinned W300 bytes."""
    require(hashlib.sha256(data).hexdigest() == BACKUP_CORE_SHA256,
            'Unreviewed W300 backup library')
    require(data[:6] == b'\x7fELF\x01\x01', 'Expected little-endian ELF32')
    header = struct.unpack_from('<HHIIIIIHHHHHH',data,16)
    sections = [struct.unpack_from('<10I',data,header[5]+i*header[10]) for i in range(header[11])]

    def file_offset(va):
        section = next(s for s in sections if s[1] != 8 and s[3] <= va < s[3]+s[5])
        return section[4]+va-section[3]

    relocations = {}
    for section in (s for s in sections if s[1] == 9):
        symbols = sections[section[6]]
        for at in range(section[4],section[4]+section[5],section[9]):
            va, info = struct.unpack_from('<II',data,at)
            symbol_value = word(data,symbols[4]+(info>>8)*symbols[9]+4)
            relocations[va] = (info&255,symbol_value)
    methods = []
    for name, va, result, slots in (
            ('markDirty',0x7a9c,0,(0x1653c,0x16588)),
            ('eraseDirty',0x7ab0,0,(0x16540,0x1658c)),
            ('isDirty',0x7ac4,1,(0x16544,0x16590))):
        at = file_offset(va)
        require(struct.unpack_from('<5I',data,at) ==
                (0xe1a0c00d,0xe92dd800,0xe3a00000+result,0xe24cb004,0xe89da800),
                f'{name} is no longer a constant-return stub')
        for slot in slots:
            require(relocations[slot] == (2,va) and word(data,file_offset(slot)) == 0,
                    f'{name} vtable relocation differs')
        methods.append(dict(name=name, elf_va=va, return_value=result, vtable_slots=list(slots)))
    at = file_offset(0x9128)
    require(data[at:at+16].hex() == '28c09ce53cff2fe1ff0000e2010050e3',
            'Flush dirty check differs')
    return dict(source='evidence/w300/baseline_files/usr/lib/libBackupCore.so',
                sha256=BACKUP_CORE_SHA256, methods=methods,
                flush_dirty_check_va=0x9128, flush_file_write_call_va=0x9160,
                explicit_dirty_mark_required=False, persistence_qualified=False,
                scope='Both reviewed shadow-accessor vtables; whole-category flush has other prerequisites and side effects.')


def native_parameter_mapping(data):
    """Describe reviewed AV shared-memory fields, never a qualified USB packet."""
    rows = []
    for at, segment, bank, pointer, default_base, offset in (
            (0x20bd60,0x22,0x3000,0x202e02ec,0x1e01ec,0x35),
            (0x20bd74,0x23,0x3100,0x202e03f0,0x1e02f0,0x45)):
        row = struct.unpack_from('<HBBIIIHH',data,at)
        require(row == (0x51,segment,3,0,bank,pointer,0x100,0),
                'Native parameter row differs')
        require(word(data,pointer-BASE) == BASE+default_base,
                'Native parameter default pointer differs')
        rows.append(dict(row_offset=at, page=0x51, segment=segment,
                         bank_base=bank, length=0x100, cnr_bank_offset=bank+offset,
                         cnr_segmented_address=(segment<<8)+offset,
                         compiled_default=data[default_base+offset]))
    require(word(data,0x22564) == 0x2032b9a0 and word(data,0x22208) == 0x2032b9a0,
            'Native parameter table pointer differs')
    for at, op in ((0x22224,0x7a48),(0x2222a,0x8948),(0x22232,0x884e),
                   (0x2224a,0x7909),(0x222f8,0x88cb),(0x22308,0x310c)):
        require(half(data,at) == op, f'Native parameter field differs at {at:#x}')
    require(data[0x2231a:0x22324].hex() == '35f104ee0122627035e0',
            'Native RAM copy and notification flag differ')
    return dict(handler=0x2220c, table_va=0x2032b9a0, rows=rows,
                body_scope='AV shared-memory adjustment body; outer USB transport unqualified',
                fields={'operation_u16':2,'flush_category_u8':4,'length_u16':6,
                        'page_u8':9,'segmented_address_u16':10,'write_payload':12},
                operations={'1':'read','2':'RAM copy','3':'RAM copy',
                            '4':'flush IPCM 0x1002/subcommand 1',
                            '5':'erase IPCM 0x1002/subcommand 3; NOT reload'},
                ram_copy_file_offset=0x2231a, ram_copy_target=0x157f24,
                ram_write_marks_local_notification=True,
                persistence_qualified=False, usb_write_qualified=False,
                limitation='Outer transport, shared-shadow binding, reload and interrupted-save recovery need a complete chain.')


def analyze(data, sa=None, backup_core=None):
    digest = hashlib.sha256(data).hexdigest()
    require(len(data) == AV_SIZE and digest == AV_SHA256, 'Unreviewed W300 AV image')
    require(data[0x1ef548:0x1ef550] == b'DSC-W300', 'W300 model anchor differs')
    require(word(data, 0x2c4b8) == 0x2032b584, 'Selected bank pointer differs')
    row = struct.unpack_from('<HBBIIIHH', data, 0x20bd60)
    require(row == (0x51,0x22,3,0,0x3000,0x202e02ec,0x100,0), 'Asys row differs')
    require(word(data, 0x1e02ec) == 0x202e01ec, 'Default block pointer differs')
    require(data[0x2cd14:0x2cd16] == bytes.fromhex('01a8'), 'Old anchor differs')
    require(data[0x2a8e2:0x2a8f4] == bytes.fromhex(
        '142803d0fef71eff182801d1012010bd0020'), 'Gate selector differs')
    names = program_names(data)
    require(thumb_bl(data,0x30a08) == 0x29726 and half(data,0x30a0c) == 0x0001
            and half(data,0x30a0e) == 0xa0bc
            and data.startswith(b'SET_AE_MODE_DSC          :[%02xh]\n\0',0x30d00),
            'AE_MODE_DSC diagnostic binding differs')
    require(word(data,0x298a8) == 0x20370698
            and data[0x29726:0x2972c].hex() == '6048c07b7047', 'AE mode getter differs')
    stages = []
    for pid, wrapper, call, normal, alternate, expected_name in STAGES:
        string_at = names[pid]['name_file_offset']
        name = names[pid]['name']
        require(name == expected_name, 'Program name table differs')
        require(half(data, wrapper+12) == 0x2100+pid, 'Wrapper program ID differs')
        require(thumb_bl(data, wrapper+16) == 0x44340, 'Program getter differs')
        require(thumb_bl(data, wrapper+30) == 0xab45c, 'Shared runner differs')
        require(thumb_bl(data, call) == wrapper, 'Dispatch call differs')
        normal_gate = gate_offset(data,normal)
        test = normal + len(bytes.fromhex(normal_gate['bytes']))
        require(half(data,test) == 0x2800, 'Expected zero gate comparison')
        branch = half(data,test+2)
        require(branch & 0xff00 == 0xd000, 'Expected BEQ after zero gate')
        displacement = branch & 0xff
        if displacement & 0x80:
            displacement -= 0x100
        zero_target = test+6+2*displacement
        stages.append(dict(program_id=pid, name=name, name_file_offset=string_at,
                           wrapper=wrapper, dispatch_call=call,
                           normal_gate=normal_gate, zero_gate_target=zero_target,
                           alternate_gate=gate_offset(data,alternate)))
    require(word(data,0x20cd38) == 0x130 and word(data,0x20cd3c) == BASE+0x2c1d1,
            'Post-task event handler differs')
    require(word(data,0x139f4) == 0xffffeffa and data[0x13848:0x1384c].hex() == '02027a80'
            and word(data,0x3664c) == 0x1009 and thumb_bl(data,0x36582) == 0x363a4,
            'NR selection event differs')
    sequences = []
    for at, stage in ((0x1d0358,5),(0x1d04b4,6),(0x1d04d8,7),(0x1d04fc,8),(0x1d0520,9)):
        record = struct.unpack_from('<6H',data,at)
        require(record[0:2] == (0x130,stage), 'Post sequence differs')
        sequences.append(dict(file_offset=at, halfwords=list(record)))
    result = {
        'schema': 'w300-nr-static-evidence-v2', 'source': 'evidence/w300/av.bin',
        'bytes': len(data), 'sha256': digest, 'address_convention': 'file offsets unless VA stated',
        'firmware_executed': False, 'hardware_validated': False,
        'nr_disable_verified': False, 'live_write_qualified': False,
        'dispatcher': 0x2c1d0, 'program_table': PROGRAM_TABLE,
        'program_table_layout': {'row':'uint32 name_pointer; uint32 program_id',
                                 'consumer':0x1a378,'consumer_id_load':0x1a3a2,
                                 'table_literal':0x1bd00,'sentinel':'NULL'},
        'shared_program_getter': 0x44340, 'shared_runner': 0xab45c,
        'post_task': {'event':0x130, 'handler_table_entry':0x20cd38,
                      'task':'tsk_camc_post', 'task_entry':0x13610,
                      'selection_event':0x1009,'selection_handler':0x1382e,
                      'selection_branch':0x13948,'event_producer':0x36578,
                      'sequences':sequences, 'still_only_verified':False},
        'engine_submission': engine_submission_contract(data),
        'selected_bank_pointer_va': 0x2032b584,
        'alternate_gate_selector': {'function':0x2a8dc, 'source_getter':0x29726,
                                    'values':[0x14,0x18], 'state_name':'AE_MODE_DSC',
                                    'state_byte_va':0x203706a7, 'diagnostic_call':0x30a08,
                                    'user_visible_mode_meaning_verified':False},
        'cnr_skip_contract': processing_contract(data),
        'raw_skip_contract': raw_skip_contract(data),
        'native_parameters': native_parameter_mapping(data),
        'asys_row': {'file_offset':0x20bd60, 'page':row[0], 'segment':row[1],
                     'bank_offset':row[4], 'length':row[6],
                     'default_3035_3036':list(data[0x1e01ec+0x35:0x1e01ec+0x37])},
        'stages': stages,
        'rejected_claim': {
            'claimed_dispatch':0x2cca0, 'claimed_bypass':0x2cd14,
            'actual_bypass_anchor_bytes':'01a8', 'actual_instruction':'add r0,sp,#4',
            'candidate_3035':'normal gate for ID 6 NR32_CNR_NR',
            'candidate_3036':'normal gate for ID 7 NR32_CNR_2RGB',
            'conclusion':'The two-byte candidate leaves other NR-labelled gates unchanged; full NR off is unproven.'},
        'superseded_interpretation': 'Schema v1 started the table four bytes late and reversed row fields; '
                                    'its fisheye identification and AV/SA index mismatch were incorrect.',
        'unresolved': [
            'Prove still-capture reachability and user-visible meaning of AE_MODE_DSC states 0x14/0x18.',
            'Prove RAWNR and CNR DSP input/output contracts; preserve required conversion stages.',
            'Bind AV native parameters to W300 plugin selection, shared shadow, service exit and recovery before a hardware write.',
            'Verify actual processing and persistence on the camera independently of file bytes.'],
    }
    if sa is not None:
        result['program_container_comparison'] = compare_program_container(sa,data)
    if backup_core is not None:
        result['backup_dirty_contract'] = backup_dirty_contract(backup_core)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=AV)
    parser.add_argument('--sa', type=Path, default=SA)
    parser.add_argument('--backup-core', type=Path, default=BACKUP_CORE)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(analyze(args.file.read_bytes(),args.sa.read_bytes(),
                                 args.backup_core.read_bytes()), indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, str(error)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
