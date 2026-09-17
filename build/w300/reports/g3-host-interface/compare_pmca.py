"""Compare actual G3 auth/header bytes with pinned PMCA; no USB or firmware execution."""
from pathlib import Path
import ast, hashlib, json, struct, subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PIN='a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0'
UP=ROOT/'build/w300/upstream/Sony-PMCA-RE'
binary=ROOT/'evidence/extracted_g3/archives_unpacked/lib/lib/libsencore.so'
data=binary.read_bytes()
assert hashlib.sha256(data).hexdigest()=='401bc78bc84bd175968513a387b8951626ceb48a345eed134b998d3630103270'
h=struct.unpack_from('<HHIIIIIHHHHHH',data,16)
sections=[struct.unpack_from('<10I',data,h[5]+i*h[10]) for i in range(h[11])]
names_section=sections[h[12]]
names=data[names_section[4]:names_section[4]+names_section[5]]
named={names[s[0]:].split(b'\0',1)[0].decode():s for s in sections}


def offset(va):
    s=next(s for s in sections if s[1]!=8 and s[3]<=va<s[3]+s[5])
    return s[4]+va-s[3]


def word(va):
    return struct.unpack_from('<I',data,offset(va))[0]


def relocation(va):
    rel=named['.rel.dyn']
    entry=next(struct.unpack_from('<II',data,a) for a in range(rel[4],rel[4]+rel[5],rel[9])
               if struct.unpack_from('<I',data,a)[0]==va)
    symtab=sections[rel[6]]
    strsec=sections[symtab[6]]
    strings=data[strsec[4]:strsec[4]+strsec[5]]
    n,value,size=struct.unpack_from('<III',data,symtab[4]+(entry[1]>>8)*symtab[9])
    return dict(slot=hex(va),type=entry[1]&255,name=strings[n:].split(b'\0',1)[0].decode(),value=hex(value))


source_pins={}
for relative in ['pmca/usb/constants.py','pmca/usb/crypto.py','pmca/usb/sony.py']:
    local=(UP/relative).read_bytes()
    blob=subprocess.run(['git','-C',str(UP),'show',f'{PIN}:{relative}'],check=True,capture_output=True).stdout
    assert local==blob,relative
    source_pins[relative]=hashlib.sha256(local).hexdigest()
tree=ast.parse((UP/'pmca/usb/constants.py').read_text())
sony_tree=ast.parse((UP/'pmca/usb/sony.py').read_text())
auth_class=next(n for n in sony_tree.body if isinstance(n,ast.ClassDef) and n.name=='SonySenserAuthDevice')
auth_method=next(n for n in auth_class.body if isinstance(n,ast.FunctionDef) and n.name=='authenticate')
pid_branch=next(n.value for n in ast.walk(auth_method) if isinstance(n,ast.Assign)
                and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='data'
                and isinstance(n.value,ast.IfExp) and isinstance(n.value.test,ast.Compare))
assert ast.unparse(pid_branch.test)=='self.driver.getId()[1] == 822'
assert ast.unparse(pid_branch.body)=='data + keys[i]'
assert ast.unparse(pid_branch.orelse)=='data[:4]'
keys=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
          and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='senserKeysSha1')
assert len(keys)==3 and all(len(k)==512 for k in keys)
base=0x119e8+word(0x11aa4)
assert base==0x1b2d4
matches=[]
for i,literal in enumerate([0x11aac,0x11ab0,0x11ab4]):
    va=(base+word(literal))&0xffffffff
    at=offset(va)
    key=data[at:at+512]
    assert key==keys[i]
    matches.append(dict(index=i,va=hex(va),file_offset=hex(at),bytes=512,
                        sha256=hashlib.sha256(key).hexdigest(),equals_pmca=True))
# The concrete manager vtable's final virtual method is getProductId(), returning 1.
get_product=relocation(0x1b6d0)
assert get_product['name']=='_ZNK19WorkerThreadManager12getProductIdEv'
assert data[offset(0x80b4):offset(0x80b8)]==bytes.fromhex('0100a0e3')
auth_thread=relocation(0x1b628)
assert auth_thread['name']=='NinThread' and auth_thread['value']=='0x7888'
# Assert key code observations independently of disassembler annotations.
assert word(0x7934)==0xe3a02f81  # mov r2,#0x204, authentication receive
assert word(0x6f68)==0xe3a0200c  # mov r2,#12, Senser packet header receive
assert word(0x11964)==0xe3a02b01  # mov r2,#0x400, selected auth hash input
assert word(0x11888)==0xe20e30ff and word(0x1188c)==0xe20420ff
sha1_iv=[word(a) for a in range(0x11414,0x11428,4)]
assert sha1_iv==[0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0]
# The finalizer masks each bit-count word to its low byte before shifting.
# For lengths below 2**29 bytes, high word is zero; the remaining length is (n&31)*8.
lengths=[0,1,4,31,32,55,56,63,64,511,512,1024,4096]
padding_checks=[dict(bytes=n,observed_encoded_bits=(n*8)&255,pmca_encoded_bits=(n&31)*8) for n in lengths]
assert all(r['observed_encoded_bits']==r['pmca_encoded_bits'] for r in padding_checks)
result=dict(scope='Static G3/PMCA correspondence; no W300 compatibility, live authentication or complete SHA1 implementation proof',
            pmca_commit=PIN,source_pins=source_pins,auth_thread=auth_thread,
            manager_get_product=get_product,sha1_keys=matches,auth_frame_bytes=0x204,
            senser_header_bytes=12,selected_hash_input_bytes=1024,
            pmca_matching_branch={'usb_pid':'0x0336','matching_input':'512-byte challenge + 512-byte key',
                                  'other_pid_input':'first 4 challenge bytes',
                                  'g3_session_pid_established_by_this_report':False,
                                  'w300_session_pid_established':False},
            sha1_initial_words=[hex(x) for x in sha1_iv],padding_length_checks=padding_checks,
            receiver_scope='12-byte header and pFunc0x40 routing observed; USB mode entry and W300 acceptance unqualified',
            firmware_executed=False,usb_commands_sent=False)
(HERE/'pmca-comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(ok=True,matched_keys=len(matches),auth_frame_bytes=0x204,senser_header_bytes=12),indent=2))
