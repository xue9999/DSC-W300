"""Bounded static G3 page61/segment0E pointer initialization; no target execution."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'build/w300/re-tools/site'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
data=(ROOT/'evidence/extracted_g3/sections/09_av.bin').read_bytes()
digest=hashlib.sha256(data).hexdigest()
assert digest=='f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb'
BASE=0x20100000
def word(at):return struct.unpack_from('<I',data,at)[0]
def thumb_bl(at):
    a,b=struct.unpack_from('<HH',data,at)
    assert a&0xf800==0xf000 and b&0xf800==0xf800
    disp=((a&2047)<<12)|((b&2047)<<1)
    if disp&0x400000:disp-=0x800000
    return at+4+disp
row=struct.unpack_from('<HBBIIIHH',data,0x1e4ab4)
assert row==(0x61,0x0e,3,0,0x1a00,0x202bb2e0,256,0)
assert word(0xedd4)==0x203043fc and word(0xedc8)==0x200fd880 and word(0xedd0)==0x20303fcc
assert word(0xedcc)==0xaaaaaaaa
assert thumb_bl(0x4216)==0xeab0
# Explicit Thumb byte-offset switch tables, not decoded as instructions.
page_table=data[0xeb48:0xeb4f]
segment_table=data[0xec80:0xec91]
assert 0xeb4a+2*page_table[0x61&15]==0xec72
assert 0xec82+2*segment_table[0x0e]==0xed34
assert data[0xed34:0xed3e]==bytes.fromhex('21680d22520289184160')
default_ptr=word(row[5]-BASE)
assert default_ptr==0x202bb1e0 and 0<=default_ptr-BASE<len(data)-row[6]
assert word(0x22908)==0x1002
ranges=[('initializer-call',0x4216,0x421a),('bank-select-and-row-dispatch',0xeab0,0xeb48),
        ('segment-switch',0xec72,0xec80),('segment0E-assignment',0xed34,0xed40),
        ('next-table-row',0xed70,0xed80),('bank-validation',0xed80,0xedb2),
        ('default-control-dispatch',0xe658,0xe67e),('single-page-default-copy',0xe6be,0xe704),
        ('group-default-copy',0xe704,0xe73c),('separate-op4-op5-request',0x225e4,0x22626),
        ('channel1002-response-callback',0xe242,0xe27c),('outgoing-ipc',0xe1f0,0xe234)]
lines=['G3 static analysis. VA=file+0x20100000. Inline switch tables are retained as data in evidence.json; firmware is never executed.']
decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
for label,start,end in ranges:
    lines.append(f'\n{label} file[{start:#x}:{end:#x}]')
    covered=start
    for ins in decoder.disasm(data[start:end],BASE+start):
        at=ins.address-BASE;covered=at+len(ins.bytes);note=''
        if ins.mnemonic=='ldr' and 'pc,' in ins.op_str:
            delta=int(ins.op_str.split('#')[1].rstrip(']'),0);literal=((at+4)&~3)+delta
            note=f' ; literal file+{literal:#x}={word(literal):#x}'
        lines.append(f'file+{at:#010x} VA={ins.address:#010x} {ins.bytes.hex():12s} {ins.mnemonic:9s} {ins.op_str}{note}')
    assert covered==end,(label,hex(covered),hex(end))
result={'source':'evidence/extracted_g3/sections/09_av.bin','sha256':digest,
        'row':{'file_offset':'0x1e4ab4','page':'0x61','segment':'0x0e','type':3,'initial_pointer':0,'size':256},
        'page_dispatch':{'table_file':'0xeb48','bytes':page_table.hex(),'index':1,'target_file':'0xec72'},
        'segment_dispatch':{'table_file':'0xec80','bytes':segment_table.hex(),'index':14,'target_file':'0xed34'},
        'bank_descriptor':'0x200fd880','bank_pointer_slot':'0x20303fcc',
        'primary_descriptor_offset':'0x10','fallback_descriptor_offset':'0x28','pointer_alias_or_mask':'0x80000000',
        'primary_check':{'offset':'0xe0','value':'0xaaaaaaaa'},
        'page_pointer_expression':'selected_bank_pointer + 0x1a00',
        'single_row_default_pointer_table':'0x202bb2e0','single_row_default_data_pointer':hex(default_ptr),
        'single_row_default_length':256,'default_bytes_exported':False,
        'op4_op5_channel':'0x1002','op4_outgoing_first_halfword':1,'op5_outgoing_first_halfword':3,
        'persistence_semantics_from_av_alone':'not established; separate request/reply path located',
        'runtime_bank_pointer_numeric_value':'not available in static image',
        'ranges':[{'label':l,'file_start':hex(a),'file_end':hex(b)}for l,a,b in ranges]}
(HERE/'page-init.asm.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(HERE/'evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ok':True,'ranges':len(ranges),'page_pointer':'selected bank + 0x1A00','runtime_base_known':False},indent=2))
