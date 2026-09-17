"""Narrow, static ELF symbol/relocation inspection. Never loads target code."""
from pathlib import Path
import hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'build/w300/re-tools/site'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_MEM,ARM_REG_PC
inventory=json.loads((ROOT/'build/w300/reports/retained-service-inventory.json').read_text())
item=next(i for i in inventory if i['path'].endswith('/libBackupCore.so'))
b=(ROOT/item['path']).read_bytes(); assert hashlib.sha256(b).hexdigest()==item['sha256']
h=struct.unpack_from('<HHIIIIIHHHHHH',b,16)
sec=[struct.unpack_from('<IIIIIIIIII',b,h[5]+i*h[10])for i in range(h[11])]
ns=sec[h[12]]; names=b[ns[4]:ns[4]+ns[5]]
named={names[z[0]:].split(b'\0')[0].decode():z for z in sec}
def off(va):return next((z[4]+va-z[3] for z in sec if z[1]!=8 and z[3]<=va<z[3]+z[5]),None)
def word(va):return struct.unpack_from('<I',b,off(va))[0]
rels={}
for r in [z for z in sec if z[1]==9]:
 sy=sec[r[6]]; st=sec[sy[6]]; strings=b[st[4]:st[4]+st[5]]
 for at in range(r[4],r[4]+r[5],r[9]):
  va,info=struct.unpack_from('<II',b,at); ss=struct.unpack_from('<IIIBBH',b,sy[4]+(info>>8)*sy[9]); name=strings[ss[0]:].split(b'\0')[0].decode()
  rels[va]=(info&255,name,ss[1])
plt=named['.plt']; rel=named['.rel.plt']
plt_names={plt[3]+20+i*12:rels[struct.unpack_from('<I',b,at)[0]][1] for i,at in enumerate(range(rel[4],rel[4]+rel[5],8))}
# This exact ELF and its PLT layout were independently validated in the preceding report.
assert item['sha256']=='56aa2595c4747b6aadc1c0c3bb7a438b15086951121024a8649254cdec61fd4b'
symbols={int(s['value'],16):s['name'] for s in item['symbols'] if s.get('file_offset')}
decoder=Cs(CS_ARCH_ARM,CS_MODE_ARM|CS_MODE_LITTLE_ENDIAN);decoder.detail=True
lines=['Static libBackupCore.so SHA256 '+item['sha256']]
if '--metadata' in sys.argv:
 for name in ['.init','.ctors','.init_array','.fini_array','.data','.bss']:
  z=named.get(name)
  if z:lines.append(name+' '+repr([hex(v)for v in z]))
  if z and name in ['.ctors','.init_array']:
   for va in range(z[3],z[3]+z[5],4):lines.append('  %x=%x relocation=%s'%(va,word(va),rels.get(va)))
 for name in ['_init','_ZN13CategoryTableC1Ev','_Z14backupUtilInitv']:
  s=next(s for s in item['symbols'] if s['name']==name)
  lines.append(name+' '+repr(s))
else:
 args=sys.argv[1:] or ['6728:67bc','6ccc:76e8','6c20:6c4c','6ca0:6ccc']
 for arg in args:
  start,end=(int(n,16)for n in arg.split(':')); at=off(start)
  assert at is not None and end>start and end-start<0x2000
  ins=list(decoder.disasm(b[at:at+end-start],start)); literal=set()
  for i in ins:
   for op in i.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC and not op.mem.index:
     literal.add(i.address+8+op.mem.disp)
  lines.append('\nrange %x:%x'%(start,end))
  for va in range(start,end,4):
   if va in literal:
    lines.append('%08x .word %08x ; PC-relative literal data'%(va,word(va)));continue
   ii=list(decoder.disasm(b[off(va):off(va)+4],va));assert len(ii)==1,hex(va)
   i=ii[0]
   annotation=''
   for op in i.operands:
    if op.type==ARM_OP_MEM and op.mem.base==ARM_REG_PC and not op.mem.index:
     va=i.address+8+op.mem.disp;annotation+=' ; literal %x=%x'%(va,word(va))
   if i.mnemonic in ['b','bl','blx'] and i.op_str.startswith('#0x'):
    target=int(i.op_str[1:],16);annotation+=' ; '+plt_names.get(target,symbols.get(target,''))
   lines.append('%08x %-10s %-8s %s%s'%(i.address,i.bytes.hex(),i.mnemonic,i.op_str,annotation))
if not sys.argv[1:]:
 # The .ctors target is the unnamed function, not a guessed scan start.
 assert word(0x16050)==0xffffffff and word(0x16054)==0x6ccc and word(0x16058)==0
 assert rels[0x16054][0]==23
 # PIC base established by the initializer's PC-relative load and ADD.
 pic=0x6cdc+8+word(0x760c)
 assert pic==0x16144
 dev=pic+word(0x7610)-0x100000000
 assert b[off(dev):off(dev)+9]==b'/dev/mem\0'
 assert word(0x7648)==0x200fd890 and word(0x76b8)==0x200fd8a8
 assert word(0x764c)==0x828 and word(0x76bc)==0x7f0
 assert pic+word(0x76d8)==0x16908 and pic+word(0x76dc)==0x16498
 for table,expected in [(0x165e0,b'/boot/factory/Areg.bin\0'),(0x16644,b'/boot/factory/Areg2.bak\0')]:
  slot=table+5*4;va=word(slot)
  assert rels[slot][0]==23 and b[off(va):off(va)+len(expected)]==expected
 # Primary read -> PIC temporary -> saved temporary index -> final array[5].
 critical={0x6f28:0xe5933000,0x6f30:0xe78a3001,0x6f34:0xe50b1044,
           0x74f8:0xe51b1044,0x7500:0xe79a3001,0x7508:0xe5823014,
           0x73c0:0xe5933000,0x73cc:0xe78a3009,
           0x754c:0xe79a3009,0x7550:0xe5823014,0x7608:0xe89daff0}
 for va,expected in critical.items():assert word(va)==expected,(hex(va),hex(word(va)))
 # Cross-model facts are deliberately excluded: this links retained G3 components only.
 facts={'scope':'G3 static initialization only','library':item['path'],'sha256':item['sha256'],
        'constructor_pointer_va':'0x16054','constructor_code_va':'0x6ccc','constructor_code_end':'0x760c',
        'constructor_literal_pool_end':'0x76e8','pic_base':'0x16144','mapped_device':'/dev/mem',
        'primary_descriptor_word':'0x200fd890','spare_descriptor_word':'0x200fd8a8',
        'primary_temporary':hex(pic+word(0x764c)),'spare_temporary':hex(pic+word(0x76bc)),
        'primary_array':'0x16908','spare_array':'0x16498','array_entry_offset':'0x14','category':5,
        'main_file':'/boot/factory/Areg.bin','spare_file':'/boot/factory/Areg2.bak',
        'file_mapping_source':'../av-page-init/linux-persistence/linux-backup-tables.txt',
        'av_selected_bank_source':'../av-page-init/evidence.json','av_page':'0x61','av_segment':'0x0e',
        'av_page_bank_offset':'0x1a00','runtime_numeric_bank_base_known':False,
        'w300_mapping_qualified':False}
 (OUT/'evidence.json').write_text(json.dumps(facts,indent=2)+'\n',encoding='utf-8')
 (OUT/'bank-map.asm.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({'ok':True,'category':5,'main_file':facts['main_file'],'w300_qualified':False}))
else:
 print('\n'.join(lines))
