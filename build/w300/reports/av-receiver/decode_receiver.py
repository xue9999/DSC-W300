"""Bounded static G3 receiver decoding; no firmware execution or USB API."""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'build/w300/re-tools/site'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_THUMB,CS_MODE_LITTLE_ENDIAN
data=(ROOT/'evidence/extracted_g3/sections/09_av.bin').read_bytes()
assert hashlib.sha256(data).hexdigest()=='f2554be5181f5765623b0771e6aef6ff99c8483980a1192c39db85c744bda4fb'
def word(at):return struct.unpack_from('<I',data,at)[0]
BASE=word(0x20)-0x3c
assert BASE==0x20100000
assert data[:4]==bytes.fromhex('18f09fe5')
assert word(0xe5b0)==BASE+0x162078 and data[0x162078:0x162082]==b'tsk_senser'
assert word(0xe58c)==BASE+0xe27d
assert word(0xe590)==0x1001
assert data[0x57780:0x57782]==bytes.fromhex('52a1')
assert ((0x57780+4)&~3)+0x148==0x578cc
source_name=b'src\\senser\\sys_senser.c'
assert data[0x578cc:0x578cc+len(source_name)]==source_name
assert data[0x1c7ee8:0x1c7eee]==b'DSC-G3'
start=0x150+word(0x150);end=0x150+word(0x154)
assert (start,end)==(0x1e3850,0x1e3900)
regions=[dict(zip(['source','destination','size','operation'],struct.unpack_from('<4I',data,at)))
         for at in range(start,end,16)]
assert regions[0]=={'source':0x202e3a78,'destination':0x20303a78,'size':0x1365c,'operation':BASE+0x158}
assert all(r['operation'] in [BASE+0x158,BASE+0x180] for r in regions)
table_va=word(0x225b0)
assert table_va==0x203043fc
region=next(r for r in regions if r['operation']==BASE+0x158 and r['destination']<=table_va<r['destination']+r['size'])
table_file=region['source']-BASE+table_va-region['destination']
assert table_file==0x1e43fc
# Only table structure and the single requested reference key; no calibration bytes.
rows=[]
for index in range(256):
    at=table_file+20*index
    page,segment,kind,p4,p8,p12,length,tail=struct.unpack_from('<HBBIIIHH',data,at)
    if page==0xff:break
    if page==0x61 and segment==0x0e:
        rows.append({'index':index,'file_offset':hex(at),'page_key':hex(page),'segment':hex(segment),
                     'type':kind,'initial_runtime_data_pointer':hex(p4),'length':length})
else:raise AssertionError('Table sentinel missing')
assert index==107 and len(rows)==1 and rows[0]['initial_runtime_data_pointer']=='0x0'
# Confirm the direct mutation callee, rather than infer memcpy from its argument convention.
call_decoder=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_LITTLE_ENDIAN)
copy_call=list(call_decoder.disasm(data[0x226c2:0x226c6],BASE+0x226c2))
assert len(copy_call)==1 and copy_call[0].mnemonic=='blx' and copy_call[0].op_str=='#0x20257d98'
assert data[0x157da8:0x157dac]==bytes.fromhex('0130d1e4')  # ldrb r3,[r1],#1
assert data[0x157db8:0x157dbc]==bytes.fromhex('0130c0e4')  # strb r3,[r0],#1
assert data[0x157e58:0x157e60]==bytes.fromhex('1850b1281850a028')  # ldmhs r1! / stmhs r0!
assert data[0x157e9c:0x157ea0]==bytes.fromhex('0120d144')  # ldrbmi r2,[r1],#1
assert data[0x157ea8:0x157eac]==bytes.fromhex('0120c044')  # strbmi r2,[r0],#1
assert data[0x157eb4:0x157eb8]==bytes.fromhex('1eff2fe1')  # bx lr
ranges=[('scatter-loop',0x120,0x150,False),('copy-region',0x158,0x180,False),
        ('ipcm-to-task-callback',0xe27c,0xe2ba,True),('senser-task',0xe2ba,0xe580,True),
        ('page-segment-lookup',0x21d6c,0x21dae,True),('remaining-length',0x21e10,0x21e5c,True),
        ('page-alias',0x21e5c,0x21e70,True),('adjust-dispatch',0x221e0,0x22596,True),
        ('page-access-handler',0x225b4,0x2279c,True),('source-name-reference',0x57772,0x5779a,True),
        ('direct-data-copy-callee',0x157d98,0x157eb8,False)]
lines=['G3 only. VA uses the byte-confirmed base0x20100000; file offsets are shown separately. No firmware execution.']
for label,a,b,is_thumb in ranges:
    decoder=Cs(CS_ARCH_ARM,(CS_MODE_THUMB if is_thumb else CS_MODE_ARM)|CS_MODE_LITTLE_ENDIAN)
    lines.append(f'\n{label}: file[{a:#x}:{b:#x}], VA={BASE+a:#x}, mode={"Thumb" if is_thumb else "ARM"}')
    covered=a
    for ins in decoder.disasm(data[a:b],BASE+a):
        file_at=ins.address-BASE;covered=file_at+len(ins.bytes);note=''
        if is_thumb and ins.mnemonic=='ldr' and 'pc,' in ins.op_str:
            displacement=int(ins.op_str.split('#')[1].rstrip(']'),0)
            literal=((file_at+4)&~3)+displacement
            note=f' ; literal file+{literal:#x}={word(literal):#x}'
        lines.append(f'file+{file_at:#010x} VA={ins.address:#010x} {ins.bytes.hex():12s} {ins.mnemonic:9s} {ins.op_str}{note}')
    assert covered==b,(label,hex(covered),hex(b))
linux=(ROOT/'evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so').read_bytes()
assert hashlib.sha256(linux).hexdigest()=='401bc78bc84bd175968513a387b8951626ceb48a345eed134b998d3630103270'
connect=struct.unpack_from('<3I',linux,0x129a0)
assert connect==(0,1,0x1001)
result={'base':hex(BASE),'base_checks':['ARM vector literal','tsk_senser literal reference','scatter copy source/destination/function pointers'],
        'scatter_table_file':hex(start),'scatter_regions':[{k:hex(v) for k,v in r.items()} for r in regions],
        'initial_page_table_va':hex(table_va),'initial_page_table_file':hex(table_file),'page_table_rows_before_sentinel':index,
        'single_reference_row':rows,'linux_ipcm_connect_words':list(connect),
        'direct_data_copy':{'call_file':'0x226c2','callee_va':'0x20257d98','callee_file':'0x157d98',
                            'callee_end_file':'0x157eb8','source_register':'r1','destination_register':'r0',
                            'length_register':'r2','basis':'Decoded byte and aligned/unaligned word load/store paths; verified final BX LR'},
        'receiver_channel_literal':hex(word(0xe590)), 'ranges':[{'label':l,'file_start':hex(a),'file_end':hex(b),'thumb':t}for l,a,b,t in ranges],
        'scope':'G3 static receiver and one table reference; no W300 mapping, no runtime pointer assumed, no device payload generated'}
(HERE/'receiver.asm.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(HERE/'receiver-evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ok':True,'ranges':len(ranges),'g3_base':hex(BASE),'initial_table_pointer_for_reference_row':rows[0]['initial_runtime_data_pointer']},indent=2))
