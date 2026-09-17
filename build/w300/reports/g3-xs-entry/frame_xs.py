"""Bounded static XS11 instruction framing from the retained G3 runtime."""
import sys,struct,json,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf
E=Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/tinyhttp')
def branch(va):
 w=E.word(va); assert w>>24==0xea
 d=w&0xffffff
 if d&0x800000:d-=1<<24
 return va+8+4*d
WIDTH={0x9403c:0,0x94334:0,0x9426c:1,0x94274:2,0x9428c:2,0x94294:4,0x9429c:8,0x942b8:4}
DISPATCH={op:branch(0x94050+4*(op-0x20)) for op in range(0x20,0x8c)}
def parse(path):
 data=(ROOT/path).read_bytes()
 pin=next(x for x in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts'] if x['path']==path)
 assert hashlib.sha256(data).hexdigest()==pin['sha256']
 assert data[4:8]==b'XS11' and int.from_bytes(data[:4],'big')==len(data)
 at=8; syms=[]
 while at<len(data):
  size,tag=struct.unpack_from('>I4s',data,at)
  assert size>=8 and at+size<=len(data)
  if tag==b'SYMB':
   n=int.from_bytes(data[at+8:at+10],'big');syms=data[at+10:at+size].split(b'\0')[:-1];assert len(syms)==n
  if tag==b'CODE': code=data[at+8:at+size];base=at+8
  at+=size
 return dict(path=path,sha256=pin['sha256'],runtime_sha256=E.sha,code_bytes=len(code),instructions=frame(code,syms,base))
def frame(code,syms,base=0):
 out=[];at=0
 while at<len(code):
  start=at;op=code[at];at+=1;t=DISPATCH.get(op);ids=[];note=''
  if t in WIDTH:
   if t in [0x94274,0x942b8]:ids=[at]
   at+=WIDTH[t]
  elif t==0x942a4:
   end=code.index(0,at);note=repr(code[at:end].decode('utf-8'));at=end+1
  elif t==0x94200:
   ids=[at];at+=3;n=code[at];assert n<128;at+=1;ids+=list(range(at,at+2*n,2));at+=2*n+1;n=code[at];assert n<128;at+=1;ids+=list(range(at,at+2*n,2));at+=2*n
  elif t==0x942d0:
   n=code[at];assert n<128;at+=1;ids=list(range(at,at+4*n,2));at+=4*n
  else:raise ValueError(f'unsupported framing {op:#x} target={t} code={start:#x}')
  assert at<=len(code)
  if op==0x20: assert at==len(code), 'early terminator'
  labels=[]
  for pos in ids:
   i=int.from_bytes(code[pos:pos+2],'big');i=i if i==65535 else i&32767;assert i==65535 or i<len(syms);labels.append(f'{i}:{syms[i].decode()}' if i<len(syms) else f'{i}:<special>')
  out.append(dict(offset=start,file_offset=base+start,opcode=op,raw=code[start:at].hex(),remap_target=hex(t),symbols=labels,note=note))
 return out
if __name__=='__main__':
 for name in sys.argv[1:] or ['senserModule.xsb','senserCmdTable.xsb']:
  r=parse('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/'+name)
  (HERE/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
  (HERE/(name+'.txt')).write_text('\n'.join(f"{i['offset']:05x} {i['raw']:24s} {' '.join(i['symbols'])} {i['note']}" for i in r['instructions'])+'\n',encoding='utf-8')
  print(name,r['code_bytes'],len(r['instructions']))
