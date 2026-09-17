"""Reproduce G3 descriptor/request bindings without loading firmware or using USB."""
from pathlib import Path
import ast, hashlib, json, struct, subprocess, tarfile
from inspect_usb import Elf, HERE, ROOT, cstr

PIN='a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'
up=ROOT/'build/w300/upstream/Sony-PMCA-RE'
pmca_pins={}
for rel in ['pmca/usb/sony.py','pmca/usb/driver/generic/libusb.py']:
    local=(up/rel).read_bytes()
    pinned=subprocess.run(['git','-C',str(up),'show',f'{PIN}:{rel}'],check=True,capture_output=True).stdout
    assert local==pinned
    pmca_pins[rel]=hashlib.sha256(local).hexdigest()
tree=ast.parse((up/'pmca/usb/sony.py').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SonySenserAuthDevice')
requests={n.targets[0].id:ast.literal_eval(n.value) for n in cls.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['SONY_VendorRequest_StartSenser','SONY_VendorRequest_StopSenser']}

e=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libusb.so')
s=Elf('evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so')
def rel_at(elf,at,typ=None,name=None):
    found=[r for r in elf.reloc if r['offset']==at and (typ is None or r['type']==typ) and (name is None or r['symbol']==name)]
    assert len(found)==1,(hex(at),typ,name)
    return found[0]
def code(elf,va,expected):assert elf.word(va)==expected,hex(va)
base=(0x9fb8+e.word(0xa360))&0xffffffff
assert base==0x18db8
got=base+e.word(0xa368)
assert rel_at(e,got,21,'ptbl_did')['symbol_value']==0x193e4
did_slot=e.sym('ptbl_did')['value']+13*4
rel_at(e,did_slot,23)
record=e.word(did_slot)
assert record==0x19598 and e.word(record)==13
desc_rel=rel_at(e,record+12,2,'sen_desc_tbl')
desc=desc_rel['symbol_value']; assert desc==e.sym('sen_desc_tbl')['value']==0x18ac0
vid,pid=struct.unpack_from('<HH',e.data,e.off(desc+0x20))
assert (vid,pid)==(0x054c,0x0336)
# createGadget loads table[DID]+0xc and submits it through GADGETCORE_START.
for va,w in [(0xa280,0xe59630a0),(0xa284,0xe7913103),(0xa28c,0xe593300c),(0xa294,0xe50b3054),(0xa304,0xe24b2054)]:code(e,va,w)
assert e.word(0xa37c)==0x400ce203
device_path=(base+e.word(0xa370))&0xffffffff
assert cstr(e.data,e.off(device_path))=='/dev/usb/gadgetcore'
# USB API allocation copies template; the slot used by libsencore is this start wrapper.
template=(0x5b90+e.word(0x5e44)+e.word(0x5e58))&0xffffffff
assert template==0x187bc and e.word(template+12)==0x6314
rel_at(e,template+12,23)
code(s,0x8514,0xe3a0100d); code(s,0x8518,0xe593c00c)
code(e,0x6408,0xe1a01004)
assert e.plt[0x5134]=='_ZN7CUsbSvc5startE11__USBIF_DIDPvhPFS1_S1_S1_hiE'
code(e,0x9584,0xd58010a0)  # accepted DID <=0x22 stored at this+0xa0
# Actual control-request table is copied into auxiliary probe data, not merely found.
sen_base=(0xcd90+e.word(0xce60))&0xffffffff
patterns=(sen_base+e.word(0xce64))&0xffffffff
assert sen_base==base and patterns==0x10294
raw=e.data[e.off(patterns):e.off(patterns)+16]
expected=b''.join(struct.pack('<BBHHH',0x43,*requests[n],0) for n in ['SONY_VendorRequest_StartSenser','SONY_VendorRequest_StopSenser'])
assert raw==expected
assert e.word(0xce6c)==0x4034e000
for va,w in [(0xcdac,0xe893000f),(0xcdc8,0xe88c000f),(0xcdd0,0xe3a03010),(0xcde8,0xe50bc02c),(0xcdec,0xe50b3028),(0xce40,0xe24b2058)]:code(e,va,w)

# Read only the model-specific GPL files needed to identify this descriptor ABI.
archive=ROOT/'build/w300/downloads/g3-gpl-reference/linux-kernel.tar.gz'
archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_sha=='cbb03d206740f0bcc8ed9efc90e1f48786f427188954616ed618a3cb7597e90a'
members=['linux/include/linux/usb/gcore/usb_gadgetcore.h','linux/drivers/usb/gcore/usb_gcore_desc.c','linux/drivers/usb/gcore/usb_gcore_main.c']
gpl=[]
target=HERE/'g3-gpl-gadgetcore';target.mkdir(exist_ok=True)
with tarfile.open(archive,'r:gz') as tf:
    for member in members:
        blob=tf.extractfile(member).read()
        dest=target/Path(member).name
        dest.write_bytes(blob)
        gpl.append(dict(member=member,local=str(dest.relative_to(ROOT)),sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob)))
header=(target/'usb_gadgetcore.h').read_text(encoding='cp932',errors='replace')
consumer=(target/'usb_gcore_desc.c').read_text(encoding='cp932',errors='replace')
assert '__u16 us_id_product' in header or '__u16  us_id_product' in header
assert 'dev_desc.idVendor  = cpu_to_le16(desc_tbl->us_id_vendor)' in consumer
assert 'dev_desc.idProduct = cpu_to_le16(desc_tbl->us_id_product)' in consumer
result=dict(scope='Static retained G3 descriptor binding and service request matching only; no live enumeration, auth, W300 support or successful normal-to-service transition.',
    inputs={e.relative:e.sha,s.relative:s.sha},pmca_commit=PIN,pmca_source_pins=pmca_pins,
    did=13,did_table_slot=hex(did_slot),did_record=hex(record),descriptor_relocation=desc_rel,descriptor_va=hex(desc),descriptor_file_offset=hex(e.off(desc)),
    descriptor_hex=e.data[e.off(desc):e.off(desc)+48].hex(),vid=hex(vid),pid=hex(pid),
    usb_api_template=hex(template),start_wrapper=hex(e.word(template+12)),gadgetcore_start_ioctl='0x400ce203',gadgetcore_path='/dev/usb/gadgetcore',
    request_table_va=hex(patterns),request_table_file_offset=hex(e.off(patterns)),request_table_hex=raw.hex(),sen_probe_ioctl='0x4034e000',
    pmca_matching_requests=[dict(name=n,bmRequestType='0x43',request=v[0],value=hex(v[1]),index=hex(v[2]),length=0) for n,v in requests.items()],
    gpl_archive_sha256=archive_sha,gpl_members=gpl,
    firmware_executed=False,usb_commands_sent=False)
(HERE/'descriptor-evidence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(ok=True,vid=hex(vid),pid=hex(pid),did=13,control_request_patterns_match_pmca=True,gpl_files=len(gpl)),indent=2))
