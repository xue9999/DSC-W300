"""Independent bounded XS11 framing review. Firmware is read as data only."""
import sys,json,struct,hashlib
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'g3-usb-descriptor'))
from inspect_usb import Elf
E=Elf('evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/tinyhttp')
def branch(pc):
    word=E.word(pc)
    assert word>>24==0xea
    displacement=word&0xffffff
    if displacement&0x800000:displacement-=0x1000000
    return pc+8+displacement*4
OPS=[0x28,0x29,0x2a,0x2e,0x42,0x64,0x6a,0x6c,0x7c,0x89]
HANDLERS={f'{op:02x}':{'normal':hex(branch(0x907d0+4*(op-0x21))), 'accelerator':hex(branch(0x8ea84+4*(op-0x21)))} for op in OPS}
RANGES=['range@0x91778:0x91a10','range@0x91e08:0x91f60','range@0x92570:0x92750','range@0x8fcf4:0x8fd90','range@0x8f9a0:0x8fb88','range@0x8fef0:0x8ff84','range@0x8f4f8:0x8f62c','range@0x8f860:0x8f888','range@0x900bc:0x900f0','range@0x9076c:0x9077c','range@0x92b10:0x92b7c','fxPutID','range@0x93ee0:0x93fa8','range@0x9401c:0x94338']
(HERE/'xs-review-handlers.asm.txt').write_text('\n\n'.join(E.decode(n) for n in RANGES)+'\n',encoding='utf-8')
pins={p['path']:p for p in json.loads((ROOT/'evidence/artifact_manifest.json').read_text())['artifacts']}
results=[]
for name in ['senserModule.xsb','senserCmdTable.xsb','regionInfo.xsb']:
    path='evidence/extracted_g3/archives_unpacked/fskrel1/dsc/fsk/'+name
    data=(ROOT/path).read_bytes();assert hashlib.sha256(data).hexdigest()==pins[path]['sha256']
    assert data[4:8]==b'XS11' and struct.unpack('>I',data[:4])[0]==len(data)
    chunks={};p=8
    while p<len(data):
        size,tag=struct.unpack_from('>I4s',data,p);assert size>=8
        assert p+size<=len(data) and tag not in chunks
        chunks[tag]=(p+8,data[p+8:p+size]);p+=size
    assert p==len(data)
    base,code=chunks[b'CODE']; sy=chunks[b'SYMB'][1]
    syms=sy[2:].split(b'\0')[:-1];assert len(syms)==int.from_bytes(sy[:2],'big')
    cursor=0;records=[];symbols=[]
    def id_at(at):
        i=int.from_bytes(code[at:at+2],'big')
        if i!=0xffff: assert (i&0x7fff)<len(syms)
        symbols.append(i)
    while cursor<len(code):
        start=cursor;op=code[cursor];cursor+=1
        assert 0x20<=op<0x8c
        target=branch(0x94050+(op-0x20)*4)
        if target in (0x9403c,0x94334):pass
        elif target==0x9426c:cursor+=1
        elif target==0x94274:id_at(cursor);cursor+=2
        elif target==0x9428c:cursor+=2
        elif target==0x94294:cursor+=4
        elif target==0x9429c:cursor+=8
        elif target==0x942b8:id_at(cursor);cursor+=4
        elif target==0x942a4:
            while code[cursor]!=0:cursor+=1
            cursor+=1
        elif target==0x94200:
            id_at(cursor);cursor+=3
            count=struct.unpack_from('b',code,cursor)[0];cursor+=1;assert count>=0
            for _ in range(count):id_at(cursor);cursor+=2
            cursor+=1
            count=struct.unpack_from('b',code,cursor)[0];cursor+=1;assert count>=0
            for _ in range(count):id_at(cursor);cursor+=2
        elif target==0x942d0:
            count=struct.unpack_from('b',code,cursor)[0];cursor+=1;assert count>=0
            for _ in range(count):id_at(cursor);id_at(cursor+2);cursor+=4
        else:raise AssertionError(hex(target))
        assert cursor<=len(code)
        records.append((start,op,code[start:cursor].hex(),base+start))
    original=json.loads((HERE/(name+'.json')).read_text())['instructions']
    assert records==[(i['offset'],i['opcode'],i['raw'],i['file_offset']) for i in original]
    boundaries={r[0] for r in records}|{len(code)}
    branches=[]
    for offset,op,raw,_ in records:
        if op in (0x28,0x29,0x2a):
            target=offset+3+struct.unpack('>h',bytes.fromhex(raw)[1:])[0]
            assert target in boundaries
            branches.append({'offset':offset,'target':target})
    results.append({'file':path,'sha256':pins[path]['sha256'],'code_bytes':len(code),'instructions':len(records),'symbol_operands':len(symbols),'branch_targets_checked':len(branches),'framing_matches':True})
report={'runtime_sha256':E.sha,'static_only':True,'w300_qualified':False,'dispatch':HANDLERS,'files':results}
(HERE/'xs-review-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
