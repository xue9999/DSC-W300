"""Reproduce bounded G3 event dispatch evidence. Firmware remains data; no USB calls."""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf,cstr
u=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so')
p=Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/PExtSenser.so')
checks=[]
def w(e,va,value):
 assert e.word(va)==value,(hex(va),hex(e.word(va)),hex(value))
 checks.append({'file':e.relative,'va':hex(va),'word':hex(value)})
def rel(e,va,kind,target=None):
 rs=[r for r in e.reloc if r['offset']==va and r['type']==kind]
 assert len(rs)==1
 if target is not None:assert rs[0]['symbol']==target
 return rs[0]
def ptr(e,va,target):w(e,va,target);rel(e,va,23)
def call(e,va,expected):
 word=e.word(va);assert word>>24&15==11
 delta=word&0xffffff
 if delta&0x800000:delta-=0x1000000
 address=va+8+4*delta
 assert e.plt[address]==expected
 checks.append({'file':e.relative,'va':hex(va),'call':expected})
# The actual Senif registration creates FID 11, with eight uniform callbacks.
ptr(u,0x18868,0xdd60)
assert (0xdd84+u.word(0xddec))&0xffffffff==0x18db8
assert (0x18db8+u.word(0xddf4))&0xffffffff==0x18870
w(u,0xddc4,0xe3a0100b)
call(u,0xddc8,'usbif_register_gadget')
for va in range(0x18870,0x18890,4):ptr(u,va,0xde64)
w(u,0xddd8,0xe3530000);w(u,0xdddc,0x158320cc)
w(u,0x823c,0xea00000b);call(u,0x828c,'_ZN13CUsbGadgetSenC1Ev')
# A 40-byte registration record is copied to gadget +0x94.
for va,value in [(0xa654,0xe1a0e004),(0xa658,0xe8be000f),(0xa65c,0xe285c094),(0xa660,0xe8ac000f),(0xa664,0xe8be000f),(0xa668,0xe8ac000f),(0xa66c,0xe89e0003),(0xa670,0xe88c0003)]:w(u,va,value)
# on_create supplies this gadget handle and proc_kevent callback in probe struct.
assert rel(u,0x19060,21,'_ZN13CUsbGadgetSen11proc_keventEmhhPv')['symbol_value']==0xcec0
for va,value in [(0xcdb8,0xe79ae00c),(0xcde0,0xe50be038),(0xcdf8,0xe50b7058),(0xce40,0xe24b2058)]:w(u,va,value)
assert (0xcd90+u.word(0xce60))&0xffffffff==0x18db8
assert 0x18db8+u.word(0xce68)==0x19060
call(u,0xce44,'ioctl');w(u,0xce6c,0x4034e000)
# Event thread opens the queue and dispatches handle, id, size, payload.
assert (0xad70+u.word(0xafd8))&0xffffffff==0x18db8
path=(0x18db8+u.word(0xafec))&0xffffffff
assert cstr(u.data,u.off(path))=='/dev/usb/event'
assert (0x18db8+u.word(0xb028))&0xffffffff==0xa82c
call(u,0xaf4c,'pthread_create');call(u,0xa8a4,'read')
for va,value in [(0xac64,0xe1a03005),(0xac68,0xe55b102a),(0xac6c,0xe51b0034),(0xac70,0xe51bc038),(0xac74,0xe12fff3c)]:w(u,va,value)
# Kernel event 7 with 4-byte payload 0/1 -> gadget event 2/3.
for va,value in [(0xcee0,0xe3510007),(0xcee8,0xe3520004),(0xcef0,0xe5933000),(0xcef4,0xe3530000),(0xcef8,0x0590c09c),(0xcefc,0x03a00002),(0xcf04,0xe3530001),(0xcf0c,0xe59ec0a0),(0xcf10,0xe3a00003),(0xcf20,0xe1a0300e),(0xcf28,0xe12fff3c)]:w(u,va,value)
# Gadget event 2/3 -> registered Senif callbacks event 1/2 and 16-byte I/O table.
for va,value in [(0xde98,0xe59330cc),(0xdea4,0xe593e000),(0xdeb0,0xe59e400c),(0xdebc,0xe3500002),(0xdec4,0xe3500003),(0xded4,0xe3a05001),(0xdedc,0xe5944000),(0xdef4,0xe58ec008),(0xdf00,0xe3a05002),(0xdf04,0xe59e6008),(0xdf08,0xe5944004),(0xdf4c,0xe3a07010),(0xdf54,0xe1a00005),(0xdf58,0xe1a01006),(0xdf5c,0xe1a02007),(0xdf64,0xe12fff34)]:w(u,va,value)
assert (0x18db8+u.word(0xdf74))&0xffffffff==0x18898
for va in range(0x18898,0x188a8,4):rel(u,va,23)
w(u,0xdc78,0xe581200c);w(u,0xdccc,0xe5834000)
for va in [0x1c540,0x1c544]:ptr(p,va,0xb504)
w(p,0xb564,0xe3530001)
# Recovered full module independently pins the same callback/payload ABI bytes.
kpath=ROOT/'build/w300/reports/g3-module-recovery/unified_drv.complete.ko'
k=kpath.read_bytes();kh=hashlib.sha256(k).hexdigest()
assert kh=='8d675f7071e49a75a174130ef8525767af07c157fe5f203018eb097e10aa1367'
h=struct.unpack_from('<HHIIIIIHHHHHH',k,16)
ss=[struct.unpack_from('<10I',k,h[5]+i*h[10])for i in range(h[11])]
ns=ss[h[12]];names=k[ns[4]:ns[4]+ns[5]]
text=next(s for s in ss if names[s[0]:].split(b'\0',1)[0]==b'.text')
for at,value in [(0x1a2b4,0xe5942000),(0x1a2b8,0xe5941020),(0x1a2bc,0xe3a0c004),(0x1a2c0,0xe3a03007),(0x1a2c4,0xe88d5000)]:assert struct.unpack_from('<I',k,text[4]+at)[0]==value
# Pin extracted GPL source; it is source-ABI corroboration, not compiled-kernel equivalence.
gpl=json.loads((HERE/'gpl-event-source.json').read_text())
for r in gpl['members']:
 data=(HERE/'g3-gpl-event'/Path(r['member']).name).read_bytes()
 assert len(data)==r['bytes']and hashlib.sha256(data).hexdigest()==r['sha256']
source=(HERE/'g3-gpl-event/usb_event.c').read_bytes()
for literal in [b'&handle, sizeof(handle)',b'&cb, sizeof(cb)',b'&id, sizeof(id)',b'&size, sizeof(size)',b'data, size']:
 assert literal in source
ranges=['range@0xa82c:0xacf4','range@0xad58:0xafd8','range@0xcd70:0xce60','range@0xcec0:0xcf30','range@0xdc60:0xdcf4','range@0xdd60:0xddec','range@0xde64:0xdf6c','range@0xa608:0xa6cc','range@0x8368:0x8430','range@0x81f8:0x829c']
(HERE/'event-chain.asm.txt').write_text('STATIC G3 ONLY. Firmware is never executed. Ranges stop before trailing literal pools.\n\n'+'\n\n'.join(u.decode(n)for n in ranges)+'\n',encoding='utf-8')
result={'ok':True,'scope':'static retained G3 code + published G3 GPL event ABI','inputs':{u.relative:u.sha,p.relative:p.sha,kpath.relative_to(ROOT).as_posix():kh},'assertions':checks,'translation':[{'kernel_event':7,'payload_u32':0,'gadget_event':2,'senif_event':1},{'kernel_event':7,'payload_u32':1,'gadget_event':3,'senif_event':2}],'io_table_va':'0x18898','io_table_bytes':16,'conditional_on_registered_created_enabled_senser_function':True,'normal_usb_lifecycle_qualified':False,'w300_qualified':False,'live_usb_test':False}
(HERE/'event-evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ok':True,'static_event_translation':result['translation'],'w300_qualified':False}))
